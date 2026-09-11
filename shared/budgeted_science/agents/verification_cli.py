"""One explicit live/dry-run verification episode, or offline inspect/render."""
import argparse
import asyncio
import json
from pathlib import Path

from ..claim_verification.runner import load_study
from .runner import run_episode
from .verification import VerificationAdapter, VerificationConfig, VerificationInstance
from .verification_reporting import regenerate
from .verification_resume import prepare_resume

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "demos/claim_verification/data/20260911T222704Z-catalog-791b1692dd"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--render", type=Path)
    mode.add_argument("--inspect", action="store_true", help="Freeze/print public prompt and tools; no API calls")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--case")
    parser.add_argument("--model", choices=["gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6-luna"])
    parser.add_argument("--output-root", type=Path, default=ROOT / "demos/claim_verification/runs")
    args = parser.parse_args()
    if args.render:
        if args.resume or args.case or args.catalog or args.model:
            parser.error("render does not accept run overrides")
        for path in regenerate(args.render):
            print(path)
        return
    execution = "live" if args.live else "dry-run"
    resume = None
    if args.resume:
        if args.case or args.catalog or args.model or args.inspect:
            parser.error("resume restores its case/model; no overrides")
        resume = prepare_resume(args.resume, mode=execution)
        config, instance = resume["config"], resume["instance"]
    else:
        catalog = (args.catalog or CATALOG).resolve()
        config = VerificationConfig(model=args.model or "gpt-5.6-terra")
        study = load_study(catalog, args.case)
        integrity = json.loads((catalog / "catalog_integrity.json").read_text(encoding="utf-8"))
        selection = "explicit catalog case" if args.case else "first case in existing development-catalog order"
        instance = VerificationInstance(study, str(catalog), integrity["catalog_digest"], selection)
    if args.inspect:
        from .records import RunLog
        log = RunLog(args.output_root, "verification-inspection")
        try:
            episode = VerificationAdapter.create_episode(config, instance, log)
            messages = VerificationAdapter.prompts(config, episode)
            tools = VerificationAdapter.tool_definitions(config)
            log.write_json("prompts.json", messages)
            log.write_json("tools.json", tools)
            print(json.dumps({"configuration": config.public(), "prompts": messages, "tools": tools}, indent=2))
            print(log.path)
        finally:
            log.close()
        return
    path, reason = asyncio.run(run_episode(
        ROOT, args.output_root, mode=execution, config=config, instance=instance,
        adapter=VerificationAdapter(), resume=resume))
    print(path)
    print("Termination:", reason)
    evaluation = json.loads((path / "evaluation.json").read_text(encoding="utf-8"))
    print(json.dumps({"evaluation": evaluation["evaluation"],
                      "api_budget": evaluation["api_budget"],
                      "model_responses": evaluation["model_responses"]}, indent=2))


if __name__ == "__main__":
    main()
