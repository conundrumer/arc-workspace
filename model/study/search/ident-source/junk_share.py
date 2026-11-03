#!/usr/bin/env python3
"""Share of kept pool tables whose clause joins Ident columns across sources.

  python3 junk_share.py [--arm context_nocover] [--seconds 22] [--every 1]

Reads *.nodes.jsonl.zst of one arm, tasks in a fixed hash order, until the time budget ends, and prints the sample it
read. A node counts as direct where its own clause holds a cross-source join, and as inherited where a clause it reads,
at any depth, holds one. Both would not be drawn under the rule.
"""
import argparse
import collections
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ident_sources as T  # noqa: E402

RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-pool-context-steers-rest31-600s-c87cf482a/out/'


def lines_of(path):
    p = subprocess.Popen(['zstd', '-dcq', path], stdout=subprocess.PIPE, bufsize=1 << 20)
    for raw in p.stdout:
        i = raw.find(b'"x_rows":')
        j = raw.rfind(b',"table_types"')
        yield json.loads(raw[:i] + raw[j + 1:] if i >= 0 else raw)
    p.wait()


def one_task(path, c, examples):
    tr = T.Tracer()
    refused = {}  # form name -> direct or inherited
    for r in lines_of(path):
        text = r['clause']
        name = text.split()[1]
        fresh = name not in tr.forms
        f = tr.add(text)
        if fresh:
            reads = {m.split('.')[0] for m in text.split() for m in [m.strip('()')] if m.startswith('&')} - {name}
            refused[name] = 'direct' if [b for b in f.bad if not b.get('neg')] else 'neg' if f.bad else 'inherited' if any(refused.get(x) for x in reads) else None
            if refused[name] in ('direct', 'neg') and len(examples) < 40:
                examples.append(text[:300])
            ctx = tr.last_ctx
            c['forms'] += 1
            c['forms:' + f.kind] += 1
            c['forms unread'] += not f.known
            c['forms ne cross'] += bool(ctx.get('ne'))
            c['forms union label'] += bool(ctx.get('union_labels'))
            c['forms branch cross'] += bool(ctx.get('branch_cross'))
            if refused[name]:
                c['forms refused:' + refused[name]] += 1
            for b in f.bad:
                pair = sorted({T.component_of(tr.forms, x) for x in b['a']} | {T.component_of(tr.forms, x) for x in b['b']})
                c['join:%s:%s:%s' % (f.kind, 'neg' if b.get('neg') else 'pos', '+'.join(pair))] += 1
            # same source, two keys
            by = collections.defaultdict(set)
            scope = {}
            for lab, nm, port, col, path_, key, got in ctx.get('reads', ()):
                by[lab, nm, port, col].add(key)
                # the options a label pick has at this Ident site: the Ident labels already in scope
                others = {k: v for k, v in scope.items() if k != lab}
                c['site options'] += len(others)
                c['site options cross'] += sum(1 for v in others.values() if not v & got)
                c['sites with two or more labels in scope'] += len(others) >= 1
                scope.setdefault(lab, got)
            c['forms same-source cross-key'] += any(len(v) > 1 for v in by.values())
            for ty, comp in ctx.get('param_cross', ()):
                c['type parameter cross:%s:%s' % (comp, ty)] += 1
        has = any('Ident' in str(t) for t in r['table_types'])
        c['nodes'] += 1
        c['nodes ident'] += has
        how = refused.get(name)
        if how:
            c['nodes refused'] += 1
            c['nodes refused:' + how] += 1
            if has:
                c['nodes ident refused'] += 1
                c['nodes ident refused:' + how] += 1
                c['nodes ident refused:%s:%s' % (f.kind, how)] += 1
        if has:
            c['nodes ident:' + f.kind] += 1
    c['unknown reads'] += tr.unknown_reads
    for k, v in tr.unread_kinds.items():
        c['unread kind ' + k] += v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='context_nocover')
    ap.add_argument('--seconds', type=float, default=22)
    ap.add_argument('--skip', type=int, default=0)
    a = ap.parse_args()
    files = sorted(glob.glob(RUN + a.arm + '/*.nodes.jsonl.zst'), key=lambda p: hashlib.sha256(os.path.basename(p).encode()).hexdigest())[a.skip:]
    c, ex, t0, done = collections.Counter(), [], time.time(), []
    for p in files:
        if time.time() - t0 > a.seconds:
            break
        one_task(p, c, ex)
        done.append(os.path.basename(p).split('.')[0])
    print('arm %s: read %d of %d tasks in %.1f s: %s' % (a.arm, len(done), len(files), time.time() - t0, ' '.join(done)))
    n, nid = c['nodes'], c['nodes ident']
    print('kept nodes %d, of them with an Ident column %d (%.1f%%)' % (n, nid, 100 * nid / max(n, 1)))
    print('Ident nodes refused: %d (%.1f%% of Ident nodes): direct %d, negated %d, inherited %d' % (
        c['nodes ident refused'], 100 * c['nodes ident refused'] / max(nid, 1), c['nodes ident refused:direct'], c['nodes ident refused:neg'], c['nodes ident refused:inherited']))
    print('all nodes refused: %d (%.1f%% of all nodes): direct %d, negated %d, inherited %d' % (
        c['nodes refused'], 100 * c['nodes refused'] / max(n, 1), c['nodes refused:direct'], c['nodes refused:neg'], c['nodes refused:inherited']))
    for k in sorted(c):
        print('  %s: %d' % (k, c[k]))
    print('examples:')
    for x in ex[:12]:
        print('  ' + x)


if __name__ == '__main__':
    main()
