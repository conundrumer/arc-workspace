"""The checks of the converted programs, run apart from the conversion.

    uv run python -m arclog_convert.verify [--out <dir>] [--no-train-replay | --accept] [--no-row-parity] [<stem> ...]

The command checks the converted programs (`programs/arclog/`) of `arclog_convert.out`, or the programs under `gen/` of
`--out`, for the solvers given, every converted solver where none is given; it
converts nothing, so run `arclog_convert.convert` first. It first requires the
native exact determination end check, recording input-bound receipts under
`determination_end_check/`. No skip flag or baseline acceptance waives this
gate. It then replays each case
of the solvers on the train pairs of its task, records the verdicts under
`train_replay/`, and reports against the baseline `unreproduced.tsv`
(`arclog_convert.train_replay` gives the details); then it compares each
relation of those solvers with Souffle's rows, records the lines under
`row_parity/`, and reports against the baseline `row_parity.tsv`
(`arclog_convert.row_parity` gives the details). The run exits with status 1
where either report finds a case or line beyond its baseline, or one that was
`Consistent` or `equal` and is not. `--no-train-replay` skips the replay;
`--no-row-parity` skips the comparison. `--accept` rewrites the baseline lines
of the solvers checked to the run's counts, keeping the ticket field of each
line whose task and verdict stay; it is refused with `--no-train-replay`, and
with `--no-row-parity` it leaves `row_parity.tsv` untouched. The replay runs
`cargo` in `engine/`, so it needs a Rust toolchain.
As each phase it runs ends (`determination end check`, `train replay`, `row parity`), the run prints a line
`<phase>: <seconds> s` with that phase's wall time.
"""

import argparse
import sys
from pathlib import Path

from arclog_convert import paths
from arclog_convert.phases import phase, use_out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m arclog_convert.verify")
    parser.add_argument("--out", type=Path, help="the directory the converter wrote under, in place of `arclog_convert.out`; its arclog and arcdata files stand in `gen/` of it; required in a linked worktree unless `ARCLOG_OUT` is set")
    parser.add_argument("--no-train-replay", action="store_true", help="check with no replay on the train pairs")
    parser.add_argument("--accept", action="store_true", help="rewrite the baseline lines of the solvers checked to the run's counts, and the row-parity baseline lines unless --no-row-parity")
    parser.add_argument("--no-row-parity", action="store_true", help="check with no comparison of the relations with Souffle's rows")
    parser.add_argument("stems", nargs="*", help="the solvers to check; every converted solver where none is given")
    args = parser.parse_args(argv)
    if args.accept and args.no_train_replay:
        parser.error("--accept needs the train replay; drop --no-train-replay")
    use_out(args.out)
    from arclog_convert import row_parity, train_replay
    stems = args.stems or sorted(p.stem for p in paths.OUT_DIR.glob("*.arclog"))
    # Mandatory even with --no-train-replay/--no-row-parity or --accept:
    # baseline acceptance cannot waive exact determination equality.
    from arclog_convert.determination_gate import require, EndCheckFailed
    from arc.task import TASKS_DIR
    try:
        with phase("determination end check"):
            require(stems, paths.OUT_DIR, TASKS_DIR, paths.OUT_ROOT / "determination_end_check")
    except EndCheckFailed as exc:
        print(exc, file=sys.stderr)
        return 1
    status = 0
    if not args.no_train_replay:
        with phase("train replay"):
            status = train_replay.replay(stems, paths.OUT_ROOT, args.accept)
    if args.no_row_parity:
        return status
    with phase("row parity"):
        return row_parity.check(stems, paths.OUT_ROOT, args.accept) or status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
