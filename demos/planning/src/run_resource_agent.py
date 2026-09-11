"""One explicit GPT-5.6 Sol resource-planning run or an offline harness check."""

import argparse
import asyncio
from pathlib import Path

from budgeted_science.agents.resource import ResourceAdapter, ResourceInstance, ResourceRunConfig
from budgeted_science.agents.runner import run_episode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--dry-run", action="store_true", help="Scripted offline test; no credentials or API calls")
    choice.add_argument("--live", action="store_true", help="One paid attempt; $2 default total ceiling, explicitly authorized overrides up to $3")
    choice.add_argument("--render", type=Path, metavar="RUN_DIR", help="Regenerate local transcript/report without execution")
    parser.add_argument("--api-key-file", type=Path, help="Live only; default openaiapi.txt in repository")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--resume", type=Path, metavar="RUN_DIR", help="Explicitly continue an interrupted run; preserves cumulative limits")
    parser.add_argument("--require-full-budget", action="store_true", help="Require the entire scientific budget before submission; disclosed to the agent")
    parser.add_argument("--scientific-budget", type=int, choices=(24, 32, 40), help="Fresh v2 run budget; default 40, restored on resume")
    parser.add_argument("--harder", action="store_true", help="Fresh run on frozen v2 target 6000 / noise replicate 0; preserves v1 defaults")
    parser.add_argument("--api-ceiling-usd", help="Explicitly authorized fresh-run ceiling up to $3; use resume override for continuations")
    parser.add_argument("--inspect-resume", action="store_true", help="With --resume, validate restoration offline without creating a continuation")
    parser.add_argument("--resume-api-ceiling-usd", help="Requires explicit user authorization; cumulative resume ceiling up to $3, never a fresh allowance")
    args = parser.parse_args()
    adapter = ResourceAdapter()
    if args.render:
        if args.resume or args.require_full_budget or args.inspect_resume or args.resume_api_ceiling_usd or args.harder or args.api_ceiling_usd or args.scientific_budget is not None:
            parser.error("render cannot be combined with resume options")
        for artifact in adapter.regenerate(args.render):
            print(artifact)
        return
    repo = Path(__file__).resolve().parents[3]
    mode = "live" if args.live else "dry-run"
    resume = None
    if args.resume:
        if args.harder or args.api_ceiling_usd or args.scientific_budget is not None:
            parser.error("resume restores its environment; use --resume-api-ceiling-usd for an authorized increase")
        from budgeted_science.agents.resume import prepare_resume
        resume = prepare_resume(args.resume, mode=mode, require_full_budget=args.require_full_budget,
                                api_ceiling_usd=args.resume_api_ceiling_usd)
        if args.inspect_resume:
            import json
            print(json.dumps({"resumable": True, "parent": str(resume["parent"]),
                              "scientific_spent": sum(e["charge"] for e in resume["saved"]["environment"]["ledger"]),
                              "prior_responses": resume["responses"], "active_seconds_used": resume["elapsed"],
                              "api_committed_upper_usd": resume["money"].status()["committed_upper_usd"],
                              "api_ceiling_usd": resume["config"].api_ceiling_usd,
                              "require_full_budget": resume["config"].require_full_budget}, indent=2))
            return
    elif args.inspect_resume or args.resume_api_ceiling_usd:
        parser.error("these options require --resume")
    if args.scientific_budget not in (None, 40) and not args.harder:
        parser.error("lower scientific budgets require --harder")
    config = resume["config"] if resume else ResourceRunConfig(
        environment_version="v2" if args.harder else "v1",
        api_ceiling_usd=args.api_ceiling_usd or "2.00", require_full_budget=args.require_full_budget,
        scientific_budget=args.scientific_budget or 40)
    instance = resume["instance"] if resume else ResourceInstance.first_evaluation(config.environment_version)
    folder = "resource_agent_v2" if config.environment_version == "v2" else "resource_agent"
    path, reason = asyncio.run(run_episode(
        repo, args.output_root or repo / "demos/planning/runs" / folder,
        mode=mode, config=config, instance=instance,
        adapter=adapter, key_file=args.api_key_file, resume=resume))
    print(f"Termination: {reason}\nRun: {path}\nTranscript: {path / 'transcript.md'}\nReport: {path / 'report.md'}")
    if reason != "submitted":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
