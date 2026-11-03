"""Gold's forms read from text, with each body a set of atoms.

Program(lines) parses a task's forms. A row leaves one atom of a body out. Its label is that atom's relation. Its context is the other atoms of the body.

A context atom keeps its relation token, its kind of place in the body, its columns, and which of its labels it shares with other atoms. The marks `*` and `^` are dropped, since `*` sits on the atom written first that binds a label. Label names are dropped, since gold numbers them in written order: a label is kept as an id local to the row.

The scope of a form is every other form that doesn't read it, directly or not. This is a fact of the read graph, so a form's place in gold's text sets nothing here.

`written` on a row holds the written facts: the left-out atom's index and the atoms written before it. The clean fact layer in features_ofree_facts.py never reads that field. Only features_ofree_ordered.py reads it.
"""
import gzip
import json
import re

R = '/Users/davidlu/code/arc-workspace/'
CORPUS = R + 'work/lm/data-study/sampler/corpus-v3mix/'
POINTS = R + 'work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/points-base.json'
HELD = R + 'work/lm/data-study/sampler/sampler-worker/held/tasks.txt'
EVAL = R + 'work/lm/data-study/features-worker/arm/eval-tasks.txt'
LEAVE_OUT = R + 'work/lm/data-study/sampler/sampler-worker/held/leave_out.txt'
REGISTRY = R + 'engine/lib/registry.sexpr'
TOK = re.compile(r'\(|\)|[^\s()]+')
NAME = re.compile(r'&r(\d+)')
CMP = ('!=', '<', '<=', '=', '>', '>=')
COMPOUND = ('OR', 'ALL', 'IF')
CONST = re.compile(r'^(-?\d+|[A-Z]+_[A-Z0-9_]+)$')


def sexp(s):
    st = [[]]
    for t in TOK.findall(s):
        if t == '(':
            st.append([])
        elif t == ')':
            x = st.pop()
            st[-1].append(x)
        else:
            st[-1].append(t)
    return st[0]


class Registry:
    """Names and kinds from the lib registry. `kind[name]` is lib, macro or fact, and `ports[component]` lists its inputs and outputs, since a form can read either."""

    def __init__(self):
        txt = re.sub(r';[^\n]*', '', open(REGISTRY, encoding='utf8').read())
        self.kind = {}
        self.cols = {}
        self.ports = {}
        for p in sexp(txt):
            if p[0] in ('relation', 'macro', 'fact'):
                self.kind[p[1]] = {'relation': 'lib', 'macro': 'macro', 'fact': 'fact'}[p[0]]
                for x in p[2:]:
                    if isinstance(x, list) and x and x[0] == 'columns':
                        self.cols[p[1]] = [c[0] for c in x[1:]]
            elif p[0] == 'component':
                for x in p[2:]:
                    if isinstance(x, list) and x and x[0] in ('inputs', 'outputs'):
                        self.ports.setdefault(p[1], []).extend(c[0] for c in x[1:] if c[0] not in self.ports.get(p[1], ()))


def args(a):
    """(column path, label or None for a constant) of an atom's arguments, in any order."""
    out = []

    def go(x, path):
        if isinstance(x, str):
            v = x.lstrip('*^')
            out.append((path, None if CONST.match(v) else v))
        elif x and isinstance(x[0], str) and x[0].startswith(':'):
            p = path + x[0] if path else x[0][1:]
            for y in x[1:]:
                go(y, p)
        else:
            for y in x:
                go(y, path)
    for x in a[1:]:
        go(x, '')
    return out


def is_conj(x):
    return isinstance(x, list) and all(isinstance(y, list) for y in x)


class Atom:
    """kind: rel, cmp, not, or a compound (OR, ALL, IF), one, or set. inner: the atom under NOT, or a compound's conjunctions."""

    def __init__(self, a):
        h = a[0]
        self.head, self.inner, self.parts = h, None, []
        if h == 'NOT':
            self.kind = 'not'
            self.inner = [Atom(x) for x in a[1:]]
        elif h in COMPOUND:
            self.kind = h
            self.inner = [[Atom(y) for y in x] for x in a[1:] if is_conj(x)]
        elif h in CMP:
            self.kind = 'cmp'
            self.parts = [('', x.lstrip('*^')) for x in a[1:] if isinstance(x, str) and not CONST.match(x.lstrip('*^'))]
        elif h == 'ONE' or h == 'SET':
            self.kind = 'one'
        else:
            self.kind = 'rel'
            self.parts = args(a)

    def walk(self):
        """This atom and each atom under it."""
        yield self
        if self.kind == 'not':
            for x in self.inner:
                yield from x.walk()
        elif self.kind in COMPOUND:
            for b in self.inner:
                for x in b:
                    yield from x.walk()


class Form:
    def __init__(self, line, p):
        self.line, self.name = line, p[1]
        self.num = int(p[1][2:])
        self.kind, self.comp = p[0], None
        self.bodies = []  # (place, port, conjunction)
        rest = p[2:]
        if p[0] in ('RULE', 'DET'):
            if rest and isinstance(rest[0], str):
                self.kind, self.comp = 'PROPOSER', rest[0]
            elif rest:
                self.bodies.append((p[0], '', [Atom(x) for x in rest]))
        elif p[0] == 'INIT':
            self.comp = rest[0]
            for x in rest[1:]:
                if x[0] == 'key':
                    self.bodies.append(('key', 'key', [Atom(y) for y in x[1]]))
                    ports = x[2:]
                else:
                    ports = [x]
                for q in ports:
                    self.bodies.append(('port', q[0], [Atom(y) for y in q[2:]]))
        elif p[0] == 'RIGID_DET':
            for x in rest:
                if x[0] == 'instance':
                    self.bodies.append(('rigid', '', [Atom(y) for y in x[1]] + [Atom(y) for y in x[2:]]))
                else:
                    self.bodies.append(('rigid', '', [Atom(x)]))
        elif p[0] == 'CHOOSE':
            for x in rest:
                if x[0] == 'for':
                    self.bodies.append(('choose', 'for', [Atom(y) for y in x[1]]))
                    for z in x[2:]:
                        self.bodies.append(('choose', 'from', [Atom(y) for y in z[1:]]))
                else:
                    self.bodies.append(('choose', x[0], [Atom(y) for y in x[1:]]))

    def atoms(self):
        for _p, _q, c in self.bodies:
            for a in c:
                yield from a.walk()


class Program:
    def __init__(self, lines, reg):
        self.reg = reg
        self.forms = []
        for i, x in enumerate(lines):
            p = sexp(x)[0]
            if p[0] != 'OUT':
                self.forms.append(Form(i, p))
        self.byname = {f.name: f for f in self.forms}
        self.nums = sorted(f.num for f in self.forms)
        self.parents = {f.name: set() for f in self.forms}
        for f in self.forms:
            for a in f.atoms():
                if a.kind == 'rel' and a.head.startswith('&'):
                    g = self.form_of(a.head)[0]
                    if g is not None and g is not f:
                        self.parents[f.name].add(g.name)
        self.anc = {}
        self.depth = {}
        for f in sorted(self.forms, key=lambda f: f.num):  # a read goes to a form of lower number, so the walk needs that sort and no fact reads it
            s, d = set(), 0
            for q in self.parents[f.name]:
                s |= {q} | self.anc.get(q, set())
                d = max(d, 1 + self.depth.get(q, 0))
            self.anc[f.name], self.depth[f.name] = s, d
        self.desc = {f.name: set() for f in self.forms}
        for f in self.forms:
            for q in self.anc[f.name]:
                self.desc[q].add(f.name)
        self.readers = {f.name: {q for q in self.forms_names() if f.name in self.parents[q]} for f in self.forms}
        self.bodyheads = {f.name: sorted({self.token(a.head) for a in f.atoms() if a.kind == 'rel'}) for f in self.forms}
        self.nbody = {f.name: sum(len(c) for _p, _q, c in f.bodies) for f in self.forms}

    def forms_names(self):
        return [f.name for f in self.forms]

    def form_of(self, head):
        """(form, port) of a derived head. A slot past a form's name, as a second proposer output, is that form's port `#k`."""
        base, _, port = head.partition('.')
        n = int(base[2:])
        f = self.byname.get(base)
        if f is not None:
            return f, port
        below = [x for x in self.nums if x <= n]
        if not below:
            return None, port
        f = self.byname['&r%d' % below[-1]]
        return f, port or '#%d' % (n - f.num)

    def family(self, f):
        return 'derived-' + f.kind.lower()

    def token(self, head):
        """The text of a head with no number in it: a lib name, a component's port, a proposer, or a family."""
        if not head.startswith('&'):
            return head
        f, port = self.form_of(head)
        if f is None:
            return 'derived-unknown'
        if f.kind == 'INIT':
            return '%s.%s' % (f.comp, port or '?')
        if f.kind == 'PROPOSER':
            return f.comp
        return self.family(f)

    def options(self, f):
        """(form, port) of each derived relation a form's scope offers. Ports of a component come from the registry, and those of a RIGID_DET from its body's heads."""
        out = []
        skip = self.desc[f.name] | {f.name}
        for g in self.forms:
            if g.name in skip and not (g is f and f.kind == 'INIT'):  # a port of an INIT can read the form's own ports
                continue
            if g.kind == 'INIT':
                for p in self.reg.ports.get(g.comp, ['']):
                    out.append((g, p))
            elif g.kind == 'RIGID_DET':
                for h in sorted({a.head for a in g.atoms() if a.kind == 'rel' and a.head.startswith('&')}):
                    out.append((g, h.split('.')[0][1:]))
            else:
                out.append((g, ''))
        return out

    def scope_names(self, f):
        skip = self.desc[f.name] | {f.name}
        return [g.name for g in self.forms if g.name not in skip]


def label_of(prog, a):
    """(class, key text, form name or None, port) of an atom as a label."""
    if a.kind == 'not':
        return 'NOT', 'op:NOT', None, ''
    if a.kind == 'cmp':
        return 'comparison', 'op:' + a.head, None, ''
    h = a.head
    if h.startswith('&'):
        f, port = prog.form_of(h)
        return 'derived', prog.token(h), f.name if f else None, port
    return prog.reg.kind.get(h, 'lib'), h, None, ''


def ctx_atom(prog, a, where, ids):
    """One context atom. Its labels become ids local to the row, so a label's written name is gone."""
    if a.kind == 'not':
        a = a.inner[0]
        where = 'neg'
    tok = 'op:' + a.head if a.kind == 'cmp' else prog.token(a.head) if a.kind == 'rel' else None
    fid = None
    if a.kind == 'rel' and a.head.startswith('&'):
        g, _ = prog.form_of(a.head)
        fid = g.name if g else None
    ls, cols = [], []
    for c, v in a.parts:
        if v is None:
            continue
        ls.append(ids.setdefault(v, len(ids)))
        cols.append(c)
    return dict(t=tok, w=where, f=fid, ls=ls, cols=cols, inb=prog.bodyheads[fid] if fid else [])


def flat_rel(conj):
    """The atoms with a relation or a comparison under a list of atoms, through NOT and compounds."""
    out = []
    for a in conj:
        if a.kind in ('rel', 'cmp'):
            out.append(a)
        elif a.kind == 'not':
            out.append(a)
        elif a.kind in COMPOUND:
            for b in a.inner:
                out += flat_rel(b)
    return out


def preorder(conj, pos):
    """The written index of each atom of a body, a head of NOT counted once. Only `written` reads it."""
    for a in conj:
        if a.kind in ('rel', 'cmp', 'not'):
            pos[id(a)] = len(pos)
        elif a.kind in COMPOUND:
            for b in a.inner:
                preorder(b, pos)


def body_rows(prog, conj, near_top, slot):
    """A row per left-out atom of a body."""
    rows = []
    pos = {}
    preorder(conj, pos)

    def emit(a, same, near, under, as_label=None):
        cl, key, fid, port = label_of(prog, as_label or a)
        ids = {}
        ctx = []
        for x, w in [(y, 'in') for y in same] + [(y, 'near') for y in near]:
            c = ctx_atom(prog, x, w, ids)
            c['_o'] = pos.get(id(x), -1)
            ctx.append(c)
        me = pos[id(a)]
        kept = sorted(range(len(ctx)), key=lambda i: ctx[i]['_o'])
        before = [i for i in kept if 0 <= ctx[i]['_o'] < me]
        for c in ctx:
            del c['_o']
        rows.append(dict(cl=cl, key=key, fid=fid, lp=port, under=sorted(under), ctx=ctx, written=dict(k=len(before) + 1, before=before, last=before[-1] if before else -1, npos=len(pos))))

    def go(cj, outer, under):
        for i, a in enumerate(cj):
            others = cj[:i] + cj[i + 1:]
            same = [x for x in others if x.kind in ('rel', 'cmp', 'not')]
            comp = flat_rel([x for x in others if x.kind in COMPOUND])
            near = outer + comp
            if a.kind in ('rel', 'cmp'):
                emit(a, same, near, under)
            elif a.kind == 'not':
                emit(a, same, near, under)
                if a.inner and a.inner[0].kind == 'rel':
                    emit2(a, same, near, under)
            elif a.kind in COMPOUND:
                for j, b in enumerate(a.inner):
                    rest = [y for k, c in enumerate(a.inner) if k != j for y in flat_rel(c)]
                    go(b, near + same + rest, under | {a.kind.lower()})

    def emit2(a, same, near, under):
        emit(a, same, near, under | {'not'}, as_label=a.inner[0])

    go(conj, list(near_top), frozenset())
    for r in rows:
        r.update(slot)
    return rows


def form_record(prog, f, task, rows):
    opts = []
    for g, p in prog.options(f):
        tok = '%s.%s' % (g.comp, p) if g.kind == 'INIT' else g.comp if g.kind == 'PROPOSER' else prog.family(g)
        opts.append(dict(f=g.name, p=p, fam=prog.family(g), comp=g.comp, tok=tok, heads=prog.bodyheads[g.name], depth=prog.depth[g.name], nbody=prog.nbody[g.name], readers=len(prog.readers[g.name] - prog.desc[f.name] - {f.name}), anc=sorted(prog.anc[g.name])))
    sc = prog.scope_names(f)
    return dict(task=task, line=f.line, name=f.name, kind=f.kind, comp=f.comp, rows=rows, opts=opts, scope_heads=sorted({h for n in sc for h in prog.bodyheads[n]}), anc={n: sorted(prog.anc[n]) for n in sc})


def records(task, lines, reg):
    """The form records of a task's RULE, DET and INIT bodies. Other kinds of form are options and write no rows."""
    prog = Program(lines, reg)
    for f in prog.forms:
        all_rows = []
        for place, port, cj in f.bodies:
            if place not in ('RULE', 'DET', 'key', 'port'):
                continue
            near = []
            if place == 'port':
                for pl2, _p2, c2 in f.bodies:
                    if pl2 == 'key':
                        near = flat_rel(c2)
            slot = dict(place=place, comp=f.comp or '', port=(f.comp + '.' + port) if f.comp else '')
            all_rows += body_rows(prog, cj, near, slot)
        if all_rows:
            yield form_record(prog, f, task, all_rows)


def corpus_lines(task):
    with gzip.open(CORPUS + task + '/pairs.jsonl.gz', 'rt') as f:
        return [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]


def read_tasks(path):
    return [x.strip() for x in open(path) if x.strip()]
