"""The comparison of each converted task's relations with Souffle's rows, and
the report of the relations that differ.

    uv run python -m arclog_convert.row_parity [--out <dir>] [<stem> ...]

The command checks the task files of `arclog_convert.out`, or of `--out`,
with no conversion: the program under `CORPUS`, which is the one under `gen/`
with the check relations of the relations the converter folds
(`arclog_convert.checks`) and the clauses of the relations the projection pass
removes (`arclog_convert.projections`), and the name map and the column map; in a linked
worktree it writes no record without
`--out` or `ARCLOG_OUT`, and it rewrites no baseline. `arclog_convert.verify` runs the same check on the
solvers it checks. For each task, `arclog-cli row-parity` compares the rows
of each relation of the cases the check runs, the concept case and the first
case that takes each ALT that no case before it takes, with the rows of
Souffle's run of the solver (`parity.rerun.case_rows`), as
`engine/arclog-cli/src/row_parity.rs` gives; its lines are `<task>
<relation> <verdict> <detail>`, with the verdict `equal`, `differ`, `fault`,
`skip` or `uncompared`. The line of a relation that the solver's program
outputs, and of each arclog relation of the name map, is one of these. `skip`
is for a relation that holds no row the solver derives: an input of the
Souffle program, a lib relation that no clause of the solver writes, a
relation of facts alone, or a relation of the converter's Souffle text, where
no arclog relation stands for it. `uncompared`
is for each other relation the check does not compare: one with no entry in
the column map, an arclog relation that no Souffle relation of the run
stands for, a relation that no case it runs has, and a relation that a case
has and no case it runs reads from the `OUT` form, at any depth (in a case, a
relation is compared only where its `OUT` form reads it, or where it is a check
relation of a folded relation, which the case counts as read, or where it is a
relation whose clause the projection pass removes and a form that read it
derives its relation in the case and the `OUT` form reads that relation, or that
relation is itself such a removed relation that the case compares:
`parity.rerun` gives the rule). A line's detail gives
the reason of a `skip` or an `uncompared`, and the case and the pair of any
other verdict. An `equal` line proves that the relation's rows in each case
that derives it and whose `OUT` form reads it, that is a check relation of a folded relation, or that the
projection pass removes and a form that read it derives its relation in, at the stored parameters, are Souffle's rows of it over the
columns the converter maps (`row_parity.rs` gives the rest). For a relation of
the converter's Souffle text (`arclog_convert.parity_text`) that is the rows of
the text's clauses with the solver's program, which says nothing on whether the
clauses hold what the solver means; that rests on the lines of the solver's
relations that read them. The tables export runs none of it.

A task's lines stand in `row_parity/<stem>.json` beside `gen/`, as a record
with these fields: `files`, the sha256 of the task's files as
`train_replay.files_digest` gives them, of its program under `CORPUS`, of its name map and column map, of the
Souffle solver file the conversion read, of the Souffle texts beside the name map
and the forms it instantiates (`lib-forms.dl`), of the Souffle-side code and lib
(`cli.common.stamp`), of the Souffle binary, of the `parity` package, and of
the form of the record (`VERSION`); `sources`, the digest of the engine's
sources; `binary`, the sha256 of the `arclog-cli` binary the run ran; and `lines`,
each `[relation, verdict, detail]`. A task is fresh, and runs nothing, by the
rule of `train_replay.stale_tasks`. The run executes a private copy of the
`arclog-cli` binary (`train_replay.private_binaries`), so a build in the checkout's
`engine/target` during the run does not change it.

The stale tasks run in chunks of `CHUNK` tasks, at most
`parity.snapshot.RECORDS_WORKERS` chunks at once, and at most
`engine.pool.pool_size()`. A chunk has two phases: the Souffle side of each
of its tasks, then one `arclog-cli row-parity` call on the chunk. The first
phase runs in a process of its own that runs that phase alone and exits when
it returns, so that no process keeps the memory of a chunk's Souffle runs for
the call or for the next chunk; that process is bound to one CPU
(`engine.pool.share_env`). The second phase runs in the main process, in the
thread of the chunk, which waits on the call and writes the records. The
Souffle runs go through the run cache. The Souffle side holds the runs of one
case and the entry of one relation at a time, writing a task's rows file as
each entry is made, and `arclog-cli row-parity` reads it one relation at a time.
The call's stderr reaches the run's output: for each task that has run 10 s,
and each further 10 s, a line `row-parity: <task> case <case>: <n> s`.

`row_parity.tsv` is the baseline: a line `<task> <relation> <verdict>
<ticket or ->` (tab-separated) for each task and relation whose verdict is
`differ`, `fault` or `uncompared`, and for each task whose Souffle side gives
no rows, with `*` as the relation. The report covers the tasks the run
covers. It prints a line for each task and relation beyond the baseline, with
its detail; a line for each relation that the task's previous record gives
`equal` and that is not `equal` now; a line for each baseline line that is now
`equal`; and a final line with the count of each verdict, and of each reason
of `skip` and of `uncompared`, and of the lines beyond the baseline. The
exit status is 1 where a line is beyond the baseline or a relation was
`equal` and is not now, and 0 otherwise.
`arclog_convert.verify --accept` rewrites the baseline; `arclog_convert.verify`
gives which lines it rewrites."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from arc.task import TASKS_DIR
from arclog_convert import OUT_ENV, parity_text, paths, train_replay
from engine import checkout
from arclog_convert.plans import bound_to_one_cpu
from engine.pool import pool_size, share_env

BASELINE = Path(__file__).with_name("row_parity.tsv")

VERSION = 5
"""The form of a record."""

CORPUS = paths.CORPUS
"""The directory beside `gen/` that holds, for each converted task, its
program with the check relations of the relations it folds
(`arclog_convert.checks`) and the clauses of the relations the projection pass
removes from the program of `gen/` (`arclog_convert.projections`), the latter
compared in a case only where a form that read the relation derives its relation
there and the `OUT` form reads it (`parity.rerun`), which
`arclog-cli row-parity` reads as its corpus."""

FAILING = ("differ", "fault", "uncompared")
"""The verdicts that the baseline holds and that fail the run."""

CHUNK = 8
"""The tasks one call of `arclog-cli row-parity` takes."""

BINARY = "arclog-cli"

type Line = tuple[str, str, str]
"""A relation, its verdict and its detail."""


def read_baseline(path: Path = BASELINE) -> dict[tuple[str, str], tuple[str, str]]:
    """The verdict and the ticket of each task and relation of the baseline."""
    baseline = {}
    for line in path.read_text().splitlines() if path.exists() else []:
        task, relation, verdict, ticket = line.split("\t")
        baseline[task, relation] = (verdict, ticket)
    return baseline


def write_baseline(baseline: dict[tuple[str, str], tuple[str, str]], path: Path = BASELINE) -> None:
    path.write_text("".join(f"{task}\t{relation}\t{verdict}\t{ticket}\n"
                            for (task, relation), (verdict, ticket) in sorted(baseline.items())))


def files_digest(stem: str, gen: Path, tasks: Path, solvers: Path) -> str:
    """The digest of everything but the engine that decides the lines of `stem`."""
    from cli.common import stamp
    from parity import rerun
    from souffle.install import binary_identity
    digest = hashlib.sha256()
    digest.update(f"{VERSION}\0{train_replay.files_digest(stem, gen, tasks)}\0".encode())
    corpus, names, columns = gen.parent / CORPUS, gen.parent / "names", gen.parent / "columns"
    for path in (corpus / f"{stem}.arclog", corpus / f"{stem}.arcdata", names / f"{stem}.json", names / f"{stem}.dl",
                 names / f"{stem}.determination.dl", columns / f"{stem}.json", solvers / f"{stem}.dl",
                 parity_text.FORMS):
        digest.update((path.read_bytes() if path.exists() else b"") + b"\0")
    digest.update(f"{stamp()}\0{rerun.code_digest()}\0".encode() + binary_identity())
    return digest.hexdigest()


def write_record(records: Path, stem: str, files: str, sources: str, binary: str, lines: list[Line]) -> None:
    records.mkdir(parents=True, exist_ok=True)
    data = {"files": files, "sources": sources, "binary": binary, "lines": [list(line) for line in lines]}
    (records / f"{stem}.json").write_text(json.dumps(data, indent=1) + "\n")


def souffle_side(stems: list[str], work: Path, solvers: Path) -> tuple[dict[str, list[Line]], list[str]]:
    """Write the rows file of each of `stems` under `work`, and give the
    fault lines of the stems that have no rows and the stems that have."""
    from parity import rerun
    faults: dict[str, list[Line]] = {}
    rows = []
    for stem in stems:
        try:
            got = rerun.case_rows(stem, solvers / f"{stem}.dl", work / f"{stem}.json")
        except (rerun.NoSuchCase, FileNotFoundError) as e:
            faults[stem] = [("*", "fault", f"no Souffle rows: {type(e).__name__}: {e}")]
            continue
        if got is not None:
            faults[stem] = [("*", "fault", f"no Souffle rows: {got}")]
            continue
        rows.append(stem)
    return faults, rows


def check_chunk(souffle: ProcessPoolExecutor, stems: list[str], corpus: Path, tasks: Path, records: Path,
                solvers: Path, files: dict[str, str], sources: str, binary: str, tool: Path) -> None:
    """Write the record of each of `stems`: the Souffle side of each, in a
    process of `souffle` that exits when it returns, then one call of the
    `arclog-cli` binary at `tool`, with the digest `binary`, on those that gave
    rows."""
    work = Path(tempfile.mkdtemp(dir=records))
    try:
        lines, rows = souffle.submit(souffle_side, stems, work, solvers).result()
        if rows:
            command = [str(tool), "row-parity", str(corpus), str(tasks), str(work), *rows]
            done = subprocess.run(command, cwd=checkout.ROOT / "engine", stdout=subprocess.PIPE, text=True,
                                  env=share_env(1))
            if done.returncode not in (0, 1):
                raise RuntimeError(f"{' '.join(command)} exited with {done.returncode}")
            for stem in rows:
                lines[stem] = []
            for line in done.stdout.splitlines():
                task, relation, verdict, detail = line.split("\t", 3)
                lines[task].append((relation, verdict, detail))
        for stem in stems:
            write_record(records, stem, files[stem], sources, binary, lines[stem])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def chunks(stems: list[str], solvers: Path) -> list[list[str]]:
    """`stems` in chunks of `CHUNK`, the largest solver files first, so that
    no long task starts last."""
    order = sorted(stems, key=lambda stem: -(solvers / f"{stem}.dl").stat().st_size)
    return [order[i:i + CHUNK] for i in range(0, len(order), CHUNK)]


def check(stems: list[str], out: Path, accept: bool = False) -> int:
    """Check the stale tasks of `stems` under `out`, print the report, and
    give the exit status."""
    from parity.snapshot import RECORDS_WORKERS
    os.environ[OUT_ENV] = str(out)
    gen, corpus, records, tasks, solvers = out / "gen", out / CORPUS, out / "row_parity", TASKS_DIR, paths.SOLVERS
    sources = train_replay.engine_digest()
    files = {stem: files_digest(stem, gen, tasks, solvers) for stem in stems}
    with train_replay.private_binaries() as copy:
        stale = train_replay.stale_tasks(stems, files.__getitem__, records, sources, lambda: copy(BINARY)[1])
        previous = {stem: train_replay.read_record(records, stem) for stem in stale}
        if stale:
            tool, built = copy(BINARY)
            records.mkdir(parents=True, exist_ok=True)
            workers = min(RECORDS_WORKERS, pool_size())
            with (ProcessPoolExecutor(workers, initializer=bound_to_one_cpu, max_tasks_per_child=1) as souffle,
                  ThreadPoolExecutor(workers) as threads):
                futures = [threads.submit(check_chunk, souffle, chunk, corpus, tasks, records, solvers, files, sources,
                                          built, tool)
                           for chunk in chunks(stale, solvers)]
                for future in futures:
                    future.result()
    lines: dict[str, list[Line]] = {}
    for stem in stems:
        record = train_replay.read_record(records, stem)
        assert record is not None
        lines[stem] = [(relation, verdict, detail) for relation, verdict, detail in record["lines"]]
    baseline = read_baseline()
    beyond = regressed = 0
    for stem in stems:
        for relation, verdict, detail in lines[stem]:
            if verdict in FAILING and baseline.get((stem, relation), ("", ""))[0] != verdict:
                beyond += 1
                print(f"{stem}\t{relation}\t{verdict}\t{detail}")
    for stem in stale:
        old = previous[stem]
        if old is None:
            continue
        was = {relation for relation, verdict, _ in old.get("lines", []) if verdict == "equal"}
        for relation, verdict, detail in lines[stem]:
            if relation in was and verdict != "equal":
                regressed += 1
                print(f"{stem}\t{relation}\twas equal and is {verdict}\t{detail}")
    for (stem, relation), (verdict, _) in sorted(baseline.items()):
        if stem in lines and any(r == relation and v == "equal" for r, v, _ in lines[stem]):
            print(f"{stem}\t{relation}\tnow equal; the baseline gives {verdict}")
    verdicts = Counter(verdict for stem in stems for _, verdict, _ in lines[stem])
    reasons = {left: Counter(detail.split(":")[0] for stem in stems for _, verdict, detail in lines[stem] if verdict == left)
               for left in ("skip", "uncompared")}
    print(f"row parity: {len(stale)} tasks checked, {len(stems) - len(stale)} taken from their record; "
          f"{', '.join(f'{n} {v}' for v, n in sorted(verdicts.items()))}; "
          + "; ".join(f"{left}: {', '.join(f'{n} {r}' for r, n in sorted(counts.items()))}" for left, counts in reasons.items())
          + f"; {beyond} beyond the baseline, {regressed} no longer equal")
    if accept:
        kept = {k: v for k, v in baseline.items() if k[0] not in lines}
        for stem in stems:
            for relation, verdict, _ in lines[stem]:
                if verdict in FAILING:
                    kept[stem, relation] = (verdict, baseline.get((stem, relation), ("", "-"))[1])
        write_baseline(kept)
    return 1 if beyond or regressed else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m arclog_convert.row_parity")
    parser.add_argument("--out", type=Path, help="the directory that holds gen/, in place of `arclog_convert.out`; required in a linked worktree unless `ARCLOG_OUT` is set")
    parser.add_argument("stems", nargs="*", help="the solvers to check; every solver of gen/ where none is given")
    args = parser.parse_args(argv)
    from arclog_convert import writable_out
    root = args.out.resolve() if args.out else writable_out()
    stems = args.stems or sorted(p.stem for p in (root / "gen").glob("*.arclog"))
    return check(stems, root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
