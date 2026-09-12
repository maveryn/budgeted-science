"""Two matched forecast-support claims in a declared finite parameter universe.

This is an evidence-sufficiency demonstration, not a confidence-interval test,
continuous identifiability certificate, agent benchmark or physical validation.
"""
import argparse
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path
import platform
from time import perf_counter

import numpy as np
import scipy
from scipy.integrate import solve_ivp

from ..agents.records import RunLog, digest, json_text, read_events
from ..fit_prediction_verification import numerics as n
from . import VERSION

ROOT=Path(__file__).resolve().parents[3]
RUNS=ROOT/"demos/claim_verification/runs"
AXES=((.6,.8,1.,1.2,1.4),(.04,.06,.08,.10,.12),(.8,1.1,1.4,1.7,2.))
GRID=[list(p) for p in itertools.product(*AXES)]
NOMINAL=GRID.index([1.,.08,1.4])
SPECS={"sparse":[(.5,0)],"rich":[(float(t),v) for t in n.CAL_TIMES for v in (0,1)]}
BUDGETS=(32,256)
POLICIES=("nominal_only","fixed_full","screened")


def source_hashes():
    files=[Path(__file__),Path(__file__).with_name("__init__.py"),Path(n.__file__),
           Path(n.rhs.__code__.co_filename),Path(__file__).parents[1]/"agents/records.py"]
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def solve(candidate,stage,spec,cap=10**8,independent=False):
    """Every candidate tool call meters actual RHS evaluations, including failures."""
    if type(candidate) is not int or not 0 <= candidate < len(GRID) or stage not in ("calibration","forecast"):
        raise ValueError("invalid candidate or stage")
    n.integer(cap,"cap")
    p=GRID[candidate]
    times=np.array(sorted({t for t,v in spec})) if stage=="calibration" else np.array([24.])
    initial=n.CAL_INITIAL if stage=="calibration" else n.PRED_INITIAL
    work,last=0,None
    def rhs(t,state):
        nonlocal work,last
        if work>=cap:
            raise n.WorkExhausted("RHS cap reached")
        work+=1
        last={"time":float(t),"state":[float(v) if np.isfinite(v) else None for v in state]}
        if independent:
            x,y=state
            result=np.array([x*(p[0]-p[1]*y-.01*x),y*(.9*p[1]*x-p[2])])
        else:
            result=n.rhs(t,state,p)
        if not np.isfinite(result).all():
            raise FloatingPointError("nonfinite derivative")
        return result
    start=perf_counter()
    status,reason,values="complete",None,None
    try:
        out=solve_ivp(rhs,(0.,float(times[-1])),initial,method="Radau" if independent else "DOP853",
                      rtol=1e-11 if independent else 1e-9,atol=1e-13 if independent else 1e-11,dense_output=True)
        if not out.success:
            raise FloatingPointError("incomplete solve")
        values=out.sol(times).T
        if not np.isfinite(values).all() or np.any(values<=0):
            raise FloatingPointError("invalid trajectory")
    except n.WorkExhausted as exc:
        status,reason="budget_exhausted",str(exc)
    except (FloatingPointError,OverflowError) as exc:
        status,reason="failed",str(exc)
    measurements=[float(values[list(times).index(t),v]) for t,v in spec] if status=="complete" and stage=="calibration" else None
    return {"candidate":candidate,"theta":list(p),"stage":stage,"status":status,"reason":reason,
        "times":times.tolist() if status=="complete" else [],"values":values.tolist() if status=="complete" else [],
        "measurements":measurements,"q":float(values[-1,0]) if status=="complete" and stage=="forecast" else None,
        "work":work,"seconds":perf_counter()-start,"last_rhs":last}


def consistent(measurements,public):
    return bool(np.all(np.abs(np.asarray(measurements)-public["data"]) <= np.asarray(public["error_bounds"])))


def inside(q,interval):
    return interval[0] <= q <= interval[1]


def commission(log=None):
    bank={}
    for cid in range(len(GRID)):
        rich=solve(cid,"calibration",SPECS["rich"],independent=True)
        forecast=solve(cid,"forecast",SPECS["rich"],independent=True)
        if rich["status"]!="complete" or forecast["status"]!="complete":
            raise ValueError("reference commissioning failed")
        bank[cid]={"rich":rich["measurements"],"sparse":[rich["measurements"][0]],"q":forecast["q"]}
        if log:
            log.write_json(f"reference/{cid}.json",{"calibration":rich,"forecast":forecast})
    nominal_q=bank[NOMINAL]["q"]
    interval=[.97*nominal_q,1.03*nominal_q]
    cases=[]
    for label,spec in SPECS.items():
        public={"candidates":GRID,"nominal_candidate":NOMINAL,"spec":[list(s) for s in spec],
                "data":bank[NOMINAL][label],"error_bounds":[.1 if v==0 else .05 for t,v in spec],
                "claim_interval":interval,"calibration_initial":list(n.CAL_INITIAL),"forecast_initial":list(n.PRED_INITIAL),
                "forecast_time":24.,"equations":["x'=theta1*x-theta2*x*y-0.01*x*x","y'=0.9*theta2*x*y-theta3*y"],
                "claim":"Every listed candidate consistent with all supplied bounded-error observations forecasts inside the stated interval.",
                "scope":"Exactly the 125 listed candidates. Exhaustive acceptance does not certify continuous parameter bounds.",
                "cost":"One credit is 256 actual RHS evaluations. Numerical tools integrate only to the requested experiment horizon. Reuse and analysis are free."}
        feasible=[cid for cid in bank if consistent(bank[cid][label],public)]
        outside=[cid for cid in feasible if not inside(bank[cid]["q"],interval)]
        if not feasible:
            raise ValueError("empty consistency set")
        original={stage:solve(NOMINAL,stage,spec) for stage in ("calibration","forecast")}
        differences=[]
        for cid in bank:
            c=solve(cid,"calibration",spec)
            f=solve(cid,"forecast",spec)
            if c["status"]!="complete" or f["status"]!="complete":
                raise ValueError("candidate numerical commissioning failed")
            delta=max(float(np.max(np.abs(np.asarray(c["measurements"])-bank[cid][label]))),abs(f["q"]-bank[cid]["q"]))
            differences.append(delta)
            # Require stable classifications away from numerical boundaries.
            ratio=max(abs(a-b)/eps for a,b,eps in zip(bank[cid][label],public["data"],public["error_bounds"]))
            if delta>1e-5 or abs(ratio-1)<1e-4 or min(abs(bank[cid]["q"]-edge) for edge in interval)<1e-4:
                raise ValueError("reference disagreement or near-boundary case; no silent relabeling")
            if consistent(c["measurements"],public)!=(cid in feasible) or inside(f["q"],interval)!=inside(bank[cid]["q"],interval):
                raise ValueError("tool/reference classification mismatch")
        cases.append({"id":"study-"+digest([VERSION,label])[:12],"public":public,"original":original,
            "private":{"regime":label,"bank":{str(cid):value for cid,value in bank.items()},"feasible":feasible,"outside":outside,"valid":not outside,
                "forecast_range":[min(bank[c]["q"] for c in feasible),max(bank[c]["q"] for c in feasible)],
                "max_solver_disagreement":max(differences),"development":True}})
    if cases[0]["private"]["valid"] or not cases[1]["private"]["valid"]:
        raise ValueError("sparse/rich ambiguity check failed; no automatic configuration changes")
    return cases


class Audit:
    """Trusted-process tool boundary, not a sandbox. No reference access in responses."""
    def __init__(self,case,credits,log=None):
        n.integer(credits,"credits")
        self.case=deepcopy(case)
        self.limit,self.spent=credits*n.WORK_UNIT,0
        self.log,self.submission=log,None
        self.runs={f"original-{s}":deepcopy(r) for s,r in case["original"].items()}
        self.cache={(NOMINAL,s):f"original-{s}" for s in ("calibration","forecast")}
        self.partial,self.calls={},{}
        self.closed=False

    def budget(self):
        return {"work_limit":self.limit,"work_spent":self.spent,"remaining":self.limit-self.spent,"credits_spent":self.spent/n.WORK_UNIT}

    def call(self,name,args=None,call_id=None):
        args={} if args is None else deepcopy(args)
        signature=digest([name,args])
        if call_id in self.calls:
            prior,result=self.calls[call_id]
            if prior!=signature: raise ValueError("call ID conflict")
            return deepcopy(result)
        if self.closed: raise ValueError("episode closed")
        if self.log: self.log.event("tool_request",name=name,arguments=args,call_id=call_id)
        try:
            result=self.execute(name,args)
        except (ValueError,KeyError,TypeError) as exc:
            result={"error":str(exc)}
        result["budget"]=self.budget()
        if self.log: self.log.event("tool_result",name=name,result=result,call_id=call_id)
        if call_id is not None: self.calls[call_id]=(signature,deepcopy(result))
        return result

    def execute(self,name,args):
        if not isinstance(args,dict): raise ValueError("arguments must be an object")
        if name=="describe" and not args:
            return {"study":deepcopy(self.case["public"]),"original":deepcopy(self.case["original"])}
        if name=="record" and set(args)=={"id"}:
            return {"id":args["id"],"record":deepcopy(self.runs[args["id"]])}
        if name=="check" and set(args)=={"candidate","stage"}:
            cid,stage=args["candidate"],args["stage"]
            if type(cid) is not int or not 0<=cid<len(GRID) or stage not in ("calibration","forecast"):
                raise ValueError("invalid candidate or stage")
            key=(cid,stage)
            cap=self.limit-self.spent
            previous=self.cache.get(key) or self.partial.get((key,cap))
            if previous: return {"id":previous,"run":deepcopy(self.runs[previous]),"charged_work":0,"reuse":True}
            if not cap: return {"status":"budget_exhausted"}
            if self.log: self.log.event("solver_started",candidate=cid,stage=stage,cap=cap)
            try:
                run=solve(cid,stage,self.case["public"]["spec"],cap)
                if type(run["work"]) is not int or not 0<=run["work"]<=cap: raise RuntimeError("invalid work accounting")
            except Exception:
                self.spent+=cap
                self.closed=True
                if self.log: self.log.event("unaccounted_failure",retained_work=cap)
                raise
            self.spent+=run["work"]
            rid="run-"+digest([cid,stage,run["work"],run["status"]])[:14]
            self.runs[rid]=run
            if run["status"]=="budget_exhausted": self.partial[key,cap]=rid
            else: self.cache[key]=rid
            if self.log:
                self.log.write_json("numerical/"+rid+".json",run)
                self.log.event("solver_finished",id=rid,charged_work=run["work"],status=run["status"])
            return {"id":rid,"run":deepcopy(run),"charged_work":run["work"],"reuse":False}
        if name=="submit" and set(args)=={"verdict","witness"}:
            if args["verdict"] not in ("ACCEPT","REJECT","ABSTAIN"): raise ValueError("invalid verdict")
            witness=args["witness"]
            if witness is not None and (type(witness) is not int or not 0<=witness<len(GRID)): raise ValueError("invalid witness")
            self.submission=deepcopy(args)
            self.closed=True
            return {"status":"submitted"}
        raise ValueError("invalid action/arguments")

    def completed(self,cid,stage):
        rid=self.cache.get((cid,stage))
        return self.runs[rid] if rid and self.runs[rid]["status"]=="complete" else None

    def evaluate(self):
        s=self.submission or {"verdict":None,"witness":None}
        public,private=self.case["public"],self.case["private"]
        correct=s["verdict"]==("ACCEPT" if private["valid"] else "REJECT")
        def checked(cid,stage):
            run=self.completed(cid,stage)
            if run is None: return None
            ref=private["bank"].get(cid,private["bank"].get(str(cid)))
            if stage=="calibration":
                error=float(np.max(np.abs(np.asarray(run["measurements"])-ref[private["regime"]])))
            else: error=abs(run["q"]-ref["q"])
            return run if np.isfinite(error) and error<=1e-5 else None
        witness_valid=False
        if s["verdict"]=="REJECT" and s["witness"] is not None:
            cid=s["witness"]
            c,f=checked(cid,"calibration"),checked(cid,"forecast")
            witness_valid=bool(c and f and cid in private["outside"] and consistent(c["measurements"],public) and not inside(f["q"],public["claim_interval"]))
        covered=[]
        for cid in range(len(GRID)):
            c=checked(cid,"calibration")
            if c is None: continue
            if not consistent(c["measurements"],public):
                if cid not in private["feasible"]: covered.append(cid)
            else:
                f=checked(cid,"forecast")
                if f and inside(f["q"],public["claim_interval"]) and inside(private["bank"][str(cid)]["q"],public["claim_interval"]): covered.append(cid)
        acceptance_covered=s["verdict"]=="ACCEPT" and len(covered)==len(GRID) and private["valid"]
        return {"verdict":s["verdict"],"correct":correct,"valid_claim":private["valid"],
            "witness_valid":witness_valid,"acceptance_covered":acceptance_covered,
            "evidence_backed_correct":correct and (witness_valid or acceptance_covered),
            "covered_candidates":len(covered),"incomplete":self.submission is None,
            "abstained":s["verdict"]=="ABSTAIN",**self.budget()}


def policy(call,name):
    if name not in POLICIES: raise ValueError("unknown policy")
    state=call("describe")
    public=state["study"]
    interval=public["claim_interval"]
    nominal=public["nominal_candidate"]
    if name=="nominal_only":
        return call("submit",{"verdict":"ACCEPT" if inside(state["original"]["forecast"]["q"],interval) else "REJECT","witness":nominal})
    order=np.random.default_rng(0).permutation(len(public["candidates"])).tolist()
    for cid in order:
        if cid==nominal: continue
        c=call("check",{"candidate":cid,"stage":"calibration"})
        if c.get("run",{}).get("status")!="complete": break
        feasible=consistent(c["run"]["measurements"],public)
        if name=="fixed_full" or feasible:
            f=call("check",{"candidate":cid,"stage":"forecast"})
            if f.get("run",{}).get("status")!="complete": break
            if feasible and not inside(f["run"]["q"],interval):
                return call("submit",{"verdict":"REJECT","witness":cid})
    else:
        return call("submit",{"verdict":"ACCEPT","witness":None})
    return call("submit",{"verdict":"ABSTAIN","witness":None})


def render(path):
    path=Path(path)
    manifest=json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    rows=[json.loads(p.read_text(encoding="utf-8")) for p in sorted((path/"episodes").glob("*/result.json"))]
    slots=[(r["case_id"],r["budget"],r["policy"]) for r in rows]
    allowed={(c,b,p) for c in manifest["cases"] for b in manifest["budgets"] for p in manifest["policies"]}
    if len(slots)!=len(set(slots)) or not set(slots)<=allowed: raise ValueError("duplicate or unexpected slot")
    result={"cases":len(manifest["cases"]),"episodes":len(rows),"missing":len(allowed-set(slots)),"api_usd":0,"rows":rows}
    lines=["# Finite-universe forecast-ambiguity CPU demonstration","",
        "Two related claims, one system, 125 public candidates. Acceptance is only within that finite universe. No confidence-coverage or continuous identifiability claim.","",
        "| Observations | Budget | Policy | Verdict | Correct | Evidence backed | Credits |",
        "|---|---:|---|---|---|---|---:|"]
    for r in rows:
        ev=r["evaluation"]
        lines.append(f"| {r['regime']} | {r['budget']} | {r['policy']} | {ev['verdict']} | {ev['correct']} | {ev['evidence_backed_correct']} | {ev['credits_spent']:.3f} |")
        ep=path/r["path"]
        events,torn=read_events(ep)
        text=["# Scripted CPU audit trace","",f"Policy: {r['policy']}. No model calls.",""]
        for v in events:
            if v["kind"] in ("tool_request","tool_result"):
                text.extend(["```json",json_text(v),"```",""])
        if torn: text.append("Interrupted final log line; earlier complete events retained.")
        (ep/"transcript.md").write_text("\n".join(text)+"\n",encoding="utf-8")
    (path/"report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    (path/"summary.json").write_text(json_text(result)+"\n",encoding="utf-8")
    return result


def run(output_root=RUNS):
    log=RunLog(output_root,"forecast-ambiguity-cpu")
    print(log.path,flush=True)
    try:
        frozen=source_hashes()
        cases=commission(log)
        log.write_json("catalog.json",cases)
        log.write_json("manifest.json",{"version":VERSION,"sources":frozen,"cases":[c["id"] for c in cases],
            "catalog_hash":digest(cases),"budgets":BUDGETS,"policies":POLICIES,"order_seed":0,"universe_size":len(GRID),
            "software":{"python":platform.python_version(),"numpy":np.__version__,"scipy":scipy.__version__},"frozen_before_policy_results":True})
        for c in cases:
            print(c["private"]["regime"],"compatible",len(c["private"]["feasible"]),"forecast range",c["private"]["forecast_range"],flush=True)
            for b in BUDGETS:
                for p in POLICIES:
                    if source_hashes()!=frozen: raise RuntimeError("source changed after freeze")
                    child=RunLog(log.path/"episodes",p)
                    start=perf_counter()
                    audit=Audit(c,b,child)
                    child.write_json("public.json",{"study":c["public"],"original":c["original"]})
                    failure=None
                    try: policy(audit.call,p)
                    except Exception as exc:
                        failure=f"{type(exc).__name__}: {exc}"
                        child.event("failure",error=failure)
                    row={"case_id":c["id"],"regime":c["private"]["regime"],"budget":b,"policy":p,
                         "evaluation":audit.evaluate(),"submission":audit.submission,"failure":failure,
                         "seconds":perf_counter()-start,"path":child.path.relative_to(log.path).as_posix()}
                    child.write_json("result.json",row)
                    child.close()
                    log.event("episode_finished",result=row)
        render(log.path)
    finally: log.close()
    print((log.path/"report.md").read_text(encoding="utf-8"),flush=True)
    return log.path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("cpu","render"))
    parser.add_argument("--path",type=Path)
    parser.add_argument("--output-root",type=Path,default=RUNS)
    args=parser.parse_args()
    if args.action=="cpu": run(args.output_root)
    elif args.path is None: parser.error("render requires --path")
    else: print(json_text(render(args.path)))


if __name__=="__main__": main()
