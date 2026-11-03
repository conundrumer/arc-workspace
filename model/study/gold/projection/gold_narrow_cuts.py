"""Projection helpers for an INIT: candidates for the DAG split stage (gold_dagcut2_one.py) in place of gold_dag_cuts.dag_candidates.

  narrow_candidates(lines, i, bits) gives Split(shape, forms, atoms, sites, est, rank) for the INIT at lines[i]; any other form gives [].

A body of the INIT (its key body, a port body or a broadcast input) is narrowable when it is one atom that reads a RULE relation R and either
  - has a dead site: a fresh label `*X` that no other place of its clause names (for the key body: the key body; for a port: its head and body), or
  - names fewer columns than R has, once its dead sites are gone.
The rewrite drops the dead sites, and where R still has columns that the atom does not name, puts in a RULE that projects R onto the named
columns, `(RULE &wcK (R (:C *C) ...))`, and the atom reads that RULE with the same sites. Atoms that read one R at one column set share one RULE.
R's columns are the labels of its clause, for a body with no OR, IF or ALL; a body with one of those is not read here, and its readers are left as they are.

Shapes, in rank order:
  narrow-all    every narrowable body of the INIT
  dead-only     the dead sites dropped, no projection
  narrow-body   one narrowable body alone (only where the INIT has 2 or more)
"""
import collections, re

from gold_chain import parse, show
from gold_orcut_cuts import Fresh
from gold_dag_cuts import Split

LABEL = re.compile(r'^[*^]?[A-Z][A-Za-z0-9_]*$')
GROUPS = ('OR', 'IF', 'ALL')


def labels(x, out):
    """Every label token in x, with its mark: the elements after a list's head that look like labels, at any depth."""
    if isinstance(x, list):
        for k, y in enumerate(x):
            if isinstance(y, list):
                labels(y, out)
            elif k > 0 and LABEL.match(y):
                out.append(y)
    return out


def bare(t):
    return t.lstrip('*^')


def rule_columns(form):
    """The columns of a RULE form (parsed), in order of first naming; None for a body with OR, IF or ALL."""
    if form[0] != 'RULE' or any(isinstance(a, list) and a and a[0] in GROUPS for a in form[2:]):
        return None
    return list(dict.fromkeys(bare(t) for t in labels(form[2:], [])))


def sites(atom):
    """(column, label token, index in atom) of each one-label site: `(:C L)` or an elided `L`."""
    out = []
    for k, y in enumerate(atom[1:], 1):
        if isinstance(y, str) and LABEL.match(y):
            out.append((bare(y), y, k))
        elif isinstance(y, list) and len(y) == 2 and isinstance(y[0], str) and y[0].startswith(':') and isinstance(y[1], str):
            out.append((y[0][1:], y[1], k))
    return out


def bodies(f):
    """(where, body list, other labels of the clause, container, offset) for each body of INIT f: the key body, then each input. Atom k of
    the body is container[offset + k], so an edit of the container edits f."""
    for y in f[3:]:
        if not isinstance(y, list) or not y:
            continue
        if y[0] == 'key':
            yield 'key', y[1], [], y[1], 0
            for z in y[2:]:
                yield 'port', z[2:], labels(z[1], []), z, 2
        else:
            yield 'port', y[2:], labels(y[1], []), y, 2


def narrow_candidates(ls, i, bits=None):
    if not ls[i].startswith('(INIT'):
        return []
    f = parse(ls[i])
    rules = {}
    for x in ls:
        if x.startswith('(RULE'):
            g = parse(x)
            rules[g[1]] = rule_columns(g)
    plans = []  # (body number, atom index in body, dead site indexes, named columns or None, relation)
    for n_body, (where, body, other, _, _) in enumerate(bodies(f)):
        atoms = [k for k, a in enumerate(body) if isinstance(a, list)]
        if len(atoms) != 1:
            continue
        a = body[atoms[0]]
        rel = a[0] if isinstance(a[0], str) else None
        cols = rules.get(rel)
        if not cols:
            continue
        named = collections.Counter(bare(t) for t in labels(body, []) + other)
        ss = sites(a)
        dead = [k for c, t, k in ss if t.startswith('*') and named[bare(t)] == 1]
        keep = [c for c, t, k in ss if k not in dead]
        if any(c not in cols for c in keep):  # a site on a column that the clause of R does not show: R's columns are not read right here
            continue
        proj = keep if set(keep) != set(cols) else None
        if dead or proj is not None:
            plans.append((n_body, atoms[0], dead, proj, rel))
    if not plans:
        return []
    fresh = Fresh(ls)

    def make(chosen, project):
        g = parse(ls[i])
        bs = [(c, o) for _, _, _, c, o in bodies(g)]
        helpers, made = {}, []
        for n_body, k, dead, proj, rel in chosen:
            nb, off = bs[n_body]
            a = nb[off + k]
            a = [y for n, y in enumerate(a) if n not in dead]
            if project and proj is not None:
                key = (rel, tuple(sorted(proj)))
                if key not in helpers:
                    name = fresh()
                    order = [c for c in rules[rel] if c in proj]
                    helpers[key] = name
                    made.append('(RULE %s (%s %s))' % (name, rel, ' '.join('(:%s *%s)' % (c, c) for c in order)))
                a[0] = helpers[key]
            nb[off + k] = a
        return made + [show(g)]

    out = [Split('narrow-all', make(plans, True), tuple(range(len(plans))), tuple(sorted({c for p in plans for c in (p[3] or ())})), None, 0)]
    if any(p[2] for p in plans) and any(p[3] is not None for p in plans):
        out.append(Split('dead-only', make([p for p in plans if p[2]], False), (), (), None, len(out)))
    if len(plans) > 1:
        for n, p in enumerate(plans):
            out.append(Split('narrow-body', make([p], True), (n,), tuple(p[3] or ()), None, len(out)))
    seen, uniq = set(), []
    for s in out:
        t = re.sub(r'&wc\d+', '&w', '\n'.join(s.forms))
        if t not in seen and s.forms[-1] != ls[i]:
            seen.add(t)
            uniq.append(s._replace(rank=len(uniq)))
    return uniq
