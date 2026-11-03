"""Runs gold_helper_one.py on a shard of the stems, one process per stem under a time cap. One row per stem, streamed; a restart skips finished stems.

  gold_helper_run.py TASKS.txt LINES.json CROSSING.json OUT.jsonl SHARD SHARDS
"""
import json, os, resource, subprocess, sys, time, zlib
tasks, lines, crossing, out, k, n = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6])
SECONDS, BYTES = 900, 12 << 30
done = {json.loads(l)['task'] for l in open(out)} if os.path.exists(out) else set()
here = os.path.dirname(os.path.abspath(__file__))


def limit():
    if sys.platform == 'linux':
        resource.setrlimit(resource.RLIMIT_AS, (BYTES, BYTES))


with open(out, 'a') as f:
    for t in open(tasks).read().split():
        if t in done or zlib.crc32(t.encode()) % n != k:
            continue
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, '-u', os.path.join(here, 'gold_cover_one.py'), t, lines, crossing, 'covers.json'], capture_output=True, text=True, timeout=SECONDS, preexec_fn=limit)
            rows = [l for l in p.stdout.splitlines() if l.startswith('{"task"')]
            row = json.loads(rows[-1]) if rows else dict(task=t, error=p.stderr[-300:])
        except subprocess.TimeoutExpired:
            row = dict(task=t, error='time')
        row['wall'] = round(time.time() - t0, 1)
        f.write(json.dumps(row) + '\n')
        f.flush()
