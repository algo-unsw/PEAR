"""Command line.

    python -m pear validate [DATA_DIR]
    python -m pear derive [DATA_DIR] [--out build/derived.json]
    python -m pear verify-list [DATA_DIR] [--out docs/to-verify.md]
    python -m pear site [DATA_DIR] [--out build/site] [--signals prominence/signals.yaml]
    python -m pear prominence fetch [DATA_DIR] [--out prominence/signals.yaml] [--only ID ...]
    python -m pear prominence show [DATA_DIR] [--signals prominence/signals.yaml]
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
    site.add_argument("--signals", type=Path, default=Path("prominence/signals.yaml"))
    prom = sub.add_parser("prominence", help="fetch or show the prominence signals (front page order)")
    prom.add_argument("action", choices=["fetch", "show"])
    prom.add_argument("data_dir", nargs="?", default="data", type=Path)
    prom.add_argument("--out", type=Path, default=Path("prominence/signals.yaml"))
    prom.add_argument("--signals", type=Path, default=Path("prominence/signals.yaml"))
    prom.add_argument("--queries", type=Path, default=Path("prominence/queries.yaml"))
    prom.add_argument("--only", nargs="*", help="fetch these problems only, keeping the others' signals")
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

    if args.command == "prominence":
        return prominence(args, data)

    from .derive import derive as run, to_json

    result = run(data)
    if args.command == "site":
        from .site import build

        site_data = build(data, result, args.out, signals_path=args.signals)
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
    if result.open:
        print(f"open: {len(result.open)} pairs of Overview bounds are undecided (no proof, no witness); "
              f"listed under open_comparisons in {args.out}")
    print(f"OK: {kept} results kept ({derived} derived), written to {args.out}.")
    return 0


def prominence(args: argparse.Namespace, data) -> int:
    import yaml

    from . import prominence as pm

    if args.action == "fetch":
        overrides = yaml.safe_load(args.queries.read_text(encoding="utf-8")) if args.queries.is_file() else {}
        unknown = sorted(set(overrides or {}) - set(data.problems))
        if unknown:
            print(f"{args.queries}: unknown problem ids {', '.join(unknown)}", file=sys.stderr)
            return 1
        old = pm.load_signals(args.out) if args.only else None

        def merged(snap: dict) -> dict:
            if old is None:
                return snap
            return {**old, "as_of": snap["as_of"], "problems": {**old["problems"], **snap["problems"]}, "errors": snap["errors"]}

        def save(snap: dict) -> None:  # after every problem, so a cut-off run keeps what it got
            pm.write_signals(merged(snap), args.out)

        snap = merged(pm.fetch(data, overrides, only=args.only, log=lambda s: print(s, flush=True), checkpoint=save))
        pm.write_signals(snap, args.out)
        for e in snap["errors"]:
            print(f"error: {e}")
        print(f"OK: signals for {len(snap['problems'])} problems written to {args.out} ({len(snap['errors'])} errors).")
        return 0
    rows = pm.scores(data, pm.load_signals(args.signals))
    groups = list(pm.GROUPS)
    print(f"{'problem':34} {'score':>6} " + " ".join(f"{g[:9]:>9}" for g in groups))
    for pid, r in sorted(rows.items(), key=lambda kv: (-kv[1]["score"], data.problems[kv[0]].name)):
        cells = " ".join(f"{'-' if r['groups'][g] is None else r['groups'][g]:>9}" for g in groups)
        print(f"{data.problems[pid].name[:34]:34} {r['score']:>6} {cells}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
