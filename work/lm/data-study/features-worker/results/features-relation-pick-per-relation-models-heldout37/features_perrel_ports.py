#!/usr/bin/env python
"""The port name of each (component, relation index) and a check of the token map, on the walks of non-held tasks.

  python features_perrel_ports.py WALK NAME [--parents]

Tallies, at picks where gold's relation is a method of an INIT form, the `.port` of that form in the target's text, and writes ports.json from the fit walks. Reports how often the token map finds a target's relation by name, which checks the slots. Only the static name of a port leaves this script.
"""
import collections
import gzip
import json
import os
import re
import sys
import time

import zstandard
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_perrel_keys as K

OUT = os.path.dirname(os.path.abspath(__file__)) + '/'
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-rank-context-rows-heldout37/walks/'
CORPUS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/corpus-v3mix/'
HELD = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/points-base.json'


def recs(p):
    with open(p, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            yield json.loads(line)


def gold_lines(task, held):
    if held is not None:
        return [x for x in held[task].splitlines() if x.strip()]
    with gzip.open(CORPUS + task + '/pairs.jsonl.gz', 'rt') as f:
        return [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]


def main():
    name, mode = sys.argv[1], sys.argv[2]
    held = {x['task']: x['gold_sexp'] for x in json.load(open(HELD))} if 'held' in name else None
    tally = collections.Counter()
    c = collections.Counter()
    F, t0 = {}, time.time()
    for d in recs(W + name):
        if d['rec'] != 'rel':
            continue
        task = d['task']
        if task not in F:
            F[task] = (K.Forms(gold_lines(task, held)))
        f = F[task]
        kept = K.parents(f.lines, d['line']) if mode == 'parents' else list(range(d['line']))
        sl, n = f.slots(kept)
        c['picks'] += 1
        for o in d.get('rowopts') or []:
            if o['kind'] == 'derived':
                c['derived options'] += 1
                t = int(o['tok'][2:])
                if t not in sl:
                    c['tok past slots'] += 1
                    continue
                L, j = sl[t]
                b = o['dag']['base'] if o['dag'] else None
                base_ok = b == '&r%d' % (t - j)
                c['base agrees'] += base_ok
                c['method agrees'] += bool(o['dag'] and o['dag']['method']) == (f.info[L][0] in ('INIT', 'RIGID_DET') and True)
        if d['gold_kind'] == 'relation':
            t = int(d['gold'][2:])
            c['gold derived'] += 1
            if t not in sl:
                c['gold past slots'] += 1
                continue
            L, j = sl[t]
            target = f.lines[d['line']]
            hd = '&r%d' % f.num[L]
            ok = re.search(re.escape(hd) + r'[\s.)]', target) is not None
            c['gold form named in target'] += ok
            if ok and f.info[L][0] == 'INIT':
                for p in re.findall(re.escape(hd) + r'\.(\w+)', target):
                    tally[f.info[L][2], j, p] += 1
    print(name, dict(c), '%.0fs' % (time.time() - t0))
    print(len(tally))
    json.dump([[a, b, p, n] for (a, b, p), n in tally.items()], open(OUT + 'scratch/ports-%s.json' % name.split('.')[0], 'w'))


if __name__ == '__main__':
    main()
