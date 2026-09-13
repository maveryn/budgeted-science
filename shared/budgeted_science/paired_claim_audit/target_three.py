"""Three target-dependent claims; frozen worlds, newly fitted report estimates.

Construction may run solvers; investigators only see public purchased evidence.
Previous paired/follow-up modules and catalogs remain immutable.
"""
from copy import deepcopy

import numpy as np
from scipy.optimize import least_squares

from . import core, followup_core
from ..agents.records import digest

VERSION = 'target-three-claims-v1'


def parameter_error(reported, target):
    reported, target = np.asarray(reported, float), np.asarray(target, float)
    if (reported.shape != (3,) or target.shape != (3,) or not np.isfinite(reported).all()
            or not np.isfinite(target).all() or np.any(target <= 0)):
        raise ValueError('three finite parameters and positive target required')
    return float(np.max(np.abs(reported - target) / target))


def classify(claim, value):
    if claim['kind'] == 'target_parameter_accuracy':
        if not np.isfinite(value) or value < 0:
            raise ValueError('invalid parameter error')
        margin = claim['threshold'] - value
        return {'criterion_margin': float(margin),
                'verdict': 'ACCEPT' if value <= claim['threshold'] + 1e-14 else 'REJECT'}
    return followup_core.classify(claim, value)


def fit_report(public_evidence):
    """Author calibration, using ONLY free noisy observations, not private truth.

    Two observations do not uniquely identify three parameters. The author fixes
    theta2=.08, fits theta1/theta3 and makes a claim that an auditor may reject.
    This restriction and every evaluated early prediction are public artifacts.
    """
    cfg = core.old.harder_config(32)
    observations = [next(o for o in public_evidence['observations']
                         if o['variable'] == variable and o['time'] == 1.) for variable in ('x', 'y')]
    values = np.array([o['value'] for o in observations])
    trace = []

    def residual(z):
        theta = [float(z[0]), .08, float(z[1])]
        predicted = core.old._solve_high(theta, cfg).sample([1.])[0]
        trace.append({'theta': theta, 'time': 1., 'predicted_xy': predicted.tolist()})
        return (predicted - values) / np.array([.1, .05])

    fit = least_squares(residual, [1., 1.2], bounds=([.6, .8], [1.4, 2.]),
                        max_nfev=100, xtol=1e-11, ftol=1e-11, gtol=1e-11)
    if not fit.success or not np.isfinite(fit.x).all():
        raise ValueError('author calibration did not complete')
    theta = [float(fit.x[0]), .08, float(fit.x[1])]
    solution = core.old._solve_low(theta, cfg)
    if not np.isfinite(solution.sample(cfg.working_times)).all():
        raise ValueError('author Euler calculation failed')
    return theta, solution, {
        'method': 'bounded least squares against noisy x(1),y(1); theta2 fixed at 0.08',
        'solver': 'DOP853, rtol=1e-10, atol=1e-12; published calibration outputs only at t=1',
        'observations': observations, 'evaluations': trace,
        'weighted_residual_squared': float(np.sum(fit.fun ** 2)),
        'note': 'Pre-existing author computations, not audit purchases. This conditional fit is not a uniqueness or accuracy certificate.'}


def build_catalog(original):
    if original['version'] != followup_core.VERSION or len(original['cases']) != 6:
        raise ValueError('expected original six frozen follow-up worlds')
    cfg, cases, reports = core.old.harder_config(32), [], {}
    for source in original['cases']:
        old = source['study']
        pair = old['private']['pair_index']
        if pair not in reports:
            # The construction boundary deliberately passes only public evidence.
            evidence = followup_core.Audit(old).evidence()
            reports[pair] = fit_report(evidence)
        estimate, solution, provenance = reports[pair]
        kept = [deepcopy(c) for c in old['public']['claims']
                if c['kind'] in ('target_integral', 'target_late_recovery')]
        claims = [{'kind': 'target_parameter_accuracy', 'scope': 'fixed_target',
                   'operator': 'le', 'threshold': .05, 'reported_parameters': estimate,
                   'text': 'Every reported parameter estimate is within 5% of the fixed target value: '
                           'max_i abs(reported_theta_i - target_theta_i)/abs(target_theta_i) <= 0.05.'}, *kept]
        order = np.random.default_rng(9100 + pair).permutation(3)
        claims = [{**claims[j], 'id': f'C{i+1}'} for i, j in enumerate(order)]
        for c in claims:
            c['text'] = c['text'].replace('The the ', 'The ')
        public = {'claims': claims, 'report_parameters': estimate,
                  'original': {'id': 'original', 'fidelity': 'low', 'step': .1,
                               **core._table(solution, cfg)},
                  'author_calibration': deepcopy(provenance), 'environment': cfg.public(),
                  'scoring': {'correct': 1, 'wrong': -2, 'abstain': 0, 'spending_penalty': 0}}
        public['report'] = ('Predator-prey calibration study; initial populations (10,5), interval [0,8]. '
            'We fit theta1 and theta3 to noisy x(1),y(1), holding theta2 at 0.08. '
            'The reported estimate and author calibration records are supplied, together with '
            'an Euler dt=0.1 trajectory at that estimate. No alternative fit or exhaustive '
            'candidate set is supplied. Audit the following three assertions about the fixed '
            'target, not merely the model at the reported parameters. Integrals are trapezoidal '
            'on 0,0.5,...,8, and late recovery is x(8)/x(6)-1.\n\n' +
            '\n\n'.join(c['id'] + ': ' + c['text'] for c in claims))
        private = {k: deepcopy(old['private'][k]) for k in
                   ('pair_index', 'member', 'target_parameters', 'noise_seed')}
        private['references'] = {'target': deepcopy(old['private']['references']['target'])}
        private['truth'] = {}
        for c in claims:
            q = (parameter_error(estimate, private['target_parameters'])
                 if c['kind'] == 'target_parameter_accuracy' else
                 followup_core.target_quantity(c['kind'], private['references']['target']))
            private['truth'][c['id']] = {'reference_value': q, **classify(c, q)}
        private['original_artifact'] = solution.artifact()
        private['source_case_id'] = source['case_id']
        private['status'] = 'reused engineered development world; not held out; author fit uses public early observations only'
        study = {'version': VERSION, 'public': public, 'private': private}
        ident = digest({'version': VERSION, 'source': source['case_id']})[:12]
        cases.append({'case_id': ident, 'study': study})
    for i in range(0, 6, 2):
        if cases[i]['study']['public'] != cases[i+1]['study']['public']:
            raise ValueError('pair reports differ')
    return {'version': VERSION, 'source_catalog_hash': digest(original), 'cases': cases,
            'case_selection': 'all six existing worlds retained; no label or performance selection'}


class Audit(core.Audit):
    def __init__(self, study, log=None, *, budget=32):
        if study['version'] != VERSION or budget != 32:
            raise ValueError('target-three toy requires version and 32 credits')
        compatible = deepcopy(study)
        compatible['version'] = core.VERSION
        super().__init__(compatible, log, budget=budget)
        self._study['version'] = VERSION
