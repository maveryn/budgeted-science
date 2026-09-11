import argparse
import json
from pathlib import Path
from .reporting import render
from .runner import DEFAULT_CATALOGS, DEFAULT_RUNS, calibrate, load_study, run_script, validate


def main():
    parser = argparse.ArgumentParser(description="Offline-only completed-study verification toy")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    calibration = sub.add_parser("calibrate")
    calibration.add_argument("--root", type=Path, default=DEFAULT_CATALOGS)
    dry = sub.add_parser("dry-run")
    dry.add_argument("--catalog", type=Path, required=True)
    dry.add_argument("--case")
    dry.add_argument("--fixture", choices=["accept", "reject", "abstain", "interrupted"], default="accept")
    dry.add_argument("--script", type=Path, help="Optional JSON sequence of scripted messages and calls")
    dry.add_argument("--root", type=Path, default=DEFAULT_RUNS)
    offline = sub.add_parser("render")
    offline.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        print(json.dumps(validate(), indent=2))
    elif args.command == "calibrate":
        path = calibrate(args.root)
        print(path)
        summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
        if not summary["complete"]:
            raise SystemExit("Commissioning incomplete; see preserved report.")
    elif args.command == "dry-run":
        steps = json.loads(args.script.read_text(encoding="utf-8")) if args.script else None
        print(run_script(load_study(args.catalog, args.case), kind=args.fixture, steps=steps, root=args.root))
    else:
        print(json.dumps(render(args.path), indent=2))


if __name__ == "__main__":
    main()
