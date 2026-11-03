#!/usr/bin/env python
"""Arrays of the relation picks of a walk: one row per option, with the features a pick may read, and the pick's fields for the tables.

  python features_rel_data.py [--crossfit] NAME WALK_FILE...   writes data-NAME.npz in the run folder

With --crossfit, each option's weight swaps the factor of the steer in use for the factor of a steer fit without the task's fold, for a task that the steer in use was fit on.

A feature here reads only what the search has at the pick: the options with their weights, kinds, types and scope facts, the prefix's relation names, and, for content, the tables. It reads no gold field: gold's index goes to `gold`, and only the fit and the tables read that.
"""
import io
import json
import math
import re
import sys
import time

import numpy as np
import zstandard

import features_rel_content as C

OUT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37/scratch/rank-steers/'
HEAD = re.compile(r'\((?:NOT \()?([^\s()]+)')
TYPES = ('Position', 'Color', 'Box', 'Nat', 'Int', 'Number', 'Ident', 'Dir', 'Offset', 'Axis')
STRUCT = ['lq', 'lp', 'steer', 'rank', 'gap_top', 'share_kind', 'is_lib', 'is_macro', 'is_fact', 'is_derived', 'is_not', 'is_cmp', 'dead_join', 'own', 'uses', 'arity', 'hit', 'hit_frac', 'none_in_scope', 'new_types',
          'readers', 'depth', 'defined', 'method', 'sibling', 'path', 'der_rank', 'k', 'ord', 'root2', 'in_branch', 'nscope', 'nopts', 'nder', 'nalive', 'entropy', 'top_q', 'last_derived', 'last_lib', 'last_not', 'ncmp', 'prefix_depth'] + ['type_' + t for t in TYPES]
EXTRA = ['t_rows_rel', 'j_match_rank', 'j_cont_rank', 's_cont_rank', 'der_rows_rank']
CONTENT = list(C.OPTION) + list(C.JOIN) + list(C.PREFIX) + EXTRA
CLASS = {'relation': 'derived', 'lib relation': 'lib', 'relation macro': 'macro', 'fact relation': 'fact'}


def records(paths):
    for p in paths:
        with open(p, 'rb') as f:
            for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
                yield json.loads(line)


def rank_of(v):
    o = np.argsort(np.argsort(-v, kind='stable'), kind='stable')
    return o.astype(np.float32)


def matrix(d):
    """(struct rows, content rows, relation names per option) of a pick."""
    opts, ro = d['opts'], d['rowopts']
    n = len(opts)
    w = np.array([x[2] for x in opts], np.float64)
    q = w / w.sum()
    lq = np.log(np.maximum(q, 1e-12))
    lp = np.log(np.maximum(np.array([r['p'] for r in ro], np.float64), 1e-9))
    rank = rank_of(lq)
    S = np.zeros((n, len(STRUCT)), np.float32)
    idx = {x: j for j, x in enumerate(STRUCT)}
    prefix = d.get('prefix') or []
    heads = [re.sub(r'\.\w+$', '', h) for a in prefix for h in HEAD.findall(a)[:1]]
    last = heads[-1] if heads else ''
    last_not = bool(prefix) and prefix[-1].startswith('(NOT')
    scope = set(d['scope'])
    kinds = [x[1] for x in opts]
    nder = sum(k == 'relation' for k in kinds)
    alive = sum(not x[3] for x in opts)
    ent = float(-(q * np.log2(np.maximum(q, 1e-12))).sum())
    der = [j for j, k in enumerate(kinds) if k == 'relation']
    der_rank = {j: r for r, j in enumerate(sorted(der, key=lambda j: -lq[j]))}
    share = {}
    for j, k in enumerate(kinds):
        share[k] = share.get(k, 0.0) + q[j]
    for j, (x, r) in enumerate(zip(opts, ro)):
        k = x[1]
        ts = r.get('types') or []
        hit = sum(t in scope for t in ts)
        dag = r.get('dag') or {}
        path = dag.get('path')
        row = dict(lq=lq[j], lp=lp[j], steer=lq[j] - lp[j], rank=math.log1p(rank[j]), gap_top=lq[j] - lq.max(), share_kind=share[k], is_lib=k == 'lib relation', is_macro=k == 'relation macro', is_fact=k == 'fact relation',
                   is_derived=k == 'relation', is_not=k == 'NOT', is_cmp=k == 'CMP', dead_join=x[3], own=x[4], uses=heads.count(r['tok']), arity=len(ts), hit=hit, hit_frac=hit / len(ts) if ts else 0.0,
                   none_in_scope=bool(ts) and hit == 0 and d['k'] > 1, new_types=len(ts) - hit, readers=dag.get('readers', 0) or 0, depth=dag.get('depth', 0) or 0, defined=bool(dag.get('defined')), method=bool(dag.get('method')),
                   sibling=bool(dag.get('sibling')), path=path if isinstance(path, (int, float)) else (-1 if path is None else 1), der_rank=der_rank.get(j, -1), k=d['k'], ord=d['ord'], root2=d['phase'] == 'root2', in_branch=d['ctx'] != 'top',
                   nscope=d['nscope'], nopts=n, nder=nder, nalive=alive, entropy=ent, top_q=q.max(), last_derived=last.startswith('&'), last_lib=bool(last) and not last.startswith('&'), last_not=last_not, ncmp=sum(a.startswith('(<') or a.startswith('(!=') or a.startswith('(=') for a in prefix),
                   prefix_depth=d.get('prefix_depth') or 0)
        for key, v in row.items():
            S[j, idx[key]] = float(v)
        for t in TYPES:
            S[j, idx['type_' + t]] = float(t in ts)
    B = np.array(d['cont'], np.float32)
    P = np.tile(np.array(d['pre'], np.float32), (n, 1))
    no, nj = len(C.OPTION), len(C.JOIN)
    rows, match, cont, sc = B[:, 2], B[:, no + C.JOIN.index('j_match')], B[:, no + C.JOIN.index('j_cont_p')], B[:, C.OPTION.index('s_cont')]
    relm = np.array([k not in ('NOT', 'CMP') for k in kinds])
    read = B[:, 0] > 0
    mean_rows = rows[read].mean() if read.any() else 0.0
    E = np.zeros((n, len(EXTRA)), np.float32)
    E[:, 0] = np.where(read, rows - mean_rows, 0.0)
    E[:, 1] = rank_of(match)
    E[:, 2] = rank_of(cont)
    E[:, 3] = rank_of(sc)
    dr = np.full(n, -1.0, np.float32)
    if der:
        dr[der] = rank_of(rows[der])
    E[:, 4] = dr
    tok = [r['tok'] if x[1] != 'relation' else '&D' for x, r in zip(opts, ro)]
    return S, np.hstack([B, P, E]), tok, last if not last.startswith('&') else '&D'


class Swap:
    """Replaces the steer's factor by that of the task's cross-fit steer."""

    def __init__(self):
        import features_rel_crossfit as X
        import relsteer
        self.X = X
        self.use = relsteer.Scorer(X.STEER)
        self.fold = {i: relsteer.Scorer(OUT + 'steer-fold%d.pkl' % i) for i in range(X.FOLDS)}

    def apply(self, p):
        row = dict(k=p['k'], phase=p['phase'], scope=p['scope'], prefix=p['prefix'], point_group={}, prefix_bases=p.get('prefix_bases') or [], prefix_depth=p.get('prefix_depth') or 0, options=[])
        for o in p['rowopts']:
            q = dict(tok=o['tok'], kind=o['kind'], name=o['tok'], p=o['p'], types=o.get('types') or [])
            if o.get('cols') is not None:
                q['columns'] = o['cols']
            if o.get('dag') is not None:
                q['dag'] = o['dag']
            row['options'].append(q)
        a = self.use.score(row)
        b = self.fold[self.X.fold_of(p['task'])].score(row)
        for x, u, v in zip(p['opts'], a, b):
            x[2] *= math.exp(max(-20.0, min(20.0, v)) - max(-20.0, min(20.0, u)))
        g = p['gold_idx']
        if g is not None:
            p['q_bits'] = -math.log2(p['opts'][g][2] / sum(x[2] for x in p['opts']))


def main():
    swap = None
    if sys.argv[1] == '--crossfit':
        sys.argv.pop(1)
        swap = Swap()
    name, paths = sys.argv[1], sys.argv[2:]
    S, Co, starts, gold = [], [], [0], []
    meta = {k: [] for k in ('task', 'line', 'ord', 'phase', 'k', 'gold_kind', 'own', 'gold_dead', 'q_bits', 'orf', 'nopts')}
    toks, last, forms = [], [], []
    t0 = time.time()
    buf = []
    for n, d in enumerate(records(paths), 1):
        if d['rec'] != 'form':
            buf.append(d)
            continue
        forms.append({k: d[k] for k in ('task', 'line', 'natoms', 'total', 'bad', 'dead', 'error', 'cpu', 'content_cpu', 'picks', 'aligned', 'orf')})
        if d['error'] or d['dead'] or d['bad'] or not d['aligned']:  # a valid form, as the census counts one
            buf = []
            continue
        for p in buf:
            if swap is not None:
                swap.apply(p)
            a, b, tok, la = matrix(p)
            S.append(a), Co.append(b), starts.append(starts[-1] + len(a))
            g = p['gold_idx']
            gold.append(-1 if g is None else g)
            toks += tok
            last.append(la)
            for k, v in dict(task=p['task'], line=p['line'], ord=p['ord'], phase=p['phase'], k=p['k'], gold_kind=p['gold_kind'], own=p['own'], gold_dead=bool(g is None or p['opts'][g][3]), q_bits=p['q_bits'], orf=p['orf'], nopts=len(a)).items():
                meta[k].append(v)
        buf = []
        if len(forms) % 500 == 0:
            print('%d forms %.0fs' % (len(forms), time.time() - t0), flush=True)
    np.savez(OUT + 'data-%s.npz' % name, S=np.vstack(S), C=np.vstack(Co).astype(np.float32), starts=np.array(starts), gold=np.array(gold), toks=np.array(toks), last=np.array(last), forms=np.array(json.dumps(forms)), **{'m_' + k: np.array(v) for k, v in meta.items()})
    print(name, len(S), 'picks', starts[-1], 'option rows', len(forms), 'forms, %.0fs' % (time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
