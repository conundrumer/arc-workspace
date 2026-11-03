#!/usr/bin/env python
"""Reads walks/*.jsonl.zst files of the pilot: python -I features_dagc_pilot.py FILE...

For each file: walks, drops by message, seconds per walk by kind, the share of picks with rowopts by kind (and the rest listed), and, for steers `off`, the picks that share a pick key (task, form, scope_id, phase, atom, downset)
across orders: whether their option sets and weights agree to 6 places.
"""
import collections
import io
import json
import sys

import zstandard


def rows(path):
    with open(path, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            if line.strip():
                yield json.loads(line)


def norm(opts):
    tot = sum(o[2] for o in opts) or 1.0
    return sorted((o[0], round(o[2] / tot, 6)) for o in opts)


def main():
    for path in sys.argv[1:]:
        walks = collections.Counter()
        secs = collections.defaultdict(list)
        drops = collections.Counter()
        picks = collections.Counter()
        has_ro = collections.Counter()
        missing = []
        keys = collections.defaultdict(list)
        heads = collections.Counter()
        for r in rows(path):
            if r['rec'] == 'form':
                walks[r['kind']] += 1
                secs[r['kind']].append(r['seconds'])
                if not r['ok']:
                    drops[r['drop']] += 1
                heads[r['heads_ok']] += 1
            else:
                picks[r['kind']] += 1
                ok = r['rowopts'] is not None and len(r['rowopts']) == len(r['opts']) and all(o.get('tok') is not None for o in r['rowopts'])
                has_ro[r['kind']] += ok
                if not ok and len(missing) < 5:
                    missing.append((r['task'], r['line_id'], r['phase']))
                keys[r['task'], r['form'], r['scope_id'], r['phase'], r['atom'], tuple(r['downset'])].append((r['order_id'], r['opts'], r['q_bits']))
        print(path)
        print('  walks %s; drops %s; heads_ok %s' % (dict(walks), dict(drops), dict(heads)))
        print('  seconds per walk: %s' % {k: round(sum(v) / len(v), 3) for k, v in secs.items()})
        print('  picks %s; rowopts present %s; missing %s' % (dict(picks), {k: '%d/%d' % (has_ro[k], picks[k]) for k in picks}, missing))
        multi = {k: v for k, v in keys.items() if len({o for o, _, _ in v}) > 1}
        bad_n = bad_w = 0
        for k, v in multi.items():
            if len({len(o) for _, o, _ in v}) > 1:
                bad_n += 1
            elif len({tuple(norm(o)) for _, o, _ in v}) > 1:
                bad_w += 1
        print('  pick keys %d; keys reached by more than one order %d; with two option counts %d; with option names or weights differing at 6 places %d' % (len(keys), len(multi), bad_n, bad_w))


if __name__ == '__main__':
    main()
