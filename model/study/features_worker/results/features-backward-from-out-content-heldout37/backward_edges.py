"""Backward edges of gold's DAG, from OUT down to the input, from the rows of features-next-form-content-given-task-heldout37.

An edge is (reader, read form, atom). The reader is OUT or a gold form. The read form is a gold form that the atom reads.

Depth: OUT has depth 0. A form's depth is 1 plus the least depth of its readers. The primary edge of a form is its reader of least depth, with ties broken by a hash of the task, the read form's text and the reader's text, so no tie reads a written order.

A body is a set. No fact reads lexical order: no first or last atom, no atom index, no position in a body, no form's place in gold's text. Facts of the DAG stay: depth, set sizes, the count of atoms, shared labels, join structure. The marks * and ^ on a site are not read, because the site that makes a label depends on written order; a site is only a label that other atoms share or don't share. `atom` in a row is an id, and no model reads it. The list that atoms_of returns is in written order only to align atoms with the row's reads.

Facts of an edge read only the output side:
  b_  the reader's body as a set, with the read atom masked: its relation name, its port and its column names are gone, and its sites stay as labels of the reader. A hole column's type comes from the lib signature alone
  c_  the reader's own columns: its head types, and a hole column's type where only the reader's head gives it
  a_  the read atom unmasked: port and column names. These are the read form's own text, so this family is an upper bound and not a fact a backward search has
  n0_ g_  the output need at OUT and the task's grids, from the state before gold's first form

The targets are those of next_form_facts, on the table the atom reads where the row names one.
"""
import collections
import gzip
import hashlib
import json
import os
import re
import statistics
import time

import next_form_facts as F

D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
CENSUS = D + 'census/census-bands-cheapest/'
VIEW = D + 'gold/gold-v3-cover-forms-a036da074/corpus-view/'
SIG = '/Users/davidlu/code/arc-workspace/src/arclog_convert/lib-signature.dl'
TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+')
ALIAS = {'input': 'in', 'ex_input': 'ex_in', 'ex_output': 'ex_out'}
WRAP = ('OR', 'IF', 'ALL', 'SET', 'ONE', 'ALSO', 'CHOOSE', 'RIGID_DET', 'DEMONSTRATED', 'DEMO_RULE')
CMP = ('=', '!=', '<', '<=', '>', '>=')
TOP_LIBS = 40


def sig_table():
    """{relation name: {lower-case column name: type}} of the lib signature."""
    out = {}
    for x in open(SIG):
        m = re.match(r'\s*\.decl\s+(\w+)\((.*?)\)', x)
        if m:
            cols = {}
            for c in m.group(2).split(','):
                if ':' in c:
                    a, b = c.split(':')
                    cols[a.strip().lower()] = b.strip()
            out[m.group(1)] = cols
    return out


SIGNATURE = sig_table()


def parse(text):
    toks = TOKEN.findall(text)
    stack = [[]]
    for t in toks:
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop()
            stack[-1].append(x)
        else:
            stack[-1].append(t)
    return stack[0][0] if stack[0] else []


def strip(label):
    return label.lstrip('*^')


def sites_of(args):
    """[(column name or None, label, mark)] of an atom's arguments. A record column's fields are sites of their own."""
    out = []

    def one(col, v):
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0].startswith(':'):
                rest = v[1:]
                for w in rest:
                    one(v[0][1:], w)
            else:
                for w in v:
                    one(col, w)
        else:
            if v == '0' or v.lstrip('-').isdigit():
                out.append((col, None, '0'))
            else:
                out.append((col, strip(v), v[0] if v[0] in '*^' else ''))

    for a in args:
        if isinstance(a, list):
            if a and isinstance(a[0], str) and a[0].startswith(':'):
                for w in a[1:]:
                    one(a[0][1:], w)
            else:
                one(None, a)
        else:
            one(None, a)
    return out


def is_port(x):
    """A port or a named clause of an instance: (name ((head sites)) body ...) or (key (body) ...)."""
    return len(x) >= 2 and isinstance(x[0], str) and re.fullmatch(r'[a-z_][a-z_0-9]*', x[0]) is not None and isinstance(x[1], list) and (not x[1] or isinstance(x[1][0], list))


def atoms_of(sexp):
    """The atoms of a form, in written order, each a dict: name, sites, neg, ors, port."""
    out = []

    def walk(x, neg, ors, port):
        if not isinstance(x, list) or not x:
            return
        h = x[0]
        if isinstance(h, list):
            for y in x:
                walk(y, neg, ors, port)
            return
        if h == 'NOT':
            for y in x[1:]:
                walk(y, not neg, ors, port)
        elif h in WRAP:
            for y in x[1:]:
                walk(y, neg, ors + (h == 'OR'), port)
        elif h in CMP:
            out.append(dict(name=h, sites=sites_of(x[1:]), neg=neg, ors=ors, port=port))
        elif is_port(x):
            for y in x[1:]:
                walk(y, neg, ors, x[0])
        elif h.startswith('&') or re.fullmatch(r'[a-z_][A-Za-z_0-9]*', h):
            out.append(dict(name=h, sites=sites_of(x[1:]), neg=neg, ors=ors, port=port))

    h = sexp[0] if sexp else None
    start = 3 if h in ('INIT', 'DET') and len(sexp) > 2 and isinstance(sexp[2], str) else 2
    for x in sexp[start:]:
        walk(x, False, 0, None)
    return out


def form_parts(sexp):
    """(kind, name, component or None)."""
    kind = sexp[0]
    name = sexp[1] if len(sexp) > 1 else None
    comp = sexp[2] if len(sexp) > 2 and isinstance(sexp[2], str) else None
    return kind, name, comp


def col_type(atom, site):
    """The type of a site from the lib's signature, or None."""
    c = SIGNATURE.get(ALIAS.get(atom['name'], atom['name']))
    if c is None:
        return None
    k = (site[0] or site[1] or '').lower()
    return c.get(k)


def norm_type(t):
    return 'Position' if t == 'Box' else t


def var_types(atoms, row):
    """{label: type} of a form's labels from lib and fact atoms, then from the form's head columns."""
    found = collections.defaultdict(set)
    for a in atoms:
        if a['name'].startswith('&') or a['name'] in CMP:
            continue
        for s in a['sites']:
            if s[1] is None:
                continue
            t = col_type(a, s)
            if t:
                found[s[1]].add(norm_type(t))
    out = {k: sorted(v)[0] for k, v in found.items()}
    if row is not None:
        for t in row.get('tables', ()):
            for lb, ty in zip(t.get('labels') or (), t.get('types') or ()):
                if lb and lb not in out:
                    out[lb] = norm_type(ty)
    return out


def out_text(split, task, cache={}):
    """The OUT line of a task."""
    if split in ('held', 'dev'):
        if 'c' not in cache:
            cache['c'] = json.load(open(CENSUS + 'texts.json'))['stems']
        st = cache['c'][task]
        for x in st['lines']:
            if x.startswith('(OUT'):
                return x
        return st.get('out')
    with gzip.open(VIEW + task + '/pairs.jsonl.gz', 'rt') as f:
        for x in json.loads(f.readline())['gold_sexp'].splitlines():
            if x.startswith('(OUT'):
                return x
    return None


def slot_of(forms):
    """{'&rN': form index} of a task's heads."""
    return {form_parts(parse(r['text']))[1]: i for i, r in enumerate(forms) if r['text']}


def table_of(r, ord_):
    ts = [t for t in r.get('tables', ()) if t.get('ord') == ord_ and 'nrows' in t]
    return ts[0] if ts else F.main_table(r)


def targets(x, forms, ord_):
    """The targets of the read form x, on the table the atom reads."""
    t = table_of(x, ord_)
    comp = x['comp'] if x['comp'] else ('body' if x['kind'] in ('DET', 'INIT') else None)
    y = dict(t_comp=comp, t_kind=x['kind'], t_lib=F.lib_set(x), t_keys=F.key_set(x, forms), t_cols=F.head_types(t), t_coarse=F.coarse_types(t), t_geom=F.geom_of(t), t_rel=F.rel_of(t))
    y['t_shape'] = y['t_geom'] + '|' + y['t_rel']
    y['t_head'] = y['t_coarse'] + '|' + y['t_shape']
    y['t_content'] = str(comp or x['kind']) + '|' + y['t_head']
    return y


def tie(task, forms, e):
    """A tie-break with no written order: a hash of the texts. Two atoms of one reader on one form tie on the text, and then on the atom's sites as a set."""
    rd = forms[e[0]]['text'] if e[0] < len(forms) else 'OUT'
    return hashlib.sha1((task + '|' + forms[e[2]]['text'] + '|' + rd).encode()).hexdigest()


def task_edges(split, task, forms):
    """Edge rows of one task, as (edges, counts)."""
    parsed = [parse(r['text']) if r['text'] else [] for r in forms]
    atoms = [atoms_of(p) for p in parsed]
    slots = slot_of(forms)
    c = collections.Counter()
    edges = []  # reader index (len(forms) for OUT), atom index, read form, ord
    n = len(forms)
    ot = out_text(split, task)
    osx = parse(ot) if ot else ['OUT']
    oat = []
    for a in osx[1:]:
        if isinstance(a, list) and a:
            oat.append(dict(name=a[0], sites=sites_of(a[1:]), neg=False, ors=0, port=None))
    for i, a in enumerate(oat):
        nm = a['name']
        base = nm.split('.')[0]
        if base in slots:
            f = slots[base]
            ord_ = None
            labs = {s[1] for s in a['sites']}
            for t in forms[f].get('tables', ()):
                if t.get('ord') is not None and labs <= set(t.get('labels') or ()):
                    ord_ = t['ord']
                    break
            edges.append((n, i, f, ord_))
        else:
            c['out atom reads no form'] += 1
    for i, r in enumerate(forms):
        ds = [x for x in r['reads'] if x[1] == 'relation' and x[2] is not None]
        ps = [j for j, a in enumerate(atoms[i]) if a['name'].startswith('&')]
        if len(ds) != len(ps):
            c['forms where parsed atoms differ from reads'] += 1
            # Keep the rows whose count agrees only; a form that does not align gives edges with no atom.
            for x in ds:
                edges.append((i, None, x[2], x[3]))
            continue
        for j, x in zip(ps, ds):
            edges.append((i, j, x[2], x[3]))
    # Depth by a walk from OUT.
    readers = collections.defaultdict(list)
    for e in edges:
        readers[e[2]].append(e)
    depth = {n: 0}
    todo = [n]
    while todo:
        nxt = []
        for a in todo:
            for e in edges:
                if e[0] == a and e[2] not in depth:
                    depth[e[2]] = depth[a] + 1
                    nxt.append(e[2])
        todo = nxt
    prim = {}
    for f, es in readers.items():
        if f not in depth:
            continue
        cand = [e for e in es if e[0] in depth]
        if cand:
            prim[f] = min(cand, key=lambda e: (depth[e[0]], tie(task, forms, e)))
    c['forms'] = n
    c['forms reached from OUT'] = sum(1 for f in range(n) if f in depth)
    return edges, depth, prim, atoms, oat, c


def out_flags(forms, atoms, oat, edges, depth, prim):
    """{form: set of its column labels that hold OUT's position or color}, walking primary edges from OUT. A column carries the mark where the reader's site on it joins a label that carries it."""
    n = len(forms)
    flags = collections.defaultdict(lambda: collections.defaultdict(set))
    for i, a in enumerate(oat):
        for e in edges:
            if e[0] == n and e[1] == i:
                for j, s in enumerate(a['sites']):
                    flags[e[2]][s[1]].add('P' if j == 0 else 'C')
    order = sorted((f for f in depth if f != n), key=lambda f: depth[f])
    for f in order:
        for e in edges:
            if e[0] == f and e[1] is not None:
                a = atoms[f][e[1]]
                for s in a['sites']:
                    fl = flags[f].get(s[1])
                    if fl and not a['neg']:
                        flags[e[2]][s[0] if s[0] is not None else s[1]] |= fl
    return flags


def lib_of(a):
    return a['name'] if not a['name'].startswith('&') and a['name'] not in CMP else None


def body_facts(forms, atoms, oat, edges, depth, flags, e, libs):
    """The facts of the reader's body for edge e, with the read atom masked."""
    n = len(forms)
    rd, j, x, _ = e
    d = {}
    dp = depth.get(rd, 9)
    d['b_depth'] = str(min(dp + 1, 4))
    if rd == n:
        r = None
        ats = oat
        a = oat[j]
        d['b_rk'] = 'OUT'
        d['b_rcomp'] = 'OUT'
        d['b_role'] = 'OUT.%d' % len(oat)
        d['c_rcols'] = 'OUT'
    else:
        r = forms[rd]
        ats = atoms[rd]
        a = ats[j] if j is not None else dict(name='?', sites=(), neg=False, ors=0, port=None)
        d['b_rk'] = r['kind']
        d['b_rcomp'] = (r['comp'] or 'body') if r['kind'] in ('INIT', 'DET') else r['kind']
        d['b_role'] = '%s.%s' % (d['b_rcomp'], a['port'] or 'body')
        d['c_rcols'] = F.coarse_types(F.main_table(r))
    vl = var_types(ats, None) if r is not None else {}
    vt = var_types(ats, r) if r is not None else {}
    if r is None:
        sites = [s[1] for s in a['sites']]
        vt = dict(zip(sites, ('Position', 'Color')))
    labs = [s[1] for s in a['sites'] if s[1] is not None]
    d['b_neg'] = 'neg' if a['neg'] else 'pos'
    d['b_or'] = str(min(a['ors'], 2))
    d['b_ncols'] = F.bucket(len(a['sites']), [1, 2, 3, 4])
    d['b_nzero'] = 'zero' if any(s[1] is None for s in a['sites']) else 'nozero'
    elsewhere = {s[1] for b in ats if b is not a for s in b['sites'] if s[1] is not None}
    d['b_nshared'] = F.bucket(sum(1 for v in set(labs) if v in elsewhere), [0, 1, 2, 3])
    d['b_nonly'] = F.bucket(sum(1 for v in set(labs) if v not in elsewhere), [0, 1, 2, 3])
    for pre, tab in (('b_', vl), ('c_', vt)):
        ty = sorted(tab.get(v, '?') for v in labs)
        d[pre + 'htypes'] = '+'.join(ty) if ty else 'none'
        d[pre + 'hcoarse'] = '+'.join(sorted(set(ty))) if ty else 'none'
        known = [t for t in ty if t != '?']
        d[pre + 'hknown'] = '+'.join(sorted(set(known))) if known else 'none'
        d[pre + 'hunk'] = F.bucket(sum(1 for t in ty if t == '?'), [0, 1, 2])
        d[pre + 'hpos'] = 'yes' if 'Position' in ty else 'no'
        d[pre + 'hcol'] = 'yes' if 'Color' in ty else 'no'
        d[pre + 'hid'] = 'yes' if 'Ident' in ty else 'no'
    others = [b for b in ats if b is not a]
    d['b_natoms'] = F.bucket(len(ats), [1, 2, 3, 5, 8])
    d['b_nsib'] = F.bucket(sum(1 for b in others if b['name'].startswith('&')), [0, 1, 2, 3])
    d['b_self'] = 'yes' if any(b['name'] == a['name'] for b in others) else 'no'
    d['b_fneg'] = 'yes' if any(b['neg'] for b in ats) else 'no'
    d['b_for'] = 'yes' if any(b['ors'] for b in ats) else 'no'
    d['b_nor'] = 'yes' if any(b['name'] in CMP for b in ats) else 'no'
    d['b_input'] = 'yes' if any(b['name'] == 'input' for b in others) else 'no'
    d['b_exout'] = 'yes' if any(b['name'] == 'ex_output' for b in others) else 'no'
    # The other atoms that join the hole.
    js = {}
    ls = set(labs)
    for b in others:
        nm = lib_of(b)
        if nm:
            hit = [s for s in b['sites'] if s[1] in ls]
            if hit:
                js[nm] = hit
    d['b_nj'] = F.bucket(len(js), [0, 1, 2, 3])
    d['b_njd'] = F.bucket(sum(1 for b in others if b['name'].startswith('&') and {s[1] for s in b['sites']} & ls), [0, 1, 2])
    s_ = {lib_of(b) for b in others} - {None}
    for t in libs:
        d['b_j_' + t] = 'yes' if t in js else 'no'
        d['b_s_' + t] = 'yes' if t in s_ else 'no'
    d['b_jfirst'] = sorted(js)[0] if js else 'none'
    d['b_jpair'] = '+'.join(sorted(js)[:2]) if js else 'none'
    fl = flags.get(rd, {}) if rd != n else None
    if rd == n:
        d['b_outP'] = 'yes'
        d['b_outC'] = 'yes' if len(a['sites']) > 1 else 'no'
    else:
        hit = set().union(*[fl.get(v, set()) for v in labs]) if labs else set()
        d['b_outP'] = 'yes' if 'P' in hit else 'no'
        d['b_outC'] = 'yes' if 'C' in hit else 'no'
    # Reader's reader, on the primary edge of the reader.
    d['c_paint'] = 'yes' if rd != n and F.main_table(forms[rd]) and {'Position', 'Color'} <= set(F.main_table(forms[rd]).get('types') or ()) else 'no'
    return d


def atom_open(forms, atoms, oat, e):
    """The read atom unmasked: the port and the column names, the read form's own text."""
    n = len(forms)
    rd, j, x, _ = e
    a = oat[j] if rd == n else (atoms[rd][j] if j is not None else None)
    d = {}
    nm = (a or {}).get('name', '')
    d['a_port'] = nm.split('.')[1] if '.' in nm else 'none'
    cols = sorted({(s[0] or s[1] or '?') for s in (a or {}).get('sites', ())})
    d['a_col1'] = cols[0] if cols else 'none'
    d['a_cols'] = '+'.join(cols[:3])
    return d


def top_libs(tasks):
    c = collections.Counter()
    for t, forms in tasks.items():
        for r in forms:
            for a in atoms_of(parse(r['text'])) if r['text'] else ():
                nm = lib_of(a)
                if nm:
                    c[nm] += 1
    return [k for k, _ in c.most_common(TOP_LIBS)]


def edge_rows(split, tasks, libs):
    """One row per edge with an atom, on forms reached from OUT. Each row has its depth and whether it is the form's primary edge."""
    out = []
    counts = collections.Counter()
    for t in sorted(tasks):
        forms = tasks[t]
        if any(r['form'] != i for i, r in enumerate(forms)):
            counts['tasks with a form gap'] += 1
            continue
        g0 = F.start_facts(forms[0]['state'])
        edges, depth, prim, atoms, oat, c = task_edges(split, t, forms)
        counts.update(c)
        flags = out_flags(forms, atoms, oat, edges, depth, prim)
        n = len(forms)
        for e in edges:
            rd, j, x, ord_ = e
            if j is None:
                counts['edges with no atom'] += 1
                continue
            if rd not in depth or x not in depth:
                counts['edges off the walk'] += 1
                continue
            t0 = time.perf_counter()
            fact = dict(g0)
            fact.update(body_facts(forms, atoms, oat, edges, depth, flags, e, libs))
            fact.update(atom_open(forms, atoms, oat, e))
            t_fact = time.perf_counter() - t0
            r = forms[x]
            y = targets(r, forms, ord_)
            out.append(dict(task=t, form=x, reader=rd if rd != n else -1, atom=j, kind=r['kind'], source=r['source'], depth=depth[x], edge_depth=min(depth[rd] + 1, 4), primary=prim.get(x) == e, fact=fact, y=y, text=r['text'], ord=ord_, t_fact=t_fact))
            counts['edges'] += 1
    return out, counts


def open_keys_row(rows, tasks):
    """Keys open at the draw of the read form: the keys of the forms that are not the form and that don't read it, directly or not. This is a fact of the DAG. It reads no form's place in gold's text."""
    down = {}
    for t, forms in tasks.items():
        rd = collections.defaultdict(set)
        for i, r in enumerate(forms):
            for x in r['reads']:
                if x[1] == 'relation' and x[2] is not None:
                    rd[x[2]].add(i)
        cl = {}
        for f in range(len(forms)):
            seen, todo = {f}, [f]
            while todo:
                for g in rd.get(todo.pop(), ()):
                    if g not in seen:
                        seen.add(g)
                        todo.append(g)
            cl[f] = seen
        down[t] = cl
    for r in rows:
        forms = tasks[r['task']]
        out = set()
        for i, p in enumerate(forms):
            if i not in down[r['task']][r['form']]:
                ords = {x.get('ord') for x in p.get('tables', ()) if x.get('ord') is not None} or {0}
                for o in ords:
                    out.add(F.key_of(p, o))
        r['open'] = out
    return rows


def depth_summary(rows):
    c = collections.Counter()
    for r in rows:
        if r['primary']:
            c[min(r['depth'], 4)] += 1
    return c
