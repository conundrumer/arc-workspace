"""The `run` command's entry: which of the one-solver check, the report
over several solvers and the run over a pairs file its arguments ask
for."""

import argparse
import sys

from cli import text
from cli.check import cmd_one
from cli.pairs import cmd_pairs
from cli.report import cmd_all


def dispatch(args: argparse.Namespace) -> int:
    if args.pairs:
        if len(args.stems) != 1:
            print(text.PAIRS_ONE_STEM, file=sys.stderr)
            return 2
        if args.as_json:
            print(text.PAIRS_NO_JSON, file=sys.stderr)
            return 2
        return cmd_pairs(args.stems[0], args.pairs)
    if len(args.stems) == 1 and not args.as_json:
        return cmd_one(args.stems[0], args.hints, args.timed)
    return cmd_all(args.hints, args.timed, args.stems or None, args.as_json)
