"""Model input layer: features of a query's own structure, from the case program's text.

Each table's query is the form that defines it: a relation's RULE or DET clause, or an instance output's INIT form (with the output's port).
"""
import re
from collections import Counter
from functools import cache
from pathlib import Path

KEYWORDS = {'RULE', 'DET', 'DET_OR_RULE', 'RULE_OR_DET', 'INIT', 'RIGID_DET', 'CHOOSE', 'OR', 'IF', 'ALL', 'NOT', 'key', 'ONE', 'SET',
            'INPUT', 'OUTPUT', 'ALTS', 'ALT', 'OUT', 'APPROXIMATED'}
FACTS = {'input', 'ex_input', 'ex_output'}
import paths  # noqa: E402

REGISTRY = paths.REGISTRY


def parse(text):
    """The top-level forms of text as nested lists of tokens."""
    toks = re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+', re.sub(r';[^\n]*', '', text))
    stack, out = [[]], None
    for t in toks:
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop()
            stack[-1].append(x)
        else:
            stack[-1].append(t)
    return stack[0]


def atoms(x, ports=frozenset()):
    """Heads of the atoms in x (lists whose head is a relation name), skipping site lists and INIT port lists."""
    out = []
    if not isinstance(x, list) or not x:
        return out
    h = x[0]
    if not isinstance(h, str):
        for y in x:
            out += atoms(y, ports)
        return out
    if not h.startswith(':') and h not in KEYWORDS and h not in ports and not h.startswith('"') and h != '=' and h[0] not in '<>!':
        out.append(h)
    for y in x[1:]:
        out += atoms(y, ports)
    if isinstance(h, str) and h in ('OR', 'IF', 'ALL', 'NOT'):
        out.append(h)
    return out


def walk(x):
    """Every list in x, x included."""
    if isinstance(x, list):
        yield x
        for y in x:
            yield from walk(y)


def query_features(text):
    """{form name: {feature: value}} for every RULE, DET and INIT form of text."""
    out = {}
    forms = []
    for f in parse(text):
        if isinstance(f, list) and f and f[0] in ('INPUT', 'OUTPUT'):
            forms += [g for g in f[3:] if isinstance(g, list)]
        else:
            forms.append(f)
    for f in forms:
        if not (isinstance(f, list) and len(f) >= 2 and f[0] in ('RULE', 'DET', 'DET_OR_RULE', 'RULE_OR_DET', 'INIT', 'RIGID_DET', 'CHOOSE')):
            continue
        kind, name = f[0], f[1]
        q = {'kind': kind}
        body = f[2:]
        ports = set()
        if kind == 'INIT':
            q['component'] = body[0] if body else None
            for part in body[1:]:
                if isinstance(part, list) and part:
                    ports.add(part[0])
                    if part[0] == 'key':
                        ports |= {p[0] for p in part[2:] if isinstance(p, list) and p}
            q['inputs written'] = sorted(p for p in ports if p != 'key')
            q['keyed'] = 'key' in ports
        # a bare name in the body of a form other than INIT is a proposer, not an atom
        heads = atoms(body if kind == 'INIT' else [b for b in body if isinstance(b, list)], frozenset(ports) | ({body[0]} if kind == 'INIT' and body else set()))
        c = Counter(heads)
        q['atoms'] = sum(n for h, n in c.items() if h not in ('OR', 'IF', 'ALL', 'NOT'))
        q['negations'] = c['NOT']
        q['control forms'] = c['OR'] + c['IF'] + c['ALL']
        q['facts read'] = sorted(h for h in c if h in FACTS)
        q['derived reads'] = len({h for h in c if h.startswith('&')})
        q['lib relations'] = sorted(h for h in c if h[0].islower() and h not in FACTS and not h.startswith('&'))
        lists = [l for l in walk(body) if l and isinstance(l[0], str)]
        q['equalities'] = sum(l[0] == '=' for l in lists)
        q['inequalities'] = sum(l[0] == '!=' for l in lists)
        q['order comparisons'] = sum(l[0] in ('<', '<=', '>', '>=') for l in lists)
        q['zero sites'] = sum(len(l) == 2 and l[0].startswith(':') and l[1] == '0' for l in lists) + sum(l[0] == '=' and len(l) == 3 and l[2] == '0' for l in lists)
        q['fresh labels'] = sum(isinstance(t, str) and t.startswith('*') for l in lists for t in l)
        q['proposer'] = next((b for b in body if isinstance(b, str) and b[0].isupper()), None) if kind in ('DET', 'DET_OR_RULE', 'RULE_OR_DET', 'RULE') else None
        out[name] = q
    return out


@cache
def component_inputs():
    """{component: set of its input ports}, from the lib registry."""
    out = {}
    for f in parse(REGISTRY.read_text()):
        if isinstance(f, list) and len(f) > 1 and f[0] == 'component':
            ins = next((g for g in f if isinstance(g, list) and g and g[0] == 'inputs'), [])
            out[f[1]] = {p[0] for p in ins[1:] if isinstance(p, list) and p}
    return out


def of_table(qf, table):
    """The query features of a table: its form's, plus, for a table of an instance, the port and whether the port is an input of the
    component."""
    node, _, port = table.partition('.')
    q = dict(qf.get(node, {}))
    if port:
        q['port'] = port
        q['instance input'] = port in component_inputs().get(q.get('component'), ())
    return q
