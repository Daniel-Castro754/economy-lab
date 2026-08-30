from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from economy_lab.validation import ENGINE_ORDER, validate_external_engines


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify Economy Lab external engines with real runtime tests.")
    parser.add_argument("--engine", action="append", choices=ENGINE_ORDER, dest="engines")
    parser.add_argument("--no-smoke", action="store_true", help="Only detect/configure engines; do not execute smoke tests")
    parser.add_argument("--no-integration", action="store_true", help="Skip Economy Zero integrated smoke tests")
    parser.add_argument("--dynare-timeout", type=int, default=60)
    parser.add_argument("--minsky-timeout", type=float, default=3.0)
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report to this path")
    parser.add_argument("--markdown-output", type=Path, default=None, help="Write Markdown report to this path")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless every requested engine reports PASS")
    parser.add_argument(
        "--strict-qualification", action="store_true",
        help="Exit non-zero unless the requested engines satisfy the current runtime qualification level",
    )
    args = parser.parse_args()

    report = validate_external_engines(
        args.engines or ENGINE_ORDER,
        smoke_tests=not args.no_smoke,
        integration_tests=not args.no_integration,
        dynare_timeout_seconds=args.dynare_timeout,
        minsky_timeout_seconds=args.minsky_timeout,
    )
    payload = report.to_dict()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(report.to_markdown(), encoding="utf-8")
    print(text)
    if report.failed:
        return 2
    if args.strict_qualification and not report.qualification_ready:
        return 4
    if args.strict and report.status != "ready":
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
