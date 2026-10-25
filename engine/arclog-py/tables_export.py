"""Write the tables of the corpus's case programs as an index and flat int32 value arrays.

    python engine/arclog-py/tables_export.py <out dir> [--all-cases] [--bodies] [--projection-cap N] [--previous <export dir>] [<task id> ...]

It needs an interpreter with `arclog`, pandas and pyarrow, such as the LM work's venv. A change to this module, or to the engine code that writes the export's files (`engine/arclog/src/eval/flows.rs`, `engine/arclog/src/decode/`), runs `engine/arclog-py/roundtrip_check.py` with an `arclog` built from its tree before its merge.

Runs one `arclog.corpus_tables` call per task id, the longest first, on a queue of N Python threads, where N is `ARCLOG_THREADS`
if set and `os.cpu_count()` otherwise. The order is that of the seconds each task took in the export `--previous` gives
(see `parts/<k>.tasks.txt`), then the tasks that export does not give, or all tasks where none is given, by the largest
`.arcdata` file first. With `--previous`, each task whose key (the sha256 of its `work/arclog/gen` `.arclog` and `.arcdata`, its task file, every file of
the installed `arclog` package, this module, `export_checks.py` and the text of `settings.json`) equals the key in that export's
`tasks.txt` lines is not replayed: its rows, values (hard-linked), fault lines, check lines and `tasks.txt` lines are those of that export,
written as parts of the out dir, and the run prints the counts reused and to replay first. An export with no key in its lines gives no reuse.
`--previous` changes no output file. The script sets `ARCLOG_THREADS=1` for the engine, so each call runs on one
worker, and each thread starts the next task as its task ends. Every 10 s the tasks ended since the last write are
written as a part. Writes to <out dir>:
  values/<task>/<case>.i32   raw int32 (np.fromfile), every row of the case: the rows of each entry, of each DET
                             at each entry's assignment, and of each projection at each entry, each row's cells in
                             column order (see `arclog.decode.columns`)
  parts/<k>.<name>.parquet   the rows of one part
  parts/<k>.report.txt       the fault lines of the part's tasks
  parts/<k>.tasks.txt        one line `<task> <seconds> <key>` per task of the part, the wall seconds of its call to 0.1 s and
                             the task's reuse key (see `--previous`; a bare task id where the writer gives none), written last: a part is whole where it stands
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
                   (its column index, -1 for a constant or a lib name, -2 for the example of the source's entry; with `det` >= 0 the index
                   is into the table's `det_types[det]`, the `DET`'s relation as the reading table holds it in assigned.parquet), `det` (the
                   source's place in the table's `det_relations`, -1 where it is none) and `atom` (the path of the atom that
                   reads it, empty where none does). A reader labels a column of `ex_output` as computed from the input where
                   every source it reaches through the flows is `ex_input` or a constant, as computed from the train outputs
                   where one is `ex_output` or a `DET` (a determination keeps the values at which the program solves every
                   train pair), and as neither where it reaches no source. An output of an instance that reads its own outputs has no flow from them
  assigned.parquet one row per DET at an entry's assignment: task, case, entry, det, rows, offset
  projections.parquet    one row per projection (columns) and projection_rows.parquet one row per projection at an entry
  orientations.json  [encoding, name] of each orientation constant; an orientation cell is its encoding
  orientation_types.json  [type name, cells] of each orientation type without a parameter (Dir, DiagDir, Dir8, Axis, DiagAxis,
                   Axis4, D4, C4, Sym, Sense): the cells its columns admit; a Pose type admits D4's
  parts/<k>.checks.txt, checks.txt  one line `<task> <case>: <invariant>: <detail>` per violation of an invariant of this layout
                   that `export_checks.check_part` checks on each case of a part, in worker processes while later tasks replay
                   (tables, entries and runs, flows, the cells against their column types, keys, the evidence tables against the
                   task file, the copy flows' values against their source columns); a part is whole, with its `tasks.txt`, once its
                   checks are written; `python engine/arclog-py/export_checks.py <out dir> --all` checks an existing export the same way
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
import collections, hashlib, json, os, sys, glob, time
import multiprocessing, traceback
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, wait, FIRST_COMPLETED
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


def write_files(out, k, results, seconds=None, keys=None):
    """Writes the files of the part `k` of the (task id, cases, lines) results but its `checks.txt` and `tasks.txt`, with the {task: seconds} and {task: key} given.
    Returns the part's (task, case) pairs."""
    frames, pairs = {p: [] for p in PARTS}, []
    for task, cases, _ in results:
        for case in cases:
            os.makedirs(f"{out}/values/{case.task}", exist_ok=True)
            if os.path.lexists(f"{out}/values/{case.task}/{case.case}.i32"):
                os.remove(f"{out}/values/{case.task}/{case.case}.i32")  # may be a link to a file of another export
            with open(f"{out}/values/{case.task}/{case.case}.i32", "wb") as sink:
                sink.write(case.values)
            of_case = {p: frame(case, p) for p in PARTS}
            for p in PARTS:
                frames[p].append(of_case[p])
            pairs.append((task, case.case))
    for p, fs in frames.items():
        if fs:
            rows = pd.concat(fs)
            if not len(rows):       # an empty frame would write `task` and `case` as a null type, which a filter on strings refuses
                rows = rows.astype({"task": "string", "case": "string", "concept": bool})
            rows.to_parquet(f"{out}/parts/{k:05d}.{p}.parquet")
    with open(f"{out}/parts/{k:05d}.report.txt", "w") as sink:
        sink.write("".join(line + "\n" for _, _, lines in results for line in lines))
    with open(f"{out}/parts/{k:05d}.tasks.tmp", "w") as sink:
        sink.write("".join(t + (f" {seconds[t]:.1f}" if seconds and t in seconds else "") + (f" {keys[t]}" if keys and t in keys else "") + "\n" for t, _, _ in results))
    return pairs


def finish_part(out, k, lines):
    """Writes `parts/<k>.checks.txt` from the check `lines`, then makes the part whole: `parts/<k>.tasks.tmp` becomes `tasks.txt`."""
    with open(f"{out}/parts/{k:05d}.checks.txt", "w") as sink:
        sink.write("".join(line + "\n" for line in lines))
    os.rename(f"{out}/parts/{k:05d}.tasks.tmp", f"{out}/parts/{k:05d}.tasks.txt")


def write_part(out, k, results, seconds=None, keys=None):
    """Writes the part `k` of the (task id, cases, lines) results, checks its cases in this process, and writes the `tasks.txt` last, with the {task: seconds} given."""
    pairs = write_files(out, k, results, seconds, keys)
    finish_part(out, k, export_checks.check_part(out, k, pairs))


MIN_SHARE_BYTES = 50_000_000     # a share of values under this costs more to start than it saves, where the part has more


def submit_checks(pool, out, k, pairs):
    """Submits the check of part `k` of the (task, case) pairs, cut into shares, to `pool`. Returns the futures."""
    size = sum(os.path.getsize(f"{out}/values/{t}/{c}.i32") for t, c in pairs)
    cut = export_checks.shares(out, pairs, set(pairs), max(1, min(os.cpu_count() or 1, size // MIN_SHARE_BYTES)))
    return [pool.submit(export_checks.check_part, out, k, share) for share in cut]


def engine_digest():
    """The sha256 of the files of the installed `arclog` package (its compiled library holds the lib's registry and constructions) and of this module and `export_checks.py`."""
    digest, here = hashlib.sha256(), os.path.dirname(os.path.abspath(__file__))
    package = os.path.dirname(arclog.__file__)
    files = [(os.path.relpath(f, package), f) for f in glob.glob(f"{package}/**", recursive=True) if os.path.isfile(f) and "__pycache__" not in f]
    files += [(name, f"{here}/{name}") for name in ("tables_export.py", "export_checks.py")]
    for name, f in sorted(files):
        digest.update(name.encode() + b"\0" + open(f, "rb").read() + b"\0")
    return digest.hexdigest()


def task_key(engine, task, settings):
    """The sha256 of the task's generated program and data, its task file, the `engine_digest` and the settings text."""
    digest = hashlib.sha256()
    for f in (f"{CORPUS}/{task}.arclog", f"{CORPUS}/{task}.arcdata", f"{TASKS}/{task}.json"):
        digest.update(open(f, "rb").read() + b"\0")
    digest.update(engine.encode() + b"\0" + settings.encode())
    return digest.hexdigest()


def reuse_parts(out, previous, keys, k, skip):
    """Writes parts from `previous`, from its `k`-th on, for each task of `keys` ({task: key}, not in `skip`) whose key the previous export's `tasks.txt` lines give equal.

    A part takes the rows, fault lines, check lines and `tasks.txt` lines of the tasks of one previous part, and the values files of
    the tasks are hard-linked. Returns the set of tasks reused and the next part number.
    """
    reused = set()
    for tasks_file in sorted(glob.glob(f"{previous}/parts/*.tasks.txt")):
        stem = os.path.basename(tasks_file).split(".")[0]
        lines = [l for l in open(tasks_file).read().splitlines() if l.split() and l.split()[0] not in skip and len(l.split()) == 3 and keys.get(l.split()[0]) == l.split()[2]]
        if not lines:
            continue
        tasks = [l.split()[0] for l in lines]
        for p in PARTS:
            f = f"{previous}/parts/{stem}.{p}.parquet"
            if os.path.exists(f):
                rows = pd.read_parquet(f)
                rows = rows[rows["task"].isin(tasks)]
                if len(rows):
                    rows.to_parquet(f"{out}/parts/{k:05d}.{p}.parquet")
        for kind in ("report", "checks"):
            with open(f"{out}/parts/{k:05d}.{kind}.txt", "w") as sink:
                sink.write("".join(l + "\n" for l in open(f"{previous}/parts/{stem}.{kind}.txt").read().splitlines() if l.split()[0] in tasks))
        for task in tasks:
            os.makedirs(f"{out}/values/{task}", exist_ok=True)
            for name in os.listdir(f"{previous}/values/{task}") if os.path.isdir(f"{previous}/values/{task}") else []:
                if os.path.lexists(f"{out}/values/{task}/{name}"):
                    os.remove(f"{out}/values/{task}/{name}")
                os.link(f"{previous}/values/{task}/{name}", f"{out}/values/{task}/{name}")
        with open(f"{out}/parts/{k:05d}.tasks.tmp", "w") as sink:
            sink.write("".join(l + "\n" for l in lines))
        os.rename(f"{out}/parts/{k:05d}.tasks.tmp", f"{out}/parts/{k:05d}.tasks.txt")
        reused |= set(tasks)
        k += 1
    return reused, k


def main(out, task_ids, previous=None, **options):
    workers = int(os.environ.get("ARCLOG_THREADS") or os.cpu_count())
    os.environ["ARCLOG_THREADS"] = "1"
    os.makedirs(f"{out}/parts", exist_ok=True)
    settings = {**options, "parts": list(PARTS)}
    if os.path.exists(f"{out}/settings.json"):
        found = json.load(open(f"{out}/settings.json"))
        if found != settings:
            print(f"{out} holds settings {json.dumps(found)}, this run has {json.dumps(settings)}", file=sys.stderr)
            sys.exit(2)
    settings_text = json.dumps(settings)
    json.dump(settings, open(f"{out}/settings.json", "w"))
    done, k = set(), 0
    for f in sorted(glob.glob(f"{out}/parts/*")):
        stem = os.path.basename(f).split(".")[0]
        if os.path.exists(f"{out}/parts/{stem}.tasks.txt"):
            k = max(k, int(stem) + 1)
            if f.endswith(".tasks.txt"):
                done |= {line.split()[0] for line in open(f) if line.strip()}
        else:
            os.remove(f)
    engine = engine_digest()
    keys = {t: task_key(engine, t, settings_text) for t in task_ids}
    reused, k = reuse_parts(out, previous, keys, k, done) if previous else (set(), k)
    done |= reused
    # Longest processing time first: the tasks the previous export gives, by its seconds, after the tasks it does not give,
    # which go by the largest .arcdata file, as the slowest tasks are among them.
    before = {}
    for f in glob.glob(f"{previous}/parts/*.tasks.txt") if previous else []:
        before.update({w[0]: float(w[1]) for w in map(str.split, open(f)) if len(w) >= 2})
    todo = sorted((t for t in task_ids if t not in done), key=lambda t: (t in before, -before.get(t, 0), -os.path.getsize(f"{CORPUS}/{t}.arcdata"), t))
    print(f"{len(reused)} tasks reused, {len(todo)} to replay", flush=True)
    started, progress, took = {}, {}, {}

    def run(task):
        progress[task] = arclog.ReplayProgress()
        started[task] = time.time()
        cases, lines = arclog.corpus_tables(CORPUS, TASKS, task_ids=[task], progress=progress[task], **options)
        took[task] = time.time() - started[task]
        return task, cases, lines

    pool = ThreadPoolExecutor(workers)
    futures = {t: pool.submit(run, t) for t in todo}
    check_pool = ProcessPoolExecutor(os.cpu_count(), mp_context=multiprocessing.get_context("spawn"))
    checking = {}         # check future -> its part
    open_parts = {}       # part -> [the (task, case) pairs, the check futures not ended, the lines of the ended ones]
    pending, results, ended, begin, last = set(futures.values()), [], len(done), time.time(), time.time()
    failure = None
    while pending and not failure:
        got, pending = wait(pending, timeout=max(0.0, last + 10 - time.time()), return_when=FIRST_COMPLETED)
        for f in got:
            if f.exception():
                failure = failure or f.exception()
            elif f in checking:
                pairs, waiting, lines = open_parts[checking[f]]
                waiting.remove(f)
                lines += f.result()
                if not waiting:
                    position = {f"{t} {c}": i for i, (t, c) in enumerate(pairs)}
                    finish_part(out, checking[f], sorted(lines, key=lambda l: position[l.split(": ", 1)[0]]))
                    del open_parts[checking[f]]
            else:
                results.append(f.result())
        replaying = pending & set(futures.values())
        if time.time() - last >= 10 or not replaying or failure:
            if results and not failure:
                pairs = write_files(out, k, results, took, keys)
                new = submit_checks(check_pool, out, k, pairs) if pairs else []
                if new:
                    open_parts[k] = [pairs, set(new), []]
                    checking.update({f: k for f in new})
                    pending |= set(new)
                else:
                    finish_part(out, k, [])
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
        workers_running = list((check_pool._processes or {}).values())
        check_pool.shutdown(wait=False, cancel_futures=True)
        for process in workers_running:
            process.kill()
        raise failure
    pool.shutdown()
    check_pool.shutdown()
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
    export_checks.number_rows(tables, entries)
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
        elif a == "--previous": options["previous"] = args.pop(0)
        elif a == "--projection-cap": options["projection_cap"] = int(args.pop(0))
        elif a == "--step-cap": options["step_cap"] = int(args.pop(0)) or None
        else: ids.append(a)
    ids = ids or sorted(os.path.basename(f)[:-len(".arcdata")] for f in glob.glob(f"{CORPUS}/*.arcdata"))
    try:
        main(sys.argv[1], ids, **options)
    except Exception:       # a failed task or check ends the run at once: the replay threads of the other tasks do not delay the exit
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)
