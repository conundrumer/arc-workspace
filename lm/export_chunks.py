"""Stream the corpus with masks in chunks of solvers, each in its own process, so an abort of the
engine in one chunk loses that chunk alone.

Writes work/lm/data/streams.pkl, which export.py reads in place of its arclog.corpus_streams call:
{"streams": [dict with the fields of arclog.CaseStream], "faults": [report lines]}. A chunk whose
process aborts is split in two and run again; a single solver whose process aborts gets a fault
line that names the abort.

    work/lm/.venv/bin/python -u lm/export_chunks.py [chunk size]
"""
import glob, os, pickle, subprocess, sys, time

DATA = "work/lm/data"
CHUNK = int(sys.argv[1]) if len(sys.argv) > 1 else 40
WORKER = """
import pickle, sys, arclog
ids = sys.argv[1].split(",")
streams, faults = arclog.corpus_streams("work/arclog/gen", all_cases=True, task_ids=ids, tasks="data/tasks")
rows = [dict(task=s.task, case=s.case, concept=s.concept, ids=bytes(s.ids), model=bytes(s.model),
             masks=None if s.masks is None else bytes(s.masks), mask_fault=s.mask_fault) for s in streams]
pickle.dump({"streams": rows, "faults": faults}, open(sys.argv[2], "wb"))
"""


def run(ids, out):
    r = subprocess.run([sys.executable, "-c", WORKER, ",".join(ids), out], capture_output=True, text=True)
    err = "\n".join(l for l in r.stderr.splitlines() if l.strip() and "RUST_BACKTRACE" not in l)
    return r.returncode, err


def stream(ids, depth=0):
    out = f"{DATA}/chunks/{ids[0]}-{len(ids)}.pkl"
    if os.path.exists(out):
        return pickle.load(open(out, "rb"))
    t = time.time()
    code, err = run(ids, out)
    if code == 0:
        print(f"{ids[0]}..{ids[-1]} ({len(ids)}): {time.time() - t:.0f}s", flush=True)
        return pickle.load(open(out, "rb"))
    print(f"{ids[0]}..{ids[-1]} ({len(ids)}): exit {code} after {time.time() - t:.0f}s: {err[-300:]}", flush=True)
    if len(ids) == 1:
        return {"streams": [], "faults": [f"{ids[0]}: the engine aborted the process (exit {code}): {err.splitlines()[-1] if err else ''}"]}
    half = len(ids) // 2
    a, b = stream(ids[:half], depth + 1), stream(ids[half:], depth + 1)
    return {"streams": a["streams"] + b["streams"], "faults": a["faults"] + b["faults"]}


os.makedirs(f"{DATA}/chunks", exist_ok=True)
ids = sorted(os.path.basename(p)[:-7] for p in glob.glob("work/arclog/gen/*.arclog"))
t0 = time.time()
streams, faults = [], []
for i in range(0, len(ids), CHUNK):
    part = stream(ids[i:i + CHUNK])
    streams += part["streams"]; faults += part["faults"]
pickle.dump({"streams": streams, "faults": faults}, open(f"{DATA}/streams.pkl", "wb"))
print(f"{len(ids)} solvers, {len(streams)} streams, {len(faults)} fault lines, {time.time() - t0:.0f}s", flush=True)
