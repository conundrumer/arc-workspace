"""Model input layer: where each column of a program's tables comes from, by the engine's flows, in the names that the task and the lib give.

A column's origins are the given columns its values come from: a column of the task's grids (`input.P`, `input.Col`, `output.P`,
`output.Col`, `example`), a column of a lib relation or macro (`opposite.Opp`), of a proposer (`DominantColor.C`) or of a component's port
(`Distance.distance.K`), or a constant. A copy flow from a table of the program passes on the origins of that table's column. A computed
flow gives the lib column that computes the value: in a clause, the column of the site that makes the column's label; in an instance's
output, the output's own column; `computed` where the clause gives none.

provenance(tb, text) gives, for each table of the engine's Tables tb, the name of each column in given terms (`describe`), the provenance
features of each column and of the table, and how the table is named to another table that reads it (`given`).
"""
import json
import re
from functools import cache
from pathlib import Path

import dependence as DEP
import identity as I
import query as Q

import paths  # noqa: E402

REGISTRY = paths.REGISTRY
FACT_COLUMNS = {'ex_input': {0: 'example', 1: 'input.P', 2: 'input.Col', -2: 'example'},
                'ex_output': {0: 'example', 1: 'output.P', 2: 'output.Col', -2: 'example'}}
PARAMETER_FORMS = ('DET', 'DET_OR_RULE', 'RULE_OR_DET', 'RIGID_DET')
COPY, COMPUTED, CONSTANT, LIB_NAME = 0, 1, 2, 3
KINDS = ('grid', 'proposer', 'lib', 'component', 'constant', 'recursive')


@cache
def registry_forms():
    """The top-level forms of the lib registry, each as nested lists."""
    return [f for f in Q.parse(REGISTRY.read_text()) if isinstance(f, list) and len(f) > 1]


def part(form, head):
    return next((p for p in form if isinstance(p, list) and p and p[0] == head), None)


@cache
def registry():
    """({lib relation or macro: [column names]}, {proposer: [column names]}), from the lib registry."""
    cols, proposers = {}, {}
    for f in registry_forms():
        c = part(f, 'columns')
        names = [x[0] if isinstance(x, list) else x for x in (c or [])[1:]]
        if f[0] in ('relation', 'macro'):
            cols[f[1]] = names
        elif f[0] == 'proposer':
            proposers[f[1]] = names
    return cols, proposers


@cache
def needs():
    """{lib relation or macro: the columns that some mode of it needs bound}, from the lib registry."""
    out = {}
    for f in registry_forms():
        if f[0] in ('relation', 'macro'):
            m = part(f, 'modes')
            out[f[1]] = {x for mode in (m or [])[1:] if isinstance(mode, list) for x in mode if isinstance(x, str)}
    return out


def origin_kind(o):
    """The kind of an origin: grid, proposer, lib, component, constant or recursive."""
    if o in ('constant', 'recursive'):
        return o
    if o == 'example' or o.split('.')[0] in ('input', 'output'):
        return 'grid'
    head = o.split('.')[0]
    if head in registry()[1]:
        return 'proposer'
    return 'component' if head[:1].isupper() else 'lib'


def frame_text(fr):
    """A column's frame in given terms: `in input`, `in output`, or `in a frame of <maker>`, with the frame it lies in."""
    if not fr:
        return ''
    if fr in ('input', 'output'):
        return 'in ' + fr
    maker, _, rest = fr.partition('@')
    inner = rest.split(' in ', 1)[1] if ' in ' in rest else ''
    return 'in a frame of %s%s' % (maker, ' in ' + frame_text(inner)[3:] if inner else '')


def sites_computing(x, label):
    """[(lib relation, column)] of each site in x that holds `label`, made there or joined, at a column of a lib relation or macro that
    no mode of it needs bound: a column the atom computes."""
    out = []
    if not isinstance(x, list) or not x:
        return out
    h = x[0]
    if isinstance(h, str) and h in registry()[0] and needs().get(h):
        for el in x[1:]:
            if el in (label, '*' + label):
                col = label
            elif isinstance(el, list) and el and isinstance(el[0], str) and el[0].startswith(':') and (label in el[1:] or '*' + label in el[1:]):
                col = el[0][1:]
            else:
                continue
            if col not in needs()[h]:
                out.append((h, col))
    if isinstance(h, str) and h == 'NOT':
        return out
    for el in x if not isinstance(h, str) else x[1:]:
        if isinstance(el, list):
            out += sites_computing(el, label)
    return out


def bodies_of(tb):
    """For each table of tb by number, (bodies, symmetries) as dependence.features reads them, from the engine's export of each table's
    body IR (`body_ir`) and column symmetries (`column_symmetries`); None for a table with no body. None where the export has no such fields."""
    T = tb.T
    if not all(k in T for k in ('body_ir', 'column_symmetries', 'column_idents')):
        return None
    out = []
    for t, raw in enumerate(T['body_ir']):
        given = json.loads(raw or '[]')
        if not given:
            out.append(None)
            continue
        idents = list(T['column_idents'][t])
        at = {c: i for i, c in enumerate(idents)}
        bodies = []
        for b in given:
            var_at = {c: v for c, v in b['table_columns']}
            body = ir_clause(b['clause'])
            body['columns'] = [var_at.get(c) for c in idents]
            bodies.append(body)
        symmetries = []
        for moves in json.loads(T['column_symmetries'][t] or '[]'):
            p = list(range(len(idents)))
            for a, b in moves:
                p[at[a]] = at[b]
            symmetries.append(p)
        out.append((bodies, symmetries))
    return out


def ir_argument(a):
    """The variable id of an argument of the body IR; None for a term."""
    return a.get('v')


def ir_clause(clause):
    """A clause of the body IR in dependence.py's form, without its columns."""
    return {'nodes': [ir_node(n) for n in clause['nodes']]}


def ir_node(n):
    k = n['k']
    if k == 'atom':
        r = n['read']
        if 'fact' in r:
            reads = ('fact', r['fact'])
        elif 'key' in r:
            reads = ('key', None)
        elif 'table' in r and r['table'] >= 0:
            reads = ('table', r['table'])
        else:
            reads = ('absent', None)
        return {'kind': 'atom', 'id': (n['form'], n['path']), 'reads': reads, 'args': [(c, ir_argument(a)) for c, a in n['args']]}
    if k == 'lib':
        return {'kind': 'lib', 'id': (n['form'], n['path']), 'relation': n['relation'], 'args': [(c, ir_argument(a)) for c, a in n['args']],
                'computes': list(n['computes'])}
    if k == 'cmp':
        return {'kind': 'cmp', 'op': n['op'], 'first': n['first'], 'second': ir_argument(n['second']), 'makes': bool(n['binds_first'])}
    if k in ('not', 'all'):
        return {'kind': k, 'outer': list(n['outer']), 'body': ir_clause(n['body'])}
    if k == 'or':
        return {'kind': 'or', 'exported': list(n['exported']), 'branches': [ir_clause(b) for b in n['branches']]}
    raise ValueError('a node of an unknown kind in the body IR: %r' % (k,))


class Provenance(dict):
    """provenance's result: a dict, with `ids`, the Identities of the program's tables and columns, and `memo`, a store that the feature
    library keeps the keys it names in."""

    def __init__(self, *a, ids=None):
        super().__init__(*a)
        self.ids = ids
        self.memo = {}


def provenance(tb, text):
    """{table: {'given': how a reader names the table, 'describe': [the name of each column], 'columns': [{provenance feature: value}],
    'table': {provenance feature: value}, 'pairs': [(column, column, feature, value)]}} of every table of tb other than the facts, as a
    Provenance with the identities of tb. Where the export gives each table's IR, the dependence features (dependence.py) stand in each
    column's and the table's features."""
    T, fl = tb.T, tb.flows
    structure = bodies_of(tb)
    forms = Q.parse(text)
    qf = Q.query_features(text)
    libcols, proposers = registry()
    names = tb.names
    into = {}
    for i, (t, c) in enumerate(zip(fl['table'], fl['column'])):
        into.setdefault((t, c), []).append(i)

    def form_of(t):
        f = T['form'][t]
        return forms[int(f)] if f not in ('', None) and int(f) < len(forms) else None

    def is_parameter(t):
        f = form_of(t)
        return bool(f) and f[0] in PARAMETER_FORMS

    def port_clause(form, port):
        """The clause of an instance input port inside an INIT form."""
        for part in form[3:]:
            if isinstance(part, list) and part:
                if part[0] == port:
                    return part
                if part[0] == 'key':
                    for p in part[2:]:
                        if isinstance(p, list) and p and p[0] == port:
                            return p
        return None

    def computing(t, c):
        """The lib columns that compute column c of table t: those of the sites that compute the column's label. The engine's
        column_source_labels gives the column of the site that makes the label; a site at that column is kept where there is one."""
        f = form_of(t)
        if not f:
            return {'computed'}
        name = names[t]
        col = T['column_names'][t][c]
        label = col
        if f[0] == 'INIT':
            comp, port = f[2] if len(f) > 2 else None, name.split('.', 1)[1] if '.' in name else ''
            if port not in Q.component_inputs().get(comp, ()):
                return {'%s.%s.%s' % (comp, port, col.split('.')[0])}
            body = port_clause(f, port) or []
            heads = body[1] if len(body) > 1 and isinstance(body[1], list) else []
            for h in heads:  # the head site that projects a label onto this column
                if isinstance(h, list) and h and h[0] == ':' + col.split('.')[0] and len(h) > 1 and isinstance(h[1], str):
                    label = h[1].lstrip('*')
            scope = [b for b in body[2:] if isinstance(b, list)]
        else:
            scope = [b for b in f[2:] if isinstance(b, list)]
        found = sites_computing(scope, label)
        at = [s for s in found if s[1] == T['column_source_labels'][t][c]]
        return {'%s.%s' % s for s in (at or found)} or {'computed'}

    memo = {}

    def trace(t, c, stack=()):
        """(origins, copy steps, reach) of column c of table t; reach: the kinds of source that its values depend on, through every flow,
        among 'input', 'output' and 'parameter'."""
        if (t, c) in memo:
            return memo[t, c]
        if (t, c) in stack:
            return {'recursive'}, 0, frozenset()
        stack = stack + ((t, c),)
        origins, steps, reach = set(), 0, set()
        if is_parameter(t):
            reach.add('parameter')
        for i in into.get((t, c), []):
            kind, rel, st, sc = fl['kind'][i], fl['source_relation'][i], fl['source_table'][i], fl['source_column'][i]
            src = names[st] if st >= 0 else rel
            if kind == COPY:
                if src in FACT_COLUMNS:
                    origins.add(FACT_COLUMNS[src].get(sc, 'example'))
                    reach.add('output' if src == 'ex_output' else 'input')
                elif st >= 0:
                    o, s, r = trace(st, sc, stack)
                    origins |= o
                    steps = max(steps, s + 1)
                    reach |= r
                elif rel in libcols and 0 <= sc < len(libcols[rel]):
                    origins.add('%s.%s' % (rel, libcols[rel][sc]))
                else:
                    origins.add('%s.%s' % (rel, sc))
            elif kind == COMPUTED:
                origins |= computing(t, c)
                if src in FACT_COLUMNS:
                    reach.add('output' if src == 'ex_output' else 'input')
                elif st >= 0:
                    reach |= trace(st, sc, stack)[2]
            elif kind == CONSTANT:
                origins.add('constant')
            elif kind == LIB_NAME and rel in Q.component_inputs():  # a component's default rows of an input
                f = form_of(t)
                port = names[t].split('.', 1)[1] if f and f[0] == 'INIT' and '.' in names[t] else 'default'
                origins.add('%s.%s.%s' % (rel, port, T['column_names'][t][c].split('.')[0]))
            elif kind == LIB_NAME:
                pcols = proposers.get(rel, [])
                slot = T['column_slots'][t][c] if T['column_slots'][t][c] >= 0 else c  # the column's place among the proposer's own
                origins.add('%s.%s' % (rel, pcols[slot] if slot < len(pcols) else pcols[0] if len(pcols) == 1 else 'column %d' % slot))
                if rel in proposers:
                    reach.add('parameter')
        memo[t, c] = (origins, steps, frozenset(reach))
        return memo[t, c]

    out = {}
    for t, name in enumerate(names):
        if not name or name in FACT_COLUMNS or name == 'input':
            continue
        f = form_of(t)
        q = qf.get(name.split('.')[0], {})
        if f and f[0] == 'INIT':
            given = '%s.%s' % (q.get('component'), name.split('.', 1)[1] if '.' in name else '')
        elif is_parameter(t):
            given = 'parameter' + (' ' + q['proposer'] if q.get('proposer') and not q.get('atoms') else '')
        else:
            given = 'relation'
        describe, columns = [], []
        n_copy_only = True
        for c, (col, ty, fr) in enumerate(zip(T['column_names'][t], T['column_types'][t], T['column_frames'][t])):
            origins, steps, reach = trace(t, c)
            prefix = ''
            if f and f[0] == 'INIT' and not col.startswith('key.'):
                prefix = '%s.%s: ' % (given, col.split('.')[0])
            ft = frame_text(fr)
            describe.append('{%s%s%s%s}' % (prefix, ty, ' ' + ft if ft else '', ' from ' + ', '.join(sorted(origins)) if origins else ''))
            kinds = {origin_kind(o) for o in origins}
            flows_here = into.get((t, c), [])
            if any(fl['kind'][i] != COPY for i in flows_here):
                n_copy_only = False
            cf = {'origin kinds': '+'.join(k for k in KINDS if k in kinds) or 'none', 'copy steps': steps,
                  'from the input': 'input' in reach, 'from the train outputs': 'output' in reach, 'from a task parameter': 'parameter' in reach}
            columns.append(cf)
        pairs = []
        dep = DEP.features(*structure[t]) if structure is not None and structure[t] is not None else None
        if dep is not None:
            dcols, dtable, pairs = dep
            for cf, dc in zip(columns, dcols):
                cf.update(dc)
        tf = {'columns of %s origin' % k: sum(k in cf['origin kinds'].split('+') for cf in columns) for k in KINDS[:5]}
        tf['every column is a copy'] = n_copy_only and bool(columns)
        tf['some column from the train outputs'] = any(cf['from the train outputs'] for cf in columns)
        tf['some column from a task parameter'] = any(cf['from a task parameter'] for cf in columns)
        if dep is not None:
            tf.update(dep[1])
        out[name] = dict(given=given, describe=describe, columns=columns, table=tf, pairs=pairs)
    named = [n for n in names if n]
    return Provenance(out, ids=I.Identities(tb, reads=I.form_reads(text, named), params={names[t] for t in range(len(names)) if names[t] and is_parameter(t)}, text=text))
