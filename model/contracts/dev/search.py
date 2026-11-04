"""Dev labeling layer: its output is not model input.

The targeted stage: for each table, variants that meet its preconditions, edited further, kept where they still meet them.

    <runtime python> -I -B search.py TASK [PER_TABLE]

Reads out/<task>.variants.jsonl, appends records with ids search.<table>.<k>. Each variant's tables go to the table cache (tablecache.py). A restart skips the ids already written.
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'features'))
import analyze as A  # noqa: E402
import engine as E  # noqa: E402
import features as F  # noqa: E402
import run as R  # noqa: E402
import jsonl as J  # noqa: E402
import tablecache as C  # noqa: E402


def main(task, per_table=150, prefix='search'):
    path = R.OUT / (task + '.variants.jsonl')
    lines = list(J.records(path))
    done = {l['id'] for l in lines}
    base = next(l for l in lines if l['kind'] == 'base')
    post = A.postconditions(base)
    graph = {k: set(v) for k, v in base['graph'].items()}
    eng = C.Engine(task)
    s, bj = eng.s, eng.bj
    up = lambda g, name: E.upstream(g, name)
    tables = [t for t in base['tables'] if t not in ('ex_input', 'ex_output')]
    eg = E.reads(s.text)
    rd = E.table_reads(s.text)
    stored = {r['id']: r['stored'] for r in J.records(R.OUT / (task + '.stored.jsonl'))}
    t0, n, total = time.time(), 0, per_table * len(tables)
    fcache = F.FeatureCache()  # the features of tables that a variant leaves as they were
    ids = {'%s.%s.%d' % (prefix, t, k) for t in tables for k in range(per_table)} - done
    with J.Appender(path) as fo, C.Cache(task, eng, ids) as cache:
        for t in tables:
            ups = A.upstream(graph, t)
            pre = [k for k in post if k.split('|')[0].split('.')[0] in ups and not A.is_output(k)]
            ok = lambda feats: all(A.holds(post[p], feats.get(p, 'MISSING')) for p in pre)
            pool = [(l['source'], l['grid']) for l in lines if l['kind'] == 'in' and 'grid' in l and l.get('stored', stored.get(l['id'], 'same')) == 'same' and ok(l['features'])]
            pool += [('train/%d' % i, p['input']) for i, p in enumerate(bj['train'])]
            rng = random.Random('%s.%s.%s' % (task, prefix, t))
            for k in range(per_table):
                vid = '%s.%s.%d' % (prefix, t, k)
                src, g0 = rng.choice(pool)
                g, ops = R.mutate(g0, rng)
                n += 1
                if vid in done:
                    continue
                rec = dict(id=vid, kind='in', source=src, ops=ops, grid=g, target=t)
                try:
                    T, tj, ex = cache.tables(rec)
                    rec['features'] = R.enc(F.all_features(T, ex, tj, eg, up, R.grids_of, fcache, reads=rd, prov=s.provenance))
                    if rec['stored'] == 'same' and ok(rec['features']):
                        pool.append((src, g))
                except Exception as e:  # noqa: BLE001
                    rec['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
                fo.write(rec)
                if n % 200 == 0:
                    el = time.time() - t0
                    print('%s %d/%d  %.1f/s  eta %.0fs  (%s: pool %d)' % (task, n, total, n / el, (total - n) * el / n, t, len(pool)), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], *[int(a) if a.isdigit() else a for a in sys.argv[2:]])
