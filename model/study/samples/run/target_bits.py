#!/usr/bin/env python
"""target_bits.py OUT SET SKELETON TASK... --tree MODEL: a target query's whole cost under a token tree at a state: its bits over all its tokens, kept separately for the head and the body, the choices where it isn't the top token, and how far the top is above it. One JSON line per target, one file per task, zstd. Run with the kit's runtime python and the overlay's folders first on PYTHONPATH."""
import argparse, importlib, io, json, os, time, types
from pathlib import Path
import numpy as np
import zstandard
import live, live_try, writer, train_rows, order, tree_dist
ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('set'); ap.add_argument('skeleton'); ap.add_argument('tasks', nargs='+'); ap.add_argument('--tree'); ap.add_argument('--samples', type=int, default=16); ap.add_argument('--targets', type=int, default=12)
a = ap.parse_args()
live_try.P.REPO = os.environ.get('ARC_ROOT', live_try.P.REPO)
pw = importlib.import_module('points_write')
TREE = tree_dist.load(a.tree)


def main():
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    smp = live.Sampler(str(Path(writer.__file__).resolve().parents[3] / 'models-current'), steers=())
    for task in a.tasks:
        path = out / f'{task}.zst'
        if path.exists():
            continue
        t0 = time.time()
        records = [json.loads(x) for x in (Path(a.skeleton) / f'{task}.jsonl').read_text().splitlines()]
        queries = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = [r for r in records if r['record'] == 'sample']
        sess, d, _ = live_try.session_of(task)
        run = live.Run(smp.pri, sess, 0, time.monotonic() + 86400, d, live.Limits())
        writer.keep_state_tables(run)
        plan = writer.default_plan(run, 3.0, ('legal',), TREE)
        env = types.SimpleNamespace(live=live, run=run)
        dec_order = train_rows.order_env(run)
        tmp = path.with_suffix('.working')
        n = 0
        with io.TextIOWrapper(zstandard.ZstdCompressor(level=3).stream_writer(open(tmp, 'wb')), encoding='utf-8') as sink:
            for sample in samples[:a.samples]:
                try:
                    texts, label = pw.scope_of(sample['state']['queries'], queries)
                    scope = tuple(texts)
                    dec0, _ = run.scope(scope)
                except Exception:
                    continue
                for h in sample['target_queries'][:a.targets]:
                    try:
                        kind, stream = pw.query_stream(env, scope, pw.rewrite(queries[h], label, f'&r{len(scope)}'))
                        walk, _, _ = order.canonical_stream(dec_order, dec0, kind, stream, train_rows.ORDER_SECONDS)
                        walk = [int(t) for t in walk]
                        if walk and walk[0] == live.KIND_TOK[kind]:
                            walk = walk[1:]
                        dec, pg = run.scope(scope)
                        pg.new = []
                        pt = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
                        head = body = 0.0
                        off = 0
                        gaps = []
                        ok = True
                        for t in walk:
                            if pt.track.where == 'done':
                                break
                            ids, fac, reason = writer.options(pt, plan)
                            at = np.flatnonzero(ids == t)
                            if reason or not len(at):
                                ok = False
                                break
                            if len(ids) > 1:
                                p, _ = writer.probabilities(pt, plan, ids, fac)
                                b = float(-np.log2(max(float(p[at[0]]), 1e-12)))
                                if pt.track.where == 'body':
                                    body += b
                                else:
                                    head += b
                                if p[at[0]] < p.max():
                                    off += 1
                                    gaps.append(round(float(np.log2(p.max() / max(float(p[at[0]]), 1e-12))), 2))
                            pt = writer.step_point(pt, t)
                        sink.write(json.dumps(dict(task=task, sample=sample['id'], target=h, kind=kind, head=head, body=body, off=off, gaps=gaps, ok=ok, tokens=len(walk))) + '\n')
                        n += 1
                    except Exception as e:
                        print('target failed', task, h[:8], type(e).__name__, str(e)[:100], flush=True)
        os.replace(tmp, path)
        print(f'{task}: {n} targets, {time.time() - t0:.1f}s', flush=True)


if __name__ == '__main__':
    main()
