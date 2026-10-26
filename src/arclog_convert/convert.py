"""Convert the Souffle solvers under programs/solvers/ to arclog and arcdata
files under gen/, and, with the expansion config `libmap.macros`, under
gen_macros/, of `arclog_convert.out`: `work/arclog/` of the main
worktree, or the directory `--out` gives; in a linked worktree, `--out` is
required (or `ARCLOG_OUT`).

    uv run python -m arclog_convert.convert [--out <dir>] [--no-train-replay | --accept] [--no-row-parity] [<stem> ...]

Each run writes both outputs for the same solvers, every solver where no
stem is given, and prints the summary of each.
Then, once both outputs are written, it replays each case of the solvers
that `gen/` converted on the train pairs of its task, records the verdicts
under `train_replay/`, and reports against the baseline
`unreproduced.tsv`; the run exits with status 1 where the report finds a
case beyond the baseline or one that was `Consistent` and is not.
`--no-train-replay` skips it. `--accept` also rewrites the baseline lines
of the covered tasks to the run's counts, keeping the ticket field of each
line whose task and verdict stay: the lines it rewrites are those of the
solvers it converted, from the files it wrote; it is refused with
`--no-train-replay`. The replay runs `cargo` in `engine/`, so it
needs a Rust toolchain; `arclog_convert.train_replay` gives the details.
After the replay it compares each relation of those solvers with Souffle's rows,
records the lines under `row_parity/`, and reports against the baseline
`row_parity.tsv`; the run exits with status 1 where either report does.
`--no-row-parity` skips it. `--accept` also rewrites the lines of
`row_parity.tsv` of the solvers it converted, from the files it wrote, after
the check; with `--no-row-parity` it leaves `row_parity.tsv` untouched.
`arclog_convert.row_parity` gives the details.
A solver's plan file under plan/ records the hash of the solver
file it was written from, and the runner and lib stamp of the run; where it
is missing or records another hash or stamp, the script first reruns
`scripts/run_dl.py determination-plan <stem>` (`arclog_convert.plans`). The
name map and the column map of each solver it converts, written under names/
and columns/, are those of `arclog_convert.names`. Beside gen/, the directory
`row_parity.CORPUS` holds, for the row-parity check alone, a copy of each
converted program with the check relations of the relations it folds
(`arclog_convert.checks`); nothing else reads it.
A form the script cannot translate is written literally, under a
`;; TODO <kind>: ...` comment.
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from engine.pool import pool_size
from engine.program import Qualifier, Variable
from arclog_convert.libmap import rename as libmap_rename
from arclog_convert import OUT_ENV, paths, writable_out

from arclog_convert.forms import (
    MERGES,
    MERGES_UNMERGED,
    Todo,
    fold_or_lines,
    hoist_shared,
    renamed,
)
from arclog_convert.leaves import ScopedName
from arclog_convert.lib import Col, ColMismatch, LIB_DL, Lib, SIGNATURE
from arclog_convert.names import check_maps, column_map, folded, name_map, unchecked
from arclog_convert.plans import refresh_plans
from arclog_convert.solver import Solver


_LIBS: tuple[Lib, Lib] | None = None



def _written_inline(s: "Solver", arclog: str) -> frozenset[str]:
    """Each relation of the solver declared `inline` that `arclog`, the pass's
    text, still writes as a `RULE` or `DET`, and whose clauses `terms.inlined`
    can inline: each has a body and a head of distinct variables. A relation
    the pass's merge removed is not in `arclog`, and one of another head
    stays as the pass wrote it."""
    c = s.c
    names = {r.name for r in c.prog.relations if Qualifier.INLINE in r.qualifiers}
    names = {n for n in names if n in c.unsafe or re.search(r"\((?:RULE|DET) &" + re.escape(n) + r"(?![\w-])", arclog)}

    def inlinable(n: str) -> bool:
        units = [u for u in c.prog.units if u.head.relation.name == n and not u.head.relation.instances]
        return n not in c.lib.top and any(u.body is not None for u in units) and all(
            u.body is None or (all(isinstance(a, Variable) for a in u.head.args)
                               and len({a.name for a in u.head.args}) == len(u.head.args))
            for u in units)
    return frozenset(n for n in names if inlinable(n))


def _finished(arclog: str, arcdata: str) -> tuple[str, str, dict[str, str]]:
    """The text of a pass after the renames that every converted program
    gets, and the instance renames they applied."""
    from arclog_convert.lint import fix_labels
    arclog = fold_or_lines(renamed(arclog))
    insts = libmap_rename.renamed_instances(libmap_rename.instances(arclog),
                                            libmap_rename.reads(arclog + arcdata))
    arclog = hoist_shared(fix_labels(libmap_rename.rename(arclog, insts)))
    return arclog, libmap_rename.rename(arcdata, insts), insts


def _with_checks(s: "Solver", lib: Lib, sig: Lib, names: dict, columns: dict, inline: frozenset[str],
                 copies: frozenset[ScopedName]) -> tuple[str, str] | None:
    """The arclog and the arcdata of the converted solver with the check
    relations of the relations it folds (`arclog_convert.checks`), and, in
    `names` and `columns`, their entries and the reason of each folded
    relation that has none; none where it folds none."""
    folds = folded(s, names)
    if not folds:
        return None
    MERGES.clear()
    MERGES_UNMERGED.clear()
    try:
        again = Solver(s.stem, lib, sig, Todo(), inline, copies, folds)
        arclog, arcdata = again.run()
        arclog, arcdata, insts = _finished(arclog, arcdata)
        got = check_maps(again, folds, insts, arclog)
    except Exception as e:  # noqa: BLE001
        reason = f"{type(e).__name__}: {e}".splitlines()[0].replace("\t", " ")
        got = unchecked(s, folds, f"the conversion with the check relations failed, {reason}")
        arclog = arcdata = None
    names["relations"] = dict(sorted({**names["relations"], **got.relations}.items()))
    names["untranslated"] = got.untranslated
    columns.update(got.columns)
    return None if arclog is None else (arclog, arcdata)


def convert_one(stem: str) -> tuple[str, str | None, str | None, Counter, Counter, list[str], ColMismatch, str | None,
                                    tuple[str, str] | None]:
    """One solver's arclog and arcdata, its TODO kinds, its merge counts and
    its parameters whose columns do not map onto their proposer's, or the
    error that stopped it, and, unless the expansion config is on, the arclog
    and the arcdata of its program with the check relations: a pool worker's
    unit of work."""
    global _LIBS
    if _LIBS is None:
        lib, sig = Lib(LIB_DL), Lib(SIGNATURE)
        lib.extend(sig)
        _LIBS = lib, sig
    lib, sig = _LIBS
    MERGES.clear()
    MERGES_UNMERGED.clear()
    todo = Todo()
    checked = None
    try:
        s = Solver(stem, lib, sig, todo)
        arclog, arcdata = s.run()
        # an `inline` relation that the pass writes as an arclog relation is no
        # relation: its body stands at each call
        stuck = _written_inline(s, arclog)
        # a relation that an alt rederives and a `DET` of the concept program
        # reads gets, in the determination, a copy of its own
        copies = s.own_copies_needed()
        if stuck or copies:
            MERGES.clear()
            MERGES_UNMERGED.clear()
            todo = Todo()
            s = Solver(stem, lib, sig, todo, stuck, copies)
            arclog, arcdata = s.run()
        arclog, arcdata, insts = _finished(arclog, arcdata)
        merges, unmerged = Counter(MERGES), list(MERGES_UNMERGED)
        if paths.MACROS_ENV not in os.environ:
            names = name_map(s, insts, arclog, arcdata)
            columns = column_map(s, names, insts)
            checked = _with_checks(s, lib, sig, names, columns, stuck, copies)
            for directory, data in ((paths.NAMES_DIR, names), (paths.COLUMNS_DIR, columns)):
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f"{stem}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
            checked = checked or (arclog, arcdata)
    except Exception as e:  # noqa: BLE001
        return stem, None, None, Counter(), Counter(), [], {}, f"{type(e).__name__}: {e}", None
    return stem, arclog, arcdata, todo.kinds, merges, unmerged, s.c.col_mismatch, None, checked


def main(argv: list[str]) -> int:
    global OUT_DIR, MACROS_DIR, PLANS, NAMES_DIR, COLUMNS_DIR
    import argparse
    parser = argparse.ArgumentParser(prog="python -m arclog_convert.convert")
    parser.add_argument("--out", type=Path, help="the directory to write under, in place of `arclog_convert.out`; required in a linked worktree unless `ARCLOG_OUT` is set")
    parser.add_argument("--no-train-replay", action="store_true", help="convert with no replay on the train pairs")
    parser.add_argument("--accept", action="store_true", help="rewrite the baseline lines of the solvers this run converted to its counts, and the row-parity baseline lines of those solvers unless --no-row-parity")
    parser.add_argument("--no-row-parity", action="store_true", help="convert with no comparison of the relations with Souffle's rows")
    parser.add_argument("stems", nargs="*", help="the solvers to convert; every solver where none is given")
    args = parser.parse_args(argv)
    if args.accept and args.no_train_replay:
        parser.error("--accept needs the train replay; drop --no-train-replay")
    if args.out is not None:
        # set before the pools start, so that their workers read it
        os.environ[OUT_ENV] = str(args.out.resolve())
        paths.OUT_DIR, paths.MACROS_DIR, paths.PLANS, paths.NAMES_DIR, paths.COLUMNS_DIR = paths.out_dirs()
    else:
        writable_out()
    stems = args.stems or sorted(p.stem for p in paths.SOLVERS.glob("*.dl"))
    refresh_plans(stems)
    print(f"{paths.OUT_DIR}:")
    converted = convert_into(stems, paths.OUT_DIR)
    # set before the second pool starts, so that its workers read it
    os.environ[paths.MACROS_ENV] = "1"
    print(f"{paths.MACROS_DIR}:")
    convert_into(stems, paths.MACROS_DIR)
    from arclog_convert import row_parity, train_replay
    status = 0 if args.no_train_replay else train_replay.replay(converted, paths.OUT_DIR.parent, args.accept)
    if args.no_row_parity:
        return status
    return row_parity.check(converted, paths.OUT_DIR.parent, args.accept) or status


def convert_into(stems: list[str], out: Path) -> list[str]:
    """Convert `stems` into `out` over a process pool, print the
    summary, and give the stems it converted."""
    from concurrent.futures import ProcessPoolExecutor
    from arclog_convert.row_parity import CORPUS
    out.mkdir(parents=True, exist_ok=True)
    corpus = out.parent / CORPUS
    total = Counter()
    per_kind_solvers = Counter()
    merges: Counter[str] = Counter()
    unmerged: list[str] = []
    mismatched: list[tuple[str, str, list[Col], list[Col]]] = []
    failed = []
    converted = []
    clean = 0
    workers = min(len(stems), pool_size())
    if workers > 1:
        pool = ProcessPoolExecutor(workers)
        # the largest solvers first, so that no long one starts last
        order = sorted(stems, key=lambda t: -(paths.SOLVERS / f"{t}.dl").stat().st_size)
        results = pool.map(convert_one, order)
    else:
        pool, results = None, map(convert_one, stems)
    for stem, arclog, arcdata, kinds, m, um, mis, err, checked in results:
        if err is not None:
            failed.append((stem, err))
            continue
        converted.append(stem)
        (out / f"{stem}.arclog").write_text(arclog)
        (out / f"{stem}.arcdata").write_text(arcdata)
        if checked is not None:
            corpus.mkdir(exist_ok=True)
            (corpus / f"{stem}.arclog").write_text(checked[0])
            (corpus / f"{stem}.arcdata").write_text(checked[1])
        merges += m
        unmerged += um
        mismatched += [(stem, name, own, prop) for name, (own, prop) in mis.items()]
        total += kinds
        for k in kinds:
            per_kind_solvers[k] += 1
        if not kinds:
            clean += 1
    if pool is not None:
        pool.shutdown()
    print(f"converted {len(stems) - len(failed)} of {len(stems)}; {clean} with no TODO")
    print(f"merged {merges['relation']} relations and {merges['input']} inputs; "
          f"unmerged {merges['unmerged']} relations ({', '.join(sorted(set(unmerged)))}) "
          f"and {merges['input-unmerged']} inputs")
    if mismatched:
        print(f"{len(mismatched)} parameters keep their own columns, which do not map onto those of the proposer or the derivation their DET names:")
        for stem, name, own, prop in sorted(mismatched, key=lambda u: u[:2]):
            print(f"  {stem} {name}: ({', '.join(f'{c.name} {c.type}' for c in own)}) "
                  f"onto ({', '.join(f'{c.name} {c.type}' for c in prop)})")
    for k, n in total.most_common():
        print(f"  {k:20} {n:6} in {per_kind_solvers[k]} solvers")
    if failed:
        print(f"failed {len(failed)}:")
        for stem, err in failed[:30]:
            print(f"  {stem}: {err}")
        errs = Counter(e.split(":")[0] + ":" + e.split(":")[1][:60] for _, e in failed)
        for e, n in errs.most_common(10):
            print(f"  {n:4} {e}")

    return converted


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
