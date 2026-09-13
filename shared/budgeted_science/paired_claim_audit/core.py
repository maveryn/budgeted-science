"""Commission paired worlds independently of investigator policies."""
from copy import deepcopy
import math
import time

import numpy as np
from scipy.optimize import least_squares

from ..agents.records import digest
from ..multi_claim_audit import core as old, mixed

VERSION = 'paired-predator-prey-claims-v1'
# Selected development regimes after a 12-anchor numerical feasibility check.
# Freeze these before running any policy; do not replace a difficult case.
PAIR_SPECS = (
    {'theta': (1., .08, 1.1), 'point_tol': .05, 'area_tol': .05,
     'target_tol': .05, 'ratio_tol': .15, 'effect_threshold': .05},
    {'theta': (1., .08, 1.3), 'point_tol': .0005, 'area_tol': .0005,
     'target_tol': .05, 'ratio_tol': .15, 'effect_threshold': .20},
    {'theta': (1.1, .08, 1.1), 'point_tol': .05, 'area_tol': .0005,
     'target_tol': .10, 'ratio_tol': .10, 'effect_threshold': .14},
)


def _table(solution, config):
    return {'times': list(config.working_times), 'values': solution.sample(config.working_times).tolist()}


def build_catalog():
    config = old.harder_config(32)
    cases, diagnostics = [], []
    for pair_index, spec in enumerate(PAIR_SPECS):
        left = spec['theta']
        early = old._solve_high(left, config).sample([1])[0]
        def residual(z):
            return old._solve_high((z[0], .12, z[1]), config).sample([1])[0] - early
        fit = least_squares(residual, [left[0]+.16, left[2]+.45],
                            bounds=([.6,.8],[1.4,2.]), xtol=1e-12, ftol=1e-12, gtol=1e-12)
        if not fit.success or np.max(np.abs(fit.fun)) >= 1e-8:
            raise ValueError('paired early-data commissioning failed')
        right = (float(fit.x[0]), .12, float(fit.x[1]))
        intervention = (left[0], left[1]*1.1, left[2])
        refs = [old.checked_reference(theta, config) for theta in (left, right, intervention)]
        low_solution = old._solve_low(left, config)
        low = _table(low_solution, config)
        intervention_solution = old._solve_low(intervention, config)
        low_intervention = _table(intervention_solution, config)
        ratio = mixed.table_value(low,'y',6)/mixed.table_value(low,'x',6)
        claims = [
            {'kind':'numerical_point', 'scope':'specified_model', 'operator':'relative_error_le',
             'reported_value':mixed.printed(mixed.quantity('numerical_point',low)), 'relative_tolerance':spec['point_tol']},
            {'kind':'cumulative_abundance', 'scope':'specified_model', 'operator':'relative_error_le',
             'reported_value':mixed.printed(mixed.quantity('cumulative_abundance',low)), 'relative_tolerance':spec['area_tol']},
            {'kind':'intervention_effect', 'scope':'specified_model', 'operator':'ge', 'threshold':spec['effect_threshold']},
            {'kind':'target_agreement', 'scope':'fixed_target', 'operator':'relative_error_le',
             'reported_value':mixed.printed(mixed.table_value(low,'x',4)), 'relative_tolerance':spec['target_tol']},
            {'kind':'target_composition', 'scope':'fixed_target', 'operator':'relative_error_le',
             'reported_value':mixed.printed(ratio), 'relative_tolerance':spec['ratio_tol']},
            {'kind':'target_recovery', 'scope':'fixed_target', 'operator':'ge', 'threshold':.20},
        ]
        definitions = {
            'numerical_point': 'baseline x(0.5) at the report parameters',
            'cumulative_abundance': 'baseline trapezoidal prey integral on 0,0.5,...,8, not the continuous integral',
            'intervention_effect': 'R=(baseline peak-intervention peak)/baseline peak, with peaks on 0,0.5,...,8',
            'target_agreement': 'noise-free target x(4)',
            'target_composition': 'noise-free target y(6)/x(6)',
            'target_recovery': 'noise-free target x(6)/x(4)-1',
        }
        order = np.random.default_rng(8200+pair_index).permutation(6)
        claims = [{**claims[j], 'id':f'C{i+1}'} for i,j in enumerate(order)]
        for c in claims:
            d = definitions[c['kind']]
            c['text'] = (f"The reported {d}, {c['reported_value']:.10g}, is accurate within {100*c['relative_tolerance']:g}%."
                         if c['operator']=='relative_error_le' else f"The {d} is at least {c['threshold']:.10g}.")
        alternatives = [list(left),list(right)]
        if pair_index % 2:
            alternatives.reverse()
        public = {'claims':claims, 'report_parameters':list(left), 'intervention_parameters':list(intervention),
                  'original':{'id':'original','fidelity':'low','step':.1,**low}, 'environment':config.public(),
                  'candidate_fits':alternatives,
                  'candidate_note':'Two competing fits to the same early calibration. They are not certified and are not guaranteed to exhaust the public parameter family. New predictions must use paid services.',
                  'intervention_summary':{'fidelity':'low','step':.1,
                      'baseline_grid_peak':mixed.printed(np.max(mixed.field(low)[:,0])),
                      'intervention_grid_peak':mixed.printed(np.max(mixed.field(low_intervention)[:,0]))},
                  'scoring':{'correct':1,'wrong':-2,'abstain':0,'spending_penalty':0}}
        public['report'] = ('Predator-prey study. Initial populations (10,5), horizon [0,8]. '
            'The baseline Euler table and intervention summary were actually computed at step 0.1. '
            'The intervention increases theta2 by 10%; all other parameters remain unchanged. '
            'Two competing parameter fits are listed; neither is asserted to be the target. '
            'Assess each claim independently; presentation order has no priority.\n\n'
            + '\n\n'.join(c['id']+': '+c['text'] for c in claims))
        pair_rows = []
        for member, theta in enumerate((left,right)):
            observations = {(v,t):mixed.table_value(refs[member],v,t) for v,t in (('x',4.),('x',6.),('y',6.))}
            truth = {}
            for c in claims:
                q = mixed.quantity(c['kind'],refs[0],refs[2],observations)
                truth[c['id']] = {'reference_value':q,**mixed.classify(c,q)}
            study = {'version':VERSION, 'public':deepcopy(public), 'private':{
                'pair_index':pair_index,'member':member,'target_parameters':list(theta),'noise_seed':8400+pair_index,
                'truth':truth,'references':{'numerical':refs[0],'target':refs[member],'intervention':refs[2]},
                'original_artifact':low_solution.artifact(),
                'intervention_original_artifact':intervention_solution.artifact(),
                'status':'designed development pair; not held out; target belongs to supplied pair in this catalog'}}
            ident = digest({'pair':pair_index,'member':member,'version':VERSION})[:12]
            cases.append({'case_id':ident,'study':study})
            pair_rows.append({'case_id':ident,'theta':list(theta),
                'truth_by_kind':{c['kind']:truth[c['id']] for c in claims}})
        # Require opposite target verdicts with margins, not merely unusual settings.
        for kind in ('target_agreement','target_composition','target_recovery'):
            t = [row['truth_by_kind'][kind] for row in pair_rows]
            if t[0]['verdict'] == t[1]['verdict']:
                raise ValueError(f'commissioning failed: pair {pair_index}, {kind} does not flip')
            if min(abs(x['criterion_margin']) for x in t) < .005:
                raise ValueError('claim too close to its reference boundary for this development catalog')
        diagnostics.append({'pair':pair_index,'early_values':early.tolist(),
                            'early_max_difference':float(np.max(np.abs(fit.fun))), 'members':pair_rows})
    return {'version':VERSION,'cases':cases,'diagnostics':diagnostics,'pair_specs':deepcopy(PAIR_SPECS)}


class Audit(old.Audit):
    """Existing seven actions and 1/8/12 prices; no hidden candidate selector."""
    def __init__(self, study, log=None, *, budget=24):
        if study['version'] != VERSION or type(budget) is not int or budget not in (24,32):
            raise ValueError('paired toy supports 24 or 32 credits')
        self._study, self.public = deepcopy(study), deepcopy(study['public'])
        self.public['environment']['budget'] = float(budget)
        self._environment = old.PlanningEnvironment(study['private']['target_parameters'],old.harder_config(budget),
                                                   log=log,noise_seed=study['private']['noise_seed'])
        # Suppress insignificant solver-fit residuals in the published early
        # calibration. Quantization is 10^-8, far below the 0.1/0.05 noise.
        for record in self._environment._observations.values():
            if record['time']==1:
                record['value']=round(record['value'],8)
        self._tools, self.submission = self._environment.tools, None

    def dispatch(self, name, args):
        keys = {'simulate_low':{'theta'},'simulate_high':{'theta'},'measure_target':{'variable','time'},
                'evidence':set(),'get_status':set(),'compare_cached_candidates':set(),
                'submit':{'verdicts','evidence_ids','explanation'}}
        if name not in keys or not isinstance(args,dict) or set(args)!=keys[name]:
            raise ValueError('unknown action or invalid argument fields')
        if self.submission is not None:
            raise ValueError('already submitted')
        if name in ('simulate_low','simulate_high'):
            from ..resource_planning.environment import _theta
            theta = _theta(args['theta'],old.harder_config(32))
            if name=='simulate_low' and list(theta)==self.public['report_parameters']:
                return {'status':'success','result_id':'original','theta':list(theta),'fidelity':'low',
                        'times':self.public['original']['times'],'values':self.public['original']['values'],
                        'charge':0,'remaining':self.status()['remaining'],'cache_hit':True}
            return getattr(self._tools,name)(theta)
        return super().dispatch(name,args)

    def evaluate(self):
        result = super().evaluate()
        result['utility'] = result['correct']-2*result['wrong']
        return result


class Session:
    def __init__(self, study, budget, log):
        self.log, self.calls, self.executed, self.artifact_count = log,0,{},0
        self.deadline = time.monotonic()+300
        self.environment = Audit(study,self._event,budget=budget)

    def _event(self, kind, **data):
        artifact = data.pop('artifact',None)
        if artifact is not None:
            self.artifact_count += 1
            data['artifact_path']=self.log.write_json(f'numerical/trajectory-{self.artifact_count:03d}.json',artifact)
        self.log.event('environment_event',role='harness',event_kind=kind,data=data)

    def call(self, name, **args):
        return self.execute(f'call-{self.calls+1}',name,args)

    def execute(self, call_id, name, args):
        if time.monotonic()>self.deadline or self.calls>=30:
            raise RuntimeError('episode limit')
        self.calls+=1
        self.log.event('tool_requested',call_id=call_id,name=name,arguments=args)
        key=digest([name,args])
        if call_id in self.executed:
            prior,result=self.executed[call_id]
            if prior!=key:
                result={'status':'invalid','error':'call ID conflict'}
        else:
            try:
                result=self.environment.dispatch(name,args)
            except (ValueError,TypeError,KeyError,OverflowError) as exc:
                result={'status':'invalid','error':str(exc)}
            self.executed[call_id]=(key,deepcopy(result))
        result=deepcopy(result)
        result['budget_after']=self.environment.status()
        self.log.event('tool_result',call_id=call_id,name=name,result=result)
        return result
