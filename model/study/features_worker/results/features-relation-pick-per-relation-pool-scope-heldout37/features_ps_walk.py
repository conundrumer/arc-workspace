#!/usr/bin/env python
"""Teacher-forced walks of the points of a points file, each over its own scope, with the walk of features_rel_walk.py.

  <runtime python> -u features_ps_walk.py --points P.jsonl --out OUT.jsonl.zst [--shard i/n] [--budget S] [--priors-fold TEMPLATE] [--limit N]

A point has task, scope (form texts), target and line, its id. One zstd frame per point, a restart skips the points it holds, and each point ends with a 'form' line that holds `decoded`: the head number that the decoder gives each scope form. Prints a rate and an ETA.
"""
import argparse
import collections
import glob
import json
import os
import pickle
import re
import sys
import time

import zstandard

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-pool-scope-heldout37')
import features_rel_walk as W  # noqa: E402

C, G, S, live, live_rows, or_q, P = W.C, W.G, W.S, W.live, W.live_rows, W.or_q, W.P
orig = W.RunX.drawer


def drawer(self, pg, kind, dec, place=None, prior=None):
    dr = orig(self, pg, kind, dec, place, prior)
    if 'decoded' not in W.CTX:
        W.CTX['decoded'] = [int(h[2:]) for h in (getattr(pg, 'written', None) or {})]
    return dr


W.RunX.drawer = drawer


def done_points(path):
    got = set()
    if os.path.exists(path):
        try:
            for d in C_records(path):
                got.add(d)
        except zstandard.ZstdError:
            pass
    return got


def C_records(path):
    import io
    with open(path, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            if line.startswith('{"rec": "form"'):
                yield json.loads(line)['line']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--points', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--budget', type=float, default=1e9)
    ap.add_argument('--priors-fold', default='')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    pts = [json.loads(x) for x in open(a.points)]
    i, n = map(int, a.shard.split('/'))
    tasks = sorted({p['task'] for p in pts})
    keep = {t for j, t in enumerate(tasks) if j % n == i}
    pts = [p for p in pts if p['task'] in keep]
    base = re.sub(r'-\d+of\d+\.jsonl\.zst$', '', a.out)
    done = set().union(*[done_points(p) for p in glob.glob(base + '-*of*.jsonl.zst')], done_points(a.out))
    todo = [p for p in pts if p['line'] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print('%d points in the shard, %d done, %d to do' % (len(pts), len(done), len(todo)), flush=True)
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    pri = {}
    t0 = time.time()
    cz = zstandard.ZstdCompressor(level=6)
    with open(a.out, 'ab') as out:
        for c, row in enumerate(todo, 1):
            task, line = row['task'], row['line']
            if time.time() - t0 > a.budget:
                break
            if a.priors_fold:
                fold = live_rows.fold_of(task, live_rows.FOLDS)
                if fold not in pri:
                    with open(a.priors_fold.format(fold), 'rb') as f:
                        pri[fold] = pickle.load(f)
                sampler.pri = pri[fold]
            scope, target = row['scope'], row['target']
            if task not in W.LIB:
                W.LIB.clear()
            G.gold_of = lambda t, c_, p, ls=scope + [target]: (t, ls)
            CTX, PEND = W.CTX, W.PEND
            CTX.clear()
            PEND.clear()
            CTX.update(task=task, line=line, orf='(OR ' in target, content_cpu=0.0, errs=collections.Counter(), grids=C.grids_of(json.load(open('%s/data/tasks/%s.json' % (P.REPO, task)))))
            t1 = time.process_time()
            rows = []
            try:
                q = or_q.one(sampler, task, 'RULE', [len(scope), 0], 'RULE', rows)
            except Exception as e:  # noqa: BLE001
                q = dict(error=repr(e)[:200])
            rel = [r for k, r in rows if k == 'rel']
            aligned = len(rel) == len(PEND) and all(r['k'] == p['k'] and r['phase'] == p['phase'] and len(r['options']) == len(p['opts']) for r, p in zip(rel, PEND))
            buf = []
            for j, p in enumerate(PEND):
                if aligned:
                    r = rel[j]
                    p['prefix'] = r['prefix']
                    p['where'], p['place'] = r['where'], r['place']
                    p['prefix_bases'], p['prefix_depth'] = r.get('prefix_bases'), r.get('prefix_depth')
                    p['rowopts'] = [dict(tok=o['tok'], kind=o['kind'], p=o['p'], types=o.get('types'), cols=o.get('columns'), dag=o.get('dag')) for o in r['options']]
                buf.append(json.dumps(p))
            cpu = time.process_time() - t1
            buf.append(json.dumps(dict(rec='form', task=task, line=line, orf=CTX['orf'], natoms=len(q.get('atoms', [])), total=q.get('total'), parts=q.get('parts'), bad=q.get('bad'), dead=q.get('dead'),
                                       error=q.get('error'), cpu=round(cpu, 3), content_cpu=round(CTX['content_cpu'], 3), picks=len(PEND), aligned=aligned, errs=dict(CTX['errs']), decoded=CTX.get('decoded'))))
            out.write(cz.compress(('\n'.join(buf) + '\n').encode()))
            out.flush()
            if c % 5 == 0 or c == len(todo):
                el = time.time() - t0
                print('[%d/%d %.0fs %.2f points/s eta %.0fs] %s %s' % (c, len(todo), el, c / el, el / c * (len(todo) - c), task, line), flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
