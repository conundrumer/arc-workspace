"""The stem rows of the census50 pass: runs a stem check on each stem of tasks-census50.txt, one process at a time, under the time cap and the memory cap. One row per stem, streamed; a restart skips finished stems.

  <runtime python> gold_helper_census50.py [ONE.py]
ONE.py defaults to gold_helper_one.py. Rows go to round-out/rows-census50.jsonl, each with the runtime and the wheel hash. A stem past a cap gets an error row and no retry.
"""
import hashlib, json, os, subprocess, sys, time
SECONDS, BYTES = 900, 8 << 30
here = os.path.dirname(os.path.abspath(__file__))
one = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'gold_helper_one.py')
RUNTIME = 'runtime-ba0754492'
WHEEL = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-ba0754492/wheels/arclog-0.1.0-cp312-abi3-macosx_11_0_arm64.whl'
sha = hashlib.sha256(open(WHEEL, 'rb').read()).hexdigest()
if not sha.startswith('a3278497561b3fab'):
    sys.exit('wheel hash differs from the manifest')
lines, crossing = here + '/round-out/lines-census50.json', here + '/round-out/crossing-census50.json'
out = here + '/round-out/rows-census50.jsonl'
done = {json.loads(l)['task'] for l in open(out)} if os.path.exists(out) else set()
cuts = json.load(open(crossing))


def rss(pid):
    p = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True)
    return int(p.stdout.strip() or 0) * 1024


def run(t):
    """One stem: its output and the cap it passed, or None."""
    p = subprocess.Popen([sys.executable, '-u', one, t, lines, crossing], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=here)
    t0, peak, over = time.time(), 0, None
    while p.poll() is None and over is None:
        peak = max(peak, rss(p.pid))
        over = 'time' if time.time() - t0 > SECONDS else 'memory' if peak > BYTES else None
        if over is None:
            try:
                p.wait(2)
            except subprocess.TimeoutExpired:
                pass
    if over:
        p.kill()
    o, e = p.communicate()
    return o, e, over, peak, round(time.time() - t0, 1)


with open(out, 'a') as f:
    for t in open(here + '/tasks-census50.txt').read().split():
        if t in done:
            continue
        if not cuts.get(t):
            row = dict(task=t, clauses=0, applied=[], failed=[])
            o, e, over, peak, wall = '', '', None, 0, 0
        else:
            o, e, over, peak, wall = run(t)
            rows = [l for l in o.splitlines() if l.startswith('{"task"')]
            row = json.loads(rows[-1]) if rows else dict(task=t, error=over or e[-300:])
        row.update(wall=wall, peak_gib=round(peak / (1 << 30), 2), runtime=RUNTIME, wheel_sha256=sha)
        f.write(json.dumps(row) + '\n')
        f.flush()
        print({k: v for k, v in row.items() if k != 'program'}, flush=True)
