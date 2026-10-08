import argparse
import json
from pathlib import Path
from .generate import generate
from .pipeline import run


def main():
    parser = argparse.ArgumentParser(description="Synthetic payment reliability demo")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--data-dir", type=Path, default=Path("data"))
    gen.add_argument("--count", type=int, default=1000)
    gen.add_argument("--seed", type=int, default=42)
    pipe = sub.add_parser("run")
    pipe.add_argument("--data-dir", type=Path, default=Path("data"))
    pipe.add_argument("--output", type=Path, default=Path("output"))
    pipe.add_argument("--as-of", default="2026-09-10T00:00:00+00:00")
    pipe.add_argument("--backend", choices=["sqlite", "postgres"], default="sqlite")
    pipe.add_argument("--grace-days", type=int, default=2)
    pipe.add_argument("--strict", action="store_true", help="Exit 2 on any reconciliation exception or quarantined row")
    args = parser.parse_args()
    try:
        if args.command == "generate":
            result = generate(args.data_dir, args.count, args.seed)
        else:
            result = run(args.data_dir, args.output, args.as_of, args.backend, args.grace_days)
        print(json.dumps(result, indent=2))
        if args.command == "run" and args.strict:
            bad = sum(v for k,v in result["status_counts"].items() if k not in {"matched","pending","not_applicable"})
            bad += sum(v for k,v in result["quality_counts"].items() if k != "exact_duplicate")
            if bad:
                raise SystemExit(2)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Pipeline error: {exc}\n")


if __name__ == "__main__":
    main()
