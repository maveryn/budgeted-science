"""Follow-up commissioning variant; the original paired catalog is unchanged."""
from copy import deepcopy
import time

import numpy as np

from . import core
from ..agents.records import digest
from ..multi_claim_audit import mixed

VERSION = 'paired-claim-followup-v2'
# Rounded development thresholds selected after inspecting the original six
# systems' coarse/fine quantities, before running the follow-up policies.
SPECS = (
    {'area':126., 'ratio':.25, 'ratio_operator':'ge', 'late':.05, 'effect':.14, 'effect_operator':'ge'},
    {'area':142., 'ratio':.19, 'ratio_operator':'le', 'late':.05, 'effect':.125, 'effect_operator':'ge'},
    {'area':130., 'ratio':.21, 'ratio_operator':'ge', 'late':-.40, 'effect':.14, 'effect_operator':'ge'},
)


def classify(claim,value):
    if claim['operator']=='le':
        return mixed.classify({**claim,'operator':'ge','threshold':-claim['threshold']},-value)
    return mixed.classify(claim,value)


def target_quantity(kind,table):
    if kind=='target_integral':
        return mixed.quantity('cumulative_abundance',table)
    if kind=='target_late_recovery':
        return mixed.table_value(table,'x',8.)/mixed.table_value(table,'x',6.)-1
    if kind=='target_composition':
        return mixed.table_value(table,'y',6.)/mixed.table_value(table,'x',6.)
    raise ValueError('unknown target quantity')


def build_catalog():
    original=core.build_catalog()
    cases,diagnostics=[],[]
    for case in original['cases']:
        study=deepcopy(case['study'])
        public,private=study['public'],study['private']
        spec=SPECS[private['pair_index']]
        for claim in public['claims']:
            kind=claim['kind']
            if kind=='target_agreement':
                claim.clear()
                claim.update(kind='target_integral',scope='fixed_target',operator='ge',threshold=spec['area'])
            elif kind=='target_composition':
                claim.pop('reported_value'); claim.pop('relative_tolerance')
                claim.update(operator=spec['ratio_operator'],threshold=spec['ratio'])
            elif kind=='target_recovery':
                claim.update(kind='target_late_recovery',threshold=spec['late'])
            elif kind=='intervention_effect':
                claim.update(threshold=spec['effect'],operator=spec['effect_operator'])
        for i,c in enumerate(public['claims']):
            c['id']=f'C{i+1}'
            if c['kind'] in ('numerical_point','cumulative_abundance'):
                continue
            description={
                'target_integral':"the target's trapezoidal prey integral on 0,0.5,...,8",
                'target_composition':"the target's predator-to-prey ratio y(6)/x(6)",
                'target_late_recovery':"the target's late prey recovery x(8)/x(6)-1",
                'intervention_effect':"the specified model's fractional grid-peak reduction after the stated intervention",
            }[c['kind']]
            operator='at least' if c['operator']=='ge' else 'at most'
            c['text']=f"The {description} is {operator} {c['threshold']:g}."
        public['report']=('Predator-prey study; initial populations (10,5), interval [0,8]. '
            'The baseline Euler trajectory and low-fidelity intervention summary are retained. '
            'The intervention increases theta2 by 10% with other parameters unchanged. '
            'Two competing fits to the same early calibration are supplied, without a guarantee '
            'that they exhaust the model family. Audit the six assertions separately. '
            'Integrals and peaks refer to the stated half-unit grid, not continuous extrema.\n\n'
            +'\n\n'.join(c['id']+': '+c['text'] for c in public['claims']))
        public['followup_version']=VERSION
        truth={}
        refs=private['references']
        low_other=core._table(core.old._solve_low(public['candidate_fits'][
            0 if public['candidate_fits'][0]!=public['report_parameters'] else 1],core.old.harder_config(32)),core.old.harder_config(32))
        for c in public['claims']:
            q=(target_quantity(c['kind'],refs['target']) if c['scope']=='fixed_target' else
               mixed.quantity(c['kind'],refs['numerical'],refs['intervention']))
            truth[c['id']]={'reference_value':q,**classify(c,q)}
        private['truth']=truth
        intervention_claim=next(c for c in public['claims'] if c['kind']=='intervention_effect')
        low_summary=public['intervention_summary']
        matched_low_effect=1-low_summary['intervention_grid_peak']/low_summary['baseline_grid_peak']
        if classify(intervention_claim,matched_low_effect)['verdict']==truth[intervention_claim['id']]['verdict']:
            raise ValueError('intervention commissioning requires a consequential matched-coarse error')
        private['matched_coarse_intervention_effect']=matched_low_effect
        private['followup_version']=VERSION
        private['status']='existing designed development pair; thresholds selected from coarse/fine diagnostics; not held out'
        study['version']=VERSION
        ident=digest({'version':VERSION,'original_case':case['case_id']})[:12]
        cases.append({'case_id':ident,'study':study})
        diagnostics.append({'case_id':ident,'original_case':case['case_id'],'pair':private['pair_index'],
            'member':private['member'],'truth':truth,
            'low_other_quantities':{c['kind']:target_quantity(c['kind'],low_other)
                                    for c in public['claims'] if c['scope']=='fixed_target'}})
    # No policy-performance gate in construction: disappointing cases are kept.
    for i in range(0,len(cases),2):
        if cases[i]['study']['public']!=cases[i+1]['study']['public']:
            raise ValueError('paired public reports differ')
    return {'version':VERSION,'cases':cases,'diagnostics':diagnostics,'specs':deepcopy(SPECS),
            'original_construction_diagnostics':original['diagnostics']}


class Audit(core.Audit):
    def __init__(self,study,log=None,*,budget=32):
        if study['version']!=VERSION or budget!=32:
            raise ValueError('follow-up commissioning uses exactly 32 credits')
        compatible=deepcopy(study)
        compatible['version']=core.VERSION
        super().__init__(compatible,log,budget=budget)
        self._study['version']=VERSION


class Session(core.Session):
    def __init__(self,study,budget,log):
        self.log,self.calls,self.executed,self.artifact_count=log,0,{},0
        self.deadline=time.monotonic()+300
        self.environment=Audit(study,self._event,budget=budget)
