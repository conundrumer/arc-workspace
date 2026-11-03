"""Keys of a relation option on a body read as a DAG: the copy of features_perrel_keys.py for the DAG conversion (item 8).

A scope is a list of form texts. `ScopeKeys(scope_texts, counts)` maps the content key of a form (the `D:<content key>.<port>` of an option) to the form, and gives the option's (family, component, relation) key.
Changes against features_perrel_keys.py:
  - `root` of a RULE or DET body is the rarest head of its relation atoms, by `HEAD_COUNTS` (counts on the fit forms), ties by name, in place of the first atom. `body_head` and `ATOM.match` are gone.
    A head is a lib relation, or a component port (`Comp.port`) for an atom that reads an INIT form. An atom that reads a RULE or DET form counts only where the body has no other head, and then it gives that form's root.
  - There is no slot map (`slots`): the content key names the form, and the port suffix of an option is the relation index.
  - The text of the scope is read as a set: no function here reads a line's position, a body's atom order, or a mark.
"""
import collections
import json
import os
import re

import features_dag_order as D

R = '/Users/davidlu/code/arc-workspace/'
NAME = re.compile(r'&r\d+')
RN = re.compile(r'&f(\d+)')
HEADNAME = re.compile(r'^\((?:\w+) (&r\d+)')
PROPOSER = re.compile(r'\(\w+ &r\d+ ([A-Za-z]\w*)\)\s*$')
HEAD = re.compile(r'\((?:NOT \()?([^\s()]+)')
DOC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/sampler-wt-d1c0f40e6/docs/study-library-meanings.source.md'  # the pin's copy
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37/'  # the data folder
COUNTS_PATH = HERE + 'scratch/head-counts.json'
HEAD_COUNTS: dict = {}


def rn(x):
    """A pool form's name &fN reads as &r(1000000+N)."""
    return RN.sub(lambda m: '&r%d' % (1000000 + int(m[1])), x)


def lib_sections():
    """{relation: the section of the lib doc that lists it}."""
    out, sec = {}, None
    for x in open(DOC, encoding='utf8'):
        m = re.match(r'## (.+)', x)
        if m:
            sec = m[1].strip().lower().replace(' ', '-')
        m = re.match(r'- `([a-z_0-9]+)\(', x)
        if m and sec:
            out.setdefault(m[1], sec)
    return out


def load_counts(rebuild=False):
    """Counts of heads over the relation atoms of the RULE and DET bodies of the fit tasks' gold. Cached in scratch/head-counts.json."""
    if HEAD_COUNTS and not rebuild:
        return HEAD_COUNTS
    if os.path.exists(COUNTS_PATH) and not rebuild:
        HEAD_COUNTS.update(json.load(open(COUNTS_PATH)))
        return HEAD_COUNTS
    import features_dagc_lib as L
    c = collections.Counter()
    for t, lines in L.fit_gold().items():
        f = Forms(lines)
        for i in sorted(f.info):
            if f.info[i][0] in ('RULE', 'DET'):
                for h in f.atom_heads(i):
                    r = f.resolve_head(h, plain=True)
                    if r:
                        c[r] += 1
    HEAD_COUNTS.update(c)
    os.makedirs(os.path.dirname(COUNTS_PATH), exist_ok=True)
    json.dump(dict(c), open(COUNTS_PATH, 'w'), sort_keys=True)
    return HEAD_COUNTS


class Forms:
    """One scope's forms (texts, with &fN already read as &rN). The functions read the set of forms."""

    def __init__(self, lines):
        self.lines = list(lines)
        self.head = {}  # &rN -> line index
        self.info = {}  # line -> (kind, 'proposer'/None, component)
        self.dags = {}
        for i, x in enumerate(self.lines):
            m = HEADNAME.match(x.strip())
            if m:
                self.head[m[1]] = i
                self.info[i] = self.form_info(x)

    @staticmethod
    def form_info(line):
        w = line.split()
        kind = w[0].lstrip('(')
        if kind in ('INIT', 'RIGID_DET'):
            return kind, None, w[2].rstrip(')') if kind == 'INIT' else 'rigid'
        m = PROPOSER.match(line.strip())
        if m:
            return 'PROPOSER', None, m[1]
        return kind, None, None

    def dag(self, i):
        if i not in self.dags:
            self.dags[i] = D.FormDag(self.lines[i])
        return self.dags[i]

    def atom_heads(self, i):
        """The head of each positive relation atom of form i (any body, any OR branch or ALL), as a set of texts with the port suffix."""
        return sorted({a.tree[0] for a in self.dag(i).atoms.values() if a.kind == 'rel' and isinstance(a.tree[0], str)})

    def resolve_head(self, h, plain=False, seen=()):
        """A head's relation: a lib relation is itself, `&rN.port` of an INIT form is Comp.port, of a RIGID_DET form is rigid.r, of a RULE or DET form its root. With plain, None for the last."""
        if not h.startswith('&'):
            return h
        base, _, port = h.partition('.')
        i = self.head.get(base)
        if i is None:
            return None if plain else 'derived-unknown'
        kind, _p, comp = self.info[i]
        if kind == 'INIT':
            return comp + '.' + port
        if kind == 'RIGID_DET':
            return 'rigid.r'
        if kind == 'PROPOSER':
            return comp
        return None if plain else self.root(i, seen + (i,))

    def root(self, line, seen=()):
        """The rarest head in the body of form `line`, followed through RULE and DET forms where no other head exists."""
        kind, _p, comp = self.info[line]
        if comp is not None:
            return comp
        counts = load_counts()
        heads = self.atom_heads(line)
        plain = {self.resolve_head(h, plain=True) for h in heads} - {None}
        if not plain:
            rest = {self.resolve_head(h, seen=seen) for h in heads if self.head.get(h.partition('.')[0]) not in seen}
            plain = rest - {None, 'derived-unknown', 'none'}
        if not plain:
            return 'none'
        return min(plain, key=lambda r: (counts.get(r, 0), r))

    def key(self, line, j, ports):
        """(family, component, relation) of relation j of the form at line."""
        kind, _p, comp = self.info[line]
        if kind in ('INIT', 'RIGID_DET'):
            p = ports.get((comp, j), str(j)) if kind == 'INIT' else 'r%d' % j
            return 'derived-' + kind.lower(), comp, comp + '.' + p
        if kind == 'PROPOSER':
            return 'derived-proposer', comp, comp
        r = self.root(line)
        return 'derived-' + kind.lower(), 'body:' + r, kind.lower() + ':' + r


class ScopeKeys:
    """The keys of the options of picks over one scope (a list of form texts). `content[name]` is the content key of a form, as the walker's ProgramDag gives it."""

    def __init__(self, scope, sections, ports):
        self.sections, self.ports = sections, ports
        self.cp = D.ProgramDag(list(scope))
        self.f = Forms([rn(x) for x in scope])
        by_text = {}
        for x in scope:
            t = D.parse(x)
            by_text[self.cp.content['OUT' if t[0] == 'OUT' else t[1]]] = x
        self.line_of = {}
        for i, x in enumerate(scope):
            t = D.parse(x)
            self.line_of.setdefault(self.cp.content['OUT' if t[0] == 'OUT' else t[1]], i)
        self.cache = {}

    def lib(self, name, kind):
        if kind in ('NOT', 'CMP'):
            return 'op', 'op:' + name, 'op:' + name
        s = self.sections.get(name)
        if kind == 'fact relation':
            return 'facts', 'fact:' + name, name
        if s is None:
            s = 'macro' if kind == 'relation macro' else 'lib-other'
        return 'lib-' + s, 'lib:' + name, name

    def derived(self, name):
        """Key of an option `D:<content key>[.<index>]`: (family, component, relation)."""
        got = self.cache.get(name)
        if got is not None:
            return got
        body = name[2:]
        ck, _, idx = body.partition('.')
        L = self.line_of.get(ck)
        if L is None or L not in self.f.info:
            got = ('derived-unknown',) * 3
        else:
            got = self.f.key(L, int(idx) if idx.isdigit() else 0, self.ports)
        self.cache[name] = got
        return got

    def form_line(self, name):
        ck = name[2:].partition('.')[0]
        return self.line_of.get(ck)

    def text_head(self, h):
        """The relation key of a head in an atom's text, where &rN is the scope's written name (names stand for forms of the scope; the name is no order)."""
        if not h.startswith('&'):
            return h
        base, _, port = h.partition('.')
        L = self.f.head.get(base)
        if L is None:
            return 'derived-unknown'
        kind, _h, comp = self.f.info[L]
        if kind in ('INIT', 'RIGID_DET'):
            return comp + '.' + (port if kind == 'INIT' else 'r')
        return self.f.key(L, 0, self.ports)[2]

    def atom_head(self, key_text):
        """The relation key of the head of an atom key (an id's text after `|`): a NOT reads its inner atom."""
        m = HEAD.match(key_text)
        return None if m is None else self.text_head(m[1])
