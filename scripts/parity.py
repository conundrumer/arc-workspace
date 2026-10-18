"""The stored Souffle outcomes that the engine's parity checks compare
with, which no check runs Souffle to make, and a Souffle case run again by
arclog names.

Run with --help for the subcommands and the files they write.

A sentence a tool prints stands in an `mctx` call where the tool prints it.
"""

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

# This script's directory, first on the path, would make `parity` this
# script in place of the package of `src/parity/`.
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).resolve().parent]

from cli.common import all_stems, engine  # noqa: E402
from controlled_markdown import mctx  # noqa: E402
from parity import rerun, snapshot, uses  # noqa: E402


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="parity.py",
        description=mctx("The stored Souffle outcomes of the solvers, by arclog names."))
    sub = top.add_subparsers(dest="cmd", required=True)
    snap = sub.add_parser("snapshot", help=mctx(
        "Write the record of each solver whose stored record is not fresh, to "
        "`.cache/parity/<stem>.json` of the main worktree, and print the path of each "
        "record written."))
    snap.add_argument("stems", nargs="*", help=mctx(
        "The solvers, each by its stem; every solver under `programs/solvers/` where none "
        "is given."))
    sub.add_parser("uses", help=mctx(
        "Write each lib name and each form keyword that a file of `work/arclog/gen/` reads, "
        "with the stems of the files that read it, to `.cache/parity/uses.json` of the "
        "main worktree, and print its path."))
    again = sub.add_parser("rerun", help=mctx(
        "Run one case of a solver again on one pair with every relation written out, and "
        "print the rows of each relation under its arclog name. It writes no file."))
    again.add_argument("stem", help=mctx("The solver's stem."))
    again.add_argument("case", help=mctx("The case's arclog name, as a record keys it."))
    again.add_argument("pair", help=mctx("The pair, as `train 0` or `test 1`."))
    return top


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv)
    if args.cmd == "snapshot":
        for path in snapshot.write_all(args.stems or all_stems()):
            print(path)
        return 0
    if args.cmd == "uses":
        print(uses.write_all())
        return 0
    try:
        got = rerun.relations(args.stem, args.case, args.pair)
    except rerun.NoSuchCase:
        print(mctx("No case of {stem} has the arclog name `{case}`.").format(
            stem=args.stem, case=args.case), file=sys.stderr)
        return 2
    except rerun.NoSuchPair:
        print(mctx("The task of {stem} has no pair `{pair}`.").format(
            stem=args.stem, pair=args.pair), file=sys.stderr)
        return 2
    if not isinstance(got, Mapping):
        print(mctx("The run gives no rows: {got}").format(got=got), file=sys.stderr)
        return 1
    eng = engine()
    for name, rows in got.items():
        print(f"{name} {len(rows)}")
        for row in rows:
            print("  " + "\t".join(eng.text(v) for v in row))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
