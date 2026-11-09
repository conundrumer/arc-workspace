"""Static size of each query of each concept case under the feature grammar, as "Reach" in
docs/feature-spec/evaluation-protocol.md defines it, with the grammar of "The generating set" in
docs/feature-spec/feature-spec.md.

    <runtime python> -u -I -B reach.py run OUT_FILE
    <runtime python> -u -I -B reach.py report OUT_FILE
    <runtime python> -u -I -B reach.py show TASK [NAME_PATTERN]

`run` writes one JSON line per task as the task ends, skips the tasks already written, and prints a rate and an ETA.
No form is evaluated: each form of the case's text is parsed and translated into a term of the grammar, and the size is the count of the term's operators.

Readings where the rules leave a choice, each the smaller:
- `size`: columns that a positive atom leaves out are dropped by one `project` at the top of the list that must have exact columns: a clause or a union branch. An input binding names its own fields and an antijoin names its own pairs, so neither takes a `project`.
- `size_per_atom`: each atom that reads fewer columns than its relation has takes a `project` of its own, in any list.
- A nested `OR` or `IF` is either a term of its own joined to the rest, or takes the atoms that bind its outer labels into each branch; each list takes the smaller.
- A `(= *X Y)`, and a `(= X Y)` whose labels stand in different atoms, is a renaming or a join pair, of size 0.
- A key clause adds nothing where an input body implies it. Otherwise it is a join into one binding, or the binding of an input filled from the key.
- An instance that no form reads still takes one `component`, since a term names a port.
"""
import collections
import itertools
import json
import random
import re
import sys
import time
from pathlib import Path

REPO = Path('/Users/davidlu/code/arc-workspace')
sys.path.insert(0, str(REPO / 'src'))
from arclog_convert.readback import read_checked  # noqa: E402  the corpus is a gen/ directory
CORPUS = REPO / 'programs/arclog'
REGISTRY = REPO / 'engine/lib/registry.sexpr'
TASKS = REPO / 'model/contracts/dev/out-expand/tasks.txt'
SKIP = {'981571dc'}
OPS = {'=', '!=', '<', '<=', '>', '>='}
COMPLEMENT = {'=': '!=', '!=': '=', '<': '>=', '>=': '<', '>': '<=', '<=': '>'}
TOK = re.compile(r'''\s+|;[^\n]*|(?P<s>"(?:[^"\\]|\\.)*")|(?P<o>\()|(?P<c>\))|(?P<a>[^\s()";]+)''')


def parse(text):
    stack = [[]]
    for m in TOK.finditer(text):
        kind = m.lastgroup
        if kind == 'o':
            stack.append([])
        elif kind == 'c':
            x = stack.pop()
            stack[-1].append(x)
        elif kind == 'a':
            stack[-1].append(m.group('a'))
    if len(stack) != 1:
        raise ValueError('unbalanced text')
    return stack[0]


# ---------------------------------------------------------------- registry

class Registry:
    def __init__(self, text):
        self.lib = {}
        self.facts = {}
        self.components = {}
        self.proposers = {}
        for f in parse(text):
            head = f[0]
            if head in ('relation', 'macro'):
                cols = next(x for x in f if isinstance(x, list) and x[0] == 'columns')[1:]
                modes = [x[1:] for x in f if isinstance(x, list) and x[0] == 'modes']
                self.lib[f[1]] = dict(cols=[c[0] for c in cols], modes=[list(m) for m in modes[0]] if modes else [])
            elif head == 'fact':
                cols = next(x for x in f if isinstance(x, list) and x[0] == 'columns')[1:]
                self.facts[f[1]] = [c[0] for c in cols]
            elif head == 'proposer':
                cols = next(x for x in f if isinstance(x, list) and x[0] == 'columns')[1:]
                self.proposers[f[1]] = dict(cols=[c[0] if isinstance(c, list) else c for c in cols], domain='domain' in f)
            elif head == 'component':
                params = {}
                inputs = {}
                outputs = {}
                for x in f[2:]:
                    if not isinstance(x, list):
                        continue
                    if x[0] == 'type-parameters':
                        for p in x[1:]:
                            if isinstance(p, list):
                                params[p[0]] = p[1]
                            else:
                                params[p] = None
                    elif x[0] == 'inputs':
                        for i in x[1:]:
                            inputs[i[0]] = dict(cols=self._cols(i[1:]), from_key='from-key' in i, reads_outputs='reads-outputs' in i)
                    elif x[0] == 'outputs':
                        for o in x[1:]:
                            outputs[o[0]] = self._cols(o[1:])
                self.components[f[1]] = dict(params=params, inputs=inputs, outputs=outputs)

    @staticmethod
    def _cols(xs):
        return [(c[0], c[1]) for c in xs if isinstance(c, list) and len(c) == 2 and isinstance(c[1], str) and c[0] not in ('default', 'copies', 'frames')]


# ---------------------------------------------------------------- body forms

class Site:
    __slots__ = ('col', 'mark', 'label')

    def __init__(self, col, mark, label):
        self.col, self.mark, self.label = col, mark, label


def split_mark(tok):
    if tok[0] in '*^':
        return tok[0], tok[1:]
    return '', tok


def parse_site(x):
    if isinstance(x, str):
        mark, label = split_mark(x)
        return [Site((label,), mark, label)]
    col = x[0][1:]
    args = x[1:]
    out = []
    for a in args:
        if isinstance(a, str):
            mark, label = split_mark(a)
            path = (col, label) if (len(args) > 1 or col == 'key') else (col,)
            out.append(Site(path, mark, label))
        else:
            for s in parse_site(a):
                out.append(Site((col,) + s.col, s.mark, s.label))
    return out


class Atom:
    __slots__ = ('rel', 'sites', 'neg', 'origin')
    counter = 0

    def __init__(self, rel, sites, neg=False, origin=None):
        self.rel, self.sites, self.neg = rel, sites, neg
        if origin is None:
            Atom.counter += 1
            origin = Atom.counter
        self.origin = origin

    def labels(self):
        return {s.label for s in self.sites if s.label != '0'}

    def fresh(self):
        return [s.label for s in self.sites if s.mark]

    def zero_sites(self):
        return [s for s in self.sites if s.label == '0']

    def repeats(self):
        c = collections.Counter(s.label for s in self.sites if s.label != '0')
        return {k: v for k, v in c.items() if v > 1}

    def site_at(self, col):
        for s in self.sites:
            if s.col[0] == col:
                return s
        return None

    def has_e(self):
        return any(s.col == ('E',) for s in self.sites)

    def text(self):
        return self.rel + '[' + ' '.join(('%s:' % '.'.join(s.col) if s.col[-1] != s.label else '') + s.mark + s.label for s in self.sites) + ']'


class Cons:
    __slots__ = ('op', 'mark', 'a', 'b')

    def __init__(self, op, mark, a, b):
        self.op, self.mark, self.a, self.b = op, mark, a, b

    def labels(self):
        return {x for x in (self.a, self.b) if x != '0'}


class Or:
    __slots__ = ('branches',)

    def __init__(self, branches):
        self.branches = branches


class If:
    __slots__ = ('test', 'then', 'els')

    def __init__(self, test, then, els):
        self.test, self.then, self.els = test, then, els


class All:
    __slots__ = ('domain', 'body')

    def __init__(self, domain, body):
        self.domain, self.body = domain, body


class Mark:
    __slots__ = ('kind', 'cols')

    def __init__(self, kind, cols):
        self.kind, self.cols = kind, cols


class NegConj:
    __slots__ = ('items',)

    def __init__(self, items):
        self.items = items


class TermFactor:
    __slots__ = ('tlabels', 'term')

    def __init__(self, tlabels, term):
        self.tlabels, self.term = set(tlabels), term


def parse_items(lst):
    out = []
    for x in lst:
        h = x[0]
        if h == 'NOT':
            a = x[1]
            out.append(Atom(a[0], [s for y in a[1:] for s in parse_site(y)], neg=True))
        elif h in OPS:
            mark, a = split_mark(x[1])
            out.append(Cons(h, mark, a, x[2]))
        elif h == 'OR':
            out.append(Or([parse_items(b) for b in x[1:]]))
        elif h == 'IF':
            out.append(If(parse_items(x[1]), parse_items(x[2]), parse_items(x[3])))
        elif h == 'ALL':
            out.append(All(parse_items(x[1]), parse_items(x[2])))
        elif h in ('ONE', 'SET'):
            out.append(Mark(h, list(x[1:])))
        else:
            out.append(Atom(h, [s for y in x[1:] for s in parse_site(y)]))
    return out


def walk_atoms(items):
    for i in items:
        if isinstance(i, Atom):
            yield i
        elif isinstance(i, Or):
            for b in i.branches:
                yield from walk_atoms(b)
        elif isinstance(i, If):
            yield from walk_atoms(i.test)
            yield from walk_atoms(i.then)
            yield from walk_atoms(i.els)
        elif isinstance(i, All):
            yield from walk_atoms(i.domain)
            yield from walk_atoms(i.body)
        elif isinstance(i, NegConj):
            yield from walk_atoms(i.items)


def mentioned(items):
    out = set()
    for i in items:
        if isinstance(i, Atom):
            out |= i.labels()
        elif isinstance(i, Cons):
            out |= i.labels()
        elif isinstance(i, Or):
            for b in i.branches:
                out |= mentioned(b)
        elif isinstance(i, If):
            out |= mentioned(i.test) | mentioned(i.then) | mentioned(i.els)
        elif isinstance(i, All):
            out |= mentioned(i.domain) | mentioned(i.body)
        elif isinstance(i, NegConj):
            out |= mentioned(i.items)
        elif isinstance(i, TermFactor):
            out |= i.tlabels
    return out


def fresh_anywhere(items):
    out = set()
    for i in items:
        if isinstance(i, Atom):
            out |= set(i.fresh())
        elif isinstance(i, Cons):
            if i.mark:
                out.add(i.a)
        elif isinstance(i, Or):
            for b in i.branches:
                out |= fresh_anywhere(b)
        elif isinstance(i, If):
            out |= fresh_anywhere(i.test) | fresh_anywhere(i.then) | fresh_anywhere(i.els)
        elif isinstance(i, All):
            out |= fresh_anywhere(i.domain) | fresh_anywhere(i.body)
        elif isinstance(i, NegConj):
            out |= fresh_anywhere(i.items)
        elif isinstance(i, TermFactor):
            out |= i.tlabels
    return out


def exports(i):
    if isinstance(i, Or):
        first = visible(i.branches[0])
        return [x for x in first if all(x in mentioned(b) for b in i.branches[1:])]
    if isinstance(i, If):
        return [x for x in visible(i.then) if x in mentioned(i.els)]
    return []


def visible(items):
    out = []
    for i in items:
        if isinstance(i, Atom) and not i.neg:
            new = i.fresh()
        elif isinstance(i, Cons) and i.mark:
            new = [i.a]
        elif isinstance(i, (Or, If)):
            new = exports(i)
        elif isinstance(i, TermFactor):
            new = sorted(i.tlabels)
        else:
            new = []
        for x in new:
            if x not in out:
                out.append(x)
    return out


def free_labels(i):
    items = [i]
    return mentioned(items) - fresh_anywhere(items)


def sub_items(items, m):
    return [sub_item(i, m) for i in items]


def sub_item(i, m):
    if not m:
        return i
    if isinstance(i, Atom):
        return Atom(i.rel, [Site(s.col, s.mark, m.get(s.label, s.label)) for s in i.sites], i.neg, i.origin)
    if isinstance(i, Cons):
        return Cons(i.op, i.mark, m.get(i.a, i.a), m.get(i.b, i.b))
    if isinstance(i, Or):
        return Or([sub_items(b, m) for b in i.branches])
    if isinstance(i, If):
        return If(sub_items(i.test, m), sub_items(i.then, m), sub_items(i.els, m))
    if isinstance(i, All):
        return All(sub_items(i.domain, m), sub_items(i.body, m))
    if isinstance(i, NegConj):
        return NegConj(sub_items(i.items, m))
    if isinstance(i, TermFactor):
        return TermFactor({m.get(x, x) for x in i.tlabels}, i.term)
    return i


# ---------------------------------------------------------------- terms

class T:
    __slots__ = ('op', 'kids', 'text', 'labels', 'hidden', 'size')

    def __init__(self, op, kids, text, labels, hidden=frozenset()):
        self.op, self.kids, self.text, self.labels, self.hidden = op, kids, text, set(labels), frozenset(hidden)
        self.size = (0 if op == 'leaf' else 1) + sum(k.size for k in kids)

    def render(self):
        if self.op == 'leaf':
            return self.text
        return '(' + ' '.join([self.op] + [k.render() for k in self.kids] + ([self.text] if self.text else [])) + ')'

    def count(self, c):
        if self.op != 'leaf':
            c[self.op] += 1
        for k in self.kids:
            k.count(c)


def leaf(text, labels):
    return T('leaf', [], text, labels)


# ---------------------------------------------------------------- one case

class Schema:
    __slots__ = ('n', 'per_input', 'source')

    def __init__(self, n, per_input, source):
        self.n, self.per_input, self.source = n, per_input, source


class Case:
    def __init__(self, reg, text, mode='small'):
        self.reg = reg
        self.mode = mode
        self.forms = parse(text)
        self.schema = {}
        self.read_cols = collections.defaultdict(set)
        self.ports_read = collections.defaultdict(set)
        self.faults = []
        self.ctx_kind = 'RULE'
        self.parsed = []
        for f in self.forms:
            self.parsed.append(self.prepare(f))
        for p in self.parsed:
            self.collect_reads(p)
        for p in self.parsed:
            self.declare(p)
        self.compute_live()

    # ------------------------------ forms into records

    def prepare(self, f):
        h = f[0]
        if h == 'RULE' or h == 'DET':
            name = f[1]
            rest = f[2:]
            props = []
            while rest and isinstance(rest[0], str):
                props.append(rest[0])
                rest = rest[1:]
            items = parse_items(rest)
            return dict(kind=h, name=name, props=props, items=items)
        if h == 'INIT':
            name, comp = f[1], f[2]
            key = None
            inputs = []
            for x in f[3:]:
                if x[0] == 'key':
                    key = parse_items(x[1])
                    for y in x[2:]:
                        inputs.append(dict(port=y[0], head=y[1], items=parse_items(y[2:]), keyed=True))
                else:
                    inputs.append(dict(port=x[0], head=x[1], items=parse_items(x[2:]), keyed=False))
            return dict(kind='INIT', name=name, comp=comp, key=key, inputs=inputs)
        if h == 'CHOOSE':
            rec = dict(kind='CHOOSE', name=f[1], for_items=[], from_items=[], never=[])
            for x in f[2:]:
                if x[0] == 'for':
                    rec['for_items'] = parse_items(x[1])
                    for y in x[2:]:
                        rec['from_items'] += parse_items(y[1:])
                elif x[0] == 'from':
                    rec['from_items'] += parse_items(x[1:])
                elif x[0] == 'never':
                    rec['never'].append(parse_items(x[1:]))
            return rec
        if h == 'RIGID_DET':
            rec = dict(kind='RIGID_DET', name=f[1], key=[], instance=[], parts=[])
            for x in f[2:]:
                if x[0] == 'key':
                    rec['key'] = parse_items(x[1])
                    for y in x[2:]:
                        if y[0] == 'instance':
                            rec['instance'] = parse_items(y[1])
                            rec['parts'] += parse_items(y[2:])
                        else:
                            rec['parts'] += parse_items([y])
                elif x[0] == 'instance':
                    rec['instance'] = parse_items(x[1])
                    rec['parts'] += parse_items(x[2:])
                else:
                    rec['parts'] += parse_items([x])
            return rec
        if h == 'OUT':
            return dict(kind='OUT', items=parse_items(f[1:]))
        self.faults.append('unknown form ' + str(h))
        return dict(kind='OTHER', head=h)

    def compute_live(self):
        """The forms that OUT reaches through reads. A form is known by the relation or the instance it declares."""
        owner = {}
        for k, p in enumerate(self.parsed):
            if p['kind'] in ('RULE', 'DET', 'INIT', 'CHOOSE', 'RIGID_DET'):
                owner[p['name']] = k
        reads = []
        for p in self.parsed:
            names = set()
            for items in self.form_items(p):
                for a in walk_atoms(items):
                    r = a.rel
                    while r not in owner and '.' in r:
                        r = r.rsplit('.', 1)[0]
                    if r in owner:
                        names.add(owner[r])
            reads.append(names)
        live = set()
        stack = [k for k, p in enumerate(self.parsed) if p['kind'] == 'OUT']
        while stack:
            k = stack.pop()
            if k not in live:
                live.add(k)
                stack.extend(reads[k])
        self.live = live
        ports = collections.defaultdict(set)
        for k in live:
            for items in self.form_items(self.parsed[k]):
                for a in walk_atoms(items):
                    if '.' in a.rel:
                        inst, port = a.rel.rsplit('.', 1)
                        ports[inst].add(port)
        self.live_ports = ports

    def form_items(self, p):
        k = p['kind']
        if k in ('RULE', 'DET', 'OUT'):
            return [p['items']]
        if k == 'INIT':
            return ([p['key']] if p['key'] else []) + [i['items'] for i in p['inputs']]
        if k == 'CHOOSE':
            return [p['for_items'], p['from_items']] + p['never']
        if k == 'RIGID_DET':
            return [p['key'], p['instance'], p['parts']]
        return []

    def collect_reads(self, p):
        for items in self.form_items(p):
            for a in walk_atoms(items):
                for s in a.sites:
                    self.read_cols[a.rel].add(s.col[0])
                if '.' in a.rel:
                    inst, port = a.rel.rsplit('.', 1)
                    self.ports_read[inst].add(port)

    # ------------------------------ schemas

    def declare(self, p):
        k = p['kind']
        if k == 'RULE':
            n = self.reg.proposers[p['props'][0]]['cols'] if p['props'] else None
            cols = list(n) if n else visible(p['items'])
            self.schema[p['name']] = Schema(len(cols), True, 'RULE')
            p['columns'] = cols
        elif k == 'DET':
            if p['props']:
                cols = list(self.reg.proposers[p['props'][0]]['cols']) if p['props'][0] in self.reg.proposers else []
                self.schema[p['name']] = Schema(len(cols), False, 'proposer')
            else:
                marks = [c for i in p['items'] if isinstance(i, Mark) and i.kind == 'ONE' for c in i.cols]
                reads = self.read_cols[p['name']]
                cols = [l for l in visible(p['items']) if l in reads or l in marks] if reads or marks else visible(p['items'])
                self.schema[p['name']] = Schema(len(cols), False, 'DET')
            p['columns'] = cols
        elif k == 'INIT':
            self.declare_init(p)
        elif k == 'CHOOSE':
            f_labels = [l for l in visible(p['for_items'])]
            c_labels = [l for l in visible(p['from_items']) if l not in f_labels]
            bodies = p['for_items'] + p['from_items']
            self.schema[p['name']] = Schema(len(f_labels) + len(c_labels), self.reads_per_input(bodies, False), 'CHOOSE')
        elif k == 'RIGID_DET':
            key_labels = visible(p['key'])
            inst_labels = visible(p['instance'])
            base = len(key_labels) + 1
            for a in p['parts']:
                own = [l for l in a.labels() if l not in inst_labels]
                self.schema[p['name'] + '.' + a.rel[1:]] = Schema(base + len(own), False, 'RIGID_DET')
            self.schema[p['name'] + '.pose'] = Schema(len(key_labels) + len(inst_labels) + 1, False, 'RIGID_DET')

    def reads_per_input(self, items, keyed_by_example):
        if keyed_by_example or any(a.rel in ('ex_input', 'ex_output') for a in walk_atoms(items)):
            return False
        for a in walk_atoms(items):
            if a.rel == 'input':
                return True
            sch = self.schema.get(a.rel)
            if sch is not None and sch.per_input and not a.has_e():
                return True
        return False

    def declare_init(self, p):
        comp = self.reg.components[p['comp']]
        key_labels = [s.label for a in walk_atoms(p['key'] or []) for s in a.sites if s.mark == '^']
        key_labels = list(dict.fromkeys(key_labels))
        p['key_labels'] = key_labels
        by_example = any(s.mark == '^' and s.col[-1] == 'E' for a in walk_atoms(p['key'] or []) for s in a.sites)
        all_items = (p['key'] or []) + [x for i in p['inputs'] for x in i['items']]
        per_input = self.reads_per_input(all_items, by_example)
        heads = {}
        for i in p['inputs']:
            heads[i['port']] = i['head']
        fields = {}

        def param_arity(tname):
            if tname in fields:
                return fields[tname]
            bound = comp['params'].get(tname)
            n = None
            for iname, idata in comp['inputs'].items():
                if iname not in heads:
                    continue
                for col, typ in idata['cols']:
                    if typ != tname or col == 'key':
                        continue
                    for site in heads[iname]:
                        if isinstance(site, str):
                            if site == col:
                                n = 1
                        elif site[0] == ':' + col:
                            n = len(parse_site(site))
                    if n is not None:
                        break
                if n is not None:
                    break
            if n is None:
                n = 1 if bound else 0
            fields[tname] = n
            return n

        for port, cols in comp['outputs'].items():
            n = 0
            for col, typ in cols:
                if col == 'key':
                    n += len(key_labels)
                elif typ in comp['params']:
                    if typ == 'Key' and col == 'key':
                        n += len(key_labels)
                    else:
                        n += param_arity(typ)
                else:
                    n += 1
            self.schema[p['name'] + '.' + port] = Schema(n, per_input, 'INIT')
            p.setdefault('output_ports', set()).add(port)
        for port, data in comp['inputs'].items():
            name = p['name'] + '.' + port
            if name not in self.schema:
                n = 0
                for col, typ in data['cols']:
                    if col == 'key':
                        n += len(key_labels)
                    elif typ in comp['params']:
                        n += param_arity(typ)
                    else:
                        n += 1
                self.schema[name] = Schema(n, per_input, 'INIT input')
        p['per_input'] = per_input

    def arity(self, a):
        if a.rel in self.reg.facts:
            return len(self.reg.facts[a.rel])
        if a.rel in self.reg.lib:
            return len(self.reg.lib[a.rel]['cols'])
        sch = self.schema.get(a.rel)
        if sch is None:
            self.faults.append('no schema for ' + a.rel)
            return len(a.sites)
        n = sch.n
        if sch.per_input and (self.ctx_kind == 'DET' or (self.ctx_kind == 'INIT' and a.has_e())):
            n += 1
        return n

    def fewer(self, a):
        n = self.arity(a)
        read = len({s.col for s in a.sites})
        if read > n:
            self.faults.append('atom %s reads %d of %d columns' % (a.text(), read, n))
        return read < n

    # ------------------------------ atoms

    def is_lib(self, a):
        return isinstance(a, Atom) and a.rel in self.reg.lib

    def modes(self, a):
        if not self.is_lib(a) or not self.reg.lib[a.rel]['modes']:
            return [set()]
        out = []
        for mode in self.reg.lib[a.rel]['modes']:
            need = set()
            ok = True
            for col in mode:
                s = a.site_at(col)
                if s is None:
                    ok = False
                    break
                if s.label != '0':
                    need.add(s.label)
            if ok:
                out.append(need)
        return out or [set()]

    def needs_bound(self, a):
        return self.is_lib(a) and bool(self.reg.lib[a.rel]['modes'])

    def f_labels(self, f):
        return f.tlabels if isinstance(f, TermFactor) else f.labels()

    def f_cost(self, f):
        if isinstance(f, TermFactor):
            return f.term.size
        return len(f.zero_sites()) + sum(v - 1 for v in f.repeats().values())

    def wrap_zero(self, t, a):
        for s in a.zero_sites():
            t = T('select', [t], '%s = 0' % '.'.join(s.col), t.labels, t.hidden)
        return t

    def wrap_project(self, t, a, fewer):
        if self.mode == 'atom' and fewer:
            return T('project', [t], ' '.join(sorted(t.labels)), t.labels, t.hidden)
        return T(t.op, t.kids, t.text, t.labels, t.hidden | ({a.origin} if fewer else set()))

    def add_factor(self, term, f):
        if isinstance(f, TermFactor):
            if term is None:
                return f.term
            return T('join', [term, f.term], '', term.labels | f.tlabels, term.hidden | f.term.hidden)
        a = f
        before = term.labels if term is not None else set()
        fewer = self.fewer(a)
        if term is None or not self.is_lib(a):
            right = self.wrap_project(self.wrap_zero(leaf(a.text(), a.labels()), a), a, fewer)
            if term is None:
                out = right
            else:
                out = T('join', [term, right], '', term.labels | right.labels, term.hidden | right.hidden)
        else:
            out = T('lib-join', [term], a.text(), term.labels | a.labels(), term.hidden)
            out = self.wrap_project(self.wrap_zero(out, a), a, fewer)
        for l, c in a.repeats().items():
            if l not in before:
                for _ in range(c - 1):
                    out = T('select', [out], '%s repeated' % l, out.labels, out.hidden)
        return out

    def cover(self, need, cands):
        """The cheapest factors of `cands` that bind the labels of `need`, with the labels that a lib atom among them needs."""
        need = set(need)
        if not need:
            return []
        best = [None, None]

        def rec(left, chosen, cost, bound):
            if best[1] is not None and cost >= best[1]:
                return
            left = left - bound
            if not left:
                best[0], best[1] = list(chosen), cost
                return
            if len(chosen) > 6:
                return
            l = sorted(left)[0]
            for f in cands:
                if l in self.f_labels(f) and not any(f is c for c in chosen):
                    base = self.f_cost(f) + (1 if chosen else 0)
                    for mode in self.modes(f) if isinstance(f, Atom) else [set()]:
                        if l in mode:
                            continue
                        gives = self.f_labels(f) - mode
                        rec((left - gives) | (mode - bound), chosen + [f], cost + base, bound | gives)

        rec(need, [], 0, set())
        return best[0]

    def cover_cost(self, need, cands):
        g = self.cover(need, cands)
        if g is None:
            return float('inf')
        return sum(self.f_cost(f) for f in g) + len(g) - 1

    def order_key(self, f):
        if isinstance(f, TermFactor):
            return (0, 0)
        return (2 if self.needs_bound(f) else (1 if self.is_lib(f) else 0), 1 if f.repeats() else 0)

    # ------------------------------ a list

    def assemble(self, factors, consts, filters, want, cands, env, allow=frozenset()):
        term = None
        for x in consts:
            term = T('select', [term] if term is not None else [], '%s := 0' % x, (term.labels if term is not None else set()) | {x}, term.hidden if term is not None else frozenset())
        pending = sorted(factors, key=self.order_key)
        while pending:
            bound = term.labels if term is not None else set()
            chosen = None
            for f in pending:
                if isinstance(f, TermFactor) or not self.needs_bound(f) or any(m <= bound for m in self.modes(f)):
                    chosen = f
                    break
            if chosen is None:
                chosen = pending[0]
                self.faults.append('needs unbound at ' + chosen.text())
            pending = [f for f in pending if f is not chosen]
            if term is None and self.needs_bound(chosen):
                self.faults.append('lib atom as base ' + chosen.text())
            term = self.add_factor(term, chosen)
        if term is None:
            term = leaf('true', set())
        for flt in filters:
            term = self.apply_filter(term, flt, cands, env)
        if want is not None and ((term.hidden - allow) or term.labels - want):
            term = T('project', [term], ' '.join(sorted(want)), set(want) & term.labels, term.hidden & allow)
        return term

    def neg_right(self, a, cands, left):
        """The right side of an antijoin for atom `a`. Its pairs name what it joins, so it takes no `project`."""
        fewer = self.fewer(a)
        if self.needs_bound(a):
            best = None
            for mode in self.modes(a):
                g = self.cover(mode, cands)
                if g is not None:
                    term = self.assemble(g, [], [], None, [], Env([], set()))
                    if best is None or term.size < best.size:
                        best = term
            if best is None or best.size > left.size:
                if not (self.modes(a)[0] <= left.labels):
                    self.faults.append('no guard for NOT ' + a.text())
                best = left
            out = T('lib-join', [best], a.text(), best.labels | a.labels())
        else:
            out = leaf(a.text(), a.labels())
        out = self.wrap_zero(out, a)
        if self.mode == 'atom' and fewer:
            out = T('project', [out], ' '.join(sorted(out.labels)), out.labels)
        return out

    def apply_filter(self, term, flt, cands, env):
        if isinstance(flt, Cons):
            return T('select', [term], '%s %s %s' % (flt.a, flt.op, flt.b), term.labels, term.hidden)
        if isinstance(flt, Atom):
            right = self.neg_right(flt, cands, term)
            return T('antijoin', [term, right], '', term.labels, term.hidden)
        if isinstance(flt, NegConj):
            return self.neg_filter(term, flt.items, cands, env)
        if isinstance(flt, All):
            return self.all_filter(term, flt, cands, env)
        raise ValueError('filter')

    def neg_filter(self, left, items, cands, env):
        items = [i for i in items if not isinstance(i, Mark)]
        if not items:
            self.faults.append('negation of an empty list')
            return left
        if len(items) == 1:
            i = items[0]
            if isinstance(i, Cons):
                return T('select', [left], '%s %s %s' % (i.a, COMPLEMENT[i.op], i.b), left.labels, left.hidden)
            if isinstance(i, Atom) and not i.neg:
                right = self.neg_right(i, cands, left)
                return T('antijoin', [left, right], '', left.labels, left.hidden)
            if isinstance(i, Atom):
                pos = Atom(i.rel, i.sites)
                return self.add_factor(left, pos)
            if isinstance(i, Or):
                for b in i.branches:
                    left = self.neg_filter(left, b, cands, env)
                return left
        env2 = Env(cands + env.guards, env.scope | left.labels)
        right = self.conj(items, env2, None, frozenset())
        return T('antijoin', [left, right], '', left.labels, left.hidden)

    def all_filter(self, term, a, cands, env):
        y = free_labels(a)
        env2 = Env(cands + env.guards, env.scope | term.labels)
        dom = self.conj(a.domain, env2, None, frozenset(y))
        dom_atoms = [i for i in a.domain if isinstance(i, Atom) and not i.neg]
        w = self.neg_filter(dom, a.body, dom_atoms + cands, env2)
        out = T('antijoin', [term, w], '', term.labels, term.hidden)
        ctx = [c for c in cands + env.guards if isinstance(c, Atom)]
        if not self.implied(a.domain, ctx, y):
            e = self.conj(a.domain, env2, None, frozenset(y & mentioned(a.domain)))
            extra = {'domain'} if e.hidden or e.labels - out.labels else set()
            out = T('join', [out, e], '', out.labels | e.labels, out.hidden | extra)
        return out

    def implied(self, target, context, fixed):
        """A mapping of the labels of `target` onto those of `context` that keeps `fixed` labels: the positive atoms of `target` map into positive atoms of `context` (a containment mapping), and its other items onto items of the same form."""
        target = [i for i in target if not isinstance(i, Mark)]
        context = [i for i in context if not isinstance(i, Mark)]
        pos = [i for i in target if isinstance(i, Atom) and not i.neg]
        others = [i for i in target if not (isinstance(i, Atom) and not i.neg)]
        ctx_pos = [i for i in context if isinstance(i, Atom) and not i.neg]
        ctx_others = [i for i in context if not (isinstance(i, Atom) and not i.neg)]

        def rec_others(j, m):
            if j == len(others):
                return True
            for c in ctx_others:
                m2 = self.match_item(others[j], c, m, fixed)
                if m2 is not None and rec_others(j + 1, m2):
                    return True
            return False

        def rec(idx, m):
            if idx == len(pos):
                return rec_others(0, m)
            a = pos[idx]
            for c in ctx_pos:
                if c.rel == a.rel:
                    m2 = self.map_atom(a, c, m, fixed)
                    if m2 is not None and rec(idx + 1, m2):
                        return True
            if self.is_lib(a) and not self.reg.lib[a.rel]['modes'] and not a.zero_sites() and not (a.labels() & (set(fixed) | set(m))):
                return rec(idx + 1, m)
            return False

        return rec(0, {})

    @staticmethod
    def bind(m, l, v, fixed):
        if l == '0' or v == '0':
            return m if l == v else None
        if l in fixed:
            return m if v == l else None
        if m.get(l, v) != v:
            return None
        m2 = dict(m)
        m2[l] = v
        return m2

    def map_atom(self, a, c, m, fixed):
        for s in a.sites:
            other = next((x for x in c.sites if x.col == s.col or (x.col[0] == s.col[0] and len(x.col) != len(s.col))), None)
            v = other.label if other is not None else '~%d.%s' % (id(c), s.col)
            if other is None and (s.label == '0' or s.label in fixed):
                return None
            m = self.bind(m, s.label, v, fixed)
            if m is None:
                return None
        return m

    def match_list(self, a, c, m, fixed):
        a = [i for i in a if not isinstance(i, Mark)]
        c = [i for i in c if not isinstance(i, Mark)]
        if len(a) != len(c):
            return None

        def rec(j, m, used):
            if j == len(a):
                return m
            for k, x in enumerate(c):
                if k not in used:
                    m2 = self.match_item(a[j], x, m, fixed)
                    if m2 is not None:
                        m3 = rec(j + 1, m2, used | {k})
                        if m3 is not None:
                            return m3
            return None

        return rec(0, m, frozenset())

    def match_item(self, a, c, m, fixed):
        if type(a) is not type(c):
            return None
        if isinstance(a, Atom):
            if a.rel != c.rel or a.neg != c.neg or len(a.sites) != len(c.sites):
                return None
            return self.map_atom(a, c, m, fixed)
        if isinstance(a, Cons):
            if a.op != c.op:
                return None
            m = self.bind(m, a.a, c.a, fixed)
            return None if m is None else self.bind(m, a.b, c.b, fixed)
        if isinstance(a, Or):
            if len(a.branches) != len(c.branches):
                return None
            for x, y in zip(a.branches, c.branches):
                m = self.match_list(x, y, m, fixed)
                if m is None:
                    return None
            return m
        if isinstance(a, If):
            for x, y in ((a.test, c.test), (a.then, c.then), (a.els, c.els)):
                m = self.match_list(x, y, m, fixed)
                if m is None:
                    return None
            return m
        if isinstance(a, All):
            for x, y in ((a.domain, c.domain), (a.body, c.body)):
                m = self.match_list(x, y, m, fixed)
                if m is None:
                    return None
            return m
        return None

    def conj(self, items, env, want, must, allow=frozenset()):
        items = [i for i in items if not isinstance(i, Mark)]
        want = set(want) if want is not None else None
        must = set(must)
        consts = []
        filters = []
        # `=` first: a renaming, a join pair, a constant column, or a filter.

        def apply(m):
            nonlocal items, want, must, consts, filters
            items = sub_items(items, m)
            filters = sub_items(filters, m)
            if want is not None:
                want = {m.get(x, x) for x in want}
            must = {m.get(x, x) for x in must}
            consts = [m.get(x, x) for x in consts]

        def here():
            out = set(consts)
            for i in items:
                if isinstance(i, Atom) and not i.neg:
                    out |= i.labels()
                elif isinstance(i, (Or, If)):
                    out |= set(exports(i)) | (free_labels(i) - env.scope)
                elif isinstance(i, TermFactor):
                    out |= i.tlabels
            return out

        while True:
            c = next((i for i in items if isinstance(i, Cons) and i.op == '='), None)
            if c is None:
                break
            items = [i for i in items if i is not c]
            h = here()
            if c.b == '0':
                if c.mark or not (c.a in h or c.a in env.scope):
                    consts.append(c.a)
                else:
                    filters.append(c)
                continue
            if c.mark:
                apply({c.a: c.b})
                continue
            hx, hy, sx, sy = c.a in h, c.b in h, c.a in env.scope, c.b in env.scope
            if not hx and not sx:
                apply({c.a: c.b})
            elif not hy and not sy:
                apply({c.b: c.a})
            elif hx and hy:
                apply({c.b: c.a})
            elif hx:
                apply({c.b: c.a})
            elif hy:
                apply({c.a: c.b})
            elif self.cover_cost({c.a}, env.guards) <= self.cover_cost({c.b}, env.guards):
                apply({c.b: c.a})
            else:
                apply({c.a: c.b})
        pos = [i for i in items if (isinstance(i, Atom) and not i.neg) or isinstance(i, TermFactor)]
        filters = filters + [i for i in items if (isinstance(i, Atom) and i.neg) or isinstance(i, (Cons, All, NegConj))]
        nested = [i for i in items if isinstance(i, (Or, If))]
        # the labels this list needs and does not bind take guards from the enclosing lists
        avail = set(consts)
        for f in pos:
            if not self.needs_bound(f):
                avail |= self.f_labels(f)
        for n in nested:
            avail |= set(exports(n)) | free_labels(n)
        unfired = [f for f in pos if self.needs_bound(f)]
        need = set(must)
        lib_need = set()
        while unfired:
            changed = True
            while changed and unfired:
                changed = False
                for f in list(unfired):
                    if any(m <= avail for m in self.modes(f)):
                        avail |= f.labels()
                        unfired.remove(f)
                        changed = True
            if unfired:
                f = min(unfired, key=lambda u: min(len(m - avail) for m in self.modes(u)))
                missing = min((m - avail for m in self.modes(f)), key=len)
                lib_need |= missing
                avail |= missing
        for flt in filters:
            if isinstance(flt, Atom):
                need |= flt.labels()
            elif isinstance(flt, Cons):
                need |= flt.labels()
            else:
                need |= free_labels(flt)
        need = (need - avail) | lib_need
        if need:
            g = self.cover(need, env.guards)
            if g is None:
                self.faults.append('no guard for %s' % sorted(need))
            else:
                pos = pos + [x for x in g if not any(x is y for y in pos)]
        for f in pos:
            avail |= self.f_labels(f)
        bound_here = set(consts)
        for f in pos:
            bound_here |= self.f_labels(f)
        env2 = Env(pos + env.guards, env.scope | bound_here)
        # nested forms, those that read another's exports after it
        options = []
        extra_cands = []
        order = []
        rest = list(nested)
        while rest:
            for n in rest:
                others = set().union(*[set(exports(o)) for o in rest if o is not n]) if len(rest) > 1 else set()
                if not (free_labels(n) & others):
                    order.append(n)
                    rest.remove(n)
                    break
            else:
                order += rest
                rest = []
        for n in order:
            outside = env2.scope | {l for o in nested if o is not n for l in exports(o)}
            y = free_labels(n) & outside
            x = set(exports(n)) | (free_labels(n) - outside)
            branches = n.branches if isinstance(n, Or) else [n.test + n.then, n.els + [NegConj(n.test)]]
            scope_n = env2.scope - x
            env_n = Env(pos + extra_cands + env.guards, scope_n)
            s2 = self.union_terms([self.conj(b, env_n, y | x, y | x) for b in branches], y | x)
            opts = [(s2, y | x, [])]
            y_guard = {l for l in y if not all(l in self.binds(b) for b in branches)}
            if y_guard:
                g = self.cover(y_guard, pos + extra_cands + env.guards)
                if g is not None:
                    gl = set().union(*[self.f_labels(f) for f in g]) | y
                    env_g = Env([f for f in pos + extra_cands + env.guards if not any(f is h for h in g)], scope_n)
                    keep = frozenset(f.origin for f in g if isinstance(f, Atom))
                    s1 = self.union_terms([self.conj(list(b) + g, env_g, gl | x, y | x, keep) for b in branches], gl | x)
                    opts.append((s1, gl | x, [f for f in g if any(f is p for p in pos)]))
            options.append(opts)
            extra_cands = extra_cands + [TermFactor(y | x, s2)]
        cands = pos + extra_cands
        best = None
        combos = itertools.product(*options) if sum(len(o) > 1 for o in options) <= 6 else [tuple(min(o, key=lambda t: t[0].size) for o in options)]
        for combo in combos:
            consumed = [f for opt in combo for f in opt[2]]
            factors = [f for f in pos if not any(f is c for c in consumed)] + [TermFactor(opt[1], opt[0]) for opt in combo]
            term = self.assemble(factors, consts, filters, want, cands, env, allow)
            if best is None or term.size < best.size:
                best = term
        return best

    def binds(self, items):
        """The labels that the positive atoms of a list bind without a guard."""
        out = set()
        for i in items:
            if isinstance(i, Atom) and not i.neg:
                if self.needs_bound(i):
                    out |= i.labels() - min(self.modes(i), key=len)
                else:
                    out |= i.labels()
            elif isinstance(i, TermFactor):
                out |= i.tlabels
        return out

    def union_terms(self, terms, labels):
        out = terms[0]
        for t in terms[1:]:
            out = T('union', [out, t], '', labels, out.hidden | t.hidden)
        if len(terms) == 1:
            out = T(out.op, out.kids, out.text, labels, out.hidden)
        return out

    # ------------------------------ a query

    def clause_term(self, p):
        self.ctx_kind = p['kind']
        want = set(p['columns'])
        return self.conj(p['items'], Env([], set()), want, frozenset())

    def rename_local(self, items, keep, prefix):
        m = {l: prefix + l for l in fresh_anywhere(items) | mentioned(items) if l not in keep and l != '0'}
        return sub_items(items, m)

    def init_query(self, p):
        self.ctx_kind = 'INIT'
        comp = self.reg.components[p['comp']]
        key_labels = p['key_labels']
        key_items = self.rename_local(p['key'], set(key_labels), 'k.') if p['key'] else None
        guards = []
        key_term = None
        if key_items:
            key_term = self.conj(key_items, Env([], set()), None, frozenset())
            top = [i for i in key_items if isinstance(i, Atom) and not i.neg]
            simple = len(top) == len([i for i in key_items if not isinstance(i, Mark)])
            guards = top if simple else [TermFactor(set(key_labels), key_term)]
        total = collections.Counter()
        parts = []
        terms = []
        any_implied = False
        key_equal = False
        written = set()
        fixed = set(key_labels)
        for inp in p['inputs']:
            written.add(inp['port'])
            head_labels = {s.label for site in inp['head'] for s in parse_site(site)}
            reads_key = bool(key_labels) and bool((mentioned(inp['items']) | head_labels) & fixed)
            must = (fixed if reads_key else set()) | head_labels
            guards_i = guards
            if len(inp['items']) == 1 and isinstance(inp['items'][0], Cons) and inp['items'][0].a == inp['items'][0].b and inp['items'][0].op in ('!=', '<', '>'):
                # a body that holds nowhere: any atom that binds the label gives its no rows
                guards_i = [a for a in walk_atoms(key_items) if not a.neg]
            t = self.conj(inp['items'], Env(guards_i, fixed), None, frozenset(must))
            parts.append((inp['port'], t))
            if key_items and reads_key:
                own = {l for a in walk_atoms(inp['items']) if not a.neg for l in a.labels()}
                if not fixed <= own:
                    any_implied = True
                elif self.key_implied(key_items, inp['items'], fixed):
                    any_implied = True
                    if self.key_implied(inp['items'], key_items, fixed):
                        key_equal = True
        key_cost_term = None
        if key_items:
            unwritten_from_key = [n for n, d in comp['inputs'].items() if d['from_key'] and n not in written]
            if p['comp'] == 'Distance' and 'source_distance' in written:
                unwritten_from_key = []
            ops = []
            if unwritten_from_key and not (p['comp'] == 'Cardinality' and key_equal):
                ops.append(key_term)
                p['key_note'] = unwritten_from_key
            if (not unwritten_from_key or p['comp'] == 'Cardinality') and not any_implied:
                ops.append(T('join', [key_term], 'key into a binding', key_term.labels))
            if ops:
                key_cost_term = ops[0] if len(ops) == 1 else T('leaf', ops, 'key', set())
        n_ports = len(self.live_ports[p['name']] & p['output_ports'])
        if not self.live_ports[p['name']] and not any(a.startswith(p['name'] + '.') for a in self.read_cols):
            n_ports = 1
        elif not n_ports and not self.ports_read[p['name']] & set(comp['inputs']):
            n_ports = 1
        return n_ports, parts, key_cost_term

    def paths(self, items):
        """The lists of items that a list holds with each `OR` read as one of its branches. None where they pass a bound."""
        base = [i for i in items if not isinstance(i, (Or, Mark))]
        out = [base]
        for o in items:
            if isinstance(o, Or):
                new = []
                for b in o.branches:
                    sub = self.paths(b)
                    if sub is None:
                        return None
                    new += [x + y for x in out for y in sub]
                if len(new) > 64:
                    return None
                out = new
        return out

    def key_implied(self, key_items, body, fixed):
        """Every way through the input's body implies some way through the key clause. A key atom that binds a label the way does not bind counts, since a guard copies it."""
        alts = self.paths(key_items)
        ways = self.paths(body)
        if alts is None or ways is None:
            return False
        for way in ways:
            bound = self.binds(way)
            ok = False
            for alt in alts:
                guards = [a for a in alt if isinstance(a, Atom) and not a.neg and (a.labels() & fixed) - bound]
                if self.implied(alt, way + guards, fixed):
                    ok = True
                    break
            if not ok:
                return False
        return True


class Env:
    __slots__ = ('guards', 'scope')

    def __init__(self, guards, scope):
        self.guards, self.scope = guards, scope


def constant_columns(items, scope):
    """The `=` forms that make a column of `0`, which the grammar's `select` leaves out."""
    here = {l for i in items if isinstance(i, Atom) and not i.neg for l in i.labels()}
    n = 0
    for i in items:
        if isinstance(i, Cons) and i.op == '=' and i.b == '0' and (i.mark or not (i.a in here or i.a in scope)):
            n += 1
        elif isinstance(i, Or):
            for b in i.branches:
                n += constant_columns(b, scope | here)
        elif isinstance(i, If):
            n += constant_columns(i.test + i.then, scope | here) + constant_columns(i.els, scope | here)
        elif isinstance(i, All):
            n += constant_columns(i.domain, scope | here) + constant_columns(i.body, scope | here | mentioned(i.domain))
    return n


def flat_count(items):
    """Atoms beyond the first of each list, NOT, constraints, `0` sites and unions, with nothing copied or projected."""
    n = 0
    pos = 0
    for i in items:
        if isinstance(i, Atom):
            n += len(i.zero_sites())
            if i.neg:
                n += 1
            else:
                pos += 1
        elif isinstance(i, Cons):
            n += 1
        elif isinstance(i, Or):
            n += len(i.branches) - 1 + sum(flat_count(b) for b in i.branches)
            pos += 1
        elif isinstance(i, If):
            n += 2 + flat_count(i.test) * 2 + flat_count(i.then) + flat_count(i.els)
            pos += 1
        elif isinstance(i, All):
            n += 2 + flat_count(i.domain) + flat_count(i.body)
    return n + max(0, pos - 1)


def term_ops(t):
    c = collections.Counter()
    if t is not None:
        t.count(c)
    return c


def queries_of(reg, text, keep_terms=False):
    """Each query with its sizes, and the gap list, for one case's text."""
    small = Case(reg, text, 'small')
    atom = Case(reg, text, 'atom')
    out = []
    gaps = collections.Counter()
    for index, (ps, pa) in enumerate(zip(small.parsed, atom.parsed)):
        k = ps['kind']
        n_before = len(out)
        if k in ('RULE', 'DET'):
            marks = [i for i in ps['items'] if isinstance(i, Mark)]
            ones = [i for i in marks if i.kind == 'ONE']
            if ones:
                gaps['ONE clause'] += 1
                gaps['ONE mark'] += len(ones)
            if ps['props']:
                for name in ps['props']:
                    pr = reg.proposers.get(name)
                    if pr is None:
                        small.faults.append('unknown proposer ' + name)
                    elif pr['domain']:
                        gaps['domain proposer as a parameter'] += 1
                    elif len(pr['cols']) == 1 and not any(i.kind == 'SET' for i in marks):
                        gaps['one-column proposer as a choice'] += 1
                size = len(ps['props']) - 1
                out.append(dict(kind=k, sub='proposer', name=ps['name'], size=size, size_per_atom=size, ops=dict(union=size) if size else {}, one=bool(ones), live=index in small.live))
                continue
            t = small.clause_term(ps)
            ta = atom.clause_term(pa)
            rec = dict(kind=k, sub='body', name=ps['name'], size=t.size, size_per_atom=ta.size, ops=dict(term_ops(t)), one=bool(ones), flat=flat_count(ps['items']))
            if keep_terms:
                rec['term'] = t.render()
            out.append(rec)
        elif k == 'INIT':
            if ps['comp'] == 'Unfold':
                gaps['Unfold'] += 1
                continue
            if ps['comp'] == 'DemonstrationConsistency':
                gaps['DemonstrationConsistency'] += 1
                continue
            n, parts, key = small.init_query(ps)
            na, partsa, keya = atom.init_query(pa)
            ops = collections.Counter(component=n)
            size = n
            size_a = na
            bodies = []
            for (port, t), (_, ta) in zip(parts, partsa):
                size += t.size
                size_a += ta.size
                ops += term_ops(t)
                bodies.append(dict(port=port, size=t.size))
            key_size = key.size if key is not None else 0
            key_size_a = keya.size if keya is not None else 0
            size += key_size
            size_a += key_size_a
            ops += term_ops(key)
            rec = dict(kind='INIT', sub=ps['comp'], name=ps['name'], size=size, size_per_atom=size_a, ops=dict(ops), ports=n, key=key_size, bodies=bodies, flat=n + sum(flat_count(i['items']) for i in ps['inputs']))
            if keep_terms:
                rec['term'] = ['%s: %s' % (port, t.render()) for port, t in parts] + (['key: ' + key.render()] if key is not None else [])
            out.append(rec)
        elif k == 'CHOOSE':
            gaps['CHOOSE'] += 1
        elif k == 'RIGID_DET':
            gaps['RIGID_DET'] += 1
        elif k == 'OTHER':
            gaps[str(ps['head'])] += 1
        if len(out) > n_before:
            out[-1]['live'] = index in small.live
    for p in small.parsed:
        for items in small.form_items(p):
            for a in walk_atoms(items):
                if a.rel == 'pose_difference':
                    gaps['pose_difference atom'] += 1
                if any(s.col == ('Pose',) for s in a.sites):
                    gaps['Pose column read'] += 1
        if p['kind'] in ('RULE', 'DET'):
            n = constant_columns(p['items'], set())
        elif p['kind'] == 'INIT':
            n = sum(constant_columns(i['items'], set(p['key_labels'])) for i in p['inputs'])
        else:
            n = 0
        if n:
            gaps['constant-0 column'] += n
    faults = list(dict.fromkeys(small.faults + atom.faults))
    return out, gaps, faults


# ---------------------------------------------------------------- run

def concept_text(task):
    import arclog
    data = CORPUS / (task + '.arcdata')
    cases = arclog.case_files(task, read_checked(CORPUS / (task + '.arclog')), read_checked(data) if data.exists() else '', str(CORPUS))
    con = [c for c in cases if c.concept]
    if len(con) != 1 or con[0].arclog is None:
        raise ValueError('concept cases %d' % len(con))
    return con[0].case, con[0].arclog


def run(out):
    reg = Registry(REGISTRY.read_text())
    done = {json.loads(l)['task'] for l in out.read_text().splitlines()} if out.exists() else set()
    tasks = [t for t in TASKS.read_text().split() if t not in done and t not in SKIP]
    t0 = time.time()
    errors = 0
    print('tasks', len(tasks), 'already written', len(done), flush=True)
    with out.open('a') as w:
        for at, task in enumerate(tasks, 1):
            try:
                case, text = concept_text(task)
                queries, gaps, faults = queries_of(reg, text)
                rec = dict(task=task, case=case, queries=queries, gaps=dict(gaps), faults=faults)
            except Exception as e:
                errors += 1
                rec = dict(task=task, error=repr(e)[:400])
            w.write(json.dumps(rec) + '\n')
            w.flush()
            if at % 50 == 0 or at == len(tasks) or 'error' in rec:
                rate = at / (time.time() - t0)
                print('%d/%d errors %d rate %.1f/s eta %.0fs %s' % (at, len(tasks), errors, rate, (len(tasks) - at) / rate, rec.get('error', '')), flush=True)
    print('finished in %.1f s, errors %d' % (time.time() - t0, errors), flush=True)


def show(task, pat):
    reg = Registry(REGISTRY.read_text())
    case, text = concept_text(task)
    queries, gaps, faults = queries_of(reg, text, keep_terms=True)
    print('case', case)
    for q in queries:
        if pat and not re.search(pat, q['name']):
            continue
        print(q['kind'], q['sub'], q['name'], 'size', q['size'], 'per atom', q['size_per_atom'], q['ops'])
        if 'term' in q:
            print('   ', q['term'])
    print('gaps', dict(gaps))
    print('faults', faults)


# ---------------------------------------------------------------- report

def pct(x):
    return '%.1f' % (100 * x)


def report(path, field='size'):
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    good = [r for r in rows if 'error' not in r]
    print('tasks', len(rows), 'errors', [r['task'] for r in rows if 'error' in r][:10])
    faults = collections.Counter(f.split(' ')[0] + ' ' + f.split(' ')[1] for r in good for f in r['faults'])
    print('tasks with a fault', sum(1 for r in good if r['faults']), faults.most_common(10))
    ds = list(range(0, 11)) + [12, 15, 20, 30, 50]
    for fld in ('size', 'size_per_atom'):
        print('\n== field', fld)
        qs = [(r['task'], q) for r in good for q in r['queries']]
        print('queries', len(qs))
        kinds = dict(all=lambda q: True, RULE=lambda q: q['kind'] == 'RULE', DET=lambda q: q['kind'] == 'DET', DET_body=lambda q: q['kind'] == 'DET' and q['sub'] == 'body', INIT=lambda q: q['kind'] == 'INIT')
        kinds['live'] = lambda q: q['live']
        kinds['dead'] = lambda q: not q['live']
        print('kind       n     ' + ' '.join('%5d' % d for d in ds) + '   mean  p50  p90  p99  max')
        for name, f in kinds.items():
            vals = sorted(q[fld] for _, q in qs if f(q))
            line = ['%-9s %5d ' % (name, len(vals))]
            for d in ds:
                line.append('%5s' % pct(sum(1 for v in vals if v <= d) / len(vals)))
            line.append('  %5.2f %4d %4d %4d %4d' % (sum(vals) / len(vals), vals[len(vals) // 2], vals[int(len(vals) * .9)], vals[int(len(vals) * .99)], vals[-1]))
            print(' '.join(line))
        per_task = collections.defaultdict(list)
        for t, q in qs:
            per_task[t].append(q)
        for name, f in kinds.items():
            shares = []
            for d in ds:
                vals = []
                for t, ql in per_task.items():
                    sel = [q for q in ql if f(q)]
                    if sel:
                        vals.append(sum(1 for q in sel if q[fld] <= d) / len(sel))
                shares.append(sum(vals) / len(vals))
            print('mean/solver %-9s ' % name + ' '.join('%5s' % pct(s) for s in shares))
        rng = random.Random(0)
        tasks = sorted(per_task)
        table = {d: [sum(1 for q in per_task[t] if q[fld] <= d) / len(per_task[t]) for t in tasks] for d in ds}
        draws = [[rng.randrange(len(tasks)) for _ in tasks] for _ in range(1000)]
        cis = []
        for d in ds:
            means = sorted(sum(table[d][i] for i in draw) / len(draw) for draw in draws)
            cis.append('%d:[%s,%s]' % (d, pct(means[25]), pct(means[974])))
        print('bootstrap 95% interval, mean over solvers: ' + ' '.join(cis))
        largest = sorted(max(q[fld] for q in ql) for ql in per_task.values() if ql)
        n = len(largest)
        print('largest per solver: n', n, 'mean %.2f' % (sum(largest) / n), 'p10', largest[n // 10], 'p25', largest[n // 4], 'p50', largest[n // 2], 'p75', largest[3 * n // 4], 'p90', largest[9 * n // 10], 'p99', largest[99 * n // 100], 'max', largest[-1])
        print('cumulative share of solvers with largest <= d: ' + ' '.join('%d:%s' % (d, pct(sum(1 for v in largest if v <= d) / n)) for d in ds))
        hist = collections.Counter(largest)
        print('histogram', sorted(hist.items()))
    qs = [(r['task'], q) for r in good for q in r['queries']]
    total = sum(q['size'] for _, q in qs)
    sq = sorted(qs, key=lambda x: -x[1]['size'])
    print('\n== concentration: operators', total)
    for frac in (0.001, 0.01, 0.05, 0.1, 0.25):
        k = max(1, int(len(sq) * frac))
        print('top %.1f%% of queries (%d, size >= %d) hold %s%% of operators; INIT share %s%%; DET %s%%; RULE %s%%' % (100 * frac, k, sq[k - 1][1]['size'], pct(sum(q['size'] for _, q in sq[:k]) / total), pct(sum(1 for _, q in sq[:k] if q['kind'] == 'INIT') / k), pct(sum(1 for _, q in sq[:k] if q['kind'] == 'DET') / k), pct(sum(1 for _, q in sq[:k] if q['kind'] == 'RULE') / k)))
    for cut in (5, 10, 15, 20, 30):
        sel = [q for _, q in qs if q['size'] > cut]
        if not sel:
            continue
        ops = sum(q['size'] for q in sel)
        ib = sum(sum(b['size'] for b in q.get('bodies', [])) for q in sel)
        print('size > %d: %d queries, INIT %s%%, RULE %s%%, DET %s%%; input bodies hold %s%% of their operators' % (cut, len(sel), pct(sum(1 for q in sel if q['kind'] == 'INIT') / len(sel)), pct(sum(1 for q in sel if q['kind'] == 'RULE') / len(sel)), pct(sum(1 for q in sel if q['kind'] == 'DET') / len(sel)), pct(ib / ops)))
    per_task_largest = [max((q for q in r['queries']), key=lambda q: q['size']) for r in good if r['queries']]
    print('largest query of each solver by kind:', collections.Counter(q['kind'] for q in per_task_largest).most_common())
    print('largest query of each solver by name:', collections.Counter(q['name'] for q in per_task_largest).most_common(6))
    print('share of the largest query of each solver in its input bodies: %s%%' % pct(sum(sum(b['size'] for b in q.get('bodies', [])) for q in per_task_largest) / sum(q['size'] for q in per_task_largest)))
    bodies = [('input', b['size']) for _, q in qs for b in q.get('bodies', [])] + [(q['kind'], q['size']) for _, q in qs if q['kind'] != 'INIT' and q['sub'] != 'proposer']
    bodies.sort(key=lambda x: -x[1])
    for frac in (0.01, 0.05, 0.1):
        k = max(1, int(len(bodies) * frac))
        print('top %.0f%% of bodies (%d, size >= %d): input bodies %s%%' % (100 * frac, k, bodies[k - 1][1], pct(sum(1 for b in bodies[:k] if b[0] == 'input') / k)))
    print('input bodies among all bodies: %s%% of %d' % (pct(sum(1 for b in bodies if b[0] == 'input') / len(bodies)), len(bodies)))
    print('operators in INIT queries by part: component %d, input bodies %d, key %d' % (sum(q.get('ports', 0) for _, q in qs), sum(sum(b['size'] for b in q.get('bodies', [])) for _, q in qs), sum(q.get('key', 0) for _, q in qs)))
    print('operators by kind: ' + str(collections.Counter({k: sum(q['size'] for _, q in qs if q['kind'] == k) for k in ('RULE', 'DET', 'INIT')}).most_common()))
    opc = collections.Counter()
    for _, q in qs:
        opc.update(q['ops'])
    print('operators by operator: ', opc.most_common())
    print('largest queries:', [(t, q['kind'], q['name'], q['size']) for t, q in sq[:15]])
    print('components by mean size:', sorted(((c, len(v), round(sum(v) / len(v), 2), max(v)) for c, v in _group(qs).items()), key=lambda x: -x[2]))
    print('\n== gaps by kind: forms, solvers')
    forms = collections.Counter()
    solvers = collections.Counter()
    for r in good:
        for k, v in r['gaps'].items():
            forms[k] += v
            solvers[k] += 1
    for k, v in forms.most_common():
        print('%-34s forms %5d solvers %4d' % (k, v, solvers[k]))
    gapset = {'CHOOSE', 'RIGID_DET', 'Unfold', 'ONE clause', 'DEMONSTRATED', 'DemonstrationConsistency'}
    print('solvers with a CHOOSE, RIGID_DET, Unfold or ONE: %d of %d' % (sum(1 for r in good if gapset & set(r['gaps'])), len(good)))
    print('by solver:', {k: sorted(r['task'] for r in good if k in r['gaps']) for k in ('CHOOSE', 'RIGID_DET', 'Unfold', 'ONE clause')})


def _group(qs):
    out = collections.defaultdict(list)
    for _, q in qs:
        if q['kind'] == 'INIT':
            out[q['sub']].append(q['size'])
    return out


def main():
    cmd = sys.argv[1]
    if cmd == 'run':
        run(Path(sys.argv[2]))
    elif cmd == 'report':
        report(Path(sys.argv[2]))
    elif cmd == 'show':
        show(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)


if __name__ == '__main__':
    main()
