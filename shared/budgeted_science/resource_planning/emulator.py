"""Paid-data-only separable multifidelity GP and finite-prior calibration.

Species are independent; times within a trajectory are correlated. Numerical
regularization below is NOT target measurement noise. No physical solver imports.
"""
from dataclasses import dataclass, asdict
import math
import time

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import qmc


@dataclass(frozen=True)
class GPSettings:
    particles: int = 2048
    fantasies: int = 8
    global_candidates: int = 8
    posterior_candidates: int = 8
    time_length: float = 0.25
    run_jitter: float = 1e-7
    likelihood_jitter: float = 1e-8
    max_fit_iterations: int = 40

    def __post_init__(self):
        for name in ("particles", "fantasies", "global_candidates", "posterior_candidates", "max_fit_iterations"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(name + " must be a nonnegative integer")
        if self.particles == 0 or self.particles & (self.particles - 1):
            raise ValueError("particles must be a positive power of two")
        if self.fantasies == 0 or self.max_fit_iterations == 0 or self.posterior_candidates > self.particles:
            raise ValueError("invalid fantasy, optimizer, or posterior candidate count")
        for name in ("time_length", "run_jitter", "likelihood_jitter"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError(name + " must be finite and positive")

    def to_dict(self):
        return asdict(self)


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("policy analysis deadline reached")


def matern(a, b, lengths, derivatives=False):
    diff = (np.asarray(a)[:, None, :] - np.asarray(b)[None, :, :]) / lengths
    squared = diff * diff
    r = np.sqrt(5 * squared.sum(axis=-1))
    exponential = np.exp(-r)
    value = (1 + r + r * r / 3) * exponential
    if derivatives:
        return value, (5 / 3) * (1 + r)[..., None] * exponential[..., None] * squared
    return value


def kernel(a, fa, b, fb, hp, derivatives=False):
    """K(L,L)=K(L,H)=k_L; K(H,H)=k_L+k_delta; rho fixed at one."""
    h = np.exp(hp)
    low, dlow = matern(a, b, h[:3], True)
    delta, ddelta = matern(a, b, h[3:6], True)
    mask = np.asarray(fa)[:, None] * np.asarray(fb)[None, :]
    low = h[6] ** 2 * low
    delta = h[7] ** 2 * mask * delta
    value = low + delta
    if derivatives:
        grads = [h[6] ** 2 * dlow[..., j] for j in range(3)]
        grads += [h[7] ** 2 * mask * ddelta[..., j] for j in range(3)]
        return value, grads + [2 * low, 2 * delta]
    return value


class ChannelGP:
    def __init__(self, theta, fidelities, values, temporal, settings, deadline=None):
        self.theta = theta
        self.fidelities = fidelities
        self.values = values
        self.settings = settings
        self.temporal = temporal
        n, m = values.shape
        tf = cho_factor(temporal, lower=True)
        sufficient = values @ cho_solve(tf, values.T)
        identity = np.eye(n)
        initial = np.log([.5] * 6 + [1., .25])
        bounds = [(np.log(.05), np.log(2.))] * 6
        bounds += [(np.log(.001), np.log(10.))] * 2

        def objective(hp):
            check_deadline(deadline)
            cov, deriv = kernel(theta, fidelities, theta, fidelities, hp, True)
            cov = cov + settings.run_jitter * identity
            factor = cho_factor(cov, lower=True, check_finite=False)
            inverse = cho_solve(factor, identity, check_finite=False)
            objective_value = m * np.log(np.diag(factor[0])).sum() + .5 * np.sum(inverse * sufficient.T)
            weight = .5 * (m * inverse - inverse @ sufficient @ inverse)
            gradient = np.array([np.sum(weight * item) for item in deriv])
            return float(objective_value), gradient

        fitted = minimize(objective, initial, jac=True, method="L-BFGS-B", bounds=bounds,
                          options={"maxiter": settings.max_fit_iterations, "ftol": 1e-8})
        if not np.all(np.isfinite(fitted.x)) or not np.isfinite(fitted.fun):
            raise FloatingPointError("nonfinite GP fit")
        self.hp = fitted.x
        cov = kernel(theta, fidelities, theta, fidelities, self.hp)
        self.factor = cho_factor(cov + settings.run_jitter * identity, lower=True)
        self.alpha = cho_solve(self.factor, values)
        self.diagnostics = {"log_hyperparameters": self.hp.tolist(),
                            "optimizer_success": bool(fitted.success),
                            "optimizer_message": str(fitted.message),
                            "iterations": int(fitted.nit), "objective": float(fitted.fun)}

    def predict(self, theta, fidelities):
        cross = kernel(theta, fidelities, self.theta, self.fidelities, self.hp)
        mean = cross @ self.alpha
        prior = np.exp(2 * self.hp[6]) + np.asarray(fidelities) * np.exp(2 * self.hp[7])
        variance = prior - np.sum(cross * cho_solve(self.factor, cross.T).T, axis=1)
        return mean, np.maximum(variance, 0.)

    def cross(self, a, fa, b, fb):
        left = kernel(a, fa, self.theta, self.fidelities, self.hp)
        right = kernel(self.theta, self.fidelities, b, fb, self.hp)
        return kernel(a, fa, b, fb, self.hp) - left @ cho_solve(self.factor, right)


def stable_weights(log_weights):
    normalizer = logsumexp(log_weights, axis=-1, keepdims=True)
    if not np.all(np.isfinite(normalizer)):
        raise FloatingPointError("nonfinite finite-prior likelihood")
    return np.exp(log_weights - normalizer)


def uncertainty(weights, log_parameters):
    mean = weights @ log_parameters
    second = weights @ (log_parameters * log_parameters)
    return np.maximum(second - mean * mean, 0.).sum(axis=-1)


class Calibration:
    """Immutable real-data fit; fantasy updates never refit hyperparameters."""
    def __init__(self, simulations, observations, bounds, initial, times, *, seed=0,
                 settings=None, deadline=None, noise_fraction=0.0):
        self.settings = settings or GPSettings()
        if not math.isfinite(noise_fraction) or not 0 <= noise_fraction <= .1:
            raise ValueError("invalid measurement noise fraction")
        self.noise_variance = noise_fraction ** 2
        self.bounds = np.asarray(bounds, dtype=float)
        self.initial = np.asarray(initial, dtype=float)
        self.times = np.asarray(times, dtype=float)
        self.temporal = matern((self.times / self.times[-1])[:, None],
                               (self.times / self.times[-1])[:, None],
                               np.array([self.settings.time_length]))
        self.temporal += np.eye(len(self.times)) * self.settings.run_jitter
        count = self.settings.particles
        if count <= 0 or count & (count - 1):
            raise ValueError("particle count must be a positive power of two")
        self.unit_particles = qmc.Sobol(3, scramble=True, seed=seed + 317).random_base2(int(np.log2(count)))
        self.particles = self.bounds[:, 0] + self.unit_particles * np.diff(self.bounds, axis=1).ravel()
        self.log_particles = np.log(self.particles)
        self.obs = [[], []]
        for record in observations:
            # Initial conditions are already public; not uncertain GP observations.
            if float(record["time"]) == 0:
                continue
            channel = {"x": 0, "y": 1}[record["variable"]]
            matches = np.flatnonzero(np.isclose(self.times, record["time"], atol=1e-12, rtol=0))
            if not len(matches):
                raise ValueError("baseline observations must be on its public working grid")
            self.obs[channel].append((int(matches[0]), float(record["value"]) / self.initial[channel] - 1))
        completed = [s for s in simulations if s["status"] == "success"]
        if not completed:
            raise ValueError("GP requires at least one purchased successful simulation")
        for item in completed:
            recorded_times = np.asarray(item.get("times", []), dtype=float)
            if recorded_times.shape != self.times.shape or not np.allclose(recorded_times, self.times, atol=1e-12, rtol=0):
                raise ValueError("purchased trajectory timestamps must match the working grid")
        theta = np.asarray([s["theta"] for s in completed], float)
        theta = (theta - self.bounds[:, 0]) / np.diff(self.bounds, axis=1).ravel()
        fidelities = np.asarray([int(s["fidelity"] == "high") for s in completed])
        arrays = np.asarray([s["values"] for s in completed], float)
        if arrays.shape != (len(completed), len(times), 2):
            raise ValueError("purchased trajectories must match the common working grid")
        self.channels = [ChannelGP(theta, fidelities, arrays[:, :, j] / self.initial[j] - 1,
                                   self.temporal, self.settings, deadline) for j in range(2)]
        self.means, self.variances = [], []
        for gp in self.channels:
            mean, variance = gp.predict(self.unit_particles, np.ones(count))
            self.means.append(mean)
            self.variances.append(variance)
        self.log_likelihood = self.likelihood(self.means, self.variances)
        self.weights = stable_weights(self.log_likelihood)
        self.current_uncertainty = float(uncertainty(self.weights, self.log_particles))

    def likelihood(self, means, variances):
        result = np.zeros(means[0].shape[:-1])
        for j, obs in enumerate(self.obs):
            if not obs:
                continue
            indices = np.array([o[0] for o in obs])
            values = np.array([o[1] for o in obs])
            temporal = self.temporal[np.ix_(indices, indices)]
            eigenvalues, vectors = np.linalg.eigh(temporal)
            residual = (values - means[j][..., indices]) @ vectors
            denominator = (variances[j][..., None] * eigenvalues
                           + self.settings.likelihood_jitter + self.noise_variance)
            result -= .5 * (np.log(denominator) + residual * residual / denominator).sum(axis=-1)
        return result

    def estimate(self):
        return (self.weights @ self.particles).tolist()

    def diagnostics(self):
        return {"posterior_mean": self.estimate(), "uncertainty_log_parameters": self.current_uncertainty,
                "effective_particles": float(1 / np.sum(self.weights ** 2)),
                "maximum_particle_weight": float(self.weights.max()),
                "gp": [gp.diagnostics for gp in self.channels], "settings": self.settings.to_dict()}

    def condition_target(self, channel, indices):
        """Predict future target readings conditional on existing real readings.

        Returns particle-specific means and covariances. The same latent target
        parameters apply to every observation, rather than redrawing the target.
        """
        indices = np.asarray(indices, dtype=int)
        mean = self.means[channel][:, indices].copy()
        variance = self.variances[channel]
        covariance = variance[:, None, None] * self.temporal[np.ix_(indices, indices)]
        obs = self.obs[channel]
        if obs:
            oi = np.array([o[0] for o in obs])
            values = np.array([o[1] for o in obs])
            observed = variance[:, None, None] * self.temporal[np.ix_(oi, oi)]
            observed += np.eye(len(oi)) * (self.settings.likelihood_jitter + self.noise_variance)
            residual = values - self.means[channel][:, oi]
            cross = variance[:, None, None] * self.temporal[np.ix_(indices, oi)]
            mean += (cross @ np.linalg.solve(observed, residual[..., None]))[..., 0]
            covariance -= cross @ np.linalg.solve(observed, np.swapaxes(cross, -1, -2))
        return mean, covariance

    def observation_gain(self, channel, index, particle_draws, normals):
        mean, cov = self.condition_target(channel, [index])
        variance = np.maximum(cov[:, 0, 0], 0.) + self.settings.likelihood_jitter + self.noise_variance
        outcomes = mean[particle_draws, 0] + np.sqrt(variance[particle_draws]) * normals[:, channel, 0]
        difference = outcomes[:, None] - mean[None, :, 0]
        log_conditional = -.5 * (np.log(variance)[None, :] + difference ** 2 / variance[None, :])
        weights = stable_weights(self.log_likelihood[None, :] + log_conditional)
        future = uncertainty(weights, self.log_particles)
        return self.current_uncertainty - float(future.mean())

    def simulation_gain(self, theta, fidelity, particle_draws, normals):
        """Joint-trajectory fantasy, conditioned on the existing target evidence.

        First draw latent target theta from its posterior; condition the action's
        GP trajectory on the actual target readings at that theta. Then draw the
        full correlated trajectory, condition the simulator GP on that purchase,
        and recompute calibration from all real observations. No truth access.
        """
        unit = ((np.asarray(theta) - self.bounds[:, 0]) / np.diff(self.bounds, axis=1).ravel())[None, :]
        flag = np.array([int(fidelity == "high")])
        future_means, future_variances = [], []
        nf, nt = len(particle_draws), len(self.times)
        for j, gp in enumerate(self.channels):
            am, av = gp.predict(unit, flag)
            am, av = am[0], float(av[0] + self.settings.run_jitter)
            cross = gp.cross(self.unit_particles, np.ones(len(self.particles)), unit, flag)[:, 0]
            conditional_mean = np.broadcast_to(am, (nf, nt)).copy()
            conditional_cov = np.broadcast_to(av * self.temporal, (nf, nt, nt)).copy()
            obs = self.obs[j]
            if obs:
                oi = np.array([o[0] for o in obs])
                values = np.array([o[1] for o in obs])
                selected_variance = self.variances[j][particle_draws]
                observed_cov = selected_variance[:, None, None] * self.temporal[np.ix_(oi, oi)]
                observed_cov += np.eye(len(oi)) * (self.settings.likelihood_jitter + self.noise_variance)
                between = cross[particle_draws, None, None] * self.temporal[:, oi]
                residual = values - self.means[j][particle_draws][:, oi]
                conditional_mean += (between @ np.linalg.solve(observed_cov, residual[..., None]))[..., 0]
                conditional_cov -= between @ np.linalg.solve(observed_cov, np.swapaxes(between, -1, -2))
            conditional_cov = .5 * (conditional_cov + np.swapaxes(conditional_cov, -1, -2))
            # Eigen sampling tolerates roundoff in a nearly deterministic posterior.
            ev, vec = np.linalg.eigh(conditional_cov)
            if ev.min() < -1e-6:
                raise FloatingPointError("negative joint fantasy covariance")
            outcomes = conditional_mean + (vec @ (np.sqrt(np.maximum(ev, 0)) * normals[:, j, :])[..., None])[..., 0]
            residual = outcomes - am
            future_means.append(self.means[j][None, :, :] + cross[None, :, None] / av * residual[:, None, :])
            future_variances.append(np.maximum(self.variances[j] - cross * cross / av, 0.)[None, :])
        weights = stable_weights(self.likelihood(future_means, future_variances))
        future = uncertainty(weights, self.log_particles)
        return self.current_uncertainty - float(future.mean())
