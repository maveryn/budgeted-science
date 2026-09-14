"""Paid-evidence-only continuous multifidelity fit and sequential local design.

This is an approximate design policy, not MR-SUR or an optimal policy.
No environment, physical solver, evaluator, API, or filesystem imports.
"""

import time

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize
from scipy.stats import qmc

from .emulator import check_deadline, matern


NAME = "adaptive_multifidelity_design"
SETTINGS = {
    "version": 1, "low_length": .6, "delta_length": .8,
    "low_amplitude": .35, "delta_amplitude": .04,
    "linear_amplitude": .6, "jitter": 1e-10,
    "candidate_pool": 256, "optimizer_starts": 6,
    "optimizer_iterations": 100, "mode_merge_distance": 1e-3,
    "prior_precision": 12., "derivative_step": 1e-4,
    "episode_seconds": 300,
}


def _kernel(a, fa, b, fb):
    """Shared low response plus an independent smooth high/low discrepancy."""
    a, b = np.atleast_2d(a), np.atleast_2d(b)
    low = SETTINGS["low_amplitude"] ** 2 * matern(a, b, np.full(3, SETTINGS["low_length"]))
    low += SETTINGS["linear_amplitude"] ** 2 * (1 + (a - .5) @ (b - .5).T)
    delta = SETTINGS["delta_amplitude"] ** 2 * (
        1 + matern(a, b, np.full(3, SETTINGS["delta_length"])))
    return low + np.asarray(fa)[:, None] * np.asarray(fb)[None, :] * delta


class Forward:
    """Joint Gaussian conditioning of transformed full purchased trajectories.

    Outputs are log(population / initial population) / time. All channels use
    the same spatial kernel; output correlations are not modeled. Log-transform
    measurement noise uses a first-order approximation, not an exact likelihood.
    """

    def __init__(self, evidence, config):
        self.config = config
        bounds = np.array(config["bounds"], float)
        self.lower, self.width = bounds[:, 0], np.diff(bounds).ravel()
        self.times = np.repeat(config["working_times"], 2)
        self.scale = np.tile(config["initial"], len(config["working_times"]))
        self.observations = [o for o in evidence["observations"] if o["time"] > 0]
        self.indices = np.array([
            2 * config["working_times"].index(o["time"]) + ("x", "y").index(o["variable"])
            for o in self.observations], int)
        measured = np.array([o["value"] for o in self.observations])
        if np.any(measured <= 0):
            raise ValueError("log-response fit requires positive purchased observations")
        self.observed = np.log(measured / self.scale[self.indices]) / self.times[self.indices]
        noise = config.get("observation_noise_fraction", 0) * self.scale[self.indices]
        self.noise = (noise / measured / self.times[self.indices]) ** 2 + SETTINGS["jitter"]
        rows = [s for s in evidence["simulations"] if s["status"] == "success"
                and np.all(np.asarray(s["values"]) > 0)]
        self.excluded = [s["result_id"] for s in evidence["simulations"] if s not in rows]
        self.x = np.array([(np.array(s["theta"]) - self.lower) / self.width for s in rows]).reshape(-1, 3)
        self.flags = np.array([int(s["fidelity"] == "high") for s in rows])
        self.factor = None
        if rows:
            values = np.array([s["values"] for s in rows]).reshape(len(rows), -1)
            self.values = np.log(values / self.scale) / self.times
            self.factor = cho_factor(_kernel(self.x, self.flags, self.x, self.flags)
                                     + np.eye(len(rows)) * SETTINGS["jitter"], lower=True)
            self.alpha = cho_solve(self.factor, self.values)

    def predict(self, points, fidelity=1):
        points = np.atleast_2d(points)
        flags = np.full(len(points), fidelity)
        prior = np.diag(_kernel(points, flags, points, flags))
        if self.factor is None:
            return np.zeros((len(points), len(self.times))), prior
        cross = _kernel(points, flags, self.x, self.flags)
        mean = cross @ self.alpha
        variance = prior - np.sum(cross * cho_solve(self.factor, cross.T).T, axis=1)
        return mean, np.maximum(variance, SETTINGS["jitter"])

    def cross(self, points, action, fidelity):
        points, action = np.atleast_2d(points), np.atleast_2d(action)
        value = _kernel(points, np.ones(len(points)), action, [fidelity])[:, 0]
        if self.factor is not None:
            left = _kernel(points, np.ones(len(points)), self.x, self.flags)
            right = _kernel(self.x, self.flags, action, [fidelity])
            value -= (left @ cho_solve(self.factor, right))[:, 0]
        return value

    def objective(self, points):
        mean, variance = self.predict(points)
        denominator = variance[:, None] + self.noise
        return .5 * np.sum((mean[:, self.indices] - self.observed) ** 2 / denominator
                           + np.log(denominator), axis=1)

    def jacobian(self, points):
        points = np.atleast_2d(points)
        result = np.empty((len(points), len(self.times), 3))
        for j in range(3):
            left, right = points.copy(), points.copy()
            left[:, j] = np.maximum(0, left[:, j] - SETTINGS["derivative_step"])
            right[:, j] = np.minimum(1, right[:, j] + SETTINGS["derivative_step"])
            result[:, :, j] = ((self.predict(right)[0] - self.predict(left)[0])
                               / (right[:, j] - left[:, j])[:, None])
        return result


def covariance(jacobian, variance, noise):
    information = np.einsum("noi,noj,no->nij", jacobian, jacobian, 1 / (variance[:, None] + noise))
    return np.linalg.inv(information + np.eye(3) * SETTINGS["prior_precision"])


def distinct_points(points):
    """Do not give a mode extra mass because several optimizer starts find it."""
    result = []
    for point in points:
        if not any(np.linalg.norm(point - other) < SETTINGS["mode_merge_distance"] for other in result):
            result.append(point)
    return result


class Design:
    """Continuous MAP plus local covariance and posterior-weighted design proxy."""

    def __init__(self, evidence, config, seed=0, deadline=None):
        self.model = model = Forward(evidence, config)
        self.config, self.evidence = config, evidence
        self.pool = qmc.Sobol(3, scramble=True, seed=seed).random_base2(
            int(np.log2(SETTINGS["candidate_pool"])))
        starts = np.vstack(([.5, .5, .5], self.pool, model.x))
        scores = model.objective(starts)
        self.bootstrap = bool(len(model.x) < 4 or np.linalg.matrix_rank(
            np.column_stack((np.ones(len(model.x)), model.x))) < 4)
        modes = []
        if not self.bootstrap:
            for index in np.argsort(scores)[:SETTINGS["optimizer_starts"]]:
                check_deadline(deadline)
                def objective(point):
                    check_deadline(deadline)
                    return float(model.objective(point)[0])
                fitted = minimize(objective, starts[index], method="L-BFGS-B", bounds=[(0, 1)] * 3,
                                  options={"maxiter": SETTINGS["optimizer_iterations"], "ftol": 1e-10})
                if np.isfinite(fitted.fun) and np.all(np.isfinite(fitted.x)):
                    modes.append((float(fitted.fun), fitted.x))
        if not modes:
            modes = [(float(scores[i]), starts[i]) for i in np.argsort(scores)[:6]]
        modes.sort(key=lambda item: item[0])
        representatives = distinct_points([point for _, point in modes])
        modes = [(score, point) for score, point in modes if any(point is p for p in representatives)]
        self.estimate = modes[0][1]
        # Local design support includes uncertainty directions, not just a MAP.
        jac = model.jacobian([self.estimate])[:, model.indices]
        variance = model.predict([self.estimate])[1]
        local_cov = covariance(jac, variance, model.noise)[0]
        eig, vec = np.linalg.eigh(local_cov)
        support = [self.estimate]
        for j in range(3):
            offset = vec[:, j] * np.sqrt(max(0, eig[j]))
            support.extend([np.clip(self.estimate + offset, 0, 1), np.clip(self.estimate - offset, 0, 1)])
        support += [point for score, point in modes[1:] if score < modes[0][0] + 3]
        self.points = np.array(distinct_points(support))
        # Symmetric local support, likelihood-weighted across separated modes.
        scores = model.objective(self.points)
        self.weights = np.exp(-np.minimum(scores - scores.min(), 30))
        self.weights /= self.weights.sum()
        self.means, self.variance = model.predict(self.points)
        self.jacobian = model.jacobian(self.points)
        self.cov = covariance(self.jacobian[:, model.indices], self.variance, model.noise)
        self.current = float(self.weights @ np.trace(self.cov, axis1=1, axis2=2))
        self.modes = [{"objective": score, "unit_theta": point.tolist()} for score, point in modes]

    def diagnostics(self):
        return {"theta_hat": self.theta_hat(), "unit_covariance": np.einsum("n,nij->ij", self.weights, self.cov).tolist(),
                "local_trace": self.current, "bootstrap": self.bootstrap, "modes": self.modes,
                "design_support": self.points.tolist(), "support_weights": self.weights.tolist(),
                "excluded_simulations": self.model.excluded,
                "uncertainty_label": "local design approximation; not calibrated confidence"}

    def theta_hat(self):
        return (self.model.lower + self.estimate * self.model.width).tolist()

    def actions(self, remaining, deadline=None):
        model, config = self.model, self.config
        purchased = {(s["fidelity"], tuple(s["theta"])) for s in self.evidence["simulations"]}
        observed = {(o["variable"], o["time"]) for o in self.evidence["observations"]}
        # Global candidates ensure the policy need not remain at its current mode.
        locations = np.vstack((self.estimate, self.points, model.x, self.pool[:16]))
        unique = {}
        for point in locations:
            unique.setdefault(tuple(np.round(point, 12)), point)
        ranked = []
        for fidelity in ("low", "high"):
            cost = config["costs"][fidelity]
            if cost > remaining:
                continue
            flag = int(fidelity == "high")
            for point in unique.values():
                check_deadline(deadline)
                theta = (model.lower + point * model.width).tolist()
                if (fidelity, tuple(theta)) in purchased or any(
                    s["fidelity"] == fidelity and np.max(
                        np.abs((np.asarray(s["theta"]) - theta) / model.width)) < 1e-9
                    for s in self.evidence["simulations"]
                ):
                    continue
                av = float(model.predict([point], flag)[1][0]) + SETTINGS["jitter"]
                if self.bootstrap:
                    # Until the 3-D local fit is determined, reduce integrated
                    # forward uncertainty under the public uniform prior.
                    cross = model.cross(self.pool[:32], point, flag)
                    gain = float(np.mean(cross ** 2 / av))
                    criterion = "bootstrap integrated forward variance"
                else:
                    cross = model.cross(self.points, point, flag)
                    reduced = np.maximum(self.variance - cross ** 2 / av, SETTINGS["jitter"])
                    future = covariance(self.jacobian[:, model.indices], reduced, model.noise)
                    gain = self.current - float(self.weights @ np.trace(future, axis1=1, axis2=2))
                    criterion = "local parameter covariance reduction"
                ranked.append({"kind": "simulation", "fidelity": fidelity, "theta": theta, "cost": cost,
                               "gain": max(0., gain), "score": max(0., gain) / cost, "criterion": criterion})
        if config["costs"]["measurement"] <= remaining:
            for channel, variable in enumerate(("x", "y")):
                for ti, t in enumerate(config["working_times"]):
                    if (variable, t) in observed:
                        continue
                    index = 2 * ti + channel
                    # Delta-method noise at the predicted population. Clip only
                    # the exp used for a design proxy to prevent overflow.
                    rate = self.means[:, index] * t
                    noise = (config.get("observation_noise_fraction", 0) / np.exp(np.clip(rate, -20, 20)) / t) ** 2
                    sensitivity = self.jacobian[:, index]
                    cj = np.einsum("nij,nj->ni", self.cov, sensitivity)
                    denominator = noise + self.variance + np.einsum("ni,ni->n", sensitivity, cj)
                    gain = float(self.weights @ (np.sum(cj * cj, axis=1) / denominator))
                    if self.bootstrap:
                        gain = 0.  # No identifiable local sensitivity model yet.
                    ranked.append({"kind": "observation", "variable": variable, "time": t,
                                   "cost": config["costs"]["measurement"], "gain": gain,
                                   "score": gain / config["costs"]["measurement"],
                                   "criterion": "local Fisher covariance reduction"})
        ranked.sort(key=lambda a: a["score"], reverse=True)
        return ranked


def run_adaptive_design(tools, seed=0, log=None, deadline=None):
    """Only receives the same public metered services available to other methods."""
    emit = log or (lambda *args, **kwargs: None)
    config = tools.public_config
    emit("adaptive_design_started", settings=SETTINGS, public_configuration=config, policy_seed=seed)
    steps = 0
    while True:
        check_deadline(deadline)
        started = time.monotonic()
        evidence = tools.evidence()
        fitted = Design(evidence, config, seed, deadline)
        emit("adaptive_design_fit", step=steps, **fitted.diagnostics(),
             analysis_seconds=time.monotonic() - started)
        remaining = tools.get_status()["remaining"]
        actions = fitted.actions(remaining, deadline)
        if not actions:
            break
        selected = actions[0]
        emit("adaptive_design_scores", step=steps, actions=actions, selected=selected, remaining=remaining)
        if selected["kind"] == "observation":
            result = tools.measure_target(selected["variable"], selected["time"])
        else:
            result = getattr(tools, "simulate_" + selected["fidelity"])(selected["theta"], config["working_times"])
        emit("adaptive_design_acquired", step=steps, action=selected, result=result)
        if result.get("charge", 0) <= 0:
            raise RuntimeError("new design action did not purchase a result")
        steps += 1
    if tools.get_status()["remaining"] >= min(config["costs"].values()):
        raise RuntimeError("design ended while a new scientific action was affordable")
    result = tools.submit(fitted.theta_hat())
    return {"submission": result, "settings": SETTINGS, "steps": steps,
            "diagnostics": fitted.diagnostics()}
