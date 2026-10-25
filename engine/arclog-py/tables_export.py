"""Write the tables of the corpus's case programs as an index and flat int32 value arrays.

    python engine/arclog-py/tables_export.py <out dir> [--all-cases] [--bodies] [--projection-cap N] [<task id> ...]

It needs an interpreter with `arclog`, pandas and pyarrow, such as the LM work's venv.

Runs one `arclog.corpus_tables` call per task id, the largest `.arcdata` file first, on a queue of N Python threads, where N is `ARCLOG_THREADS`
if set and `os.cpu_count()` otherwise. The script sets `ARCLOG_THREADS=1` for the engine, so each call runs on one
worker, and each thread starts the next task as its task ends. Every 10 s the tasks ended since the last write are
written as a part. Writes to <out dir>:
  values/<task>/<case>.i32   raw int32 (np.fromfile), every row of the case: the rows of each entry, of each DET
                             at each entry's assignment, and of each projection at each entry, each row's cells in
                             column order (see `arclog.decode.columns`)
  parts/<k>.<name>.parquet   the rows of one part
  parts/<k>.report.txt       the fault lines of the part's tasks
  parts/<k>.tasks.txt        the task ids of the part, one per line, written last: a part is whole where it stands
  index.parquet    one row per (table, example, entry): task, case, concept, the table's columns, the entry's columns
  tables.parquet   one row per table: its columns, and its depth in the dependency graph (0 for an evidence table and each fact
                   relation), its candidate keys (`keys`, a list of lists of column indexes: the columns of each `ONE` mark of
                   its clause, none for `(ONE)`, the row's columns of a `CHOOSE`'s chosen relation, and `E` with `P` of
                   `ex_input` and `ex_output`; the registry declares no key of a component's output, so any other table
                   gives none), and, for the table of the relation at which the replay's consistency test found the grid
                   columns of `ex_output`, the index of its Position column (`output_position`) and of its Color column
                   (`output_color`), which map to `P` and `Col` of `ex_output`, with the entry's example as `E`; -1 in each
                   other table
  flows.parquet    one row per source of a column of a table, keyed by task, case, `table` and `column`: `kind` (copy 0,
                   computed 1, constant 2, lib name 3), `source_table` (the row of the source's table in the case, -1 where
                   the case gives none: a lib relation, a constant, a lib name), `source_relation`
                   (the relation as the program spells it, `ex_input` for a read of `input`, or the lib name), `source_column`
                   (its column index, -1 for a constant or a lib name, -2 for the example of the source's entry), `det` (the
                   source's place in the table's `det_relations`, -1 where it is none) and `atom` (the path of the atom that
                   reads it, empty where none does). A reader labels a column of `ex_output` as computed from the input where
                   every source it reaches through the flows is `ex_input` or a constant, as computed from the train outputs
                   where one is `ex_output` or a `DET` (a determination keeps the values at which the program solves every
                   train pair), and as neither where it reaches no source
  assigned.parquet one row per DET at an entry's assignment: task, case, entry, det, rows, offset
  projections.parquet    one row per projection (columns) and projection_rows.parquet one row per projection at an entry
  orientations.json  [encoding, name] of each orientation constant; an orientation cell is its encoding
  orientation_types.json  [type name, cells] of each orientation type without a parameter (Dir, DiagDir, Dir8, Axis, DiagAxis,
                   Axis4, D4, C4, Sym, Sense): the cells its columns admit; a Pose type admits D4's
  parts/<k>.checks.txt, checks.txt  one line `<task> <case>: <invariant>: <detail>` per violation of an invariant of this layout
                   that `export_checks.check_case` checks on each case (tables, entries and runs, flows, the cells against their
                   column types, keys, the evidence tables against the task file);
                   `python engine/arclog-py/export_checks.py <out dir>` checks an existing export, and the copy flows' values
                   against their source columns, which the export does not check
  settings.json    the options the calls run under, written before the first task: {"projection_cap": N, "step_cap": N, "parts": [...]} with 10000 and 10000 (null for --step-cap 0, no cap)
                   where no --projection-cap is given, each other option given, and the names of the parts the run writes
  report.txt       the fault lines, by task id
The whole files hold the rows of the parts sorted by task, in the order of the parts within a task.
A run on an out dir whose `settings.json` gives other options prints both and exits with status 2. Otherwise the
run takes as done each task id of a `parts/*.tasks.txt`, removes the files of a part with no `tasks.txt`, runs the
other tasks, and ends with the files a run that was not stopped gives.
Every 10 s a line gives `<k> of <n> tasks ended, <s> s, about <t> s left, running past 10 s: <id> <s> s <p>% ...`:
the ended tasks (done ones of an earlier run included), the seconds since the start, the seconds left (`?` while no
task has ended in this run), then the tasks running past 10 s, longest first (the first 10 and a count of the rest
where more), each with the seconds since its call started and the share of its model steps done, as
arclog.ReplayProgress gives them.

`export_streams(out, task, streams, names=None, settings=None, bodies=False, step_cap=10000)` writes the same layout
for the token streams of one task, for a caller that imports the module: `streams` is a list of `(ids, model)`
pairs as `arclog.stream_tables` takes them. `out` must not exist or be empty (else `FileExistsError`). Its
`report.txt` holds, for each stream replayed, `<task> <case>: ended <kind> at token <index>` (`<kind>` the
consistency of the last `RULE` clause the stream ends, or `ended none`), then the fault line of each stream that
faults (its tables up to the fault are kept) or lies past the cap. It writes no `settings.json`.
"""
import collections, json, os, sys, glob, time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import numpy as np
import pandas as pd
import arclog
import export_checks

ROOT = os.path.dirname(os.path.abspath(__file__)) + "/../.."
CORPUS, TASKS = f"{ROOT}/work/arclog/gen", f"{ROOT}/data/tasks"
PARTS = ("tables", "entries", "assigned", "projections", "projection_rows", "flows")


def frame(case, part):
    d = {k: (np.frombuffer(v, dtype=case.dtypes[f"{part}.{k}"]) if f"{part}.{k}" in case.dtypes else v)
         for k, v in getattr(case, part).items()}
    n = len(next(iter(d.values()))) if d else 0
    return pd.DataFrame(dict(task=[case.task] * n, case=[case.case] * n, concept=[case.concept] * n, **d))


def write_part(out, k, results):
    """Writes the part `k` of the (task id, cases, lines) results, the `tasks.txt` last."""
    frames, checks = {p: [] for p in PARTS}, []
    orientation = export_checks.orientation_sets(arclog.orientation_types())
    for task, cases, _ in results:
        task_json = json.load(open(f"{TASKS}/{task}.json")) if cases else None
        for case in cases:
            os.makedirs(f"{out}/values/{case.task}", exist_ok=True)
            with open(f"{out}/values/{case.task}/{case.case}.i32", "wb") as sink:
                sink.write(case.values)
            of_case = {p: frame(case, p) for p in PARTS}
            for p in PARTS:
                frames[p].append(of_case[p])
            checks += [f"{task} {case.case}: {line}" for line in export_checks.check_case(of_case, np.frombuffer(case.values, np.int32), task_json, orientation, copies=False)]
    for p, fs in frames.items():
        if fs:
            pd.concat(fs).to_parquet(f"{out}/parts/{k:05d}.{p}.parquet")
    with open(f"{out}/parts/{k:05d}.report.txt", "w") as sink:
        sink.write("".join(line + "\n" for _, _, lines in results for line in lines))
    with open(f"{out}/parts/{k:05d}.checks.txt", "w") as sink:
        sink.write("".join(line + "\n" for line in checks))
    with open(f"{out}/parts/{k:05d}.tasks.tmp", "w") as sink:
        sink.write("".join(t + "\n" for t, _, _ in results))
    os.rename(f"{out}/parts/{k:05d}.tasks.tmp", f"{out}/parts/{k:05d}.tasks.txt")


def main(out, task_ids, **options):
    workers = int(os.environ.get("ARCLOG_THREADS") or os.cpu_count())
    os.environ["ARCLOG_THREADS"] = "1"
    os.makedirs(f"{out}/parts", exist_ok=True)
    settings = {**options, "parts": list(PARTS)}
    if os.path.exists(f"{out}/settings.json"):
        found = json.load(open(f"{out}/settings.json"))
        if found != settings:
            print(f"{out} holds settings {json.dumps(found)}, this run has {json.dumps(settings)}", file=sys.stderr)
            sys.exit(2)
    json.dump(settings, open(f"{out}/settings.json", "w"))
    done, k = set(), 0
    for f in sorted(glob.glob(f"{out}/parts/*")):
        stem = os.path.basename(f).split(".")[0]
        if os.path.exists(f"{out}/parts/{stem}.tasks.txt"):
            k = max(k, int(stem) + 1)
            if f.endswith(".tasks.txt"):
                done |= set(open(f).read().split())
        else:
            os.remove(f)
    # The largest .arcdata files first: the slowest tasks are among them, so they start early.
    todo = sorted((t for t in task_ids if t not in done), key=lambda t: (-os.path.getsize(f"{CORPUS}/{t}.arcdata"), t))
    started, progress = {}, {}

    def run(task):
        progress[task] = arclog.ReplayProgress()
        started[task] = time.time()
        cases, lines = arclog.corpus_tables(CORPUS, TASKS, task_ids=[task], progress=progress[task], **options)
        return task, cases, lines

    pool = ThreadPoolExecutor(workers)
    futures = {t: pool.submit(run, t) for t in todo}
    pending, results, ended, begin, last = set(futures.values()), [], len(done), time.time(), time.time()
    failure = None
    while pending and not failure:
        got, pending = wait(pending, timeout=max(0.0, last + 10 - time.time()), return_when=FIRST_COMPLETED)
        for f in got:
            if f.exception():
                failure = failure or f.exception()
            else:
                results.append(f.result())
        if time.time() - last >= 10 or not pending or failure:
            if results:
                write_part(out, k, results)
                k, ended, results = k + 1, ended + len(results), []
            now = time.time()
            running = sorted((t for t in started if started[t] < now - 10 and futures[t] in pending), key=lambda t: started[t])
            shown = " ".join(f"{t} {now - started[t]:.0f} s {100 * progress[t].done / progress[t].total if progress[t].total else 0:.0f}%" for t in running[:10])
            more = f" and {len(running) - 10} more" if len(running) > 10 else ""
            ran = ended - len(done)
            left = f"{(now - begin) * (len(task_ids) - ended) / ran:.0f}" if ran else "?"
            print(f"{ended} of {len(task_ids)} tasks ended, {now - begin:.0f} s, about {left} s left, running past 10 s: {shown}{more}", flush=True)
            last = now
    if failure:
        pool.shutdown(wait=False, cancel_futures=True)
        raise failure
    pool.shutdown()
    merge(out)


def merge(out):
    """Writes the whole files, `orientations.json` and `report.txt` from the parts of `out`, and prints the counts."""
    parts = lambda p: sorted(glob.glob(f"{out}/parts/*.{p}.parquet"))
    lines = [l for f in sorted(glob.glob(f"{out}/parts/*.report.txt")) for l in open(f).read().splitlines()]
    lines.sort(key=lambda l: l.split()[0])
    json.dump(sorted(arclog.orientation_names()), open(f"{out}/orientations.json", "w"))
    json.dump(arclog.orientation_types(), open(f"{out}/orientation_types.json", "w"))
    open(f"{out}/report.txt", "w").write("\n".join(lines) + "\n")
    checks = [l for f in sorted(glob.glob(f"{out}/parts/*.checks.txt")) for l in open(f).read().splitlines()]
    checks.sort(key=lambda l: l.split()[0])
    open(f"{out}/checks.txt", "w").write("".join(l + "\n" for l in checks))
    by_invariant = collections.Counter(l.split(": ", 1)[1].split(": ", 1)[0] for l in checks)
    summary = f", {len(checks)} check lines" + (": " + ", ".join(f"{inv} {n}" for inv, n in sorted(by_invariant.items())) if checks else "")
    if not parts("tables"):
        print(f"0 index rows, {len(lines)} fault lines{summary}")
        return
    whole = {p: pd.concat([pd.read_parquet(f) for f in parts(p)]).astype({"concept": bool}).sort_values("task", kind="stable") for p in PARTS}
    tables, entries = whole["tables"], whole["entries"]
    tables["table"] = tables.groupby(["task", "case"]).cumcount()
    entries["entry"] = entries.groupby(["task", "case"]).cumcount()
    entries.merge(tables, on=["task", "case", "table"], suffixes=("", "_table")).to_parquet(f"{out}/index.parquet")
    for p in ("tables", "assigned", "projections", "projection_rows", "flows"):
        whole[p].to_parquet(f"{out}/{p}.parquet")
    print(f"{len(entries)} index rows, {len(lines)} fault lines{summary}")


def export_streams(out, task, streams, names=None, settings=None, bodies=False, step_cap=10000):
    """Writes the tables export of the token `streams` of `task` to the new or empty directory `out`.

    `streams`, `names`, `settings` and `bodies` are those of `arclog.stream_tables`, and `step_cap` is its
    cap, 10000 as in the corpus export. The layout is that of `main`, with one part and no `settings.json`; its
    `report.txt` holds, for each stream replayed, the line `<task> <case>: ended <kind> at token <index>` (or
    `ended none`) and then the fault lines of the streams that fault or lie past the cap.
    """
    if os.path.exists(out) and os.listdir(out):
        raise FileExistsError(f"{out} exists and is not empty")
    os.makedirs(f"{out}/parts", exist_ok=True)
    cases, lines = arclog.stream_tables(task, TASKS, streams, names=names, settings=settings, bodies=bodies, step_cap=step_cap)
    write_part(out, 0, [(task, cases, lines)])
    merge(out)


if __name__ == "__main__":
    args, options, ids = sys.argv[2:], {"projection_cap": 10000, "step_cap": 10000}, []
    while args:
        a = args.pop(0)
        if a == "--all-cases": options["all_cases"] = True
        elif a == "--bodies": options["bodies"] = True
        elif a == "--projection-cap": options["projection_cap"] = int(args.pop(0))
        elif a == "--step-cap": options["step_cap"] = int(args.pop(0)) or None
        else: ids.append(a)
    ids = ids or sorted(os.path.basename(f)[:-len(".arcdata")] for f in glob.glob(f"{CORPUS}/*.arcdata"))
    main(sys.argv[1], ids, **options)
