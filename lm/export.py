"""Export the gold streams of every case of the corpus for the language model.

Writes to work/lm/data/:
  vocab.json      {"names": the engine vocabulary's token names, "kinds": the kind of each token, as
                  arclog.Vocabulary.kind gives it}, both indexed by token id
  keys.json       {task: {"key": the task's reuse key (see `--previous`), "streamed": the count of its streams that the
                  engine gave masks for, "problems": {"duplicate stream": n, "model reads undeclared": n} (the counts
                  that are not 0)}} for each task the run streamed or reused
  cases.npz       the distinct streams of each task, concatenated:
                  ids (uint16 token id), model (bool, the model writes the token), offsets (int64,
                  case i spans offsets[i]:offsets[i+1]), task, case (str), concept (bool), heldout (bool)
                  mask_table (uint8, one row per distinct mask, MASK_BYTES bytes: bit id % 8 of byte id // 8 is
                  set where the engine's decoder admits the token with that id), mask_index (int32, for each
                  model-written step of ids, in order, the row of mask_table that is the mask the decoder gave
                  before it stepped that token)

A stream whose model reads a relation or label before the engine declares it is dropped, and so is one
for which the engine gives no masks; the stream report gives the reason.

    work/lm/.venv/bin/python lm/export.py [--out <dir>] [--heldout <id>,<id>,...] [--step-cap N] [--previous <export dir>] [<task id> ...]

`--out` writes to another directory in place of work/lm/data/, and task ids stream those tasks alone. The
held-out marks come from work/lm/data/evaluation.ids, or from `--heldout` where it is given. Task ids need `--out`.
`--step-cap N` bounds the replay of each solver to the streams, in the order of their tokens, up to the last one at which
the model steps of their prefix tree stay within N, 10000 where it is not given and 0 for no cap; each later stream of the
solver gets a line in the stream report that gives the cap.

While arclog.corpus_streams runs, a line is printed every 10 s:

    <s> s: <k> tasks ended, running past 10 s: <id> <s> s ..., <p>% of <total> steps, about <s> s left

where the last part is the share of the replay's model steps done, as arclog.ReplayProgress gives them, and
the seconds since the call started times (total - done) / done ("about ? s left" while done is 0;
no such part while the total is 0), and with the time the call has run, the count of tasks whose streams have ended, and the tasks whose replay
started over 10 s ago and has not ended, longest first: the first 10, then "and <n> more" where there are more.

`--previous <dir>` takes, for each task whose key equals the key in <dir>/keys.json, that task's rows of <dir>/cases.npz
and its lines of <dir>/stream-report-all.txt, and streams only the other tasks; the files written are those a run with
no `--previous` writes. A task's key is the sha256 of its work/arclog/gen `.arclog` and `.arcdata`, its task file, the files
of the installed `arclog` package, `tables_export.py`, `export_checks.py`, this file and the step cap
(`tables_export.task_key` computes it). A <dir> with no keys.json gives no reuse. With a <out>/streams.pkl, `--previous`
exits with a message.

Where <out>/streams.pkl exists, written by export_chunks.py, and no task id is given, the streams come from it
instead.
"""
import argparse, collections, concurrent.futures, glob, hashlib, json, os, pickle, sys, threading, time, types
import arclog, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "arclog-py"))
import tables_export as X

ap = argparse.ArgumentParser()
ap.add_argument("--out", help="the output directory; work/lm/data where no task id is given")
ap.add_argument("--heldout", help="a comma-separated list of task ids to mark held out, in place of work/lm/data/evaluation.ids")
ap.add_argument("--step-cap", type=int, default=10000, help="the most model steps of the prefix tree of a solver's streams that are replayed; 0 for no cap")
ap.add_argument("--previous", help="an earlier export directory whose rows of the tasks with an equal key are reused")
ap.add_argument("task_ids", nargs="*")
args = ap.parse_args()
if args.task_ids and not args.out:
    ap.error("task ids need --out, so that they do not overwrite work/lm/data")
args.out = args.out or "work/lm/data"
DATA = args.out
if args.previous and os.path.exists(f"{DATA}/streams.pkl"):
    sys.exit(f"{DATA}/streams.pkl exists: its streams come from export_chunks.py, and --previous cuts the arclog.corpus_streams call")
os.makedirs(DATA, exist_ok=True)
held_out = set(args.heldout.split(",")) if args.heldout is not None else set(open("work/lm/data/evaluation.ids").read().split())
voc = arclog.Session(arclog.Task.from_json(open("data/tasks/007bbfb7.json").read(), arclog.World.Closed)).vocabulary
names = [voc.name(i) for i in range(len(voc))]
kinds = [voc.kind(i) for i in range(len(voc))]
declared = {i for i, k in enumerate(kinds) if k in ("relation", "label")}

CORPUS = "work/arclog/gen"
X.CORPUS, X.TASKS = CORPUS, "data/tasks"
task_ids = args.task_ids or sorted(os.path.basename(f)[:-len(".arcdata")] for f in glob.glob(f"{CORPUS}/*.arcdata"))
engine = hashlib.sha256((X.engine_digest() + open(os.path.abspath(__file__)).read()).encode()).hexdigest()
task_keys = {t: X.task_key(engine, t, f"step_cap={args.step_cap}") for t in task_ids}
previous = json.load(open(f"{args.previous}/keys.json")) if args.previous and os.path.exists(f"{args.previous}/keys.json") else {}
reused = {t for t in task_ids if t in previous and previous[t]["key"] == task_keys[t]}
to_stream = [t for t in task_ids if t not in reused]
if args.previous:
    print(f"{len(reused)} tasks reused, {len(to_stream)} to stream", flush=True)

t0 = time.time()
if not to_stream:
    streams, faults = [], []
elif os.path.exists(f"{DATA}/streams.pkl") and not args.task_ids:     # written by export_chunks.py, one process per chunk of solvers
    cached = pickle.load(open(f"{DATA}/streams.pkl", "rb"))
    streams, faults = [types.SimpleNamespace(**s) for s in cached["streams"]], cached["faults"]
else:
    running, ended, lock = {}, [0], threading.Lock()     # task id -> start time of the tasks running; count of tasks ended

    def started_task(task):
        with lock:
            running[task] = time.time()

    def ended_task(task):
        with lock:
            running.pop(task, None)
            ended[0] += 1

    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        progress, since = arclog.ReplayProgress(), time.time()     # since: when the call is submitted
        call = pool.submit(arclog.corpus_streams, "work/arclog/gen", all_cases=True, tasks="data/tasks",
                           started=started_task, ended=ended_task, progress=progress, step_cap=args.step_cap or None, **({"task_ids": to_stream} if args.task_ids or reused else {}))
        while True:
            try:
                streams, faults = call.result(timeout=10)
                break
            except concurrent.futures.TimeoutError:
                now = time.time()
                with lock:
                    slow = sorted(((now - t, task) for task, t in running.items() if now - t > 10), reverse=True)
                    count = ended[0]
                shown = " ".join(f"{task} {s:.0f} s" for s, task in slow[:10]) + (f" and {len(slow) - 10} more" if len(slow) > 10 else "")
                done, total = progress.done, progress.total
                share = f", {100 * done / total:.0f}% of {total} steps, about {(now - since) * (total - done) / done:.0f} s left" if done else \
                        f", 0% of {total} steps, about ? s left" if total else ""
                print(f"{now - t0:.0f} s: {count} tasks ended, running past 10 s: {shown}{share}", flush=True)
mask_faults = [f"{s.task} {s.case}: mask fault: {s.mask_fault}" for s in streams if s.mask_fault is not None]
streams = [s for s in streams if s.mask_fault is None]
faults = faults + mask_faults
streamed = collections.Counter(s.task for s in streams)
if reused:      # the earlier report's lines of the reused tasks, and the count of their streams
    faults = faults + [l for l in open(f"{args.previous}/stream-report-all.txt").read().splitlines() if X.line_task(l) in reused]
    streamed.update({t: previous[t]["streamed"] for t in reused})
open(f"{DATA}/stream-report-all.txt", "w").write("\n".join(faults) + f"\ncorpus: {sum(streamed.values())} cases streamed, {sum(' ' in f.split(':')[0] for f in faults)} cases whose stream faults\n")
print(f"streamed in {time.time() - t0:.0f}s", flush=True)
MASK_BYTES = (len(names) + 7) // 8


def compact(s):
    return s.task, tuple(np.frombuffer(s.ids, np.uint32).tolist()), tuple(np.frombuffer(s.model, np.uint8).astype(bool).tolist())


def mask_rows(s, model):
    """The masks of the model-written steps of s, one MASK_BYTES-wide row per step."""
    rows = np.frombuffer(s.masks, np.uint8).reshape(-1, MASK_BYTES)
    assert len(rows) == sum(model), f"{s.task} {s.case}: {len(rows)} masks for {sum(model)} model-written steps"
    return rows


keyed = [(s, compact(s)) for s in streams]
concept = {key for s, key in keyed if s.concept}

problems, counts, seen, rows = collections.defaultdict(collections.Counter), collections.Counter(), set(), []
mask_row = {}                   # the row of each distinct mask, in order of first use
for s, key in keyed:
    _, t, m = key
    if key in seen:
        problems[s.task]["duplicate stream"] += 1; continue
    seen.add(key)
    decl = set()
    for i, w in zip(t, m):
        if i in declared:
            if not w:
                decl.add(i)
            elif i not in decl:
                problems[s.task]["model reads undeclared"] += 1; break
    else:
        index = [mask_row.setdefault(row.tobytes(), len(mask_row)) for row in mask_rows(s, m)]
        rows.append((s.task, s.case, key in concept, t, m, index))
if reused:      # the rows of the reused tasks, with the masks of the earlier table taken into this run's
    old = np.load(f"{args.previous}/cases.npz")
    old_ids, old_model, old_offsets, old_tasks, old_table = old["ids"], old["model"], old["offsets"], old["task"], old["mask_table"]
    steps = np.concatenate([[0], np.cumsum(old_model)])     # steps[j]: the model-written steps of ids[:j]
    for i in np.flatnonzero(np.isin(old_tasks, list(reused))):
        a, b = old_offsets[i], old_offsets[i + 1]
        rows.append((str(old_tasks[i]), str(old["case"][i]), bool(old["concept"][i]), tuple(old_ids[a:b].tolist()), tuple(old_model[a:b].tolist()),
                     [mask_row.setdefault(old_table[j].tobytes(), len(mask_row)) for j in old["mask_index"][steps[a]:steps[b]]]))
    for t in reused:
        problems[t].update(previous[t]["problems"])
rows.sort(key=lambda r: (r[0], r[1]))
# The table lists the distinct masks in order of first use over the sorted rows, whichever rows were reused.
flat = np.fromiter((i for r in rows for i in r[5]), np.int32, sum(len(r[5]) for r in rows))
used, first = np.unique(flat, return_index=True)
by_use = np.argsort(first)
rank = np.empty(len(used), np.int32)
rank[by_use] = np.arange(len(used))
flat = rank[np.searchsorted(used, flat)]
table_rows = list(mask_row)
lengths = np.array([len(r[3]) for r in rows])
mask_table = np.frombuffer(b"".join(table_rows[j] for j in used[by_use]), np.uint8).reshape(-1, MASK_BYTES)
np.savez_compressed(f"{DATA}/cases.npz",
         ids=np.fromiter((i for r in rows for i in r[3]), np.uint16, lengths.sum()),
         model=np.fromiter((w for r in rows for w in r[4]), bool, lengths.sum()),
         mask_table=mask_table, mask_index=flat,
         offsets=np.concatenate([[0], np.cumsum(lengths)]),
         task=np.array([r[0] for r in rows], dtype=str), case=np.array([r[1] for r in rows], dtype=str),
         concept=np.array([r[2] for r in rows]), heldout=np.array([r[0] in held_out for r in rows]))
counts = collections.Counter("heldout" if r[0] in held_out else "train" for r in rows)
json.dump({t: {"key": task_keys[t], "streamed": streamed[t], "problems": {k: n for k, n in problems[t].items() if n}} for t in task_ids}, open(f"{DATA}/keys.json", "w"))
json.dump({"names": names, "kinds": kinds}, open(f"{DATA}/vocab.json", "w"))
print(dict(counts), dict(sum(problems.values(), collections.Counter())), f"{len(mask_table)} distinct masks, {time.time() - t0:.0f}s")
