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

from cli.common import all_stems, engine, solver_path
from controlled_markdown import mctx
from parity import lib, rerun, snapshot, uses


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
        "`programs/arclog/` uses, with the stems of the files that use it, to "
        "`.cache/parity/uses.json` of the main worktree, and print its path."))
    lib_cmd = sub.add_parser("lib", help=mctx(
        "Write the Souffle rows of each inputs file of the lib elements under "
        "`.cache/parity/lib/inputs/` of the main worktree whose record is not fresh, to "
        "`.cache/parity/lib/`, and print the path of each record written. "
        "`arclog-cli lib-compare` writes the inputs files."))
    lib_cmd.add_argument("elements", nargs="*", metavar="element", help=mctx(
        "The lib elements, each by its name; every element with an inputs file where none "
        "is given."))
    again = sub.add_parser("rerun", help=mctx(
        "Run one case of a solver again on one pair with every relation written out, and "
        "print the rows of each relation under its arclog name. With `--json`, a rerun that gives "
        "rows is kept under `.cache/parity/reruns/` of the main worktree, and printed again "
        "while each input of the rerun is unchanged; with no `--json`, it writes no file."))
    again.add_argument("stem", help=mctx("The solver's stem."))
    again.add_argument("case", help=mctx("The case's arclog name, as a record keys it."))
    again.add_argument("pair", help=mctx("The pair, as `train 0` or `test 1`."))
    again.add_argument("--json", action="store_true", help=mctx(
        "Print the relations' rows and the number of each orientation constant of the lib "
        "as one JSON object, in place of the text."))
    rows = sub.add_parser("case-rows", help=mctx(
        "Write `<out>/<stem>.json` for each solver: the Souffle rows of its concept case, and of the first case "
        "that takes each ALT no case before it takes, on each train and test pair, for each relation that "
        "the column map (`columns/<stem>.json` beside `names/` of `arclog_convert.out`) gives an entry, projected "
        "onto the columns it gives to compare, with the numbers of the orientation constants; and each relation "
        "of the run or of the name map it leaves out, with its verdict and reason. Print the path of each file "
        "written."))
    rows.add_argument("stems", nargs="+", help=mctx("The solvers, each by its stem."))
    rows.add_argument("--out", type=Path, required=True, help=mctx("The directory to write the files under."))
    rows.add_argument("--solvers", type=Path, help=mctx(
        "The directory to read `<stem>.dl` from, in place of `programs/solvers/`; give the one "
        "`ARCLOG_SOLVERS` names for a conversion that set it."))
    return top


def case_rows(stems: list[str], out: Path, solvers: Path | None) -> int:
    """Write the file of each stem; 1 where a solver gives no rows."""
    out.mkdir(parents=True, exist_ok=True)
    status = 0
    for stem in stems:
        file = (solvers / f"{stem}.dl") if solvers else solver_path(stem)
        try:
            got = rerun.case_rows(stem, file, out / f"{stem}.json")
        except rerun.NoSuchCase:
            print(mctx("No concept case of {stem}.").format(stem=stem), file=sys.stderr)
            status = 1
            continue
        if got is not None:
            print(mctx("{stem}: the run gives no rows: {got}").format(stem=stem, got=got), file=sys.stderr)
            status = 1
            continue
        print(out / f"{stem}.json")
    return status


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
    if args.cmd == "lib":
        try:
            written = lib.write_all(args.elements)
        except lib.NoInputsFile as missing:
            print(mctx("No inputs file of the lib element {name}.").format(name=missing), file=sys.stderr)
            return 2
        for path in written:
            print(path)
        return 0
    if args.cmd == "uses":
        print(uses.write_all())
        return 0
    if args.cmd == "case-rows":
        return case_rows(args.stems, args.out, args.solvers)
    try:
        got = (rerun.kept_json(args.stem, args.case, args.pair) if args.json
               else rerun.relations(args.stem, args.case, args.pair))
    except rerun.NoSuchCase:
        print(mctx("No case of {stem} has the arclog name `{case}`.").format(
            stem=args.stem, case=args.case), file=sys.stderr)
        return 2
    except rerun.NoSuchPair:
        print(mctx("The task of {stem} has no pair `{pair}`.").format(
            stem=args.stem, pair=args.pair), file=sys.stderr)
        return 2
    if isinstance(got, str):
        print(got)
        return 0
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
