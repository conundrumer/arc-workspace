#!/usr/bin/env python3
"""The retro window and the mark that bounds it, as JSON on stdout. Deprecated.

    uv run python tools/console/retro.py window   # the callouts since the mark
    uv run python tools/console/retro.py mark     # move the mark to now

Env:
    CONSOLE_STATE_DIR  where the mark and the reports live (default: tools/console/state)
"""

import argparse
import json
import sys
from pathlib import Path

# The package sits beside this file, which the interpreter puts on the path
# only as this script's own directory.
sys.path.append(str(Path(__file__).resolve().parent))

from solver_console import ledger  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("window", help="the tasks whose callouts landed since the mark")
    sub.add_parser("mark", help="move the mark to now")
    args = ap.parse_args(argv)
    out = ledger.retro_view() if args.cmd == "window" else ledger.mark_retro()
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
