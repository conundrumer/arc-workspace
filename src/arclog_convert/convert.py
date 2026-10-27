"""Convert the Souffle solvers under programs/solvers/ to arclog and arcdata
files under gen/ of `arclog_convert.out`: `work/arclog/` of the main
worktree, or the directory `--out` gives; in a linked worktree, `--out` is
required (or `ARCLOG_OUT`).

    uv run python -m arclog_convert.convert [--out <dir>] [<stem> ...]

Each run writes the output for the solvers, every solver where no
stem is given, and prints its summary; the run exits with status 1
where a solver fails to convert. The checks of the converted programs, the
replay on the train pairs and the comparison with Souffle's rows, are
`arclog_convert.verify`, which runs apart from the conversion.
A solver's plan file under plan/ records the hash of the solver file, task
file and witness file it was written from, and the runner and lib stamp of
the run; where it is missing or records another hash or stamp, the script
first restores it from the plans kept under `.cache/plans/`, which every
`--out` directory shares, and reruns the determination plan of the solver,
without the moved witnesses that the plan file does not hold, in a worker
process where none is kept for that hash and stamp (`arclog_convert.plans`). The
name map and the column map of each solver it converts, written under names/
and columns/, are those of `arclog_convert.names`, and names/ also holds the
Souffle texts that derive the rows of the relations the converter adds
(`arclog_convert.parity_text`): `<stem>.dl`, which the runs of the cases add to
the solver's program, and `<stem>.determination.dl`, which the determination's
run adds. Beside gen/, the directory
`row_parity.CORPUS` holds, for the row-parity check alone, a copy of each
converted program with the check relations of the relations it folds
(`arclog_convert.checks`) and the clauses of the relations the projection pass
removes from `gen/`; nothing else reads it.
A pass after the conversion moves the unjoined factors of clause bodies into
the clauses that join them (`arclog_convert.pull_up`); it runs on both texts,
and the column map lists the columns it took away from each relation no more.
Before that pass, each text gets `(OUT (&output ^<l0> ^<l1>))` in the tail and in each
`ALT` block whose own forms derive `&output`, with `<l0>` and `<l1>` the labels that the column map
entry of `&output` gives the first two columns of the solver's `out`
(`docs/arclog/arclog.md#the-out-form`).
A pass after that one folds each relation that only projects one earlier
relation into the atoms that read it (`arclog_convert.projections`), the atoms of
each `OUT` form among them, removes a clause of `&output` where it states the output's two
columns alone for the `OUT` form of its block, and removes each `OUT` form of an `ALT` block
that restates the `OUT` form its cases take without it: it runs
on both texts, and in the copy under `CORPUS` it keeps each clause it removes,
as a relation that nothing reads. The name map lists under `checks` the check
relations of the relations the conversion folds, which the row-parity check
compares in each case, and under `removed`, by each relation whose clause the
pass removes, the forms that held an atom on it before the pass redirected it
(`projections.ReaderForm`): the check compares that relation in a case only
where one of those forms derives its relation and `&output` reads that relation
(`parity.rerun`).
A form the script cannot translate is written literally, under a
`;; TODO <kind>: ...` comment.
A clause or a factor that a pass keeps because a block other than the reader's derives its relation again, or because
its relation has clauses in several blocks, holds in the flat program of a case, where each relation has one deriving
form (`projections.Projected.blocked`, `pull_up.Pulled.blocked`). On each solver where a pass keeps one, the run
writes, once every solver stands in `gen/`, the files of the cases whose program read alone differs after the two
passes (`convert_cases`): `gen/cases/<stem>/<case>.arclog` and `.arcdata`, with `<case>` as `arclog.case_files`
names the file of the case. A case whose program the passes leave as `arclog.case_files` gives it, and a case of
which it gives a fault, have no files. The passes read Souffle's rows of the whole program
(`pull_up.Rows.single`). The run removes `gen/cases/<stem>/` of each solver it converts before it converts it.
As each phase it runs ends (`plans`, `conversion`, `cases`), the run prints a line `<phase>: <seconds> s` with that phase's
wall time. Under `scripts/run_heavy.py --cpus <n>`, the processes and threads
the run has going at once, Souffle processes included, are at most `n`.
"""

import json
import re
import shutil
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple
from engine.pool import pool_size
from engine.program import Qualifier, Variable
from arclog_convert.libmap import rename as libmap_rename
from arclog_convert.lint_alts import alt_blocks, derived, placements
from arclog_convert.lint_read import L, read
from arclog_convert import paths
from arclog_convert.phases import phase, use_out

from arclog_convert.forms import (
    MERGES,
    MERGES_UNMERGED,
    Todo,
    fold_or_lines,
    hoist_shared,
    renamed,
)
from arclog_convert.checks import Fold
from arclog_convert.leaves import ScopedName
from arclog_convert.lib import Col, ColMismatch, LIB_DL, Lib, SIGNATURE
from arclog_convert.names import Checks, check_maps, column_map, dropped, folded, name_map, parity, placed, unchecked, untranslated
from arclog_convert.plans import refresh_plans
from arclog_convert.projections import project, readers_json
from arclog_convert.pull_up import OUTPUT, Pulled, Rows, drop_columns, pull_up
from arclog_convert.solver import Solver


_LIBS: tuple[Lib, Lib] | None = None

CASES = "cases"
"""The directory of `gen/` that holds, in a directory per solver, the files of the cases whose normal form
`convert_cases` writes."""


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


def _finished(arclog: str, arcdata: str, concept_empty: frozenset[str] | set[str]) -> tuple[str, str, dict[str, str]]:
    """The text of a pass after the renames that every converted program
    gets, and the instance renames they applied. `concept_empty` is the
    relations the solver derives no rows of in the concept case."""
    from arclog_convert.lint import fix_labels
    arclog = fold_or_lines(renamed(arclog))
    insts = libmap_rename.renamed_instances(libmap_rename.instances(arclog),
                                            libmap_rename.reads(arclog + arcdata))
    arclog = hoist_shared(fix_labels(libmap_rename.rename(arclog, insts)), concept_empty)
    return arclog, libmap_rename.rename(arcdata, insts), insts


def _with_checks(s: "Solver", lib: Lib, sig: Lib, names: dict, columns: dict, inline: frozenset[str],
                 copies: frozenset[ScopedName]) -> tuple[str, str] | None:
    """The arclog and the arcdata of the converted solver with the check
    relations of the relations it folds (`arclog_convert.checks`), and, in
    `names` and `columns`, their entries, their names under `checks`, and the
    reason of each folded relation that has none; none where it folds none."""
    folds = folded(s, names)
    if not folds:
        return None
    arclog = arcdata = None
    left: dict[Fold, str] = {}
    try:
        # a check relation with a clause the converter cannot write is left out, and the
        # conversion runs again without it
        keep = folds
        while keep:
            MERGES.clear()
            MERGES_UNMERGED.clear()
            again = Solver(s.stem, lib, sig, Todo(), inline, copies, keep)
            arclog, arcdata = again.run()
            arclog, arcdata, insts = _finished(arclog, arcdata, again.concept_empty)
            more = dropped(again, keep, insts, arclog)
            if not more:
                break
            left |= more
            keep = [f for f in keep if f not in more]
        if keep:
            got = check_maps(again, keep, insts, arclog)
        else:
            got, arclog, arcdata = Checks(), None, None
        got = Checks(got.relations, got.columns, {**got.untranslated, **untranslated(s, left).untranslated})
    except Exception as e:  # noqa: BLE001
        reason = f"{type(e).__name__}: {e}".splitlines()[0].replace("\t", " ")
        got = unchecked(s, folds, f"the conversion with the check relations failed, {reason}")
        arclog = arcdata = None
    names["relations"] = dict(sorted({**names["relations"], **got.relations}.items()))
    names["untranslated"] = got.untranslated
    names["checks"] = sorted(got.relations)
    columns.update(got.columns)
    return None if arclog is None else (arclog, arcdata)


def _output_form(columns: dict) -> str:
    """The `OUT` form of a program: it reads `&output` at the arclog columns that the column map entry of
    `&output` gives the first two columns of the solver's `out`, its Position and its Color. The entry that the
    top level writes is the one that counts."""
    entry = columns[OUTPUT]["out"]
    grid = (entry["writings"][0]["columns"] if isinstance(entry, dict) else entry)[:2]
    if len(grid) != 2 or any(len(leaves) != 1 or leaves[0]["field"] is not None for leaves in grid):
        raise ValueError(f"the first two columns of `out` are not one arclog column each: {grid}")
    return f"(OUT ({OUTPUT} ^{grid[0][0]['label']} ^{grid[1][0]['label']}))"


def _with_output_form(arclog: str, form: str) -> str:
    """`arclog` with `form` after its last form, a blank line between, and in each `ALT` block whose own forms derive
    `&output`, on a line of its own after the block's forms other than its `ALT` blocks and `ALTS` forms."""
    inserts: list[tuple[int, str]] = []
    for path, block in alt_blocks(read(arclog)):
        own = [f for f in block.items[2:] if isinstance(f, L) and f.head not in ("ALT", "ALTS")]
        if not any(p.alts == path and derived(p) == OUTPUT for p in placements(block.items[2:], alts=path)):
            continue
        line = arclog.rfind("\n", 0, own[-1].start) + 1
        indent = arclog[line:own[-1].start] if not arclog[line:own[-1].start].strip() else ""
        inserts.append((own[-1].end, "\n" + indent + form))
    for at, text in sorted(inserts, reverse=True):
        arclog = arclog[:at] + text + arclog[at:]
    return arclog.rstrip("\n") + "\n\n" + form + "\n"


def _write_json(directory: Path, stem: str, data: dict) -> None:
    (directory / f"{stem}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


type Answers = Mapping[tuple[str, frozenset[str]], bool]
"""The answers of `Rows.single` by the question: a relation and the arclog columns read."""


class Converted(NamedTuple):
    """What `convert_one` gives for one solver."""

    stem: str
    arclog: str | None
    arcdata: str | None
    kinds: Counter
    """The TODO kinds."""
    merges: Counter
    unmerged: list[str]
    mismatched: ColMismatch
    """The parameters whose columns do not map onto their proposer's."""
    error: str | None
    checked: tuple[str, str] | None
    """The arclog and the arcdata of the program with the check relations."""
    answers: Answers | None
    """The answers of `Rows.single` for the solver, where a rule on blocks kept a clause or a factor in the passes on
    the whole program, so that `convert_cases` runs the passes on each case; none otherwise."""


def _pull_up_all(rows: Rows, texts: Sequence[tuple[str, str]]) -> list[Pulled]:
    """The pull-up pass on each (arclog, arcdata) text of `texts`, with Souffle's rows asked once for all of them."""
    asked: set[tuple[str, frozenset[str]]] = set()
    for text, data in texts:
        pull_up(text, data, lambda relation, read: bool(asked.add((relation, read))))
    rows.ask(asked)
    return [pull_up(text, data, rows.single) for text, data in texts]


def convert_one(stem: str) -> Converted:
    """One solver's arclog and arcdata, its TODO kinds, its merge counts and
    its parameters whose columns do not map onto their proposer's, or the
    error that stopped it, the arclog and the arcdata of its program with
    the check relations, and the answers of `Rows.single` where
    `convert_cases` is to run: a pool worker's unit of work. The run first
    removes `cases/<stem>/` of `gen/`, which `convert_cases` writes."""
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
    answers = None
    shutil.rmtree(paths.OUT_DIR / CASES / stem, ignore_errors=True)
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
        arclog, arcdata, insts = _finished(arclog, arcdata, s.concept_empty)
        merges, unmerged = Counter(MERGES), list(MERGES_UNMERGED)
        names = name_map(s, insts, arclog, arcdata)
        text = parity(s, names, insts)
        names = placed(names, text)
        columns = column_map(s, names, insts, text)
        checked = _with_checks(s, lib, sig, names, columns, stuck, copies)
        paths.NAMES_DIR.mkdir(parents=True, exist_ok=True)
        _write_json(paths.NAMES_DIR, stem, names)
        (paths.NAMES_DIR / f"{stem}.dl").write_text(text.text)
        (paths.NAMES_DIR / f"{stem}.determination.dl").write_text(text.determination)
        # the pass reads Souffle's rows, which `parity.rerun` gives from the name map and the texts just written
        rows = Rows(stem, columns)
        pulled, *copy = _pull_up_all(rows, [(arclog, arcdata), *([checked] if checked is not None else [])])
        dropped = dict(pulled.dropped)
        arclog = pulled.arclog
        if checked is not None:
            checked = (copy[0].arclog, checked[1])
            dropped.update({n: dropped.get(n, frozenset()) | g for n, g in copy[0].dropped.items()})
        columns = drop_columns(columns, dropped)
        paths.COLUMNS_DIR.mkdir(parents=True, exist_ok=True)
        _write_json(paths.COLUMNS_DIR, stem, columns)
        # each `OUT` form reads `&output`; the projection pass folds it into what the clause of `&output` in its block
        # projects
        output = _output_form(columns)
        arclog = _with_output_form(arclog, output)
        if checked is not None:
            checked = (_with_output_form(checked[0], output), checked[1])
        # the copy keeps each clause the pass removes, as a relation that nothing reads
        base = checked or (arclog, arcdata)
        kept = project(base[0], base[1], columns, keep=True)
        checked = (kept.arclog, base[1])
        projected = project(arclog, arcdata, columns)
        arclog = projected.arclog
        if pulled.blocked or projected.blocked:
            answers = rows.answers
        if kept.readers:
            names["removed"] = readers_json(kept.readers)
            _write_json(paths.NAMES_DIR, stem, names)
    except Exception as e:  # noqa: BLE001
        return Converted(stem, None, None, Counter(), Counter(), [], {}, f"{type(e).__name__}: {e}", None, None)
    return Converted(stem, arclog, arcdata, todo.kinds, merges, unmerged, s.c.col_mismatch, None, checked, answers)


def convert_cases(stem: str, answers: Answers) -> tuple[str, int, str | None]:
    """Write the files of the cases of the solver `stem` whose normal form differs from the case as `gen/` gives it:
    `gen/cases/<stem>/<case>.arclog` and `.arcdata`, with `<case>` as `arclog.case_files` gives it. The normal form of
    a case is its program read alone (`arclog.case_files`) after the pull-up pass and then the projection pass, which
    read Souffle's rows of the whole program (`Rows.single`; `answers` are those `convert_one` found). A case of which
    `arclog.case_files` gives a fault gets no files. It reads the texts, the column map and the files of the
    solvers `gen/` holds that `convert_one` and the run wrote, so it runs after every solver is converted, and it
    writes nothing but those files.

    Gives the stem, the number of cases it wrote files of, and the error that stopped it."""
    from arclog import case_files
    try:
        gen = paths.OUT_DIR
        texts = (gen / f"{stem}.arclog").read_text(), (gen / f"{stem}.arcdata").read_text()
        columns = json.loads((paths.COLUMNS_DIR / f"{stem}.json").read_text())
        rows = Rows(stem, columns)
        rows.answers.update(answers)
        files = [f for f in case_files(stem, *texts, str(gen)) if f.fault is None]
        pulled = _pull_up_all(rows, [(f.arclog, f.arcdata) for f in files])
        normal = [project(p.arclog, f.arcdata, drop_columns(columns, p.dropped)).arclog for f, p in zip(files, pulled)]
        written = [(f, text) for f, text in zip(files, normal) if text != f.arclog]
        directory = gen / CASES / stem
        if written:
            directory.mkdir(parents=True, exist_ok=True)
        for f, text in written:
            (directory / f"{f.file}.arclog").write_text(text)
            (directory / f"{f.file}.arcdata").write_text(f.arcdata)
    except Exception as e:  # noqa: BLE001
        return stem, 0, f"{type(e).__name__}: {e}"
    return stem, len(written), None


def main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="python -m arclog_convert.convert")
    parser.add_argument("--out", type=Path, help="the directory to write under, in place of `arclog_convert.out`; required in a linked worktree unless `ARCLOG_OUT` is set")
    parser.add_argument("stems", nargs="*", help="the solvers to convert; every solver where none is given")
    args = parser.parse_args(argv)
    use_out(args.out)
    stems = args.stems or sorted(p.stem for p in paths.SOLVERS.glob("*.dl"))
    with phase("plans"):
        refresh_plans(stems)
    print(f"{paths.OUT_DIR}:")
    with phase("conversion"):
        converted = convert_into(stems, paths.OUT_DIR)
    return int(len(converted) < len(stems))


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
    asked: dict[str, Answers] = {}
    for stem, arclog, arcdata, kinds, m, um, mis, err, checked, answers in results:
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
        if answers is not None:
            asked[stem] = answers
        merges += m
        unmerged += um
        mismatched += [(stem, name, own, prop) for name, (own, prop) in mis.items()]
        total += kinds
        for k in kinds:
            per_kind_solvers[k] += 1
        if not kinds:
            clean += 1
    # the files of a case read the files of the solvers its solver names, so they are written once all stand
    with phase("cases"):
        cased = list(pool.map(convert_cases, asked, asked.values()) if pool is not None
                     else map(convert_cases, asked, asked.values()))
    for stem, count, err in cased:
        if err is not None:
            failed.append((stem, f"the case files: {err}"))
            converted.remove(stem)
    written = [count for _, count, err in cased if err is None]
    if pool is not None:
        pool.shutdown()
    print(f"converted {len(stems) - len(failed)} of {len(stems)}; {clean} with no TODO")
    print(f"case files: {sum(written)} cases of {sum(1 for count in written if count)} solvers; "
          f"the passes ran on the cases of {len(written)} solvers")
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
