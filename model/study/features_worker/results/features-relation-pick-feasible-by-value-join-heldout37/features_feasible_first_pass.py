#!/usr/bin/env python
"""First pass at the feasible set, from the rank read's existing rows alone: no engine call.

Reads the join features that the rank read wrote per option (j_read, j_pairs, j_zero) and writes one row per gold-alive pick to first-pass-rows.jsonl. The rows hold capped tables and leave out Ident joins, so an option with no read stays in the set. Use features_feasible_walk.py for the set that the report quotes.

  python features_feasible_first_pass.py
"""
import io
import json
import math
import os
import statistics as st

import zstandard

HERE = os.path.dirname(os.path.abspath(__file__))
RANK = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-rank-context-rows-heldout37/'
NOPT = 19  # count of C.OPTION
J_READ, J_PAIRS, J_ZERO = NOPT, NOPT + 1, NOPT + 4
T_READ, T_EMPTY = 0, 1


def records(path):
    with open(path, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            yield json.loads(line)


def status(d, j):
    """'in', 'out' or 'unread' for option j of pick d."""
    x, c = d['opts'][j], d['cont'][j]
    if x[1] in ('NOT', 'CMP'):
        return 'unread'
    if d['k'] == 1:
        if not c[T_READ]:
            return 'unread'
        return 'out' if c[T_EMPTY] else 'in'
    if x[3]:
        return 'out'  # dead by column type
    if not c[J_READ] or not c[J_PAIRS]:
        return 'unread'
    return 'out' if c[J_ZERO] else 'in'


def main():
    out = open(HERE + '/first-pass-rows.jsonl', 'w')
    buf, rows = [], []
    for d in records(RANK + 'walks/features-walk-held-0of1.jsonl.zst'):
        if d['rec'] != 'form':
            buf.append(d)
            continue
        ok = not (d['error'] or d['dead'] or d['bad'] or not d['aligned'])
        for p in buf if ok else ():
            g = p['gold_idx']
            if g is None or p['opts'][g][3]:
                continue
            s = [status(p, j) for j in range(len(p['opts']))]
            W = sum(x[2] for x in p['opts'])
            alive = [j for j, x in enumerate(p['opts']) if not x[3]]
            keep = [j for j in alive if s[j] != 'out']
            Wk = sum(p['opts'][j][2] for j in keep)
            r = dict(task=p['task'], line=p['line'], ord=p['ord'], phase=p['phase'], k=p['k'], gold=p['gold'], gold_kind=p['gold_kind'], own=p['own'], q_bits=p['q_bits'], nalive=len(alive), nfeas=len(keep), nunread=sum(s[j] == 'unread' for j in alive), gold_status=s[g],
                     bits_uniform=math.log2(len(keep)) if s[g] != 'out' else None, bits_restricted=-math.log2(p['opts'][g][2] / Wk) if s[g] != 'out' else None, check_q=-math.log2(p['opts'][g][2] / W))
            rows.append(r)
            out.write(json.dumps(r) + '\n')
        out.flush()
        buf = []
    n = len(rows)
    ing = [r for r in rows if r['gold_status'] != 'out']
    print('picks', n, 'prior bits %.3f' % st.mean(r['q_bits'] for r in rows), 'max gap to weights %.4f' % max(abs(r['q_bits'] - r['check_q']) for r in rows))
    print('alive median %.1f, kept median %.1f, unread median %.1f' % (st.median(r['nalive'] for r in rows), st.median(r['nfeas'] for r in rows), st.median(r['nunread'] for r in rows)))
    print('gold kept %d of %d, gold status %s' % (len(ing), n, {k: sum(r['gold_status'] == k for r in rows) for k in ('in', 'out', 'unread')}))
    print('on gold-kept picks: prior %.3f, restricted %.3f, uniform %.3f' % (st.mean(r['q_bits'] for r in ing), st.mean(r['bits_restricted'] for r in ing), st.mean(r['bits_uniform'] for r in ing)))


if __name__ == '__main__':
    main()
