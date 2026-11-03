#!/usr/bin/env python3
"""Cross-source joins, unions and same-source joins at two keys in the gold corpus, first case of each task.

  python3 gold_share.py [--seconds 20]
"""
import argparse
import collections
import glob
import gzip
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ident_sources as T  # noqa: E402

CORPUS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/corpus-v3mix/'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=20)
    a = ap.parse_args()
    c, t0 = collections.Counter(), time.time()
    shown = collections.defaultdict(list)
    tasks = sorted(os.listdir(CORPUS))
    for t in tasks:
        if time.time() - t0 > a.seconds:
            break
        p = CORPUS + t + '/pairs.jsonl.gz'
        if not os.path.exists(p):
            continue
        with gzip.open(p, 'rt') as f:
            r = json.loads(f.readline())
        c['tasks'] += 1
        tr = T.Tracer()
        cross = False
        for line in r['gold_sexp'].strip().split('\n'):
            if not line.startswith('('):
                continue
            head = line.split()[0][1:]
            if head == 'OUT':
                continue
            try:
                f_ = tr.add(line)
            except Exception as e:  # noqa: BLE001
                c['parse fail'] += 1
                continue
            ctx = tr.last_ctx
            c['forms'] += 1
            c['forms:' + head] += 1
            if f_.cols and any(f_.cols.values()):
                c['forms with an Ident column'] += 1
            if any(len(v) > 1 for v in f_.cols.values() if v):
                c['forms with a union column'] += 1
                if len(shown['union']) < 8:
                    shown['union'].append((t, line[:260]))
            for b in f_.bad:
                kind = 'neg' if b.get('neg') else 'pos'
                c['cross ' + kind] += 1
                cross = True
                if len(shown[kind]) < 8:
                    shown[kind].append((t, line[:260]))
            c['cross !='] += bool(ctx.get('ne'))
            if ctx.get('branch_cross'):
                c['forms with a branch that does not meet its outside'] += 1
                if len(shown['branch']) < 8:
                    shown['branch'].append((t, line[:300]))
            by = collections.defaultdict(set)
            for lab, nm, port, col, path_, key, got in ctx.get('reads', ()):
                by[lab, nm, port, col].add(key)
            for ty, comp in ctx.get('param_cross', ()):
                c['type parameter cross:%s:%s' % (comp, ty)] += 1
            two = [k for k, v in by.items() if len(v) > 1 and k[3] == 'Id']
            if two:
                c['forms join one source at two keys (Id column)'] += 1
                if len(shown['twokeys']) < 10:
                    shown['twokeys'].append((t, line[:300]))
            two_any = [k for k, v in by.items() if len(v) > 1]
            c['forms join one source at two keys (any Ident column)'] += bool(two_any)
            c['forms read an Ident in a join'] += any(len(v) >= 1 for v in by.values()) and len(ctx.get('reads', ())) > len(by)
        c['tasks with a cross-source join'] += cross
        c['tasks with a maker'] += any(f.kind == 'INIT' and (f.comp in ('Connectivity', 'Enclosure', 'Quotient')) for f in tr.forms.values())
        c['unread forms'] += sum(tr.unread_kinds.values())
        c['unknown reads'] += tr.unknown_reads
    print('%.1f s' % (time.time() - t0))
    for k in sorted(c):
        print('  %s: %d' % (k, c[k]))
    for k, v in shown.items():
        print('==', k)
        for t, x in v:
            print('  ', t, x)


if __name__ == '__main__':
    main()
