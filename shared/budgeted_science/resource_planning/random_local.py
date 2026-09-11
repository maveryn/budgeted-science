"""Fixed random acquisitions, followed by the existing paid-data local fit."""

import time
import numpy as np
from scipy.stats import qmc

from .emulator import check_deadline
from .local_policy import LocalFit, SETTINGS


def fixed_design(config, seed=0):
    """Exactly the existing lower-budget random-GP design, before evidence."""
    if config['budget'] != 32 or config['costs'] != {'low': 1, 'high': 8, 'measurement': 12}:
        raise ValueError('random_local pilot is frozen at 32 credits and prices 1/8/12')
    bounds = np.asarray(config['bounds'])
    unit = qmc.Sobol(3, scramble=True, seed=seed).random_base2(5)
    locations = bounds[:, 0] + unit * np.diff(bounds).ravel()
    menu = [(v, t) for v in ('x', 'y') for t in config['working_times'] if t not in (0, 1)]
    selected = menu[int(np.random.default_rng(seed + 71).integers(len(menu)))]
    return {'low_locations': locations[:12].tolist(), 'high': locations[0].tolist(),
            'measurement': list(selected), 'policy_seed': seed}


def run_random_local(tools, seed=0, log=None, deadline=None):
    emit = log or (lambda kind, **data: None)
    started = time.monotonic()
    config = tools.public_config
    plan = fixed_design(config, seed)
    emit('random_local_plan', **plan, settings=SETTINGS)
    for theta in plan['low_locations']:
        check_deadline(deadline)
        result = tools.simulate_low(theta)
        if result['status'] not in ('success', 'failed'):
            raise RuntimeError('random_local low purchase rejected')
    check_deadline(deadline)
    result = tools.simulate_high(plan['high'])
    if result['status'] != 'success':
        raise RuntimeError('random_local high calibration failed')
    result = tools.measure_target(*plan['measurement'])
    if result['status'] != 'success':
        raise RuntimeError('random_local measurement failed')
    check_deadline(deadline)
    evidence = tools.evidence()
    fit = LocalFit(evidence, config)
    if not fit.biases:
        raise RuntimeError('random_local requires its purchased paired high/low correction')
    proposals = fit.proposals()
    residual, point = proposals[0]
    estimate = (fit.lower + np.clip(point, 0, 1) * fit.width).tolist()
    check_deadline(deadline)
    emit('random_local_fit', estimate=estimate, predicted_residual_squared=residual,
         proposals=[{'residual': loss, 'unit_point': p.tolist()} for loss, p in proposals],
         simulation_ids=[s['result_id'] for s in evidence['simulations']],
         observation_ids=[o['record_id'] for o in evidence['observations']],
         note='Existing local affine fit to purchased data; no additional physical evaluations.')
    result = tools.submit(estimate)
    emit('random_local_finished', estimate=estimate, status=result['status'],
         elapsed_seconds=time.monotonic() - started)
    return {'submission': result, 'settings': SETTINGS, 'plan': plan}
