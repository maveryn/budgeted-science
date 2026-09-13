"""Public-evidence-only heuristics. No physical solver or evaluator imports.

The two-fit belief and 10% low-model discrepancy are approximations, NOT
validated confidence. All policies below share this estimator. Information
seeking uses expected verdict utility, not raw parameter entropy.
"""
from copy import deepcopy
import math

import numpy as np
from scipy.special import ndtr, softmax

LOW_RELATIVE_SD = .10
HIGH_SD = 1e-6
NODES = (-math.sqrt(3),0.,math.sqrt(3))
WEIGHTS = (1/6,2/3,1/6)
METHODS = ('simulation_first','measure_x4_intervention','measure_y6_intervention',
           'measure_x4_fit','adaptive_utility','all_accept','all_reject','numerical_accept_target_reject')


def utility(p):
    return max(3*p-2,1-3*p,0.)


def verdict(p):
    if p>2/3:
        return 'ACCEPT'
    if p<1/3:
        return 'REJECT'
    return 'ABSTAIN'


def probability(claim, mean, sd):
    sd=max(float(sd),HIGH_SD)
    if claim['operator']=='ge':
        return float(ndtr((mean-claim['threshold'])/sd))
    reported,tol=claim['reported_value'],claim['relative_tolerance']
    lo,hi=reported/(1+tol),reported/(1-tol)
    return float(np.clip(ndtr((hi-mean)/sd)-ndtr((lo-mean)/sd),0,1))


class Belief:
    def __init__(self, public):
        self.public=deepcopy(public)
        self.fits=[tuple(t) for t in public['candidate_fits']]
        self.baseline=tuple(public['report_parameters'])
        self.other=next(t for t in self.fits if t!=self.baseline)
        self.intervention=tuple(public['intervention_parameters'])
        self.tables={(self.baseline,'low'):deepcopy(public['original'])}
        self.observations={}
        self.purchased=set()

    def ingest(self, name, result):
        if result.get('status')!='success':
            return
        if name in ('simulate_low','simulate_high'):
            key=(tuple(result['theta']),result['fidelity'])
            self.tables[key]=deepcopy(result)
            self.purchased.add(key)
        elif name=='measure_target':
            self.observations[result['variable'],result['time']]=deepcopy(result)

    def table(self, theta):
        if (theta,'high') in self.tables:
            return self.tables[theta,'high'],True
        return self.tables[theta,'low'],False

    def prediction(self, theta, variable, time):
        table,high=self.table(theta)
        value=float(table['values'][table['times'].index(time)][('x','y').index(variable)])
        sd=HIGH_SD if high else LOW_RELATIVE_SD*max(abs(value),.1)
        return value,sd

    def weights(self):
        # Both supplied alternatives fit the same initial evidence. Do not
        # break that tie by comparing low numerical errors to tiny sensor noise.
        logs=[]
        for theta in self.fits:
            value=0.
            for (variable,time),record in self.observations.items():
                mean,sd=self.prediction(theta,variable,time)
                variance=sd*sd+record['noise_std']**2
                value-=.5*((record['value']-mean)**2/variance+math.log(variance))
            logs.append(value)
        return softmax(logs)

    def target_scalar(self, theta, variable, time):
        record=self.observations.get((variable,time))
        return ((record['value'],record['noise_std']) if record else self.prediction(theta,variable,time))

    def target_quantity(self, theta, kind):
        if kind=='target_agreement':
            return self.target_scalar(theta,'x',4.)
        if kind=='target_composition':
            numerator,sn=self.target_scalar(theta,'y',6.)
            denominator,sd=self.target_scalar(theta,'x',6.)
            offset=0
        else:
            numerator,sn=self.target_scalar(theta,'x',6.)
            denominator,sd=self.target_scalar(theta,'x',4.)
            offset=1
        denominator=max(denominator,1e-8)
        ratio=numerator/denominator
        sigma=math.sqrt((sn/denominator)**2+(numerator*sd/denominator**2)**2)
        return ratio-offset,sigma

    def probabilities(self):
        base,base_high=self.table(self.baseline)
        result={}
        for claim in self.public['claims']:
            kind=claim['kind']
            if kind.startswith('target_'):
                result[claim['id']]=float(sum(w*probability(claim,*self.target_quantity(t,kind))
                                             for t,w in zip(self.fits,self.weights())))
                continue
            if kind=='numerical_point':
                if not base_high:
                    result[claim['id']]=.5
                    continue
                value,_=self.prediction(self.baseline,'x',.5)
                reported=claim['reported_value']
                result[claim['id']]=float(abs(reported-value)/abs(value)<=claim['relative_tolerance'])
            elif kind=='cumulative_abundance':
                if not base_high:
                    result[claim['id']]=.5
                    continue
                value=float(np.trapezoid([10.]+[v[0] for v in base['values']],[0.]+base['times']))
                result[claim['id']]=float(abs(claim['reported_value']-value)/abs(value)<=claim['relative_tolerance'])
            else:
                peak=max(10.,max(v[0] for v in base['values']))
                high=self.tables.get((self.intervention,'high'))
                other_peak=(max(10.,max(v[0] for v in high['values'])) if high else
                            self.public['intervention_summary']['intervention_grid_peak'])
                mean=1-other_peak/peak
                sigma=HIGH_SD if high else LOW_RELATIVE_SD*other_peak/peak
                result[claim['id']]=probability(claim,mean,sigma)
        return result

    def total_utility(self):
        return sum(utility(p) for p in self.probabilities().values())

    def actions(self, remaining):
        result=[]
        if remaining>=8:
            for theta in (self.intervention,self.other):
                if (theta,'high') not in self.purchased:
                    result.append(('simulate_high',{'theta':list(theta)},8))
        if remaining>=12:
            for variable in ('x','y'):
                for t in self.public['environment']['working_times']:
                    if t!=1 and (variable,t) not in self.observations:
                        result.append(('measure_target',{'variable':variable,'time':t},12))
        return result

    def expected_gain(self, name, args):
        """Quadrature fantasies only: never call the physical environment."""
        before=self.total_utility()
        if name=='simulate_high' and tuple(args['theta'])==self.intervention:
            claim=next(c for c in self.public['claims'] if c['kind']=='intervention_effect')
            # This trajectory is relevant only to the intervention claim.
            return 1-utility(self.probabilities()[claim['id']])
        after=0.
        if name=='measure_target':
            var,t=args['variable'],args['time']
            sensor=.1 if var=='x' else .05
            for theta,weight in zip(self.fits,self.weights()):
                mean,sd=self.prediction(theta,var,t)
                for z,w in zip(NODES,WEIGHTS):
                    fantasy=deepcopy(self)
                    fantasy.observations[var,t]={'value':mean+z*math.hypot(sd,sensor),'noise_std':sensor}
                    after+=float(weight)*w*fantasy.total_utility()
        else:
            theta=tuple(args['theta'])
            table,_=self.table(theta)
            # A trajectory purchase is represented by a correlated multiplicative
            # error per population across all times (9 quadrature trajectories).
            # This is a cheap heuristic approximation, not calibrated solver error.
            for zx,wx in zip(NODES,WEIGHTS):
                for zy,wy in zip(NODES,WEIGHTS):
                    fantasy=deepcopy(self)
                    values=np.asarray(table['values'])*(1+LOW_RELATIVE_SD*np.array([zx,zy]))
                    fantasy.tables[theta,'high']={**table,'values':values.tolist(),'fidelity':'high'}
                    after+=wx*wy*fantasy.total_utility()
        return after-before


def run_policy(method, public, call, diagnostic):
    if method not in METHODS:
        raise ValueError('unknown policy')
    if method in ('all_accept','all_reject','numerical_accept_target_reject'):
        values={c['id']:('ACCEPT' if method=='all_accept' or
                       method=='numerical_accept_target_reject' and c['scope']=='specified_model' else 'REJECT')
                for c in public['claims']}
        return call('submit',verdicts=values,evidence_ids=['report'],explanation='Frozen no-purchase blanket control.')
    belief=Belief(public)
    ids=['original','report']
    def buy(name,args):
        result=call(name,**args)
        belief.ingest(name,result)
        if result.get('status')=='success':
            ident=result.get('result_id',result.get('record_id'))
            if ident and ident not in ids:
                ids.append(ident)
        return result
    # Common paid initialization: 8 + 1 = 9. Not a mandatory future-agent plan.
    for name,args in [('simulate_high',{'theta':list(belief.baseline)}),
                      ('simulate_low',{'theta':list(belief.other)})]:
        if buy(name,args)['status']!='success':
            raise RuntimeError('required initialization failed; no fabricated estimates')
    if method=='adaptive_utility':
        while True:
            remaining=call('get_status')['remaining']
            scores=[]
            for name,args,cost in belief.actions(remaining):
                gain=belief.expected_gain(name,args)
                scores.append({'name':name,'args':args,'cost':cost,'gain':gain,'gain_per_credit':gain/cost})
            diagnostic('action_scores',scores=scores,probabilities=belief.probabilities(),
                       candidate_weights=belief.weights().tolist())
            if not scores:
                break
            best=max(scores,key=lambda x:x['gain_per_credit'])
            if best['gain']<=1e-9:
                break
            if buy(best['name'],best['args'])['status']!='success':
                break
    else:
        high_i=('simulate_high',{'theta':list(belief.intervention)})
        high_f=('simulate_high',{'theta':list(belief.other)})
        x4=('measure_target',{'variable':'x','time':4.})
        y6=('measure_target',{'variable':'y','time':6.})
        orders={'simulation_first':[high_i,high_f,x4], 'measure_x4_intervention':[x4,high_i,high_f],
                'measure_y6_intervention':[y6,high_i,high_f], 'measure_x4_fit':[x4,high_f,high_i]}
        for name,args in orders[method]:
            buy(name,args)
    probabilities=belief.probabilities()
    diagnostic('final_belief',probabilities=probabilities,candidate_weights=belief.weights().tolist(),
               note='Approximate two-fit model and unvalidated numerical-error assumptions; not confidence certificates.')
    return call('submit',verdicts={k:verdict(p) for k,p in probabilities.items()},evidence_ids=ids,
                explanation='Public-evidence-only two-fit heuristic. Verdict threshold 2/3 under +1/-2/0 utility. Probabilities are approximations, not validated confidence.')
