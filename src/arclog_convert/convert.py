"""Convert the Souffle solvers under programs/solvers/ to arclog and arcdata
files under gen/ of `arclog_convert.out`: `work/arclog/` of the main
worktree, or the directory `--out` gives; in a linked worktree, `--out` is
required (or `ARCLOG_OUT`).

    uv run python -m arclog_convert.convert [--out <dir>] [--require-current-lib] [--require-current-code] [<stem> ...]

Each run writes the output for the solvers, every solver where no
stem is given, and prints its summary; the run exits with status 1
where a solver fails to convert. The checks of the converted programs, the
replay on the train pairs and the comparison with Souffle's rows, are
`arclog_convert.verify`, which runs apart from the conversion.
A solver's plan file under plan/ records the hash of the solver file, task
file and witness file it was written from, and the runner and lib stamp of
the run that wrote it; where it is missing or records another hash, the script
first restores it from the plans kept under `.cache/plans/`, which every
`--out` directory shares, and reruns the determination plan of the solver,
without the moved witnesses that the plan file does not hold, in a worker
process where none is kept for that hash (`arclog_convert.plans`). With
`--require-current-lib`, a plan file or a kept plan is also current only where
it records the current runner and lib stamp, so that a change in the runner or
the lib reruns the plan of every solver whose stamp differs. The
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
A pass removes each atom that another atom of the same conjunction implies
(`arclog_convert.implied`): it runs on the text of the solver and on the text of each case, before the projection pass,
which folds a relation the removal leaves a projection, and after it; it runs as well on the copy under `CORPUS`, before
the projection pass.
The same pass removes a membership atom (`(dir_elem *D)`) whose label a later atom of the conjunction makes at a column of
the atom's type or below, which is the static prune's rule `membership.implied_later`
(`engine/arclog/src/program/static_prune.rs`); the pass's text says where it applies.
Where the later atom is on a relation of the program, the case files drop it (`_typed_membership`), with the column types
that the checker gives the sites in `StudyProgram.render_json`; the run writes the case files of each solver whose text holds
such a pair.
A form the script cannot translate is written literally, under a
`;; TODO <kind>: ...` comment.
A clause or a factor that a pass keeps because a block other than the reader's derives its relation again, or because
its relation has clauses in several blocks, holds in the flat program of a case, where each relation has one deriving
form (`projections.Projected.blocked`, `pull_up.Pulled.blocked`). On each solver where a pass keeps one, the run
writes, once every solver stands in `gen/`, the files of the cases whose program read alone differs after the
passes (`convert_cases`): `gen/cases/<stem>/<case>.arclog` and `.arcdata`, with `<case>` as `arclog.case_files`
names the file of the case. A case whose program the passes leave as `arclog.case_files` gives it, and a case of
which it gives a fault (the checker refuses the case program read alone), have no files: the run skips that case, and
the summary gives the number of such cases of each solver. A solver none of whose cases has files gets no case files. The passes read Souffle's rows of the whole program
(`pull_up.Rows.single`). After a solver's case files stand, `case_records/` beside `gen/` holds a file `<stem>.sha256`
with two lines: `inputs <hash>`, the inputs hash of the solver (`plans.inputs_hash`: its solver file, task file and
witness file), and `code <hash>`, the hash of the code and the data the passes read (`_cases_code_digest`); a line
`skipped <n>` follows them where the run skipped `n` cases for a fault. A record is
current where its inputs hash is the solver's, whatever its code hash, so that a change in the converter or the lib
leaves the case files of a solver whose files are the same; with `--require-current-code`, a record is current also
only where its code hash is the current one. The run keeps the case files of a solver whose record is current;
otherwise it removes the record and `gen/cases/<stem>/`, and writes the files again, over the pool in parts of the
solver's cases, and writes the record once every part ends with no error. Where the files cannot be made and the
error is a `ValueError` or a `Fault`, the run removes `gen/cases/<stem>/` and the record gets a third line
`error <JSON string>`; that record is current only where its code hash is the current one, with or without the flag, and
the run reports its error without making the files again. A solver that is not converted, or that has no answers, has
neither the directory nor the record.
As each phase it runs ends (`plans`, `conversion`, `cases`), the run prints a line `<phase>: <seconds> s` with that phase's
wall time. Under `scripts/run_heavy.py --cpus <n>`, the processes and threads
the run has going at once, Souffle processes included, are at most `n`.
"""

import ast
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Executor, Future, wait
from functools import cache
from pathlib import Path
from typing import NamedTuple
from engine import checkout
from engine.memo import hash_files, write_whole
from engine.pool import pool_size
from engine.program import Qualifier, Variable
from arclog_convert.implied import drop_implied, drop_typed_membership, has_program_membership
from arclog_convert.libmap import rename as libmap_rename
from arclog_convert.lint_alts import alt_blocks, derived, placements, selects_case
from arclog_convert.lint_read import L, read
from arclog_convert import paths
from arclog_convert.phases import phase, use_out

from arclog_convert.forms import (
    MERGES,
    MERGES_UNMERGED,
    Todo,
    fold_or_lines,
    hoist_shared,
    sink_alt_dets,
    renamed,
)
from arclog_convert.checks import Fold
from arclog_convert.leaves import ScopedName
from arclog_convert.lib import REGISTRY, Col, ColMismatch, LIB_DL, Lib, SIGNATURE
from arclog_convert.names import Checks, check_maps, column_map, dropped, folded, name_map, parity, placed, unchecked, untranslated
from arclog_convert.plans import inputs_hash, refresh_plans
from arclog_convert.projections import project, readers_json
from arclog_convert.pull_up import OUTPUT, Pulled, Rows, drop_columns, pull_up
from arclog_convert.solver import Solver


_LIBS: tuple[Lib, Lib] | None = None

CASES = "cases"
"""The directory of `gen/` that holds, in a directory per solver, the files of the cases whose normal form
`convert_cases` writes."""
PART_CASES = 16
"""The fewest cases of one solver that `convert_cases` gives a worker as a unit of work."""
PARTS_PER_WORKER = 4
"""The parts `convert_cases` makes of a solver's cases for each worker of the pool, at most."""


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
    arclog = sink_alt_dets(hoist_shared(fix_labels(libmap_rename.rename(arclog, insts)), concept_empty))
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


def _ask_all(rows: Rows, texts: Sequence[tuple[str, str]]) -> None:
    """Ask `rows` the questions that the pull-up pass on each (arclog, arcdata) text of `texts` puts, all at once."""
    asked: set[tuple[str, frozenset[str]]] = set()
    for text, data in texts:
        pull_up(text, data, lambda relation, read: bool(asked.add((relation, read))))
    rows.ask(asked)


def _pull_up_all(rows: Rows, texts: Sequence[tuple[str, str]]) -> list[Pulled]:
    """The pull-up pass on each (arclog, arcdata) text of `texts`, with Souffle's rows asked once for all of them."""
    _ask_all(rows, texts)
    return [pull_up(text, data, rows.single) for text, data in texts]


def _drop_cases(stem: str) -> None:
    """Remove the record of the inputs of the case files of `stem`, and then its case files."""
    (paths.CASE_RECORDS / f"{stem}.sha256").unlink(missing_ok=True)
    shutil.rmtree(paths.OUT_DIR / CASES / stem, ignore_errors=True)


def convert_one(stem: str) -> Converted:
    """One solver's arclog and arcdata, its TODO kinds, its merge counts and
    its parameters whose columns do not map onto their proposer's, or the
    error that stopped it, the arclog and the arcdata of its program with
    the check relations, and the answers of `Rows.single` where
    `convert_cases` is to run: a pool worker's unit of work. Where it fails or
    gives no answers, it removes `cases/<stem>/` of `gen/` and the record of
    its inputs, which `convert_cases` writes."""
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
        # an atom the pass removes may leave a clause that only projects one relation, which the projection pass folds
        arclog = drop_implied(pulled.arclog).arclog
        if checked is not None:
            checked = (drop_implied(copy[0].arclog).arclog, checked[1])
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
        arclog = drop_implied(projected.arclog).arclog
        # the cases of a solver where a later atom on a relation of the program makes a membership atom redundant get
        # their files, which drop it (`_typed_membership`)
        if pulled.blocked or projected.blocked or has_program_membership(arclog):
            answers = rows.answers
        if kept.readers:
            names["removed"] = readers_json(kept.readers)
            _write_json(paths.NAMES_DIR, stem, names)
    except Exception as e:  # noqa: BLE001
        _drop_cases(stem)
        return Converted(stem, None, None, Counter(), Counter(), [], {}, f"{type(e).__name__}: {e}", None, None)
    if answers is None:
        _drop_cases(stem)
    return Converted(stem, arclog, arcdata, todo.kinds, merges, unmerged, s.c.col_mismatch, None, checked, answers)


def _module_files(roots: Sequence[str]) -> set[Path]:
    """The file of each module under `src/` that the modules `roots` name or import, with the files of the packages
    they stand in, followed through the imports in those files at any depth. A module that has no file under `src/`
    has none in the set."""
    src = checkout.ROOT / "src"
    files: dict[str, Path] = {}
    todo = list(roots)
    while todo:
        name = todo.pop()
        if name in files:
            continue
        base = src.joinpath(*name.split("."))
        file = base.with_suffix(".py")
        if not file.is_file():
            file = base / "__init__.py"
        if not file.is_file():
            continue
        files[name] = file
        parent = name.rpartition(".")[0]
        if parent:
            todo.append(parent)
        package = name if file.name == "__init__.py" else parent
        for node in ast.walk(ast.parse(file.read_bytes())):
            match node:
                case ast.Import(names=aliases):
                    todo += [alias.name for alias in aliases]
                case ast.ImportFrom(level=level, module=module, names=aliases):
                    held = package.split(".")[:len(package.split(".")) - level + 1] if level else []
                    imported = ".".join([*held, *([module] if module else [])])
                    todo += [imported, *(f"{imported}.{alias.name}" for alias in aliases)]
    return set(files.values())


@cache
def _cases_code_digest() -> str:
    """The hash of the code and the data the case phase reads besides the solvers' texts: the modules that the
    pull-up pass, the projection pass and the implied-atom pass import, followed through their imports under `src/`, this file, the sources
    that the Souffle runs of `Rows` depend on (`cli.common.SOURCES`), and the lib's files. The native streams digest also binds the static-valid
    normalization implementation and registry types."""
    from cli.common import SOURCES
    files = {*_module_files(["arclog_convert.pull_up", "arclog_convert.projections", "arclog_convert.implied"]),
             *checkout.matched(checkout.ROOT, SOURCES), Path(__file__).resolve(), LIB_DL, SIGNATURE, REGISTRY}
    from arclog import streams_digest
    digest = hashlib.sha256(streams_digest().encode())
    hash_files(digest, ((str(path.relative_to(checkout.ROOT)), path) for path in sorted(files)))
    return digest.hexdigest()


type CaseTexts = list[tuple[str, str, str]]
"""The file name, the arclog text and the arcdata text of each case, as `arclog.case_files` gives them."""


class Record(NamedTuple):
    """The content of `case_records/<stem>.sha256`."""

    inputs: str
    """The inputs hash of the solver (`plans.inputs_hash`) that the case files were made from."""
    code: str
    """The hash of the code the case files were made with (`_cases_code_digest`)."""
    error: str | None
    """The error that stopped the case files of the solver, where one did and `REPEATABLE` holds it."""
    skipped: int = 0
    """The number of cases that `arclog.case_files` gave a fault, and that got no files."""


REPEATABLE = ("ValueError", "Fault")
"""The names of the errors of the case files that the same inputs and the same code give again. The record of a
solver that stopped with one holds it; any other error (a full disk, a killed process) leaves no record."""


def _read_record(stem: str) -> Record | None:
    """The record of `stem` in `case_records/`; none where there is no file, or it is not in the form of
    `_write_record`."""
    try:
        lines = (paths.CASE_RECORDS / f"{stem}.sha256").read_text().splitlines()
        fields = dict(line.split(" ", 1) for line in lines)
        error = json.loads(fields["error"]) if "error" in fields else None
        return Record(fields["inputs"], fields["code"], error, int(fields.get("skipped", 0)))
    except (OSError, ValueError, KeyError):
        return None


def _write_record(stem: str, inputs: str, error: str | None = None, skipped: int = 0) -> None:
    """Write the record of `stem` whole: its inputs hash `inputs`, the current code hash, the number `skipped` of
    cases that got a fault where it is not 0, and `error` where one is given."""
    lines = [f"inputs {inputs}", f"code {_cases_code_digest()}", *([f"skipped {skipped}"] if skipped else []),
             *([f"error {json.dumps(error)}"] if error else [])]
    paths.CASE_RECORDS.mkdir(parents=True, exist_ok=True)
    write_whole(paths.CASE_RECORDS / f"{stem}.sha256", ("\n".join(lines) + "\n").encode())


def _standing(stem: str, inputs: str, require_current_code: bool) -> "Cased | None":
    """The outcome of `stem` that its record gives without a run, with `inputs` its inputs hash: that its case files
    stand, where the record is current (see the head of this file), or the error that stopped them, where the record
    holds one and the code hash is the current one; none where the solver's case files are to be made."""
    record = _read_record(stem)
    if record is None or record.inputs != inputs:
        return None
    if record.error is not None:
        return Cased(stem, 0, False, record.error, record.skipped) if record.code == _cases_code_digest() else None
    if require_current_code and record.code != _cases_code_digest():
        return None
    return Cased(stem, 0, True, None, record.skipped)


class Prepared(NamedTuple):
    """What `_prepare_cases` gives for one solver."""

    stem: str
    answers: Answers
    """The answers of `Rows.single` to every question that the pull-up pass puts on the cases."""
    cases: CaseTexts | None
    """The cases to write the files of; none where `error` is set."""
    error: str | None
    skipped: int = 0
    """The number of cases of which `arclog.case_files` gives a fault."""


def _excluded(arcdata: str) -> list[list[str]]:
    """The combinations of alts that the `exclude` records of the arcdata text leave out, each as the names the
    record gives. A case that one selects (`selects_case`) is no case of the solver, and its program may derive a
    relation twice."""
    return [m.group(1).split() for m in re.finditer(r"\(exclude \(([^()]*)\)", arcdata)]


def _prepare_cases(stem: str, answers: Answers) -> Prepared:
    """The first round of the case phase for the solver `stem`, whose record is not current: read the texts of its
    cases, remove the record and the solver's case files, and ask Souffle's rows the questions of the pull-up pass on
    every case, once. `answers` are those `convert_one` found."""
    from arclog import case_files
    try:
        gen = paths.OUT_DIR
        texts = (gen / f"{stem}.arclog").read_text(), (gen / f"{stem}.arcdata").read_text()
        excluded = _excluded(texts[1])
        files = case_files(stem, *texts, str(gen))
        skipped = sum(1 for f in files if f.fault is not None)
        cases = [(f.file, f.arclog, f.arcdata) for f in files
                 if f.fault is None and not any(selects_case(e, f.case.split()) for e in excluded)]
        _drop_cases(stem)
        rows = Rows(stem, json.loads((paths.COLUMNS_DIR / f"{stem}.json").read_text()))
        rows.answers.update(answers)
        _ask_all(rows, [(arclog, arcdata) for _, arclog, arcdata in cases])
        return Prepared(stem, rows.answers, cases, None, skipped)
    except Exception as e:  # noqa: BLE001
        return Prepared(stem, {}, None, f"{type(e).__name__}: {e}")


EQUALITY_RULES = {
    "compose.left_zero": ("C", "B"),
    "compose.right_zero": ("C", "A"),
    "relative.zero_base": ("X_rel", "X"),
    "relative.same": ("X_rel", None),
    "jump.zero": ("Q", "P"),
    "inset_outset.zero": ("B", None),
    "axis_inset_outset.zero": ("B", None),
    "jump_offset.zero": ("V", None),
}
"""The alias and constant rules of `engine/arclog/src/program/static_prune.rs` (`classify_atom`), by name: the column
whose label the atom makes, and the column whose label it equals, or none where it equals `0`."""


def _equality_edit(text: str, match: dict) -> tuple[int, int, str] | None:
    """The edit of `text` that writes the atom of the static-prune `match` as the equality binding
    `(= *X Y)` that the match gives, where the atom is a top-level conjunct of a `RULE` or `DET` body and each
    conjunct up to it is an atom, a comparison or a `NOT` atom; none elsewhere. The decoder with static pruning
    classifies only such atoms (`check_static_prune` in `engine/arclog/src/decode/mod.rs`)."""
    from arclog_convert.pull_up import atom_sites
    path, rule = match["path"], EQUALITY_RULES.get(match["rule"])
    if match["class"] not in ("alias", "constant") or match.get("replacement") is None or rule is None \
            or len(path) != 3 or path[1] != 0:
        return None
    forms = [x for x in read(text) if isinstance(x, L)]
    if path[0] >= len(forms) or forms[path[0]].head not in ("RULE", "DET"):
        return None
    body = forms[path[0]].items[2:]
    if path[2] >= len(body) or any(
            not isinstance(x, L) or x.head in ("OR", "IF", "ALL")
            or x.head == "NOT" and (len(x.items) != 2 or not isinstance(x.items[1], L) or x.items[1].head in ("OR", "IF", "ALL"))
            for x in body[:path[2] + 1]):
        return None
    atom = body[path[2]]
    sites = atom_sites(atom)
    out_column, equal_column = rule
    if sites is None or out_column not in sites or sites[out_column].mark != "*" or sites[out_column].label is None:
        return None
    if equal_column is None:
        equal = "0"
    elif equal_column in sites and sites[equal_column].mark == "" and sites[equal_column].label is not None:
        equal = sites[equal_column].label
    else:
        return None
    return atom.start, atom.end, f"(= *{sites[out_column].label} {equal})"


def _typed_membership(text: str) -> str:
    """`text`, a case program, with each membership atom dropped that a later atom on a relation of the program makes
    redundant, as `arclog_convert.implied` gives for an atom on a lib relation: the types of the columns of the program's
    relations are those that the checker gives the sites in `StudyProgram.render_json` (`typed_sites.arguments`,
    `column_type`), which the pass in Python cannot infer. A text that the engine does not read stays as it is."""
    from arclog import DecodeSettings, StudyProgram
    while True:
        try:
            arguments = json.loads(StudyProgram.from_sexp(text, DecodeSettings.corpus()).render_json())["typed_sites"]["arguments"]
        except ValueError:
            return text
        columns = {tuple(a["site_path"]): a["column_type"] for a in arguments if a["column_type"]}
        step = drop_typed_membership(text, lambda path, types: columns.get(path) in types)
        if step is None:
            return text
        text = step


EQUALITY_REFUSAL = "static prune: use the admitted equality binding"
"""The refusal of the decoder with static pruning at an alias or constant atom whose equality binding the checker
admits (`check_static_prune` in `engine/arclog/src/decode/mod.rs`)."""

SAMPLER_DECODE = dict(rule_tests=False, table_work_cap=1 << 21, static_pruning=True)
"""The decode settings of the sampler (`model/study/sampler/live_try.py`), with a deadline that a loaded machine does
not reach."""


def _equality_refusal(stem: str, text: str) -> list[int] | None:
    """The path of the token at which the decoder, with the sampler's settings on the task `stem` with no test output,
    refuses the program `text` with `EQUALITY_REFUSAL`; none where it refuses it otherwise or takes it."""
    import arclog
    from arc.task import TASKS_DIR
    task = json.loads((TASKS_DIR / f"{stem}.json").read_text())
    for pair in task["test"]:
        pair.pop("output", None)
    session = arclog.Session(arclog.Task.from_json(json.dumps(task), arclog.World.Open),
                             arclog.DecodeSettings(**SAMPLER_DECODE), session_bytes=2 << 30)
    ids, model, token_paths = arclog.StudyProgram.from_sexp(text, session.settings).decode_stream()
    decoder = session.decoder()
    for token, stepped, path in zip(ids, model, token_paths):
        if stepped:
            try:
                decoder.step(token)
            except (arclog.Refusal, arclog.Fault) as e:
                return list(path) if EQUALITY_REFUSAL in str(e) else None
    return None


def _equality_bindings(stem: str, text: str, matches: list[dict]) -> str:
    """`text`, the program of a case of the solver `stem`, with each atom at which the decoder refuses it with
    `EQUALITY_REFUSAL` written as its equality binding, one at a time. The refused atom is the alias or constant atom
    that `_equality_edit` finds among the static-prune `matches` in the form of the refused token, the last before the
    token's conjunct. `matches` are those of `text`."""
    from arclog import DecodeSettings, StudyProgram
    while True:
        edits = {tuple(m["path"]): edit for m in matches if (edit := _equality_edit(text, m)) is not None}
        refused = _equality_refusal(stem, text) if edits else None
        if refused is None:
            return text
        before = [path for path in edits if path[0] == refused[0]
                  and (len(refused) < 3 or refused[1] != 0 or path[2] < refused[2])]
        if not before:
            return text
        start, end, equality = edits[max(before)]
        text = text[:start] + equality + text[end:]
        matches = json.loads(StudyProgram.from_sexp(text, DecodeSettings.corpus()).static_prune_json())["matches"]


def _write_cases(stem: str, answers: Answers, part: CaseTexts) -> tuple[str, int, str | None]:
    """The second round of the case phase for the cases `part` of the solver `stem`: write the files of those whose
    normal form differs from the case as `arclog.case_files` gives it, `gen/cases/<stem>/<case>.arclog` and
    `.arcdata`. The normal form is the pull-up and projection passes (which read
    Souffle's rows through `Rows.single`), the implied-atom pass, deletion of native static-valid
    tests, then `_equality_bindings`. Deletion reads only the checked program, and `_equality_bindings` the decoder on
    the task's inputs, not task rows.

    Gives the stem, the number of cases it wrote files of, and the error that stopped it."""
    try:
        from arclog import DecodeSettings, StudyProgram
        columns = json.loads((paths.COLUMNS_DIR / f"{stem}.json").read_text())
        rows = Rows(stem, columns)
        rows.answers.update(answers)
        written = []
        for file, arclog, arcdata in part:
            pulled = pull_up(arclog, arcdata, rows.single)
            text = project(drop_implied(pulled.arclog).arclog, arcdata, drop_columns(columns, pulled.dropped)).arclog
            text = drop_implied(text).arclog
            # The corpus draw and Decoder use this same native classifier.
            # It edits original AST paths, preserves clause interfaces, refuses
            # removal of a binder, and re-resolves/checks the normalized case.
            # A case that holds a DEMONSTRATED form is no study input, so the classifier does not read it.
            if "(DEMONSTRATED " not in text:
                text = _typed_membership(text)
                program = StudyProgram.from_sexp(text, DecodeSettings.corpus())
                # With `normalize=True` the report also holds a provenance record of megabytes, which this pass does
                # not use. The call is made only for a case in which the classifier finds a test to delete.
                matches = json.loads(program.static_prune_json())["matches"]
                if any(m["class"] == "valid" for m in matches):
                    pruned = json.loads(program.static_prune_json(normalize=True))
                    if pruned["removed_atom_paths"]:
                        text = pruned["normalized_program_sexp"]
                        matches = json.loads(StudyProgram.from_sexp(text, DecodeSettings.corpus()).static_prune_json())["matches"]
                text = _equality_bindings(stem, text, matches)
            if text != arclog:
                written.append((file, text, arcdata))
        directory = paths.OUT_DIR / CASES / stem
        if written:
            directory.mkdir(parents=True, exist_ok=True)
        for file, text, arcdata in written:
            (directory / f"{file}.arclog").write_text(text)
            (directory / f"{file}.arcdata").write_text(arcdata)
    except Exception as e:  # noqa: BLE001
        return stem, 0, f"{type(e).__name__}: {e}"
    return stem, len(written), None


class Cased(NamedTuple):
    """What `convert_cases` gives for one solver."""

    stem: str
    written: int
    """The number of cases it wrote files of."""
    kept: bool
    """Whether the solver's case files stood as the record says, so that the run wrote none."""
    error: str | None
    skipped: int = 0
    """The number of cases of the solver that got no files for a fault of `arclog.case_files`."""


def _submit[**P, R](pool: Executor | None, fn: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> Future[R]:
    """A future of `fn(*args, **kwargs)` on `pool`, or, where there is no pool, one that holds the result of the call."""
    if pool is not None:
        return pool.submit(fn, *args, **kwargs)
    done: Future[R] = Future()
    done.set_result(fn(*args, **kwargs))
    return done


def convert_cases(pool: Executor | None, workers: int, asked: Mapping[str, Answers],
                  require_current_code: bool = False) -> list[Cased]:
    """Write the files of the cases of the solvers `asked` names, whose normal form differs from the case as `gen/`
    gives it, `gen/cases/<stem>/<case>.arclog` and `.arcdata`, with `<case>` as `arclog.case_files` gives it. `asked`
    gives, by solver, the answers of `Rows.single` that `convert_one` found. A case of which `arclog.case_files`
    gives a fault gets no files. It reads the texts, the column map and the files of the solvers `gen/` holds that
    `convert_one` and the run wrote, so it runs after every solver is converted, and it writes nothing but those files
    and the records of `case_records/`.

    A solver whose record is current (`_standing`) keeps its case files, or, where the record holds an error, gives
    that error, with no work in a worker; the code hash is read only where the flag `require_current_code` is set or a
    record holds an error. For the others the pool runs two rounds, the second of a solver beginning as its first
    ends: `_prepare_cases` per solver, and `_write_cases` per part of its cases, `workers` times `PARTS_PER_WORKER`
    parts at most. The record of a solver is written once each of its parts ends, with the error where one of them
    stopped with a `REPEATABLE` one.

    Gives the outcome of each solver, the largest solver file first."""
    order = sorted(asked, key=lambda t: -(paths.SOLVERS / f"{t}.dl").stat().st_size)
    inputs = {stem: inputs_hash(stem, paths.SOLVERS) for stem in order}
    outcomes: dict[str, Cased] = {}
    for stem in order:
        if (standing := _standing(stem, inputs[stem], require_current_code)) is not None:
            outcomes[stem] = standing
    preparing = {_submit(pool, _prepare_cases, stem, asked[stem]) for stem in order if stem not in outcomes}
    pending: set[Future] = set(preparing)
    left: Counter[str] = Counter()
    written: Counter[str] = Counter()
    errors: dict[str, str] = {}
    skipped: Counter[str] = Counter()

    def finish(stem: str) -> None:
        error = errors.get(stem)
        if error is None:
            _write_record(stem, inputs[stem], skipped=skipped[stem])
        elif error.partition(":")[0] in REPEATABLE:
            shutil.rmtree(paths.OUT_DIR / CASES / stem, ignore_errors=True)
            _write_record(stem, inputs[stem], error, skipped[stem])
        outcomes[stem] = Cased(stem, written[stem], False, error, skipped[stem])

    while pending:
        done, pending = wait(pending, return_when=FIRST_COMPLETED)
        for future in done:
            if future in preparing:
                prepared = future.result()
                stem = prepared.stem
                skipped[stem] = prepared.skipped
                if prepared.error is not None or not prepared.cases:
                    if prepared.error is not None:
                        errors[stem] = prepared.error
                    finish(stem)
                else:
                    size = max(PART_CASES, -(-len(prepared.cases) // (workers * PARTS_PER_WORKER)))
                    parts = [prepared.cases[i:i + size] for i in range(0, len(prepared.cases), size)]
                    left[stem] = len(parts)
                    pending |= {_submit(pool, _write_cases, stem, prepared.answers, part) for part in parts}
            else:
                stem, count, error = future.result()
                written[stem] += count
                if error is not None:
                    errors.setdefault(stem, error)
                left[stem] -= 1
                if left[stem] == 0:
                    finish(stem)
    return [outcomes[stem] for stem in order]


def main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="python -m arclog_convert.convert")
    parser.add_argument("--out", type=Path, help="the directory to write under, in place of `arclog_convert.out`; required in a linked worktree unless `ARCLOG_OUT` is set")
    parser.add_argument("--require-current-lib", action="store_true", help="rerun the determination plan of each solver whose plan file records another runner and lib stamp than the current one; otherwise a plan is current where its inputs hash matches")
    parser.add_argument("--require-current-code", action="store_true", help="make the case files again of each solver whose case record holds another converter code hash than the current one; otherwise a case record is current where its inputs hash matches")
    parser.add_argument("stems", nargs="*", help="the solvers to convert; every solver where none is given")
    args = parser.parse_args(argv)
    use_out(args.out)
    stems = args.stems or sorted(p.stem for p in paths.SOLVERS.glob("*.dl"))
    with phase("plans"):
        refresh_plans(stems, args.require_current_lib)
    print(f"{paths.OUT_DIR}:")
    with phase("conversion"):
        converted = convert_into(stems, paths.OUT_DIR, args.require_current_code)
    return int(len(converted) < len(stems))


def convert_into(stems: list[str], out: Path, require_current_code: bool = False) -> list[str]:
    """Convert `stems` into `out` over a process pool, print the
    summary, and give the stems it converted. `require_current_code` is
    that of `convert_cases`."""
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
    stubbed: list[str] = []
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
        if any(k.startswith("no-det-") or k in ("unresolved", "parse-key") for k in kinds):
            # a `(DET &x)` with no body has no columns, and the engine reads no relation of an unresolved name or of
            # a parse the key of a read widens, so each case of the solver fails its checks
            stubbed.append(stem)
            _drop_cases(stem)
        elif answers is not None:
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
        cased = convert_cases(pool, workers, asked, require_current_code)
    for c in cased:
        if c.error is not None:
            failed.append((c.stem, f"the case files: {c.error}"))
            converted.remove(c.stem)
    ok = [c for c in cased if c.error is None]
    if pool is not None:
        pool.shutdown()
    print(f"converted {len(stems) - len(failed)} of {len(stems)}; {clean} with no TODO")
    print(f"case files: {sum(c.written for c in ok)} cases of {sum(1 for c in ok if c.written)} solvers; "
          f"the passes ran on the cases of {sum(1 for c in ok if not c.kept)} solvers; "
          f"kept the case files of {sum(1 for c in ok if c.kept)} solvers")
    faulted = {c.stem: c.skipped for c in ok if c.skipped}
    if faulted:
        print(f"cases skipped, the checker refuses the case program read alone: {sum(faulted.values())} cases of "
              f"{len(faulted)} solvers ({', '.join(f'{s} {n}' for s, n in sorted(faulted.items()))})")
    if stubbed:
        print(f"case files skipped, no determination plan or an unresolved relation: {len(stubbed)} stems ({', '.join(sorted(stubbed))})")
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
