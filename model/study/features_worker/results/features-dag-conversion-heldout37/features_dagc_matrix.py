"""The columns of a relation pick, as a function of its row in walks/*.jsonl.zst (the copy of features_rel_data.matrix for the DAG conversion, item 8).

A pick row has the options (`opts`, `rowopts`), the downset D (`downset`, sorted atom ids), `place`, `phase`, `nscope`, `dsize`, `d_depth`, and with --content the tables `cont` and `pre`. The columns are exactly
features_dagc_facts.ALLOWED_COLUMNS (and its patterns). `check_columns` runs on `NAMES` when this module loads, so a name outside the list stops the import.

Changes against features_rel_data.matrix:
  - `dsize` and `d_depth` stand where `k` and `ord` stood. `rank`, `steer`, `der_rank`, `readers`, `last_*` are gone.
  - A rank of a number is `scipy.stats.rankdata(method='average')`, so a tie reads no option place.
  - `uses` counts the atoms of D whose relation key equals the option's relation key. `ncmp` counts comparisons in D. `in_branch` is a pick in a body that is not the form's root body.
  - `prefix_depth` is 0 (the walker writes no such field, and the old rows held 0 too).
  - Columns of the scope's column types (`hit`, `hit_frac`, `none_in_scope`, `new_types`, `col*_in_scope`, `scope_n_*`) need `scope`, a list of types, in the row. The walker writes `nscope` alone, so these hold -1 (0 for `scope_n_*`), and the builder says so.
  - FORM columns are `form_atoms`, `form_not`, `form_or` of the option's form. `recency`, `recency_frac`, `kept_reads` are gone.
"""
import math
import re

import numpy as np
from scipy.stats import rankdata

import features_dagc_facts as F
import features_rel_content as C

TYPES = ('Position', 'Color', 'Box', 'Nat', 'Int', 'Number', 'Ident', 'Dir', 'Offset', 'Axis')
STRUCT = ['lq', 'lp', 'gap_top', 'share_kind', 'is_lib', 'is_macro', 'is_fact', 'is_derived', 'is_not', 'is_cmp', 'dead_join', 'own', 'uses', 'arity', 'hit', 'hit_frac', 'none_in_scope', 'new_types',
          'depth', 'defined', 'method', 'sibling', 'path', 'dsize', 'd_depth', 'root2', 'in_branch', 'nscope', 'nopts', 'nder', 'nalive', 'entropy', 'top_q', 'ncmp', 'prefix_depth'] + ['type_' + t for t in TYPES]
EXTRA = ['t_rows_rel', 'j_match_rank', 'j_cont_rank', 's_cont_rank', 'der_rows_rank']
CONTENT = list(C.OPTION) + list(C.JOIN) + list(C.PREFIX) + EXTRA
XCOLS = ['col%d_in_scope' % i for i in range(5)] + ['form_atoms', 'form_not', 'form_or']
SCOPE = ['scope_n_' + t for t in TYPES]
CLASS = {'relation': 'derived', 'lib relation': 'lib', 'relation macro': 'macro', 'fact relation': 'fact'}
CMPHEAD = re.compile(r'^\((<|<=|>|>=|=|!=)[ )]')
ATOMH = re.compile(r'\((&r\d+(?:\.\w+)?|[a-z_]\w*) \(:')


def names(grid):
    n = STRUCT + CONTENT + XCOLS + SCOPE + ['grid_' + g for g in grid]
    return F.check_columns(n)


def rank_avg(v):
    """Rank from the highest (0), ties at their average place, so a tie reads no option place."""
    return (rankdata(-np.asarray(v, np.float64), method='average') - 1).astype(np.float32)


def matrix(d, sk, rel_keys, has_scope):
    """(S, C, X, scnt, tokens) of a pick. sk: ScopeKeys of the pick's scope. rel_keys: the (family, component, relation) of each option. scnt: counts of scope types (zeros without `scope`)."""
    opts, ro = d['opts'], d['rowopts']
    n = len(opts)
    w = np.array([x[2] for x in opts], np.float64)
    q = w / w.sum()
    lq = np.log(np.maximum(q, 1e-12))
    lp = np.log(np.maximum(np.array([r['p'] for r in ro], np.float64), 1e-9))
    down = [x.split('|', 1)[1] for x in d['downset']]
    dheads = [sk.atom_head(t) for t in down]
    dheads = [h for h in dheads if h]
    ncmp = sum(bool(CMPHEAD.match(t)) for t in down)
    scope = d.get('scope')
    sc_set = set(scope) if scope is not None else None
    kinds = [x[1] for x in opts]
    nder = sum(k == 'relation' for k in kinds)
    alive = sum(not x[3] for x in opts)
    ent = float(-(q * np.log2(np.maximum(q, 1e-12))).sum())
    share = {}
    for j, k in enumerate(kinds):
        share[k] = share.get(k, 0.0) + q[j]
    S = np.zeros((n, len(STRUCT)), np.float32)
    idx = {x: j for j, x in enumerate(STRUCT)}
    in_branch = d['place'] in ('branch', 'all', 'outside')
    for j, (x, r) in enumerate(zip(opts, ro)):
        k = x[1]
        ts = r.get('types') or []
        dag = r.get('dag') or {}
        path = dag.get('path')
        if sc_set is None:
            hit, hit_frac, none_in, new = -1, -1.0, -1, -1
        else:
            hit = sum(t in sc_set for t in ts)
            hit_frac = hit / len(ts) if ts else 0.0
            none_in = bool(ts) and hit == 0 and d['nscope'] > 0
            new = len(ts) - hit
        uses = dheads.count(rel_keys[j][2]) if k not in ('NOT', 'CMP') else 0
        row = dict(lq=lq[j], lp=lp[j], gap_top=lq[j] - lq.max(), share_kind=share[k], is_lib=k == 'lib relation', is_macro=k == 'relation macro', is_fact=k == 'fact relation', is_derived=k == 'relation', is_not=k == 'NOT', is_cmp=k == 'CMP',
                   dead_join=x[3], own=x[4], uses=uses, arity=len(ts), hit=hit, hit_frac=hit_frac, none_in_scope=none_in, new_types=new, depth=dag.get('depth', 0) or 0, defined=bool(dag.get('defined')), method=bool(dag.get('method')),
                   sibling=bool(dag.get('sibling')), path=path if isinstance(path, (int, float)) else (-1 if path is None else 1), dsize=d['dsize'], d_depth=d['d_depth'], root2=d['phase'] == 'root2', in_branch=in_branch,
                   nscope=d['nscope'], nopts=n, nder=nder, nalive=alive, entropy=ent, top_q=q.max(), ncmp=ncmp, prefix_depth=0)
        for key, v in row.items():
            S[j, idx[key]] = float(v)
        for t in TYPES:
            S[j, idx['type_' + t]] = float(t in ts)
    # content
    no, nj = len(C.OPTION), len(C.JOIN)
    E = np.zeros((n, len(EXTRA)), np.float32)
    if 'cont' in d:
        B = np.array(d['cont'], np.float32)
        P = np.tile(np.array(d['pre'], np.float32), (n, 1))
        rows, match, cont, sc = B[:, 2], B[:, no + C.JOIN.index('j_match')], B[:, no + C.JOIN.index('j_cont_p')], B[:, C.OPTION.index('s_cont')]
        read = B[:, 0] > 0
        mean_rows = rows[read].mean() if read.any() else 0.0
        E[:, 0] = np.where(read, rows - mean_rows, 0.0)
        E[:, 1] = rank_avg(match)
        E[:, 2] = rank_avg(cont)
        E[:, 3] = rank_avg(sc)
        der = [j for j, k in enumerate(kinds) if k == 'relation']
        dr = np.full(n, -1.0, np.float32)
        if der:
            dr[der] = rank_avg(rows[der])
        E[:, 4] = dr
        Cm = np.hstack([B, P, E])
    else:
        Cm = np.zeros((n, len(CONTENT)), np.float32)
    # form columns of the option's form
    X = np.full((n, len(XCOLS)), -1.0, np.float32)
    if sc_set is not None:
        for j, r in enumerate(ro):
            for c, t in enumerate((r.get('types') or [])[:5]):
                X[j, c] = list(scope).count(t)
    for j, (o, r) in enumerate(zip(opts, ro)):
        if o[1] == 'relation':
            L = sk.form_line(o[0])
            if L is not None:
                tx = sk.f.lines[L]
                X[j, 5:8] = len(ATOMH.findall(tx)), '(NOT' in tx, '(OR' in tx
    scnt = np.array([list(scope).count(t) for t in TYPES] if scope is not None else [0] * len(TYPES), np.float32)
    return S, Cm, X, scnt


def registry_ports():
    """{(component, index): output's name}, in the registry's order of outputs."""
    txt = re.sub(r';[^\n]*', '', open('/Users/davidlu/code/arc-workspace/engine/lib/registry.sexpr', encoding='utf8').read())
    out = {}
    for m in re.finditer(r'\(component (\w+)', txt):
        i = txt.find('(outputs', m.end())
        nxt = txt.find('(component ', m.end())
        if i < 0 or (nxt > 0 and i > nxt):
            continue
        depth, j, nm = 0, i, []
        while True:
            c = txt[j]
            if c == '(':
                depth += 1
                if depth == 2:
                    nm.append(re.match(r'\(([\w]+)', txt[j:])[1])
            elif c == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        for n, x in enumerate(nm):
            out[m[1], n] = x
    return out
