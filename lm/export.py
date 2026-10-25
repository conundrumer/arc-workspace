"""Export the gold streams of every case of the corpus for the language model.

Writes to work/lm/data/:
  vocab.json      {"names": the engine vocabulary's token names, "kinds": the kind of each token, as
                  arclog.Vocabulary.kind gives it}, both indexed by token id
  cases.npz       the distinct streams of each task, concatenated:
                  ids (uint16 token id), model (bool, the model writes the token), offsets (int64,
                  case i spans offsets[i]:offsets[i+1]), task, case (str), concept (bool), heldout (bool)
                  mask_table (uint8, one row per distinct mask, MASK_BYTES bytes: bit id % 8 of byte id // 8 is
                  set where the engine's decoder admits the token with that id), mask_index (int32, for each
                  model-written step of ids, in order, the row of mask_table that is the mask the decoder gave
                  before it stepped that token)

A stream whose model reads a relation or label before the engine declares it is dropped, and so is one
for which the engine gives no masks; the stream report gives the reason.

    work/lm/.venv/bin/python lm/export.py [--out <dir>] [--heldout <id>,<id>,...] [--step-cap N] [<task id> ...]

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

Where <out>/streams.pkl exists, written by export_chunks.py, and no task id is given, the streams come from it
instead.
"""
import argparse, collections, concurrent.futures, json, os, pickle, threading, time, types
import arclog, numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--out", help="the output directory; work/lm/data where no task id is given")
ap.add_argument("--heldout", help="a comma-separated list of task ids to mark held out, in place of work/lm/data/evaluation.ids")
ap.add_argument("--step-cap", type=int, default=10000, help="the most model steps of the prefix tree of a solver's streams that are replayed; 0 for no cap")
ap.add_argument("task_ids", nargs="*")
args = ap.parse_args()
if args.task_ids and not args.out:
    ap.error("task ids need --out, so that they do not overwrite work/lm/data")
args.out = args.out or "work/lm/data"
DATA = args.out
os.makedirs(DATA, exist_ok=True)
held_out = set(args.heldout.split(",")) if args.heldout is not None else set(open("work/lm/data/evaluation.ids").read().split())
voc = arclog.Session(arclog.Task.from_json(open("data/tasks/007bbfb7.json").read(), arclog.World.Closed)).vocabulary
names = [voc.name(i) for i in range(len(voc))]
kinds = [voc.kind(i) for i in range(len(voc))]
declared = {i for i, k in enumerate(kinds) if k in ("relation", "label")}

t0 = time.time()
if os.path.exists(f"{DATA}/streams.pkl") and not args.task_ids:     # written by export_chunks.py, one process per chunk of solvers
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
                           started=started_task, ended=ended_task, progress=progress, step_cap=args.step_cap or None, **({"task_ids": args.task_ids} if args.task_ids else {}))
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
open(f"{DATA}/stream-report-all.txt", "w").write("\n".join(faults) + f"\ncorpus: {len(streams)} cases streamed, {sum(' ' in f.split(':')[0] for f in faults)} cases whose stream faults\n")
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

problems, counts, seen, rows = collections.Counter(), collections.Counter(), set(), []
mask_row = {}                   # the row of each distinct mask, in order of first use
for s, key in keyed:
    _, t, m = key
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
        index = [mask_row.setdefault(row.tobytes(), len(mask_row)) for row in mask_rows(s, m)]
        rows.append((s.task, s.case, key in concept, t, m, index))
rows.sort(key=lambda r: (r[0], r[1]))
lengths = np.array([len(r[3]) for r in rows])
mask_table = np.frombuffer(b"".join(mask_row), np.uint8).reshape(-1, MASK_BYTES)
np.savez_compressed(f"{DATA}/cases.npz",
         ids=np.fromiter((i for r in rows for i in r[3]), np.uint16, lengths.sum()),
         model=np.fromiter((w for r in rows for w in r[4]), bool, lengths.sum()),
         mask_table=mask_table, mask_index=np.fromiter((i for r in rows for i in r[5]), np.int32, sum(len(r[5]) for r in rows)),
         offsets=np.concatenate([[0], np.cumsum(lengths)]),
         task=np.array([r[0] for r in rows]), case=np.array([r[1] for r in rows]),
         concept=np.array([r[2] for r in rows]), heldout=np.array([r[0] in held_out for r in rows]))
counts = collections.Counter("heldout" if r[0] in held_out else "train" for r in rows)
json.dump({"names": names, "kinds": kinds}, open(f"{DATA}/vocab.json", "w"))
print(dict(counts), dict(problems), f"{len(mask_table)} distinct masks, {time.time() - t0:.0f}s")
