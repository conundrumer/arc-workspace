"""Dev labeling layer: the input worlds of a task, which novelty.py reads. Not model input.

    <runtime python> -I -B judge_worlds.py OUT_DIR K TASK [TASK ...]

A task's worlds are its own examples and K input variants of its corpus (a seeded sample), each run as an extra test input. Each world holds
every table's features at its example, the row digests, the solver's output grid there, and the base tables' features
(features.base_features). Tables come from the table cache; a variant that the cache lacks is skipped, and the end of the run says how many.

Writes OUT_DIR/<task>.worlds.jsonl: a base record with the own examples, each form's reads (engine.table_reads), each instance's input
ports and each table's columns, then one record per variant. A restart skips the variants written.
"""
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'features'))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import jsonl as J  # noqa: E402
import outvariants as O  # noqa: E402
import paths  # noqa: E402
import query as Q  # noqa: E402
import run as R  # noqa: E402
import tablecache as C  # noqa: E402
from refeature import digests  # noqa: E402

CORPUS = paths.DATA / 'corpus'


def solver_grid(T, ex, out):
    """The solver's output grid at ex, or None where its rows give no whole grid."""
    try:
        return O.out_grid(T, ex, [list(x) for x in out])
    except (IndexError, ValueError):
        return None


def base_of(task_json, ex):
    """{base table: {feature: value}} at ex, descriptions left out."""
    out = {}
    for (b, k), v in F.base_features(task_json, ex, R.grids_of).items():
        if not k.endswith(' describe'):
            out.setdefault(b, {})[k] = v
    return out


def main(out_dir, k, tasks):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        dst = out_dir / (task + '.worlds.jsonl')
        done = {r['id'] for r in J.records(dst)} if J.exists(dst) else set()
        t0 = time.time()
        eng = C.Engine(task)
        s, bj, T0 = eng.s, eng.bj, eng.T0
        graph, rd = E.reads(s.text), E.table_reads(s.text)
        up = lambda g, name: E.upstream(g, name)
        fcache = F.FeatureCache()
        corpus = [r for r in J.records(CORPUS / (task + '.jsonl')) if r.get('kind') == 'in' and 'grid' in r]
        random.Random(task).shuffle(corpus)
        want = {r['id']: r for r in corpus[:k] if r['id'] not in done}
        n = 0
        with J.Appender(dst) as fo:
            if 'base' not in done:
                exs = ['train/%d' % j for j in range(len(bj['train']))] + ['test/%d' % j for j in range(len(bj['test']))]
                worlds = {ex: dict(features=R.enc(F.all_features(T0, ex, bj, graph, up, R.grids_of, fcache, reads=rd, prov=s.provenance)),
                                   digests=digests(T0, ex), solver_out=solver_grid(T0, ex, s.out), base=base_of(bj, ex)) for ex in exs}
                qf = Q.query_features(s.text)
                ports = {f: sorted(Q.component_inputs().get(q.get('component'), ())) for f, q in qf.items() if q.get('component')}
                fo.write(dict(id='base', task=task, examples=worlds, reads={kk: sorted(v) for kk, v in rd.items()}, instance_inputs=ports,
                              tables={nm: [list(c) for c in t['columns']] for nm, t in T0.items()}))
            with C.Cache(task, eng, hold=False) as cache:
                for r, T, tj, ex in cache.hits(want):
                    try:
                        rec = dict(id=r['id'], ex=ex, source=r.get('source'),
                                   features=R.enc(F.all_features(T, ex, tj, graph, up, R.grids_of, fcache, reads=rd, prov=s.provenance)),
                                   digests=digests(T, ex), solver_out=solver_grid(T, ex, s.out), base=base_of(tj, ex))
                    except Exception as e:  # noqa: BLE001
                        rec = dict(id=r['id'], error='%s: %s' % (type(e).__name__, str(e)[:200]))
                    fo.write(rec)
                    n += 1
                    if n % 100 == 0:
                        el = time.time() - t0
                        print('%s %d/%d  %.1f/s  eta %.0fs' % (task, n, len(corpus[:k]), n / el, (len(corpus[:k]) - n) * el / n), flush=True)
        print('%s done: %d worlds, %d not in the cache, %.0f s' % (task, n, len(want), time.time() - t0), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3:])
