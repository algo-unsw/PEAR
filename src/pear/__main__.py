"""Command line.

    python -m pear validate [DATA_DIR]
    python -m pear derive [DATA_DIR] [--out build/derived.json]
    python -m pear site [DATA_DIR] [--out build/site]
    python -m pear verify-list [DATA_DIR] [--out docs/to-verify.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .validate import validate_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pear")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate", help="check every data file against the schema")
    check.add_argument("data_dir", nargs="?", default="data", type=Path)
    derive = sub.add_parser("derive", help="compute best and derived bounds (rulebook)")
    derive.add_argument("data_dir", nargs="?", default="data", type=Path)
    derive.add_argument("--out", type=Path, default=Path("build/derived.json"))
    site = sub.add_parser("site", help="write the page data for the static site")
    site.add_argument("data_dir", nargs="?", default="data", type=Path)
    site.add_argument("--out", type=Path, default=Path("build/site"))
    todo = sub.add_parser("verify-list", help="write the list of what still needs reading or checking")
    todo.add_argument("data_dir", nargs="?", default="data", type=Path)
    todo.add_argument("--out", type=Path, default=Path("docs/to-verify.md"))
    args = parser.parse_args(argv)

    data, issues = validate_dir(args.data_dir)
    for issue in issues:
        print(issue)
    counts = ", ".join(f"{len(v)} {k}" for k, v in data.entries.items())
    if issues:
        print(f"\n{len(issues)} problem(s) found ({counts} valid).", file=sys.stderr)
        return 1
    if args.command == "validate":
        print(f"OK: {counts}.")
        return 0
    if args.command == "verify-list":
        from .verify_list import write_list

        text = write_list(args.data_dir, args.out)
        print(f"OK: {text.count(chr(10))} lines written to {args.out}.")
        return 0

    from .derive import derive as run, to_json

    result = run(data)
    if args.command == "site":
        from .site import build

        site_data = build(data, result, args.out)
        print(f"OK: {len(site_data['pages'])} problem pages, written to {args.out}.")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(to_json(data, result), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    kept = sum(len(v) for v in result.results.values())
    derived = sum(1 for v in result.results.values() for r in v if r.derived)
    for line in result.log:
        print(f"note: {line}")
    for u in result.undecided:
        rel = "equal to" if u["equal"] else "at most"
        print(f"undecided: {u['problem']} ({u['node']}): {u['smaller']} looks {rel} {u['larger']} "
              f"at all {u['samples']} sample points, but the comparator cannot prove it; add the missing fact or rule")
    print(f"OK: {kept} results kept ({derived} derived), written to {args.out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
