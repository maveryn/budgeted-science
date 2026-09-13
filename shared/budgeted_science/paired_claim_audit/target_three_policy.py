"""Continuous local-fitting control; only public report and paid-data calls.

No import of physical solver, target service, private references or labels.
Verdicts are plug-in estimates, not certified confidence or interval tests.
"""
from copy import deepcopy

import numpy as np

from ..resource_planning.local_policy import LocalFit, run_local_policy


def inferred_verdicts(public, theta, table):
    theta, values = np.asarray(theta, float), np.asarray(table, float)
    if theta.shape != (3,) or np.any(theta <= 0) or not np.isfinite(theta).all():
        raise ValueError('invalid fitted parameters')
    if values.shape != (16, 2) or not np.isfinite(values).all() or np.any(values <= 0):
        return {c['id']: 'ABSTAIN' for c in public['claims']}, {}
    times = np.array(public['environment']['working_times'])
    quantities = {
        'target_parameter_accuracy': float(np.max(np.abs(np.array(public['report_parameters']) - theta) / theta)),
        'target_integral': float(np.trapezoid(np.r_[10., values[:, 0]], np.r_[0., times])),
        'target_late_recovery': float(values[-1, 0] / values[list(times).index(6.), 0] - 1),
    }
    verdicts = {}
    for c in public['claims']:
        q = quantities[c['kind']]
        holds = q <= c['threshold'] + 1e-14 if c['operator'] == 'le' else q >= c['threshold'] - 1e-14
        verdicts[c['id']] = 'ACCEPT' if holds else 'REJECT'
    return verdicts, quantities


class Tools:
    """Match the planning local policy's interface through logged audit calls."""
    def __init__(self, call, public, emit):
        self.call, self.public, self.emit = call, deepcopy(public), emit
        self.public_config = deepcopy(public['environment'])

    def simulate_low(self, theta, times=None):
        return self.call('simulate_low', theta=theta)

    def simulate_high(self, theta, times=None):
        return self.call('simulate_high', theta=theta)

    def measure_target(self, variable, time):
        return self.call('measure_target', variable=variable, time=float(time))

    def get_status(self):
        return self.call('get_status')

    def evidence(self):
        evidence = self.call('evidence')
        original = {'status': 'success', 'theta': self.public['report_parameters'],
                    'result_id': 'original', **self.public['original']}
        if not any(s['fidelity'] == 'low' and s['theta'] == original['theta']
                   for s in evidence['simulations']):
            evidence['simulations'].append(original)
        return evidence

    def submit(self, theta):
        evidence = self.evidence()
        fit = LocalFit(evidence, self.public_config)
        point = (np.asarray(theta) - fit.lower) / fit.width
        intercept, _ = fit.affine(point)
        # Free surrogate analysis of purchased data; NOT an unpaid ODE solve.
        prediction = (intercept * fit.scale).reshape(-1, 2)
        verdicts, quantities = inferred_verdicts(self.public, theta, prediction)
        self.emit('continuous_audit_fit', theta_hat=theta, predicted_table=prediction.tolist(),
                  estimated_quantities=quantities, proposals=[{'loss': loss, 'unit_point': p.tolist()}
                    for loss, p in fit.proposals()],
                  note='Local affine fit with nearest purchased high-minus-low correction; plug-in verdicts only.')
        ids = ['report', 'original'] + [s['result_id'] for s in evidence['simulations']]
        ids += [o['record_id'] for o in evidence['observations']]
        return self.call('submit', verdicts=verdicts, evidence_ids=list(dict.fromkeys(ids)),
                         explanation='Continuous local fitting of available observations and purchased '
                         'trajectories. Parameter and trajectory plug-in verdicts; no certified confidence.')


def run_policy(call, public, emit, deadline):
    return run_local_policy(Tools(call, public, emit), seed=0, log=emit, deadline=deadline)
