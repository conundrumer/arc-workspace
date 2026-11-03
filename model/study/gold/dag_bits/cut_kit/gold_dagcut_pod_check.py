"""The checks of check.sh for the DAG split stage. Each part prints what it read and `ok`, and exits 1 at the first failure.

  <runtime python> gold_dagcut_pod_check.py limits SHARDS      the wheel, /proc, and the process, file and memory limits for SHARDS shards (gold_combined_check.py)
  <runtime python> gold_dagcut_pod_check.py group              the group memory count, the cap and the reaping, on test processes (gold_combined_check.py)
  <runtime python> gold_dagcut_pod_check.py rows ROWS EXPECTED the check stem's row against the row that the Mac gave
  <runtime python> gold_dagcut_pod_check.py expect ROWS EXPECTED writes EXPECTED from the rows of a Mac run

A row is compared by its digest: the hashes and numbers that do not depend on the machine's time. Bits are compared to 0.02, since the pod's libm may differ from the Mac's in the last digit of a sum.
"""
import hashlib, json, sys
import gold_combined_check as C

TOL = 0.02


def block(b):
    return None if b is None else {k: b.get(k) for k in ('forms', 'undrawn', 'kinds', 'status', 'bits', 'worst', 'sum', 'score')}


def digest(r):
    return dict(stage=r.get('stage'), task=r.get('task'), base_sha=r.get('base_sha'), cap=r.get('cap'), delta=r.get('delta'), base_ended=r.get('base_ended'), landed=r.get('landed'),
                program_steps=[hashlib.sha256(s['program'].encode()).hexdigest()[:16] for s in r.get('steps') or []],
                steps=[[s.get('shape'), s.get('form'), s.get('rank'), s.get('forms')] for s in r.get('steps') or []],
                before=block(r.get('before')), after=block(r.get('after')))


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) <= TOL
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def rows(path, expected):
    got = [json.loads(l) for l in open(path)]
    want = json.load(open(expected))
    if [r['stage'] for r in got] != ['dagcut'] * len(want) or len(got) != len(want):
        C.fail('the check has rows %s, not %d of dagcut' % ([r['stage'] for r in got], len(want)))
    for r, w in zip(got, want):
        c = r.get('counts') or {}
        print(r['stage'], r['task'], 'cpu', r.get('cpu'), 'wall', r.get('wall'), 'peak GiB', r.get('peak_gib'), 'processes', r.get('peak_procs'), 'dag reads', c.get('dag reads'), 'walks', c.get('walks'), 'steps', len(r.get('steps') or []), 'error', r.get('error'))
        if r.get('error') or not r.get('finished'):
            C.fail('the %s stage did not finish' % r['stage'])
        if not r.get('peak_gib') or (r.get('peak_procs') or 0) < 2 or not c.get('dag reads'):
            C.fail('the %s stage shows no reads or no memory count' % r['stage'])
        if c.get('read crashes'):
            C.fail('a fork ended with no answer')
        d = digest(r)
        for k in w:
            if not same(d[k], w[k]):
                C.fail('%s of the %s stage is not the Mac\'s: %s against %s' % (k, r['stage'], str(d[k])[:300], str(w[k])[:300]))
    print('rows ok: the dagcut row equals the Mac\'s row')


def expect(path, out):
    got = [json.loads(l) for l in open(path)]
    json.dump([digest(r) for r in got], open(out, 'w'), indent=1)
    print('wrote', out, len(got), 'rows')


if __name__ == '__main__':
    what = sys.argv[1]
    if what == 'limits':
        C.limits(int(sys.argv[2]))
    elif what == 'group':
        C.group()
    elif what == 'rows':
        rows(sys.argv[2], sys.argv[3])
    else:
        expect(sys.argv[2], sys.argv[3])
