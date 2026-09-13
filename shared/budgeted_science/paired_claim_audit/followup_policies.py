"""Public-only follow-up heuristics; no physical solver or reference imports."""
from copy import deepcopy
import math

import numpy as np

from . import policies as old

MEASUREMENTS=tuple((v,i/2) for v in ('x','y') for i in range(1,17) if i!=2)
# This includes all 90 one-measurement/one-follow-up/no-follow-up schedules,
# plus no-measurement controls and a cheap discrepancy-correction control.
FIXED=tuple(f'fixed:{v}:{t:g}:{after}' for v,t in MEASUREMENTS for after in ('none','intervention','fit'))
METHODS=('adaptive_followup','adaptive_full','fixed:none:0:both','fixed:none:0:intervention',
         'fixed:none:0:fit','fixed:none:0:none','corrected_x4_intervention',
         'fixed:x:4:fit_plugin','fixed:x:4:fit_accept','fixed:x:4:fit_reject',
         'all_accept','all_reject','numerical_accept_target_reject')+FIXED


class Belief(old.Belief):
    def __init__(self,public):
        self.actual_claims=deepcopy(public['claims'])
        compatible=deepcopy(public)
        compatible['claims']=[{**c,'operator':'ge'} if c['operator']=='le' else c
                              for c in compatible['claims']]
        super().__init__(compatible)

    def target_quantity(self,theta,kind):
        if kind=='target_integral':
            table,high=self.table(theta)
            value=float(np.trapezoid([10.]+[v[0] for v in table['values']],[0.]+table['times']))
            # Correlated trajectory-error approximation. A scalar observation
            # updates candidate weights, not a fictitious full measured integral.
            return value,old.HIGH_SD if high else old.LOW_RELATIVE_SD*abs(value)
        if kind=='target_late_recovery':
            num,sn=self.target_scalar(theta,'x',8.)
            den,sd=self.target_scalar(theta,'x',6.)
            den=max(den,1e-8)
            return num/den-1,math.hypot(sn/den,num*sd/den**2)
        return super().target_quantity(theta,kind)

    def probabilities(self):
        p=super().probabilities()
        for claim in self.actual_claims:
            if claim['kind']=='intervention_effect' and (self.intervention,'high') not in self.tables:
                # Use a matched-fidelity effect. Mixing a fine baseline peak
                # with a coarse intervention peak creates an avoidable bias.
                s=self.public['intervention_summary']
                ratio=s['intervention_grid_peak']/s['baseline_grid_peak']
                p[claim['id']]=old.probability({**claim,'operator':'ge'},1-ratio,
                                             old.LOW_RELATIVE_SD*ratio)
            if claim['operator']=='le':
                p[claim['id']]=1-p[claim['id']]
        return p


def run_policy(method,public,call,diagnostic):
    if method not in METHODS:
        raise ValueError('unknown follow-up policy')
    if method in ('all_accept','all_reject','numerical_accept_target_reject'):
        return old.run_policy(method,public,call,diagnostic)
    belief=Belief(public)
    ids=['original','report']
    def buy(name,**args):
        r=call(name,**args)
        belief.ingest(name,r)
        if r.get('status')=='success':
            ident=r.get('result_id',r.get('record_id'))
            if ident and ident not in ids: ids.append(ident)
        return r
    for name,theta in (('simulate_high',belief.baseline),('simulate_low',belief.other)):
        if buy(name,theta=list(theta))['status']!='success':
            raise RuntimeError('paid initialization failed')
    if method=='adaptive_full' or method=='adaptive_followup':
        if method=='adaptive_followup':
            if buy('measure_target',variable='x',time=4.)['status']!='success':
                raise RuntimeError('measurement failed')
        while True:
            remaining=call('get_status')['remaining']
            scores=[{'name':name,'args':args,'cost':cost,'gain':belief.expected_gain(name,args)}
                    for name,args,cost in belief.actions(remaining)]
            for row in scores: row['gain_per_credit']=row['gain']/row['cost']
            diagnostic('action_scores',scores=scores,probabilities=belief.probabilities(),
                       candidate_weights=belief.weights().tolist())
            if not scores: break
            best=max(scores,key=lambda r:r['gain_per_credit'])
            if best['gain']<=1e-9: break
            if buy(best['name'],**best['args'])['status']!='success': break
    else:
        if method=='corrected_x4_intervention':
            variable,t,after='x',4.,'intervention'
        else:
            _,variable,t,after=method.split(':'); t=float(t)
        if variable!='none': buy('measure_target',variable=variable,time=t)
        for theta in ([belief.intervention,belief.other] if after=='both' else
                      [belief.intervention] if after=='intervention' else
                      [belief.other] if after.startswith('fit') else []):
            buy('simulate_high',theta=list(theta))
        if method=='corrected_x4_intervention':
            low_a=np.asarray(belief.tables[belief.baseline,'low']['values'])
            high_a=np.asarray(belief.tables[belief.baseline,'high']['values'])
            other=belief.tables[belief.other,'low']
            other['values']=(np.asarray(other['values'])*high_a/low_a).tolist()
            diagnostic('cheap_correction',description='Pointwise high/low correction transferred from A to B; unvalidated; no extra solver.')
    p=belief.probabilities()
    mode=method.rsplit(':',1)[-1]
    if mode in ('fit_plugin','fit_accept','fit_reject'):
        c=next(c for c in public['claims'] if c['kind']=='intervention_effect')
        s=public['intervention_summary']
        effect=1-s['intervention_grid_peak']/s['baseline_grid_peak']
        plug=(effect>=c['threshold'] if c['operator']=='ge' else effect<=c['threshold'])
        p[c['id']]=float(plug if mode=='fit_plugin' else mode=='fit_accept')
        diagnostic('cheap_intervention_rule',mode=mode,matched_low_effect=effect,
                   note='Point estimate or constant label, not validated confidence; no extra purchase.')
    diagnostic('final_belief',probabilities=p,candidate_weights=belief.weights().tolist(),
               note='Two-fit and numerical-uncertainty heuristics, not confidence certificates.')
    return call('submit',verdicts={k:old.verdict(v) for k,v in p.items()},evidence_ids=ids,
                explanation='Public-evidence-only follow-up heuristic; +1/-2/0 utility; approximate probabilities.')
