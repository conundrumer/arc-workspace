"""The stored Souffle outcomes that the engine's parity checks compare
with, which no check runs Souffle to make, and a Souffle case run again by
arclog names.

Run with --help for the subcommands and the files they write.

A sentence a tool prints stands in an `mctx` call where the tool prints it.
"""

import argparse
import json
import sys
from collections.abc import Mapping

from cli.common import all_stems, engine, solver_path
from controlled_markdown import mctx
from engine import AdtValue, NilValue, RecordValue, Rows
from engine.program import Value
from parity import rerun, snapshot, uses
from solver.load import load


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="souffle_parity.py",
        description=mctx("The stored Souffle outcomes of the solvers, by arclog names."))
    sub = top.add_subparsers(dest="cmd", required=True)
    snap = sub.add_parser("snapshot", help=mctx(
        "Write the record of each solver whose stored record is not fresh, to "
        "`.cache/parity/<stem>.json` of the main worktree, and print the path of each "
        "record written; then the stem of each solver that has no record written because a run "
        "of it was stopped at its wall limit, under a line that says so."))
    snap.add_argument("stems", nargs="*", help=mctx(
        "The solvers, each by its stem; every solver under `programs/solvers/` where none "
        "is given."))
    sub.add_parser("uses", help=mctx(
        "Write each lib name, each proposer and each form keyword that a file of "
        "`work/arclog/gen/` uses, with the stems of the files that use it, to "
        "`.cache/parity/uses.json` of the main worktree, and print its path."))
    again = sub.add_parser("rerun", help=mctx(
        "Run one case of a solver again on one pair with every relation written out, and "
        "print the rows of each relation under its arclog name. It writes no file."))
    again.add_argument("stem", help=mctx("The solver's stem."))
    again.add_argument("case", help=mctx("The case's arclog name, as a record keys it."))
    again.add_argument("pair", help=mctx("The pair, as `train 0` or `test 1`."))
    again.add_argument("--json", action="store_true", help=mctx(
        "Print the relations' rows and the number of each orientation constant of the lib "
        "as one JSON object, in place of the text."))
    return top


def leaves(value: Value) -> list[int | float | str]:
    """The leaves of `value`, as `rerun --json` writes a row's values."""
    match value:
        case RecordValue(fields=fields) | AdtValue(args=fields):
            return [leaf for field in fields for leaf in leaves(field)]
        case NilValue():
            return []
        case _:
            return [value]


def rerun_json(stem: str, got: Mapping[str, Rows]) -> str:
    """The JSON object `rerun --json` prints for the rows `got` of a case
    of `stem`."""
    lib = load(stem, engine(), solver_path(stem)).lib
    members = {name for names in lib.orientation_types.values() for name in names}
    return json.dumps({
        "relations": [[name, [[leaf for value in row for leaf in leaves(value)] for row in rows]]
                      for name, rows in got.items()],
        "orientation_constants": {name: value for name, value in lib.constants.items()
                                  if name in members},
    })


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv)
    if args.cmd == "snapshot":
        written = snapshot.write_all(args.stems or all_stems())
        for path in written.paths:
            print(path)
        if written.stopped:
            print(mctx("Each of these solvers has no record written, since a run of it "
                       "was stopped at its wall limit:"))
            for stem in written.stopped:
                print(stem)
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
    if args.json:
        print(rerun_json(args.stem, got))
        return 0
    eng = engine()
    for name, rows in got.items():
        print(f"{name} {len(rows)}")
        for row in rows:
            print("  " + "\t".join(eng.text(v) for v in row))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
