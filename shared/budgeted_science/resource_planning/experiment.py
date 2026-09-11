"""Offline, supervised CPU experiments with a development-to-pilot freeze gate.

Run ``python -m budgeted_science.resource_planning.experiment --phase debug``.
After a complete development run, explicitly freeze its exact code with
``experiment freeze DEVELOPMENT_RUN --output FREEZE.json``. A pilot requires
``--freeze FREEZE.json`` and verifies it before sampling any evaluation target.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
import hashlib
import importlib
import importlib.metadata
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import sys
import time
import traceback

from budgeted_science.agents.records import RunLog, digest, json_text, read_events, utc_now


POLICIES = ("random", "adaptive")
HARD_EPISODE_SECONDS = 300.0
THREAD_LIMITS = {key: "1" for key in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS")}
REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = REPO / "demos/planning/runs/resource_planning"
REQUIRED_MODULES = ("config.py", "environment.py", "policies.py", "emulator.py",
                    "experiment.py", "validate.py", "reporting.py")


def versions():
    return {"python": platform.python_version(),
            **{name: importlib.metadata.version(name) for name in ("numpy", "scipy")}}


def source_hashes(repo=REPO):
    """Hash package code, tests and build configuration; never read credentials."""
    repo = Path(repo).resolve()
    paths = list((repo / "shared/budgeted_science").rglob("*.py"))
    paths += list((repo / "tests").rglob("*.py"))
    paths += list((repo / "demos/planning/tests").rglob("*.py"))
    for name in ("pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini"):
        if (repo / name).is_file():
            paths.append(repo / name)
    return {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths)) if "__pycache__" not in p.parts}


def _config():
    from .config import Config
    return Config()


def configuration(config):
    from .emulator import GPSettings
    if not is_dataclass(config):
        raise TypeError("Config must be a dataclass")
    # JSON normalization makes tuples in dataclass fields comparable to the
    # saved list representation without changing the actual Config instance.
    return json.loads(json_text({"environment": {f.name: _plain(getattr(config, f.name)) for f in fields(config)}, "public": config.public(),
                                 "emulator": GPSettings().to_dict(),
                                 "hard_episode_seconds": HARD_EPISODE_SECONDS,
                                 "worker_thread_limits": THREAD_LIMITS}))


def _check_implementation(repo=REPO):
    directory = Path(repo) / "shared/budgeted_science/resource_planning"
    absent = [name for name in REQUIRED_MODULES if not (directory / name).is_file()]
    if absent:
        raise ValueError("cannot freeze an incomplete implementation: " + ", ".join(absent))
    from .environment import Episode
    from .policies import run_policy
    if not callable(run_policy) or not callable(getattr(Episode, "evaluate", None)):
        raise ValueError("environment/policy implementation is incomplete")


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def freeze_development(development_run, output, *, config=None, repo=REPO):
    """Freeze only code/configuration actually used by a complete development run."""
    from .reporting import load_attempts
    _check_implementation(repo)
    config = config if config is not None else _config()
    run = Path(development_run).resolve()
    manifest, rows, recovery = load_attempts(run)
    if manifest["phase"] != "development" or not recovery["experiment_finished"] or recovery["torn_final_event"]:
        raise ValueError("freeze requires a complete development run")
    expected = {(f"development-{s}", p, 0) for s in range(1000, 1008) for p in POLICIES}
    actual = {(r["target_id"], r["policy"], r["policy_seed"]) for r in rows}
    if len(rows) != 16 or actual != expected or any(r["status"] != "completed" for r in rows):
        raise ValueError("freeze requires all 16 development attempts to finish without execution failures")
    hashes = source_hashes(repo)
    settings = configuration(config)
    if manifest["source_hashes"] != hashes or manifest["configuration"] != settings:
        raise ValueError("code/config changed since development; rerun development before freezing")
    if manifest["versions"] != versions():
        raise ValueError("numerical runtime changed since development")
    completion = _json(run / "completion.json")
    if not completion.get("source_unchanged") or not completion.get("complete"):
        raise ValueError("development was incomplete or code changed during execution")
    payload = {"schema_version": 1, "created_utc": utc_now(), "phase": "development-freeze",
               "development_run": str(run), "development_manifest_sha256": hashlib.sha256((run / "manifest.json").read_bytes()).hexdigest(),
               "configuration": settings, "source_hashes": hashes, "versions": versions(),
               "development_attempts": len(rows),
               "evaluation_design": {"target_seeds": list(range(2000, 2020)), "policy_seeds": [0, 1, 2],
                                     "policies": list(POLICIES), "attempts": 120}}
    payload["digest"] = digest(payload)
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json_text(payload) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return payload


def verify_freeze(path, *, config=None, repo=REPO):
    """Called before target generation, including before any pilot manifest."""
    _check_implementation(repo)
    freeze = _json(path)
    payload = {k: v for k, v in freeze.items() if k != "digest"}
    if freeze.get("digest") != digest(payload) or freeze.get("phase") != "development-freeze":
        raise ValueError("invalid freeze digest or phase")
    if freeze.get("source_hashes") != source_hashes(repo):
        raise ValueError("source/test/config hashes differ from the development freeze")
    if freeze.get("configuration") != configuration(config if config is not None else _config()):
        raise ValueError("configuration differs from the development freeze")
    if freeze.get("versions") != versions():
        raise ValueError("Python/NumPy/SciPy versions differ from the development freeze")
    expected = {"target_seeds": list(range(2000, 2020)), "policy_seeds": [0, 1, 2],
                "policies": list(POLICIES), "attempts": 120}
    if freeze.get("evaluation_design") != expected or freeze.get("development_attempts") != 16:
        raise ValueError("freeze does not match the preregistered development/pilot design")
    return freeze


def target_set(phase, config):
    """Private harness sampling. Policy code receives none of these values/seeds."""
    import numpy as np
    if phase == "debug":
        return [{"target_id": "debug-fixed", "target_seed": None, "theta": [1.0, .08, 1.4]}]
    if phase not in ("development", "pilot"):
        raise ValueError("unknown experiment phase")
    bounds = np.asarray(config.public()["bounds"], dtype=float)
    if bounds.shape != (3, 2) or not np.all(np.isfinite(bounds)) or np.any(bounds[:, 0] >= bounds[:, 1]):
        raise ValueError("public bounds must be three finite [lower, upper] pairs")
    seeds = range(1000, 1008) if phase == "development" else range(2000, 2020)
    return [{"target_id": f"{phase}-{seed}", "target_seed": seed,
             "theta": np.random.default_rng(seed).uniform(bounds[:, 0], bounds[:, 1]).tolist()} for seed in seeds]


def _plain(value):
    """Preserve numerical diagnostics, explicitly representing nonfinite values."""
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "tolist"):
        return _plain(value.tolist())
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite": repr(value)}
    return value


def _identity(spec):
    return {key: spec[key] for key in ("attempt_id", "target_id", "target_seed", "policy", "policy_seed")}


def _resources(status):
    """Retain the full ledger separately; expose numeric resource summaries."""
    if not isinstance(status, dict):
        return {}
    result = {}
    for key, value in status.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            result[key] = value
    # The full status remains in the canonical result even if an environment
    # adds a new nested diagnostic that has no aggregate interpretation yet.
    if "spent" in result:
        result["credits_spent"] = result["spent"]
    elif "budget_spent" in result:
        result["credits_spent"] = result["budget_spent"]
    for key in ("counts", "action_counts", "spent_by_type"):
        for name, value in status.get(key, {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                result[f"{key}_{name}"] = value
    ledger = status.get("ledger")
    if isinstance(ledger, list):
        for kind in ("simulate_low", "simulate_high", "measure_target"):
            entries = [entry for entry in ledger if entry.get("kind") == kind]
            result[f"{kind}_count"] = len(entries)
            result[f"{kind}_credits"] = sum(entry["charge"] for entry in entries)
    return result


def _evaluation_fields(evaluation, status):
    # Strictly consume private evaluator output. The runner never supplies an
    # estimate and never calls tools.submit on a policy's behalf.
    from .reporting import finite
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    errors = evaluation.get("errors")
    valid = (status == "completed" and evaluation.get("status") == "submitted" and evaluation.get("valid") is True
             and isinstance(errors, list) and len(errors) == 3 and all(finite(e) and e >= 0 for e in errors)
             and finite(evaluation.get("parameter_error")) and evaluation["parameter_error"] == max(errors)
             and evaluation.get("score") in (0, 1))
    success = bool(valid and evaluation.get("success") is True)
    return {"valid": bool(valid), "success": success,
            "score": int(success),
            "objective_successes": evaluation.get("successes") if valid else [False] * 3,
            "parameter_errors": errors if valid else [None] * 3,
            "parameter_error": evaluation["parameter_error"] if valid else None}


def _episode_worker(spec, config_values, root, deadline):
    """Spawn entry point: no numerical imports until single-thread limits are set."""
    os.environ.update(THREAD_LIMITS)
    log = RunLog(root, spec["policy"])
    started = time.monotonic()
    episode, evaluation, diagnostics, public_status = None, None, None, None
    status, error = "worker_error", None
    def callback(kind, **data):
        for key in ("artifact", "target_artifact"):
            if data.get(key) is not None:
                data[key + "_path"] = log.write_json(f"numerical/{log._sequence + 1:06d}-{key}.json", _plain(data[key]))
        event = log.event(kind, **_plain(data))
        if episode is not None and kind in {"simulation", "measurement", "rejected", "submitted", "aborted", "charge", "charged"}:
            log.event("public_status", public_status=_plain(episode.tools.get_status()))
        return event
    try:
        log.write_json("manifest.json", {**_identity(spec), "PRIVATE_harness_only": {"theta": spec["theta"]},
                                        "deadline_monotonic": deadline, "thread_limits": THREAD_LIMITS})
        callback("worker_started")
        from .environment import Episode
        from .config import Config
        from .policies import run_policy
        if time.monotonic() >= deadline:
            raise TimeoutError("hard episode deadline reached before initialization")
        episode = Episode(spec["theta"], config=Config(**config_values), log=callback)
        callback("episode_initialized")
        diagnostics = run_policy(episode.tools, policy=spec["policy"], seed=spec["policy_seed"],
                                 log=callback, deadline=deadline)
        if not isinstance(diagnostics, dict):
            raise TypeError("run_policy must return diagnostics dict")
        if time.monotonic() >= deadline:
            raise TimeoutError("hard episode deadline reached after policy return")
        evaluation = episode.evaluate()
        if time.monotonic() >= deadline:
            raise TimeoutError("hard episode deadline reached during evaluation")
        status = "completed"
    except TimeoutError as exc:
        status, error = "timeout", log.redactor.error(exc)
        callback("episode_timeout", error=error)
    except Exception as exc:
        status, error = "policy_error" if episode is not None else "initialization_error", log.redactor.error(exc)
        callback("episode_error", error=error, traceback=traceback.format_exc())
    finally:
        try:
            if episode is not None:
                if status != "completed" and callable(getattr(episode, "abort", None)):
                    try:
                        episode.abort(status)
                    except Exception as exc:
                        callback("abort_error", error=log.redactor.error(exc))
                try:
                    public_status = episode.tools.get_status()
                except Exception as exc:
                    callback("status_error", error=log.redactor.error(exc))
            result = {**_identity(spec), "status": status, "started": True,
                      **_evaluation_fields(evaluation, status), "evaluation": _plain(evaluation),
                      "diagnostics": _plain(diagnostics), "public_status": _plain(public_status),
                      "resources": _resources(public_status), "error": error,
                      "elapsed_seconds": time.monotonic() - started}
            log.write_json("result.json", result)
            callback("episode_finished", result=result)
        finally:
            log.close()


def _partial_status(trace):
    """Recover only explicitly saved public ledger data from an interrupted child."""
    if trace is None or not (trace / "events.jsonl").exists():
        return None, False
    events, torn = read_events(trace)
    for event in reversed(events):
        for key in ("public_status", "budget_after", "status_after", "ledger"):
            if isinstance(event.get(key), dict):
                return event[key], torn
    initial = next((e for e in events if e["kind"] == "episode_started"), None)
    budget = initial.get("config", {}).get("budget") if initial else None
    if budget is not None:
        result = {"remaining": budget, "spent": 0.0, "ledger": [], "recovered_from_events": True}
        for event in events:
            saved = event.get("result")
            if isinstance(saved, dict) and isinstance(saved.get("remaining"), (int, float)):
                result.update(remaining=saved["remaining"], spent=budget - saved["remaining"])
                if saved.get("charge", 0) > 0:
                    kind = "simulate_" + saved["fidelity"] if event["kind"] == "simulation" else "measure_target"
                    result["ledger"].append({"kind": kind, "charge": saved["charge"], "status": saved.get("status")})
        return result, torn
    return None, torn


def supervise(spec, config, root, *, timeout_seconds=HARD_EPISODE_SECONDS, worker=_episode_worker):
    """Enforce the elapsed-time cap outside the trusted numerical worker.

    The supervisor retains a truthful failure and partial chronology even when
    native numerical code does not cooperate with the policy deadline.
    """
    if not 0 < timeout_seconds <= HARD_EPISODE_SECONDS:
        raise ValueError("episode timeout must be positive and at most 300 seconds")
    os.environ.update(THREAD_LIMITS)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = start + timeout_seconds
    config_values = {f.name: _plain(getattr(config, f.name)) for f in fields(config)} if is_dataclass(config) else config
    process = multiprocessing.get_context("spawn").Process(target=worker, args=(spec, config_values, str(root), deadline))
    failure, error, interrupted = None, None, False
    try:
        process.start()
        while process.is_alive():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "timeout"
                break
            process.join(min(.1, remaining))
    except KeyboardInterrupt:
        failure, interrupted = "interrupted", True
    except Exception as exc:
        failure, error = "worker_start_error", {"class": type(exc).__name__, "message": str(exc)}
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
                process.join(2)
                if process.is_alive():
                    process.kill()
                    process.join(2)
            else:
                process.join()
    elapsed = time.monotonic() - start
    traces = sorted(p for p in root.iterdir() if p.is_dir() and (p / "events.jsonl").exists())
    trace = traces[0] if len(traces) == 1 else None
    result = None
    if trace is not None and (trace / "result.json").exists():
        try:
            result = _json(trace / "result.json")
        except (ValueError, OSError) as exc:
            error = {"class": type(exc).__name__, "message": str(exc)}
            failure = failure or "corrupt_worker_result"
    if failure is None and (process.exitcode != 0 or result is None):
        failure = "worker_crash" if process.exitcode else "missing_result"
    if failure is not None:
        public_status, torn = _partial_status(trace)
        result = {**_identity(spec), "status": failure, "started": process.pid is not None,
                  "valid": False, "success": False, "score": 0.0, "parameter_error": None,
                  "parameter_errors": [None] * 3, "objective_successes": [False] * 3,
                  "evaluation": None, "diagnostics": None, "error": error,
                  "public_status": public_status, "resources": _resources(public_status),
                  "torn_worker_event": torn,
                  "partial_worker_result_path": str((trace / "result.json").relative_to(root)) if trace and (trace / "result.json").exists() else None}
    if any(result.get(key) != value for key, value in _identity(spec).items()):
        raise ValueError("worker result identity mismatch")
    result.update(elapsed_seconds=elapsed, worker_exitcode=process.exitcode,
                  trace_path=trace.relative_to(root).as_posix() if trace else None,
                  timeout_seconds=timeout_seconds, interrupted=interrupted)
    if process.pid is not None:
        process.close()
    return result


def run_experiment(phase, output_root=DEFAULT_OUTPUT_ROOT, *, freeze=None, config=None):
    os.environ.update(THREAD_LIMITS)
    config = config if config is not None else _config()
    if phase not in ("debug", "development", "pilot"):
        raise ValueError("phase must be debug, development or pilot")
    frozen = None
    if phase == "pilot":
        if freeze is None:
            raise ValueError("pilot requires --freeze from a complete development run")
        frozen = verify_freeze(freeze, config=config)  # Must precede target_set.
    elif freeze is not None:
        raise ValueError("--freeze is an input gate for pilot only; use the freeze subcommand after development")
    hashes = source_hashes()
    targets = target_set(phase, config)
    policy_seeds = [0, 1, 2] if phase == "pilot" else [0]
    specs = []
    for target in targets:
        for seed in policy_seeds:
            for policy in POLICIES:
                attempt_id = f"{target['target_id']}-s{seed}-{policy}"
                specs.append({**target, "attempt_id": attempt_id, "policy_seed": seed, "policy": policy,
                              "result_path": f"attempts/{attempt_id}/result.json"})
    log = RunLog(output_root, phase)
    completed = []
    try:
        manifest = {"schema_version": 1, "phase": phase, "created_utc": utc_now(),
                    "configuration": configuration(config), "source_hashes": hashes, "versions": versions(),
                    "freeze_digest": frozen["digest"] if frozen else None,
                    "policy_seeds": policy_seeds, "policies": list(POLICIES),
                    "target_sampling": "independent NumPy default_rng(seed), uniform in the linear parameter box",
                    "attempts": [{k: v for k, v in spec.items() if k != "theta"} for spec in specs],
                    "PRIVATE_harness_only": {"targets": targets}}
        log.write_json("manifest.json", manifest)
        if frozen:
            log.write_json("freeze.json", frozen)
        log.event("experiment_started", phase=phase, attempts=len(specs))
        for spec in specs:
            log.event("attempt_started", **_identity(spec))
            try:
                result = supervise(spec, config, log.path / "attempts" / spec["attempt_id"])
            except Exception as exc:
                result = {**_identity(spec), "status": "supervisor_error", "started": True,
                          "valid": False, "success": False, "score": 0.0, "parameter_error": None,
                          "resources": {}, "elapsed_seconds": None, "error": log.redactor.error(exc)}
                log.event("supervisor_error", attempt_id=spec["attempt_id"], traceback=traceback.format_exc())
            log.write_json(spec["result_path"], result)
            log.event("attempt_finished", result=result)
            completed.append(result)
            print(f"{len(completed)}/{len(specs)} {spec['attempt_id']}: {result['status']} "
                  f"score={result.get('score', 0)} seconds={result['elapsed_seconds']}", flush=True)
            if result.get("interrupted"):
                break
        completion = {"complete": len(completed) == len(specs), "attempts": len(completed),
                      "expected_attempts": len(specs), "source_unchanged": source_hashes() == hashes,
                      "execution_failures": sum(r["status"] != "completed" for r in completed)}
        log.write_json("completion.json", completion)
        if completion["complete"]:
            log.event("experiment_finished", **completion)
        else:
            log.event("experiment_interrupted", **completion)
    finally:
        log.close()
    from .reporting import regenerate
    regenerate(log.path)
    return log.path


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "report":
        from .reporting import main as report_main
        return report_main(argv[1:])
    if argv and argv[0] == "validate":
        from .validate import main as validate_main
        return validate_main(argv[1:])
    if argv and argv[0] == "freeze":
        parser = argparse.ArgumentParser(description="Freeze code actually exercised by a complete development run")
        parser.add_argument("development_run", type=Path)
        parser.add_argument("--output", required=True, type=Path)
        args = parser.parse_args(argv[1:])
        os.environ.update(THREAD_LIMITS)
        result = freeze_development(args.development_run, args.output)
        print(json_text({"freeze": str(args.output.resolve()), "digest": result["digest"]}))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("debug", "development", "pilot"), required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args(argv)
    path = run_experiment(args.phase, args.output_root, freeze=args.freeze)
    completion = _json(path / "completion.json")
    print(json_text({"run": str(path), **completion}))
    return 0 if completion["complete"] and completion["source_unchanged"] and not completion["execution_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
