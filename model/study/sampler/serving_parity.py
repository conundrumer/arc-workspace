"""Serving parity: whether a worker's model input rows equal the rows that a session made for training gives at the same state and path.

With WRITER_PARITY_DIR set, a worker writes a sample of its points there: for each, the state's forms and the path, by token name, and the whole row. `serving_parity.py DIR --tree MODEL --models DIR` rebuilds each point at a session as training rows make it, compares every column, and exits 1 on a difference beyond float noise. A whole-atom point also compares the proposals and their bits. dev_run.py runs this before a live run, and refuses the run on a difference."""
import argparse
import base64
import collections
import glob
import io
import json
import os
import sys
import time

import numpy as np

DIR = os.environ.get('WRITER_PARITY_DIR')
SINK = []
SEEN = collections.Counter()
KEPT = collections.Counter()
PLAN = dict(token=(12, 25, 40), atom=(8, 5, 24))  # (the first points kept, then one in this many, up to this many)


def _b64(x):
    return base64.b64encode(np.asarray(x, '<f4').tobytes()).decode()


def _array(text, shape):
    return np.frombuffer(base64.b64decode(text), '<f4').reshape(shape)


def _put(record):
    import zstandard
    if not SINK:
        SINK.append(open(os.path.join(DIR, 'parity.%d.zst' % os.getpid()), 'ab'))
    SINK[0].write(zstandard.ZstdCompressor(level=3).compress((json.dumps(record) + '\n').encode()))
    SINK[0].flush()


def _due(name, pt):
    first, every, most = PLAN[name]
    SEEN[name] += 1
    if pt.run.__dict__.get('current_forms') is None or KEPT[name] >= most or (SEEN[name] > first and SEEN[name] % every):
        return False
    KEPT[name] += 1
    return True


def _task():
    return os.path.basename(sys.argv[sys.argv.index('--task') + 1]).split('.')[0]


def note_token(pt, ids, x, core):
    """A worker's token row: the point's row for each id."""
    if _due('token', pt):
        X = x.vectors()
        _put(dict(record='token', task=_task(), kind=pt.kind, forms=list(pt.run.current_forms), tokens=[core.names[int(t)] for t in pt.tokens], ids=[core.names[int(t)] for t in ids], columns=list(x.names), shape=list(X.shape), X=_b64(X)))


def note_atom(pt, keep, point, tok, struct, defined, av, delta, bits, core):
    """A worker's whole-atom row: the proposals at a decision and their columns."""
    if _due('atom', pt):
        _put(dict(record='atom', task=_task(), kind=pt.kind, forms=list(pt.run.current_forms), tokens=[core.names[int(t)] for t in pt.tokens], cands=[[core.names[int(t)] for t in c[0]] for c in keep], point=_b64(point), tok=_b64(tok), struct=_b64(struct), defined=_b64(defined), av=_b64(av), delta=_b64(delta), bits=_b64(bits), n=len(keep), widths=[len(point), tok.shape[1], struct.shape[1], av.shape[1]]))


def records(folder):
    import zstandard
    for path in sorted(glob.glob(os.path.join(folder, 'parity.*.zst'))):
        with open(path, 'rb') as raw:
            yield from map(json.loads, io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw, read_across_frames=True), encoding='utf-8'))


def differ(a, b):
    """The columns where two rows differ beyond float noise: a NaN equals a NaN."""
    both = np.isnan(a) & np.isnan(b)
    same = np.isclose(a, b, rtol=1e-4, atol=1e-5) | both
    return np.flatnonzero(~same.all(0))


def check(folder, tree, models, atoms_wanted=True):
    import live, live_try, tree_dist, writer
    live_try.P.REPO = os.environ.get('ARC_ROOT', live_try.P.REPO)
    distribution = tree_dist.load(tree)
    sampler = live.Sampler(models, steers=())
    by_task = collections.defaultdict(list)
    for r in records(folder):
        by_task[r['task']].append(r)
    points = collections.Counter()
    bad = collections.Counter()
    examples = {}
    for task, held in sorted(by_task.items()):
        sess, d, _ = live_try.session_of(task)
        run = live.Run(sampler.pri, sess, 0, time.monotonic() + 86400, d, live.Limits())
        writer.keep_state_tables(run)
        core = writer.core_of(run)
        plan = writer.default_plan(run, 3.0, ('legal',), distribution)
        at = {n: i for i, n in enumerate(core.names)}
        for r in held:
            dec, pg = run.scope(tuple(r['forms']))
            pg.new = []
            pt = writer.start_point(run, pg, run.open_form(pg, dec, r['kind']), r['kind'])
            for name in r['tokens'][len(pt.tokens):]:
                pt = writer.step_point(pt, at[name])
            if r['record'] == 'token':
                ids = np.array([at[n] for n in r['ids']], pt.ids_.dtype)
                x = writer.Features(pt, ids)
                if list(x.names) != r['columns']:
                    bad['column names differ'] += 1
                    continue
                here = x.vectors()
                there = _array(r['X'], r['shape'])
                points['token'] += 1
                points['token columns'] = here.shape[1]
                for c in differ(here, there):
                    bad['token ' + r['columns'][c]] += 1
                    examples.setdefault('token ' + r['columns'][c], (task, r['tokens'][-3:], here[:, c][:4].tolist(), there[:, c][:4].tolist()))
            else:
                import atom_writer as AW
                n, (p_w, t_w, s_w, a_w) = r['n'], r['widths']
                cands = []
                for tokens in r['cands']:
                    end = pt
                    for name in tokens:
                        end = writer.step_point(end, at[name])
                    cands.append(([at[x] for x in tokens], end, 0.0, 0.0))
                got = AW.rows_of(pt, cands, core)
                points['atom'] += 1
                if got is None or len(got[6]) != n:
                    bad['atom candidates lost'] += 1
                    continue
                pairs = dict(point=(got[0][None, :], _array(r['point'], (1, p_w))), tok=(got[1], _array(r['tok'], (n, t_w))), struct=(got[2], _array(r['struct'], (n, s_w))), defined=(got[3][:, None], _array(r['defined'], (n, 1))), av=(got[4], _array(r['av'], (n, a_w))), delta=(got[5], _array(r['delta'], (n, a_w))))
                for block, (a, b) in pairs.items():
                    for c in differ(a, b):
                        bad['atom %s column %d' % (block, c)] += 1
                        examples.setdefault('atom %s column %d' % (block, c), (task, r['tokens'][-3:], a[:, c][:4].tolist(), b[:, c][:4].tolist()))
                walk = AW.top_atoms(pt, AW.K, core, plan)
                mine = [[core.names[x] for x in c[0]] for c in walk]
                if mine != r['cands']:
                    bad['atom proposals differ'] += 1
                    examples.setdefault('atom proposals differ', (task, r['tokens'][-3:], mine[:4], r['cands'][:4]))
                else:
                    bits = np.array([c[2] for c in walk], np.float32)
                    if not np.isclose(bits, _array(r['bits'], (n,)), rtol=1e-3, atol=1e-3).all():
                        bad['atom bits differ'] += 1
    print('serving parity on', len(by_task), 'tasks:', dict(points))
    if bad:
        print('DIFFERENCES:')
        for k, v in bad.most_common(30):
            print('  %s at %d points: %s' % (k, v, str(examples.get(k, ''))[:220]))
    else:
        print('no difference beyond float noise')
    return not bad and points['token'] > 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('folder'); ap.add_argument('--tree', required=True); ap.add_argument('--models', required=True)
    a = ap.parse_args()
    sys.exit(0 if check(a.folder, a.tree, a.models) else 1)
