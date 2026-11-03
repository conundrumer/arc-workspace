"""Throwaway: first rows of a non-held walk, without the content columns, with a read rate. Runs under the kaggle runtime python for zstandard."""
import collections
import io
import json
import sys
import time

import zstandard

P = sys.argv[1]
N = int(sys.argv[2])
t0 = time.time()
n = 0
forms = 0
kinds = collections.Counter()
phases = collections.Counter()
ok = collections.Counter()
with open(P, 'rb') as f:
    for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
        d = json.loads(line)
        if d['rec'] == 'form':
            forms += 1
            ok[(d.get('bad') == [] and d.get('dead') is None, d.get('aligned'))] += 1
            if forms == 1:
                print(json.dumps(d)[:600])
        else:
            n += 1
            kinds[d['gold_kind']] += 1
            phases[d['phase']] += 1
            if n in (1, 2, 5, 40):
                x = {k: v for k, v in d.items() if k not in ('cont', 'rowopts', 'pre')}
                x['opts'] = x['opts'][:4] + ['...'] + x['opts'][-4:]
                x['nopts'] = len(d['opts'])
                print(json.dumps(x)[:1100])
                print(json.dumps(d.get('rowopts', [])[:2])[:500])
        if n >= N:
            break
print(n, forms, kinds, phases, ok, round(time.time() - t0, 2))
