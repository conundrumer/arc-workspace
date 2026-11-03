"""Keys of a relation option, read from the form that the search has at the pick.

The search has, at a pick, the text of each form in scope and the option's token. A key never reads the target form or gold's pick.

  Forms(lines, kept)        the slot of each scope form, so a walk's token &rN maps to (form line, relation index of that form)
  Forms.key(tok)            the option's derived keys: (family, component, relation)

Keys of a derived option:
  an INIT or RIGID_DET form's relation   family init:     component = the component's name     relation = component.port
  a DET form that is a proposer alone    family proposer: component = the proposer's name      relation = the same
  a RULE or DET form with a body         family rule:     component = root of its body         relation = root + the first atom's count of columns read
  The root of a body is the head of its first atom, followed through derived heads to a lib relation or a component's port.
"""
import json
import re

R = '/Users/davidlu/code/arc-workspace/'
NAME = re.compile(r'&r\d+')
HEADNAME = re.compile(r'^\((?:\w+) (&r\d+)')
ATOM = re.compile(r'\((?:NOT \()?([^\s()]+)')
DOC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/sampler-wt-d1c0f40e6/docs/study-library-meanings.source.md'  # the pin's copy


def parents(lines, i):
    """The indexes before i of the forms that line i reads, directly or not, in order. Equal to live_rows.parents."""
    head = {NAME.search(x)[0]: j for j, x in enumerate(lines) if NAME.search(x)}
    got, todo = set(), [i]
    while todo:
        for n in NAME.findall(lines[todo.pop()]):
            j = head.get(n)
            if j is not None and j < i and j not in got:
                got.add(j)
                todo.append(j)
    return sorted(got)


def lib_sections():
    """{relation: the section of the lib doc that lists it}: the stand-in for a concept that a pick can observe."""
    out, sec = {}, None
    for x in open(DOC, encoding='utf8'):
        m = re.match(r'## (.+)', x)
        if m:
            sec = m[1].strip().lower().replace(' ', '-')
        m = re.match(r'- `([a-z_0-9]+)\(', x)
        if m and sec:
            out.setdefault(m[1], sec)
    return out


def body_head(line):
    """The text of the first body atom's head, the kind of the form, and its component where it has one."""
    w = line.split()
    kind = w[0].lstrip('(')
    if kind in ('INIT', 'RIGID_DET'):
        return kind, None, w[2].rstrip(')') if kind == 'INIT' else 'rigid'
    m = re.match(r'\(\w+ &r\d+ ([A-Za-z]\w*)\)\s*$', line.strip())
    if m:  # a proposer alone
        return 'PROPOSER', None, m[1]
    rest = line.split(None, 2)[2] if len(w) > 2 else ''
    if rest.startswith('(OR'):
        return kind, 'OR', None
    a = ATOM.match(rest)
    return kind, a[1] if a else None, None


class Forms:
    """One task's forms, and the slots of the kept forms in the order of the decoded program."""

    def __init__(self, lines):
        self.lines = lines
        self.head = {}  # gold's &rN -> line
        self.num = {}  # line -> N
        self.info = {}
        for i, x in enumerate(lines):
            m = HEADNAME.match(x.strip())
            if m:
                self.head[m[1]] = i
                self.num[i] = int(m[1][2:])
                self.info[i] = body_head(x)
        order = sorted(self.num)
        self.count = {i: (self.num[order[n + 1]] - self.num[i] if n + 1 < len(order) else 1) for n, i in enumerate(order)}

    def slots(self, kept):
        """{decoded slot number: (line, relation index)} for the kept lines."""
        out, s = {}, 0
        for i in kept:
            if i not in self.num:
                continue
            for j in range(self.count[i]):
                out[s + j] = (i, j)
            s += self.count[i]
        return out, s

    def root(self, line, seen=()):
        """The lib relation or component port at the root of a form's body, through the first atoms."""
        kind, head, comp = self.info[line]
        if comp is not None:
            return comp
        if head is None:
            return 'none'
        if head == 'OR':
            return 'OR'
        if not head.startswith('&'):
            return head
        base, _, port = head.partition('.')
        i = self.head.get(base)
        if i is None or i in seen:
            return 'none'
        r = self.root(i, seen + (line,))
        return r + '.' + port if port and '.' not in r else r

    def key(self, line, j, ports):
        """(family, component, relation) of relation j of the form at line."""
        kind, head, comp = self.info[line]
        if kind in ('INIT', 'RIGID_DET'):
            p = ports.get((comp, j), str(j)) if kind == 'INIT' else 'r%d' % j
            return 'derived-' + kind.lower(), comp, comp + '.' + p
        if kind == 'PROPOSER':
            return 'derived-proposer', comp, comp
        r = self.root(line)
        return 'derived-' + kind.lower(), 'body:' + r, kind.lower() + ':' + r


def load_ports(path):
    return {(a, int(b)): c for a, b, c in json.load(open(path))}
