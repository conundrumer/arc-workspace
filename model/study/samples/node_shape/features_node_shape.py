"""Form shape of a clause as a set of counts. No `*` or `^` marks, no label names, no form numbers, no order.

  shape_names() -> list of feature names
  shape_features(clause) -> dict name -> float
  parse(text) -> nested lists
  vocab_counts(clause) -> (atom heads, port names read from forms, op name), for building vocab.json

vocab.json (this folder) lists the 80 most frequent lib relations, the ports read from forms and the op names; it is built
by features_node_vocab.py from R120 and N600 clauses only.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
TOK = re.compile(r'[()]|[^\s()]+')
KEYWORDS = {'NOT', 'OR', 'ALL', 'AND', 'IF', 'DET', 'RULE', 'INIT', 'OUT'}
CMP = {'!=', '<', '<=', '>', '>=', '='}
READS = ('input', 'ex_input', 'ex_output')
FORM = re.compile(r'^&f\d+(\.\w+)?$')
_V = None


def vocab():
    global _V
    if _V is None:
        _V = json.load(open(HERE + 'vocab.json'))
        _V['rel_ix'] = {r: i for i, r in enumerate(_V['relations'])}
    return _V


def parse(text):
    stack, top = [], []
    cur = top
    for t in TOK.findall(text):
        if t == '(':
            n = []
            cur.append(n)
            stack.append(cur)
            cur = n
        elif t == ')':
            cur = stack.pop() if stack else cur
        else:
            cur.append(t)
    return top[0] if top else []


def is_atom(x):
    if not x or not isinstance(x[0], str):
        return False
    h = x[0]
    if h.startswith(':') or h in KEYWORDS:
        return False
    if h.startswith('&') or h in CMP:
        return True
    return len(x) > 1 and isinstance(x[1], list) and bool(x[1]) and isinstance(x[1][0], str) and x[1][0].startswith(':')


def _label(tok):
    return tok.lstrip('*^')


def walk(x, neg, orr, acc):
    """Fills acc: list of (atom, under NOT, under OR), counts of OR branches, ALL, IF, NOT."""
    if not isinstance(x, list) or not x:
        return
    h = x[0] if isinstance(x[0], str) else None
    if h is not None and is_atom(x):
        acc['atoms'].append((x, neg, orr))
        return
    if h == 'NOT':
        for y in x[1:]:
            walk(y, True, orr, acc)
        return
    if h == 'OR':
        acc['n_or'] += 1
        acc['or_branches'] += len(x) - 1
        for y in x[1:]:
            walk(y, neg, True, acc)
        return
    if h == 'ALL':
        acc['all'] += 1
    if h == 'IF':
        acc['if'] += 1
    for y in x:
        walk(y, neg, orr, acc)


def _bindings(atom):
    for b in atom[1:]:
        if isinstance(b, list) and len(b) == 2 and isinstance(b[0], str) and b[0].startswith(':') and isinstance(b[1], str):
            yield b[0][1:], _label(b[1])
        elif isinstance(b, str):
            continue


def analyse(clause):
    p = parse(clause or '')
    acc = dict(atoms=[], n_or=0, or_branches=0, all=0, **{'if': 0})
    kind = p[0] if p and isinstance(p[0], str) else 'none'
    named = len(p) > 2 and isinstance(p[2], str)
    op = p[2] if named else 'body'
    body = p[3:] if named else p[2:]
    for y in body:
        walk(y, False, False, acc)
    return p, kind, op, acc


def vocab_counts(clause):
    p, kind, op, acc = analyse(clause)
    heads = [a[0] for a, _, _ in acc['atoms'] if not a[0].startswith('&')]
    ports = [pn for a, _, _ in acc['atoms'] if a[0].startswith('&') for pn, _ in _bindings(a)]
    return heads, ports, op


def own_sources(acc, kind, op):
    out = set()
    for a, _, _ in acc['atoms']:
        if a[0] in ('input', 'ex_input'):
            out.add('colors' if any(pn == 'Col' for pn, _ in _bindings(a)) else 'shape')
        elif a[0] == 'ex_output':
            out.add('output')
    if op in ('ColorDomain', 'NumberDomain'):
        out.add('colors')
    elif op != 'body' and not op.endswith('Domain') and kind != 'INIT':
        out.add('colors')
    return out


_NAMES = None


def shape_names():
    global _NAMES
    if _NAMES is None:
        v = vocab()
        n = ['sh_atoms', 'sh_neg_atoms', 'sh_or_branches', 'sh_n_or', 'sh_cmp', 'sh_all', 'sh_if', 'sh_labels', 'sh_labels_multi', 'sh_head_cols',
             'sh_n_input', 'sh_n_ex_input', 'sh_n_ex_output', 'sh_form_reads', 'sh_form_reads_distinct',
             'ce_reads', 'ce_distinct', 'ce_fixed', 'ce_negated', 'ce_union', 'ce_src_none', 'ce_src_shape', 'ce_src_colors', 'ce_src_output']
        n += ['sh_rport_' + x for x in v['ports']] + ['sh_rport_other']
        n += ['sh_op_' + x for x in v['ops']] + ['sh_op_other', 'sh_op_body']
        n += ['sh_rel_' + x for x in v['relations']] + ['sh_rel_other']
        _NAMES = n
    return _NAMES


def shape_features(clause, ncols):
    v = vocab()
    d = dict.fromkeys(shape_names(), 0.0)
    p, kind, op, acc = analyse(clause)
    atoms = acc['atoms']
    d['sh_atoms'] = len(atoms)
    d['sh_neg_atoms'] = sum(1 for _, n, _ in atoms if n)
    d['sh_or_branches'], d['sh_n_or'], d['sh_all'], d['sh_if'] = acc['or_branches'], acc['n_or'], acc['all'], acc['if']
    d['sh_cmp'] = sum(1 for a, _, _ in atoms if a[0] in CMP)
    sites = {}
    forms, fdist = 0, set()
    for a, neg, orr in atoms:
        h = a[0]
        for pn, lab in _bindings(a):
            sites[lab] = sites.get(lab, 0) + 1
        if h in READS:
            d['sh_n_' + h] += 1
        if h.startswith('&'):
            forms += 1
            fdist.add(h.split('.')[0])
            for pn, _ in _bindings(a):
                k = 'sh_rport_' + pn
                d[k if k in d else 'sh_rport_other'] += 1
        elif h not in CMP:
            k = 'sh_rel_' + h
            d[k if k in d else 'sh_rel_other'] += 1
    d['sh_labels'] = len(sites)
    d['sh_labels_multi'] = sum(1 for c in sites.values() if c >= 2)
    d['sh_head_cols'] = ncols
    d['sh_form_reads'] = forms
    d['sh_form_reads_distinct'] = len(fdist)
    if op == 'body':
        d['sh_op_body'] = 1.0
    else:
        k = 'sh_op_' + op
        d[k if k in d else 'sh_op_other'] = 1.0
    reads = [a for a, _, _ in atoms if a[0].startswith('&') or a[0] in READS]
    d['ce_reads'] = len(reads)
    d['ce_distinct'] = len({a[0].split('.')[0] for a in reads})
    d['ce_fixed'] = len(atoms) - len(reads)
    d['ce_negated'] = sum(1 for a, n, _ in atoms if n and (a[0].startswith('&') or a[0] in READS))
    d['ce_union'] = float(any(o for _, _, o in atoms))
    src = own_sources(acc, kind, op)
    d['ce_src_none'] = float(not src)
    for s in ('shape', 'colors', 'output'):
        d['ce_src_' + s] = float(s in src)
    return d
