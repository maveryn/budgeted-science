"""Explicit dry-run/live entry point and offline audit-artifact regeneration."""

import argparse
import asyncio
from pathlib import Path

from budgeted_science.agents.reporting import regenerate
from budgeted_science.agents.config import RunConfig
from budgeted_science.agents.runner import run_episode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--dry-run", action="store_true", help="Scripted offline harness test; no credential access")
    choice.add_argument("--live", action="store_true", help="Explicitly authorize ONE paid episode, bounded by $2")
    choice.add_argument("--render", type=Path, metavar="RUN_DIR", help="Regenerate transcript/report from existing logs only")
    parser.add_argument("--api-key-file", type=Path, help="Live only; defaults to the repository's openaiapi.txt")
    parser.add_argument("--output-root", type=Path, help="Optional run-parent directory; existing runs are never overwritten")
    parser.add_argument("--two-parameter", action="store_true", help="Infer viscosity and unknown initial amplitude")
    parser.add_argument("--max-output-tokens", type=int, default=8192,
                        help="Explicit per-response allowance (default 8192; maximum 32768); $2 ceiling unchanged")
    args = parser.parse_args()
    if args.render:
        for path in regenerate(args.render):
            print(path)
        return
    repo = Path(__file__).resolve().parents[3]
    config = RunConfig(task_variant="viscosity_amplitude" if args.two_parameter else "viscosity",
                       max_output_tokens=args.max_output_tokens)
    path, reason = asyncio.run(run_episode(repo, args.output_root or repo / "demos/planning/runs",
                                         mode="live" if args.live else "dry-run", key_file=args.api_key_file,
                                         config=config))
    print(f"Termination: {reason}\nRun: {path}\nTranscript: {path / 'transcript.md'}\nReport: {path / 'report.md'}")
    if reason != "submitted":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
