"""Stream the corpus with masks in chunks of solvers, each in its own process, so an abort of the
engine in one chunk loses that chunk alone.

Writes work/lm/data/streams.pkl, which export.py reads in place of its arclog.corpus_streams call:
{"streams": [dict with the fields of arclog.CaseStream], "faults": [report lines]}. A chunk whose
process aborts is split in two and run again; a single solver whose process aborts gets a fault
line that names the abort.

    work/lm/.venv/bin/python -u model/export_chunks.py [chunk size]
"""
import glob, json, os, pickle, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from arclog_convert import determination_gate as D

DATA = "work/lm/data"
CHUNK = int(sys.argv[1]) if len(sys.argv) > 1 else 40
WORKER = f"""
import pickle, sys, arclog
sys.path.insert(0, {os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "arclog-py")!r})
import tables_export
sys.path.insert(0, {os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")!r})
import json
from pathlib import Path
from arclog_convert import determination_gate as D
ids = sys.argv[1].split(",")
receipts = json.load(open(sys.argv[3]))
if any(receipts[t]["context"] != D.mask_context() for t in ids):
    raise D.EndCheckFailed("chunk mask engine differs from its admission context")
for t in ids:
    D.check_unchanged(receipts[t], Path("programs/arclog"), Path("data/tasks"))
streams, faults = arclog.corpus_streams("programs/arclog", all_cases=True, task_ids=ids, tasks="data/tasks")
for t in ids:
    D.check_unchanged(receipts[t], Path("programs/arclog"), Path("data/tasks"))
pickle.dump({{"streams": [tables_export.stream_fields(s) for s in streams], "faults": faults,
             "determination_receipts": {{t: receipts[t] for t in ids}}}}, open(sys.argv[2], "wb"))
"""


def run(ids, out):
    r = subprocess.run([sys.executable, "-c", WORKER, ",".join(ids), out, f"{DATA}/determination-receipts.json"], capture_output=True, text=True)
    err = "\n".join(l for l in r.stderr.splitlines() if l.strip() and "RUST_BACKTRACE" not in l)
    return r.returncode, err


def stream(ids, depth=0):
    out = f"{DATA}/chunks/{ids[0]}-{len(ids)}.pkl"
    if os.path.exists(out):
        cached = pickle.load(open(out, "rb"))
        try:
            D.validate_cached(cached.get("determination_receipts", {}), {t: RECEIPTS[t] for t in ids})
            return cached
        except D.EndCheckFailed:
            pass  # Unproven cached masks are regenerated, never admitted.
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
    return {"streams": a["streams"] + b["streams"], "faults": a["faults"] + b["faults"],
            "determination_receipts": {**a.get("determination_receipts", {}), **b.get("determination_receipts", {})}}


os.makedirs(f"{DATA}/chunks", exist_ok=True)
ids = sorted(os.path.basename(p)[:-7] for p in glob.glob("programs/arclog/*.arclog"))
t0 = time.time()
RECEIPTS = D.require(ids, Path("programs/arclog"), Path("data/tasks"),
                     Path(DATA) / "determination_end_check", D.mask_context())
Path(f"{DATA}/determination-receipts.json").write_text(json.dumps(RECEIPTS))
streams, faults = [], []
for i in range(0, len(ids), CHUNK):
    part = stream(ids[i:i + CHUNK])
    streams += part["streams"]; faults += part["faults"]
for task in ids:
    D.check_unchanged(RECEIPTS[task], Path("programs/arclog"), Path("data/tasks"))
pickle.dump({"streams": streams, "faults": faults, "determination_receipts": RECEIPTS}, open(f"{DATA}/streams.pkl", "wb"))
print(f"{len(ids)} solvers, {len(streams)} streams, {len(faults)} fault lines, {time.time() - t0:.0f}s", flush=True)
