"""The FunctionVector (contract, `FunctionVector`): the features of one function, one level above its tables.

  function_vec(fn, tables, givens, ctx) -> dict   names, values, use_names, per_use, column_origin

A feature is computed from the function's used tables, the tables it computes, the relation between them, and the given tables. The relation
features are computed for each assignment of the function, against the used tables at that assignment restricted to the DETs each depends on,
for each Name; the value at an assignment is the greatest over the Names. They combine over the assignments by the least, mean and greatest of
each feature. A feature against one used table (`per_use`) is the mean over the assignments. The count of assignments, whether the engine stopped
at the cap, whether the tables differ, and the aggregates of the TableVectors of the tables it computes are in the AssignmentVector of each of its
Names (`build_tables.assignment_vector_records`), and not here. Where an example has several Rows, a feature is the mean over joint choices of one Rows per example for each table
(`table_vec.picks`), which is the mean over pairs of Rows where an example holds one choice. The family computed from the body is whole.
"""
import collections
import importlib.util
import math
import os
import sys
from typing import Any

import row_store as RS
from table_read import TableAt, TaskCtx, fsum
from table_vec import NAN, paint_state, picks

SCHEMA = 'f2'
KINDS = {'DET': 0, 'RULE': 1, 'INIT': 2}
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'node_shape')  # set T's features_node_shape.py and its vocab.json
LINK = ['link_row_ratio', 'link_filter', 'link_grow', 'link_disjoint', 'link_parent_gain', 'link_adds', 'link_better', 'link_new_cells',
        'link_new_count', 'link_pair_union']
AGGS = ['min', 'mean', 'max']
USE_NAMES = ['row_ratio_mean', 'row_ratio_min', 'row_ratio_max', 'type_share', 'gain_delta', 'fixed_new_share']

type Ref = tuple[str, str]  # a Table: (function id, Name), or ('given', GivenName)

_SH: list[Any] = []


def shape() -> Any:
    """The Form shape counts of set T (features_node_shape.py), which read a function's text."""
    if not _SH:
        spec = importlib.util.spec_from_file_location('features_node_shape', os.path.join(RESULTS, 'features_node_shape.py'))
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules['features_node_shape'] = mod
        spec.loader.exec_module(mod)
        _SH.append(mod)
    return _SH[0]


def body_names() -> list[str]:
    """The names of the family computed from the body: kind, count of Names, and the counts of the Form shape less those that read label names."""
    return ['dp_kind', 'dp_n_names'] + [n for n in shape().shape_names() if not n.startswith('sh_rport_') and n != 'sh_head_cols']


def value_names() -> list[str]:
    return (['depth', 'n_used_members', 'n_used_given'] + [f'{f}_{a}' for f in LINK for a in AGGS]
            + ['co_carried', 'co_new', 'co_unused_tables'] + body_names())


# ---------------------------------------------------------------------- the body


def used_tables(text: str, refmap: dict[str, str]) -> list[Ref]:
    """The tables the function uses (its Reference atoms), given tables first in the order of GivenName, then members' tables by (id, Name)."""
    SH = shape()
    _, _, _, acc = SH.analyse(text)
    out: set[Ref] = set()
    for a, _, _ in acc['atoms']:
        h = a[0]
        if h in SH.READS:
            out.add(('given', h))
        elif h.startswith('&'):
            label, _, port = h.partition('.')
            if label in refmap:
                out.add((refmap[label], port))
    return sorted(out, key=lambda r: (r[0] != 'given', RS.GIVEN.index(r[1]) if r[0] == 'given' else 0, r[0], r[1]))


def column_origin(text: str, kind: str, refmap: dict[str, str], types: list[str], labels: list[str]) -> list[tuple[str, list[Ref]]]:
    """For each column of a table of the function: (type, the tables it is carried over from). A column is carried over from a used table when the
    function binds its label at a column of an atom that uses that table, outside a NOT. The columns of an INIT output and of a DET without a body
    are new. Sorted by type, then by the set."""
    SH = shape()
    _, _, _, acc = SH.analyse(text)
    bound: dict[str, set[Ref]] = collections.defaultdict(set)
    if kind != 'INIT':
        for a, neg, _ in acc['atoms']:
            if neg:
                continue
            h = a[0]
            ref: Ref | None = ('given', h) if h in SH.READS else None
            if h.startswith('&'):
                label, _, port = h.partition('.')
                ref = (refmap[label], port) if label in refmap else None
            if ref is not None:
                for _, lab in SH._bindings(a):
                    bound[lab].add(ref)
    cols = [(t, sorted(bound.get(lab, ()))) for t, lab in zip(types, labels)]
    return sorted(cols, key=lambda c: (c[0], c[1]))


def body_values(fn: dict, n_cols: int) -> dict[str, float]:
    SH = shape()
    d = {'dp_kind': float(KINDS.get(fn['kind'], 3)), 'dp_n_names': float(len(fn['outputs']))}
    d.update({k: float(v) for k, v in SH.shape_features(fn['text'], n_cols).items() if not k.startswith('sh_rport_') and k != 'sh_head_cols'})
    return d


# ---------------------------------------------------------------------- the relation to the used tables


def base_cells(state: dict) -> set:
    return state['fixed'] or state['cells']


def mean_dicts(ds: list[dict[str, float]], keys: list[str]) -> dict[str, float]:
    out = {}
    for k in keys:
        v = [d[k] for d in ds if k in d and d[k] == d[k]]
        out[k] = fsum(v) / len(v) if v else NAN
    return out


def row_ratios(f: TableAt, u: TableAt) -> tuple[float, float, float]:
    """The log of the row count against the used table's, per example the mean over pairs of Rows; then the mean, least and greatest over examples."""
    per = []
    for e in sorted(set(f.per_example) | set(u.per_example)):
        vs = [math.log((a.n + 1) / (b.n + 1)) for a in f.rows_of(e) for b in u.rows_of(e)]
        per.append(fsum(vs) / len(vs))
    return (fsum(per) / len(per), min(per), max(per)) if per else (NAN, NAN, NAN)


def type_share(f: TableAt, u: TableAt) -> float:
    if not f.types:
        return NAN
    return sum((collections.Counter(f.types) & collections.Counter(u.types)).values()) / len(f.types)


def relation_at(F: TableAt, members: list[TableAt], givens: list[TableAt], ctx: TaskCtx, pairs: list[Any], outfeat: Any) -> tuple[dict[str, float], list[dict[str, float]]]:
    """(the link features of F against its used members' tables, the features against each used table: members first, then givens)."""
    tabs = [F, *members, *givens]
    choices = picks(tabs, ctx.n_train)
    link_ds, use_ds = [], []
    for p in choices:
        states = [paint_state(t, i, p, ctx, pairs)[1] for i, t in enumerate(tabs)]
        nodes = {i: ([], {}, states[i + 1]) for i in range(len(members))}
        d: dict[str, float] = {}
        outfeat.link_one(list(range(len(members))), d, states[0], nodes)
        link_ds.append(d)
        per = []
        for i in range(1, len(tabs)):
            s, u = states[0], states[i]
            x: dict[str, float] = {}
            x['gain_delta'] = s['gain'] - u['gain'] if s['gain'] is not None and u['gain'] is not None else NAN
            fs = base_cells(s)
            x['fixed_new_share'] = len(fs - base_cells(u)) / len(fs) if fs else NAN
            per.append(x)
        use_ds.append(per)
    link = mean_dicts(link_ds, LINK)
    per_use = []
    for i in range(1, len(tabs)):
        x = mean_dicts([ds[i - 1] for ds in use_ds], ['gain_delta', 'fixed_new_share'])
        x['row_ratio_mean'], x['row_ratio_min'], x['row_ratio_max'] = row_ratios(F, tabs[i])
        x['type_share'] = type_share(F, tabs[i])
        per_use.append(x)
    return link, per_use


def restrict(a: RS.AssignKey, dets: set[str]) -> RS.AssignKey:
    return tuple(p for p in a if p[0] in dets)


def aggregate(xs: list[float]) -> tuple[float, float, float]:
    v = [x for x in xs if x == x]
    return (min(v), fsum(v) / len(v), max(v)) if v else (NAN, NAN, NAN)


def function_vec(fn: dict, by_table: dict[Ref, dict[RS.AssignKey, TableAt]], dets: dict[str, set[str]], ctx: TaskCtx, pairs: list[Any], outfeat: Any) -> dict:
    """fn: the function's record of the row store. by_table: for each table the store holds, its TableAt at each assignment (the given tables
    under ('given', name), at the empty assignment). dets: for each function id, the DETs it depends on."""
    used = used_tables(fn['text'], fn['refmap'])
    members = [u for u in used if u[0] != 'given']
    givens = [u for u in used if u[0] == 'given']
    outs = [o for o in fn['outputs'] if 'error' not in o]
    # per assignment, per Name: the link features and the features against each used table
    link_at: dict[RS.AssignKey, list[dict[str, float]]] = collections.defaultdict(list)
    use_at: dict[Ref, list[dict[str, float]]] = {u: [] for u in used}
    for o in outs:
        for a, F in by_table.get((fn['id'], o['name']), {}).items():
            ms = [by_table.get(u, {}).get(restrict(a, dets.get(u[0], set()))) for u in members]
            gs = [by_table.get(u, {}).get(()) for u in givens]
            if F.counts_only or any(t is None or t.counts_only for t in (*ms, *gs)):
                link_at[a].append({})
                continue
            link, per_use = relation_at(F, [t for t in ms if t is not None], [t for t in gs if t is not None], ctx, pairs, outfeat)
            link_at[a].append(link)
            for u, x in zip([*members, *givens], per_use):
                use_at[u].append(x)
    names = value_names()
    vals = dict.fromkeys(names, NAN)
    vals['depth'] = float(fn['depth'])
    vals['n_used_members'] = float(len(members))
    vals['n_used_given'] = float(len(givens))
    for k in LINK:  # at one assignment the greatest over Names; then the aggregates over assignments
        per_a = []
        for ds in link_at.values():
            v = [d[k] for d in ds if k in d and d[k] == d[k]]
            per_a.append(max(v) if v else NAN)
        for agg, x in zip(AGGS, aggregate(per_a)):
            vals[f'{k}_{agg}'] = x
    origin = {o['name']: column_origin(fn['text'], fn['kind'], fn['refmap'], o['types'][:len(o['labels'])], o['labels']) for o in outs}
    if origin:
        carried = [sum(1 for _, s in cols if s) for cols in origin.values()]
        news = [sum(1 for _, s in cols if not s) for cols in origin.values()]
        unused = [len(used) - len({r for _, s in cols for r in s}) for cols in origin.values()]
        vals['co_carried'], vals['co_new'], vals['co_unused_tables'] = float(max(carried)), float(max(news)), float(max(unused))
    vals.update(body_values(fn, max((len(o['labels']) for o in outs), default=0)))
    per_use_out = [[list(u), [mean_dicts(use_at[u], USE_NAMES)[k] for k in USE_NAMES]] for u in used]
    return dict(function=fn['id'], names=names, values=[vals[k] for k in names], use_names=USE_NAMES, per_use=per_use_out,
                column_origin=[[n, [[t, [list(r) for r in s]] for t, s in cols]] for n, cols in sorted(origin.items())])

