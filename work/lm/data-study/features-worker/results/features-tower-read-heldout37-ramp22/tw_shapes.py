"""Replays the held gold program of one task on its set's models, checks the Ident-only forms against the pinned list (K4), and writes
R/shapes/T.json: g, key, kind, shape, holds per form. A rerun with the file present does nothing.

  tw_shapes.py --task T [--force]
"""
import argparse
import json
import os
import sys
import time

import tw_lib as T

L = T.L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    task = a.task
    out = '%s/shapes/%s.json' % (T.R, task)
    if os.path.exists(out) and not a.force:
        print('%s: shapes done' % task)
        return 0
    live = T.setup()
    st = L.set_of(task)
    if st == 'corpus':
        sys.exit('%s is not a held task' % task)
    t0 = time.time()
    forms = T.gold_forms(task)
    sampler = live.Sampler(L.MODELS[st])
    sess, d = L.session_of(L.task_path(task, st))
    cts, err = L.replay(sampler, d, sess, forms)
    info, _ = L.analyze(forms, cts)
    got = [x['i'] for x in info if x['ident_only']]
    want = L.ident_list()[task]['ident_only']
    print('%s (%s): replay of %d forms in %.1fs, ident-only %s, pinned %s' % (task, st, len(forms), time.time() - t0, got, want), flush=True)
    if err or len(info) != len(forms) or got != want:
        sys.exit('K4 FAIL on %s: replay error %s, %d of %d analyzed, ident-only forms %s, pinned %s' % (task, err, len(info), len(forms), got, want))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = [dict(g=x['i'], key=x['head'], kind=x['kind'], shape=x['shape'], holds=bool(x['holds'])) for x in info]
    tmp = out + '.tmp'
    json.dump(rows, open(tmp, 'w'), separators=(',', ':'))
    os.replace(tmp, out)
    print('K4 PASS %s: %d forms, %.1f s' % (task, len(rows), time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
