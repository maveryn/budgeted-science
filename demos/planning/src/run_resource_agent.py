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
    choice.add_argument("--live", action="store_true", help="Authorize exactly ONE paid episode with a $2 ceiling")
    choice.add_argument("--render", type=Path, metavar="RUN_DIR", help="Regenerate local transcript/report without execution")
    parser.add_argument("--api-key-file", type=Path, help="Live only; default openaiapi.txt in repository")
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    adapter = ResourceAdapter()
    if args.render:
        for artifact in adapter.regenerate(args.render):
            print(artifact)
        return
    repo = Path(__file__).resolve().parents[3]
    path, reason = asyncio.run(run_episode(
        repo, args.output_root or repo / "demos/planning/runs/resource_agent",
        mode="live" if args.live else "dry-run", config=ResourceRunConfig(),
        instance=ResourceInstance.first_evaluation(), adapter=adapter, key_file=args.api_key_file))
    print(f"Termination: {reason}\nRun: {path}\nTranscript: {path / 'transcript.md'}\nReport: {path / 'report.md'}")
    if reason != "submitted":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
