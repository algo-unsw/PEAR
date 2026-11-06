"""Command line: python -m pear validate [DATA_DIR]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .validate import validate_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pear")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("validate", help="check every data file against the schema")
    check.add_argument("data_dir", nargs="?", default="data", type=Path)
    args = parser.parse_args(argv)

    data, issues = validate_dir(args.data_dir)
    for issue in issues:
        print(issue)
    counts = ", ".join(f"{len(v)} {k}" for k, v in data.entries.items())
    if issues:
        print(f"\n{len(issues)} problem(s) found ({counts} valid).", file=sys.stderr)
        return 1
    print(f"OK: {counts}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
