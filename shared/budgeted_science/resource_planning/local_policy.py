"""Paid-data-only, multistart local least-squares with fidelity correction.

This is an engineering baseline, not a reproduction of a published optimizer.
Local affine response models and their bounded least-squares minimization are
uncharged analysis of PURCHASED trajectories. Every actual simulator evaluation
goes through tools. No equations, private target, reference solver, or GP posterior
is imported here. A final interpolated estimate need not itself be simulated.
"""

import time
import numpy as np
from scipy.optimize import least_squares
from scipy.stats import qmc

from .emulator import check_deadline

SETTINGS = {"initial_radius": .2, "trust_radius": .3, "neighbors": 8,
            "starts": 3, "ridge": 1e-8, "high_fidelity_purchases": 1}


class LocalFit:
    def __init__(self, evidence, config):
        self.config = config
        bounds = np.asarray(config['bounds'])
        self.lower, self.width = bounds[:, 0], np.diff(bounds).ravel()
        self.times = np.asarray(config['working_times'])
        self.scale = np.tile(config['initial'], len(self.times))
        self.low = [s for s in evidence['simulations'] if s['status'] == 'success' and s['fidelity'] == 'low']
        self.high = [s for s in evidence['simulations'] if s['status'] == 'success' and s['fidelity'] == 'high']
        if len(self.low) < 4:
            raise ValueError('local fitting requires four successful low trajectories')
        self.points = np.array([(np.array(s['theta']) - self.lower) / self.width for s in self.low])
        self.values = np.array([np.asarray(s['values']).ravel() / self.scale for s in self.low])
        self.obs = [o for o in evidence['observations'] if o['time'] > 0]
        self.indices = np.array([self.index(o['variable'], o['time']) for o in self.obs])
        self.observed = np.array([o['value'] / config['initial'][('x', 'y').index(o['variable'])] for o in self.obs])
        self.biases = []
        for high in self.high:
            match = next((i for i,s in enumerate(self.low) if s['theta'] == high['theta']), None)
            if match is not None:
                self.biases.append((self.points[match], np.asarray(high['values']).ravel() / self.scale - self.values[match]))

    def index(self, variable, at):
        return 2 * int(np.flatnonzero(np.isclose(self.times, at, atol=1e-12, rtol=0))[0]) + ('x', 'y').index(variable)

    def bias(self, point):
        if not self.biases:
            return np.zeros(len(self.scale))
        return min(self.biases, key=lambda item: np.linalg.norm(item[0] - point))[1]

    def affine(self, center):
        distances = np.linalg.norm(self.points - center, axis=1)
        selected = np.argsort(distances)[:SETTINGS['neighbors']]
        design = np.column_stack([np.ones(len(selected)), self.points[selected] - center])
        weights = 1 / (.05 + distances[selected]) ** 2
        regularizer = SETTINGS['ridge'] * np.eye(4)
        regularizer[0, 0] = 0
        coefficients = np.linalg.solve(design.T @ (weights[:, None] * design) + regularizer,
                                       design.T @ (weights[:, None] * self.values[selected]))
        return coefficients[0] + self.bias(center), coefficients[1:].T

    def scores(self):
        corrected = np.array([v + self.bias(p) for p,v in zip(self.points, self.values)])
        return np.sum((corrected[:, self.indices] - self.observed) ** 2, axis=1)

    def proposals(self):
        candidates = []
        for index in np.argsort(self.scores())[:SETTINGS['starts']]:
            center = self.points[index]
            intercept, jacobian = self.affine(center)
            radius = SETTINGS['trust_radius']
            fitted = least_squares(lambda p: (intercept + jacobian @ (p - center))[self.indices] - self.observed,
                                   center, jac=lambda p: jacobian[self.indices],
                                   bounds=(np.maximum(0, center - radius), np.minimum(1, center + radius)),
                                   max_nfev=50, ftol=1e-10, xtol=1e-10, gtol=1e-10)
            candidates.append((float(np.sum(fitted.fun ** 2)), fitted.x))
        return sorted(candidates, key=lambda item: item[0])

    def measurement(self):
        center = self.points[np.argmin(self.scores())]
        _, jacobian = self.affine(center)
        old = jacobian[self.indices]
        information = old.T @ old + np.eye(3) * 1e-10
        bought = {(o['variable'], o['time']) for o in self.obs}
        scores = []
        for variable in ('x', 'y'):
            for at in self.times:
                if (variable, at) in bought or at == 0:
                    continue
                row = jacobian[self.index(variable, at)]
                gain = float(np.linalg.slogdet(information + np.outer(row, row))[1]
                             - np.linalg.slogdet(information)[1])
                scores.append({'variable': variable, 'time': float(at), 'logdet_gain': gain})
        return sorted(scores, key=lambda item: item['logdet_gain'], reverse=True)


def run_local_policy(tools, seed=0, log=None, deadline=None):
    """Explore cheaply, choose one measurement, fit, calibrate one high solve,
    then refine locally. All finite-difference information comes from purchases.
    """
    emit = log or (lambda kind, **data: None)
    config = tools.public_config
    bounds = np.array(config['bounds'])
    lower, width = bounds[:, 0], np.diff(bounds).ravel()
    low_price, high_price, measurement_price = (config['costs'][name] for name in ('low', 'high', 'measurement'))
    low_allowance = int((config['budget'] - high_price - measurement_price) // low_price)
    if low_allowance < 4:
        raise ValueError('local baseline needs one measurement, one high solve, and at least four low solves')
    started = time.monotonic()
    emit('local_plan', settings=SETTINGS, seed=seed, low_allowance=low_allowance,
         noise_fraction=config.get('observation_noise_fraction', 0))
    initial = [np.full(3, .5)]
    for sign in (1, -1):
        initial += [np.full(3, .5) + sign * SETTINGS['initial_radius'] * np.eye(3)[j] for j in range(3)]
    # Leave some low calls for refinement whenever the budget permits it.
    initial = initial[:min(7, low_allowance)]
    fallback = qmc.Sobol(3, scramble=True, seed=seed + 923).random_base2(8)
    fallback_index = 0

    def buy_low(point):
        check_deadline(deadline)
        result = tools.simulate_low((lower + np.clip(point, 0, 1) * width).tolist(), config['working_times'])
        if result['status'] not in ('success', 'failed'):
            raise RuntimeError('rejected baseline purchase: ' + result['status'])
        return result

    for point in initial:
        buy_low(point)
    local = LocalFit(tools.evidence(), config)
    measurements = local.measurement()
    emit('measurement_design', scores=measurements)
    choice = measurements[0]
    result = tools.measure_target(choice['variable'], choice['time'])
    if result['status'] != 'success':
        raise RuntimeError('target measurement did not complete')

    # Reserve ~40% of cheap calls for fitting after correcting low/high bias.
    post_calls = max(0, min(low_allowance - len(initial), int(np.ceil(.4 * low_allowance))))
    reserve = high_price + post_calls * low_price

    def refine(keep):
        nonlocal fallback_index
        while tools.get_status()['remaining'] >= keep + low_price:
            check_deadline(deadline)
            local = LocalFit(tools.evidence(), config)
            proposals = local.proposals()
            new = [(loss, point) for loss,point in proposals
                   if np.min(np.linalg.norm(local.points - point, axis=1)) > 1e-5]
            if new:
                loss, point = new[0]
            else:
                point, loss = fallback[fallback_index], None
                fallback_index += 1
            emit('local_proposal', unit_point=point.tolist(), predicted_residual_squared=loss,
                 high_correction=bool(local.biases), starts=len(proposals))
            buy_low(point)

    refine(reserve)
    local = LocalFit(tools.evidence(), config)
    best = local.low[int(np.argmin(local.scores()))]
    result = tools.simulate_high(best['theta'], config['working_times'])
    if result['status'] != 'success':
        raise RuntimeError('high-fidelity calibration failed')
    refine(0)
    local = LocalFit(tools.evidence(), config)
    _, point = local.proposals()[0]
    estimate = (lower + np.clip(point, 0, 1) * width).tolist()
    submitted = tools.submit(estimate)
    emit('local_finished', estimate=estimate, status=submitted['status'],
         elapsed_seconds=time.monotonic() - started,
         note='Continuous estimate from purchased-data local fit; not an unpaid physical solve.')
    return {'submission': submitted, 'settings': SETTINGS}
