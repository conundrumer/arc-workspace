"""Export the gold streams of every case of the corpus for the language model.

Writes to work/lm/data/:
  vocab.json      {"names": the engine vocabulary's token names, "kinds": the kind of each token, as
                  arclog.Vocabulary.kind gives it}, both indexed by token id
  keys.json       {task: {"key": the task's reuse key (see `--previous`; null where the streams come from streams.pkl),
                  "seconds": the wall seconds of the task's arclog.corpus_streams call to 0.1 s, or the previous export's
                  where the task is reused (null where it gives none), "streamed": the count of its streams that the
                  engine gave masks for, "problems": {"duplicate stream": n, "model reads undeclared": n} (the counts
                  that are not 0)}} for each task the run streamed or reused
  cases.npz       the distinct streams of each task, concatenated:
                  ids (uint16 token id), model (bool, the model writes the token), offsets (int64,
                  case i spans offsets[i]:offsets[i+1]), task, case (str), concept (bool), heldout (bool)
                  mask_table (uint8, one row per distinct mask, (len(names) + 7) // 8 bytes: bit id % 8 of byte id // 8 is
                  set where the engine's decoder admits the token with that id), mask_index (int32, for each
                  model-written step of ids, in order, the row of mask_table that is the mask the decoder gave
                  before it stepped that token)
  stream-report-all.txt  the stream report: the lines of each task in task order, then a `corpus:` line
  tasks/<task>/   the output of one task, made as the task ends, for a consumer that starts on a task before the run ends:
                  cases.npz  the arrays of the whole cases.npz for the task's rows but `heldout` (the held-out marks come from the run's
                             set, which the task's key does not cover): offsets from 0, and mask_table and mask_index over the task's own
                             distinct masks, in order of first use over its rows sorted by case, so a mask that two tasks share stands in both tables
                  key.json   the task's entry of keys.json
                  report.txt the task's lines of the stream report
                  DONE       an empty file, made last: where it stands, every other file of the directory is whole
                  A task that gets no output has FAILED in place of DONE, with the reason: the fault line `tables_export.death_line` gives for a
                  task whose worker process died on both runs, the traceback of a call that raised, or `the export stopped: <the exception's
                  type and first line>` for a task that had not ended when the run ended with an exception, a KeyboardInterrupt or the SIGTERM that
                  `timeout` sends. A kill that gives the process no chance to run Python (SIGKILL) leaves the tasks that had not ended with neither
                  marker. The whole files are assembled from these directories, which stay after the run.

A stream whose model reads a relation or label before the engine declares it is dropped, and so is one
for which the engine gives no masks; the stream report gives the reason.

    work/lm/.venv/bin/python model/export.py [--out <dir>] [--heldout <id>,<id>,...] [--step-cap N] [--previous <export dir>] [<task id> ...]

`--out` writes to another directory in place of work/lm/data/, and task ids stream those tasks alone. The
held-out marks come from work/lm/data/evaluation.ids, or from `--heldout` where it is given. Task ids need `--out`.
`--step-cap N` bounds the replay of each solver to the streams, in the order of their tokens, up to the last one at which
the model steps of their prefix tree stay within N, 10000 where it is not given and 0 for no cap; each later stream of the
solver gets a line in the stream report that gives the cap.

One arclog.corpus_streams call per task id, on a queue of N worker processes, where N is `ARCLOG_THREADS` if set and `os.cpu_count()`
otherwise, each process on one engine thread and running one call after another (`tables_export.run_in_worker`). The tasks go longest first, in the order of `tables_export.replay_order` over the `seconds`
of the `--previous` keys.json. While the calls run, `tables_export.print_progress` prints a line every 10 s:

    <k> of <n> tasks ended, <s> s, about <t> s left, running past 10 s: <id> <s> s <p>% ...

the tasks ended, the seconds since the start, the seconds left (`?` while no task has ended), then the tasks running past 10 s,
longest first (the first 10 and a count of the rest where more), each with the seconds since its call started and the share of its
model steps done, as arclog.ReplayProgress gives them.

`--previous <dir>` takes, for each task whose key equals the key in <dir>/keys.json, that task's directory <dir>/tasks/<task>/ by hard links,
and streams only the other tasks; the files written are those a run with
no `--previous` writes. A task's key is the sha256 of its programs/arclog `.arclog` and `.arcdata`, its files under programs/arclog/cases/<task>/ with their names, its task file,
`arclog.streams_digest()` (fixed when the package is built, over the inputs of the compile of the crates the streams bindings are built from, and
over no file of the crates that only the tables export runs), the files of the installed `arclog` package other than its compiled library,
the versions of Python and numpy, this file and the step cap (`tables_export.task_key` computes it). A <dir> with no keys.json gives no reuse. With a <out>/streams.pkl, `--previous`
exits with a message.

As each call ends, its worker writes the task's directory under <out>/tasks, after it removes the directory of an earlier run. A run on an <out> whose tasks/ holds
a task's directory with `DONE` and with the task's key in its key.json takes the task from that directory and streams only the other tasks, so a run that was stopped loses only the calls that were
running. Where a worker process dies in a call, the export prints on stderr the task and the exit status, and runs the call
once more in a new worker; where that one dies too, the task gets FAILED with the fault line `tables_export.death_line` gives, no streams, and
a null key in keys.json.

Where <out>/streams.pkl exists, written by export_chunks.py, and no task id is given, the streams come from it
instead, grouped by task, and each task's directory is written from them with a null key.
"""
import argparse, collections, concurrent.futures, functools, glob, hashlib, importlib.machinery, json, os, pickle, shutil, signal, sys, time, types
from typing import NamedTuple
import arclog, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "arclog-py"))
import tables_export as X
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from pathlib import Path
from arclog_convert import determination_gate as D

CORPUS, TASKS = "programs/arclog", "data/tasks"


@functools.cache
def vocabulary():
    """(the token names, the token kinds, the declared token ids) of the engine vocabulary, indexed by token id, read once per process. A declared id is that of a relation or a label."""
    voc = arclog.Session(arclog.Task.from_json(open(f"{TASKS}/007bbfb7.json").read(), arclog.World.Closed)).vocabulary
    names = [voc.name(i) for i in range(len(voc))]
    kinds = [voc.kind(i) for i in range(len(voc))]
    return names, kinds, {i for i, k in enumerate(kinds) if k in ("relation", "label")}


def mask_bytes():
    """The width of a mask row, in bytes."""
    return (len(vocabulary()[0]) + 7) // 8


class TaskRows(NamedTuple):
    """The rows of one task's streams after the filter of `task_rows`."""
    cases: list                         # (case, concept, ids, model, mask_index) per row, sorted by case
    mask_table: list                    # the bytes of each distinct mask, in order of first use over `cases`
    streamed: int                       # the count of streams the engine gave masks for
    problems: collections.Counter       # "duplicate stream" and "model reads undeclared" counts
    lines: list                         # a stream report line per mask fault


def compact(s):
    return tuple(np.frombuffer(s.ids, np.uint32).tolist()), tuple(np.frombuffer(s.model, np.uint8).astype(bool).tolist())


def mask_rows(s, model):
    """The masks of the model-written steps of s, one mask-wide row per step."""
    rows = np.frombuffer(s.masks, np.uint8).reshape(-1, mask_bytes())
    assert len(rows) == sum(model), f"{s.task} {s.case}: {len(rows)} masks for {sum(model)} model-written steps"
    return rows


def task_rows(streams):
    """The rows of the `streams` of one task, which hold the fields of arclog.CaseStream: a stream with a mask fault gets a report line and no row;
    a stream equal in ids and model to an earlier one is a `duplicate stream`; a stream that reads a relation or label before the engine declares it is a `model reads undeclared`;
    a row is concept where any stream equal to it is."""
    declared = vocabulary()[2]
    lines = [f"{s.task} {s.case}: mask fault: {s.mask_fault}" for s in streams if s.mask_fault is not None]
    streams = [s for s in streams if s.mask_fault is None]
    keyed = [(s, compact(s)) for s in streams]
    concept = {key for s, key in keyed if s.concept}
    problems, seen, rows = collections.Counter(), set(), []
    for s, key in keyed:
        t, m = key
        if key in seen:
            problems["duplicate stream"] += 1; continue
        seen.add(key)
        decl = set()
        for i, w in zip(t, m):
            if i in declared:
                if not w:
                    decl.add(i)
                elif i not in decl:
                    problems["model reads undeclared"] += 1; break
        else:
            rows.append((s.case, key in concept, t, m, mask_rows(s, m)))
    rows.sort(key=lambda r: r[0])
    table = {}                  # the row of each distinct mask, in order of first use
    cases = [(case, is_concept, t, m, [table.setdefault(row.tobytes(), len(table)) for row in masks]) for case, is_concept, t, m, masks in rows]
    return TaskRows(cases, list(table), len(streams), problems, lines)


def write_task_dir(directory, task, rows, faults, key, seconds, receipt):
    """Makes `directory` of `task` as the module docstring gives `tasks/<task>/`, `DONE` last, from the `TaskRows` `rows`, the `faults` (report lines) of the task, its reuse `key` and its call's `seconds`."""
    D.check_unchanged(receipt, Path(CORPUS), Path(TASKS))
    shutil.rmtree(directory, ignore_errors=True)
    os.makedirs(directory)
    cases = rows.cases
    lengths = np.array([len(c[2]) for c in cases], np.int64)
    np.savez_compressed(f"{directory}/cases.npz",
             ids=np.fromiter((i for c in cases for i in c[2]), np.uint16, lengths.sum()),
             model=np.fromiter((w for c in cases for w in c[3]), bool, lengths.sum()),
             mask_table=np.frombuffer(b"".join(rows.mask_table), np.uint8).reshape(-1, mask_bytes()),
             mask_index=np.fromiter((i for c in cases for i in c[4]), np.int32, sum(len(c[4]) for c in cases)),
             offsets=np.concatenate([[0], np.cumsum(lengths)]),
             task=np.array([task] * len(cases), dtype=str), case=np.array([c[0] for c in cases], dtype=str),
             concept=np.array([c[1] for c in cases], dtype=bool))
    with open(f"{directory}/key.json", "w") as sink:
        json.dump({"key": key, "seconds": seconds, "streamed": rows.streamed, "problems": {k: n for k, n in rows.problems.items() if n},
                   "determination_end_check": receipt}, sink)
    with open(f"{directory}/report.txt", "w") as sink:
        sink.write("".join(line + "\n" for line in [*faults, *rows.lines]))
    X.write_marker(directory, X.DONE)


def stream_task(payload, progress):
    """The call of a worker process: streams the task of `payload` and writes its directory."""
    task, corpus, tasks, step_cap, key, directory, receipt = payload
    shutil.rmtree(directory, ignore_errors=True)
    D.check_unchanged(receipt, Path(corpus), Path(tasks))
    if receipt["context"] != D.mask_context():
        raise D.EndCheckFailed(f"{task}: mask engine differs from the checked admission context")
    start = time.time()
    streams, faults = arclog.corpus_streams(corpus, all_cases=True, task_ids=[task], tasks=tasks, progress=progress, step_cap=step_cap)
    seconds = round(time.time() - start, 1)
    write_task_dir(directory, task, task_rows([types.SimpleNamespace(**X.stream_fields(s)) for s in streams]), faults, key, seconds, receipt)


def task_dir(data, task):
    return f"{data}/tasks/{task}"


def read_key(data, task):
    """The entry of `key.json` in the directory of `task` that holds `DONE`, or None where it holds none."""
    return json.load(open(f"{task_dir(data, task)}/key.json")) if os.path.exists(f"{task_dir(data, task)}/{X.DONE}") else None


def reuse_task(data, previous, task, receipt):
    """Makes the directory of `task` in `data` from hard links of its directory in `previous`."""
    D.check_unchanged(receipt, Path(CORPUS), Path(TASKS))
    D.validate_cached({task: read_key(previous, task).get("determination_end_check", {})}, {task: receipt})
    shutil.rmtree(task_dir(data, task), ignore_errors=True)
    X.link_files(f"{previous}/tasks/{task}", task_dir(data, task), skip=(X.DONE, X.FAILED))
    X.write_marker(task_dir(data, task), X.DONE)


def write_from_pickle(data, tasks, cached, receipts):
    """Writes the directory of each of `tasks` from `cached`, the content of streams.pkl: its streams and fault lines grouped by task, a null key and no seconds."""
    D.validate_cached(cached.get("determination_receipts", {}), {t: receipts[t] for t in tasks})
    streams, faults = collections.defaultdict(list), collections.defaultdict(list)
    for s in cached["streams"]:
        streams[s["task"]].append(types.SimpleNamespace(**s))
    for line in cached["faults"]:
        faults[X.line_task(line)].append(line)
    for t in tasks:
        write_task_dir(task_dir(data, t), t, task_rows(streams[t]), faults[t], None, None, receipts[t])


def stream_with_workers(data, to_stream, resumed, before, key_of, step_cap, t0, receipts):
    """Streams the `to_stream` tasks on a queue of worker processes, each task into its directory. `resumed` is the count of tasks taken from `data` already, `before` the {task: seconds} of the previous export."""
    workers = X.take_workers()
    running, ended = {}, set()      # task id -> (start, progress) of the tasks running; the tasks whose call ended

    def stream_in_worker(task):
        start, progress = time.time(), types.SimpleNamespace(done=0, total=0)
        running[task] = start, progress
        directory = task_dir(data, task)
        with X.failing_into(directory):
            try:
                X.run_in_worker([sys.executable, os.path.abspath(__file__)], task, (task, CORPUS, TASKS, step_cap, key_of[task], directory, receipts[task]), progress)
            except X.WorkerDied as death:
                shutil.rmtree(directory, ignore_errors=True)        # the worker may have died with the files half written
                X.write_marker(directory, X.FAILED, X.death_line(task, death.status) + "\n")
        ended.add(task)
        del running[task]

    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        pending = {pool.submit(stream_in_worker, t) for t in X.replay_order(to_stream, before)}
        last = t0
        try:
            while pending:
                got, pending = concurrent.futures.wait(pending, timeout=max(0.0, last + 10 - time.time()), return_when=concurrent.futures.FIRST_COMPLETED)
                for f in got:
                    f.result()
                if time.time() - last >= 10:
                    X.print_progress(t0, resumed + len(ended), resumed + len(to_stream), resumed, running)
                    last = time.time()
        except BaseException:
            X.ignore_interrupts()
            X.stop_workers()
            pool.shutdown(wait=False, cancel_futures=True)
            raise
    X.close_workers()


def assemble(data, task_ids, held_out):
    """Writes cases.npz, keys.json and stream-report-all.txt of `data` from the directories of the `task_ids`, and returns the {task: key.json entry}, the count of cases of held-out and of train tasks, and the count of distinct masks.
    A task with FAILED gets an entry with a null key and its reason in the report."""
    entries, lines, parts = {}, [], []
    table = {}      # the row of each distinct mask, in order of first use over the tasks in order
    for t in sorted(task_ids):
        entry = read_key(data, t)
        if entry is None:
            entries[t] = {"key": None, "seconds": None, "streamed": 0, "problems": {}}
            lines += open(f"{task_dir(data, t)}/{X.FAILED}").read().splitlines()
            continue
        entries[t] = entry
        lines += open(f"{task_dir(data, t)}/report.txt").read().splitlines()
        cases = np.load(f"{task_dir(data, t)}/cases.npz")
        row = np.array([table.setdefault(mask.tobytes(), len(table)) for mask in cases["mask_table"]], np.int32)
        parts.append({**{name: cases[name] for name in ("ids", "model", "task", "case", "concept")}, "lengths": np.diff(cases["offsets"]), "mask_index": row[cases["mask_index"]]})
    joined = lambda name, dtype: np.concatenate([np.empty(0, dtype), *[p[name] for p in parts]])
    lengths = joined("lengths", np.int64)
    tasks = joined("task", str)
    np.savez_compressed(f"{data}/cases.npz", ids=joined("ids", np.uint16), model=joined("model", bool),
             mask_table=np.frombuffer(b"".join(table), np.uint8).reshape(-1, mask_bytes()), mask_index=joined("mask_index", np.int32),
             offsets=np.concatenate([[0], np.cumsum(lengths)]), task=tasks, case=joined("case", str), concept=joined("concept", bool),
             heldout=np.isin(tasks, list(held_out)))
    json.dump({t: entries[t] for t in task_ids}, open(f"{data}/keys.json", "w"))
    corpus = f"corpus: {sum(e['streamed'] for e in entries.values())} cases streamed, {sum(' ' in line.split(':')[0] for line in lines)} cases whose stream faults"
    open(f"{data}/stream-report-all.txt", "w").write("\n".join(lines) + f"\n{corpus}\n")
    counts = collections.Counter("heldout" if t in held_out else "train" for t in tasks)
    return entries, counts, len(table)


def main():
    signal.signal(signal.SIGTERM, signal.default_int_handler)       # the SIGTERM of `timeout` ends the run as an interrupt does
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="the output directory; work/lm/data where no task id is given")
    ap.add_argument("--heldout", help="a comma-separated list of task ids to mark held out, in place of work/lm/data/evaluation.ids")
    ap.add_argument("--step-cap", type=int, default=10000, help="the most model steps of the prefix tree of a solver's streams that are replayed; 0 for no cap")
    ap.add_argument("--previous", help="an earlier export directory whose rows of the tasks with an equal key are reused")
    ap.add_argument("task_ids", nargs="*")
    args = ap.parse_args()
    if args.task_ids and not args.out:
        ap.error("task ids need --out, so that they do not overwrite work/lm/data")
    data = args.out or "work/lm/data"
    if args.previous and os.path.exists(f"{data}/streams.pkl"):
        sys.exit(f"{data}/streams.pkl exists: its streams come from export_chunks.py, and --previous cuts the arclog.corpus_streams call")
    os.makedirs(data, exist_ok=True)
    held_out = set(args.heldout.split(",")) if args.heldout is not None else set(open("work/lm/data/evaluation.ids").read().split())
    X.CORPUS, X.TASKS = CORPUS, TASKS
    task_ids = args.task_ids or sorted(os.path.basename(f)[:-len(".arcdata")] for f in glob.glob(f"{CORPUS}/*.arcdata"))
    t0 = time.time()
    try:
        receipts = D.require(task_ids, Path(CORPUS), Path(TASKS),
                             Path(data) / "determination_end_check", D.mask_context())
        names, kinds, _ = vocabulary()
        json.dump({"names": names, "kinds": kinds}, open(f"{data}/vocab.json", "w"))
        package_files = [(name, f) for name, f in X.package_files() if not f.endswith(tuple(importlib.machinery.EXTENSION_SUFFIXES))]     # the compiled library is covered by arclog.streams_digest()
        engine = hashlib.sha256((arclog.streams_digest() + X.digest_files(package_files) + f"{sys.version} {np.__version__}" + open(os.path.abspath(__file__)).read() + Path(D.__file__).read_text()).encode()).hexdigest()
        task_keys = {t: X.task_key(engine, t, f"step_cap={args.step_cap}", ()) for t in task_ids}
        previous = json.load(open(f"{args.previous}/keys.json")) if args.previous and os.path.exists(f"{args.previous}/keys.json") else {}
        cached = os.path.exists(f"{data}/streams.pkl") and not args.task_ids      # written by export_chunks.py, one process per chunk of solvers
        if cached:
            task_keys = dict.fromkeys(task_ids)     # export_chunks.py replays with no step cap, so no later --previous may reuse these rows
        resumed = set() if cached else {t for t in task_ids if (entry := read_key(data, t)) is not None and entry["key"] == task_keys[t] and entry.get("determination_end_check", {}).get("proof") == receipts[t]["proof"]}
        reused = {t for t in task_ids if t not in resumed and t in previous and previous[t]["key"] == task_keys[t] and os.path.exists(f"{args.previous}/tasks/{t}/{X.DONE}") and read_key(args.previous, t).get("determination_end_check", {}).get("proof") == receipts[t]["proof"]}
        to_stream = [t for t in task_ids if t not in resumed | reused]
        if args.previous:
            print(f"{len(reused)} tasks reused, {len(to_stream)} to stream", flush=True)
        if resumed:
            print(f"{len(resumed)} tasks taken from {data}/tasks, {len(to_stream)} to stream", flush=True)
        for t in sorted(reused):
            reuse_task(data, args.previous, t, receipts[t])
        if cached:
            write_from_pickle(data, to_stream, pickle.load(open(f"{data}/streams.pkl", "rb")), receipts)
        elif to_stream:
            before = {t: v["seconds"] for t, v in previous.items() if v.get("seconds") is not None}
            stream_with_workers(data, to_stream, len(resumed), before, task_keys, args.step_cap or None, t0, receipts)
        for task in task_ids:
            D.check_unchanged(receipts[task], Path(CORPUS), Path(TASKS))
        print(f"streamed in {time.time() - t0:.0f}s", flush=True)
        entries, counts, distinct = assemble(data, task_ids, held_out)
    except BaseException as stop:       # an exception, a KeyboardInterrupt, or the SIGTERM turned into one
        X.ignore_interrupts()
        X.mark_stopped(data, task_ids, stop)
        raise
    print(dict(counts), dict(sum((collections.Counter(e["problems"]) for e in entries.values()), collections.Counter())), f"{distinct} distinct masks, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        X.serve(stream_task)
    else:
        main()
