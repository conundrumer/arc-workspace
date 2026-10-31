"""Group G5, connectivity of the form: the finished clause's form and the library interfaces.

An atom makes the labels that it stars (`*V`, `^V`). Where one branch of an OR stars a label that every other branch
names, every atom of the OR that names the label makes it. The atoms that make a label are its binders. A join is a
site, in an atom other than a comparison, that names a label and does not make it.
"""
import collections as C

from featlib import feature

LIBRARY_KINDS = ('relation', 'macro')
TABLE_KINDS = ('fact', 'table', 'clause', 'port', 'output', 'x')


def _made(body):
    """{(OR path, label)}: the labels that a starred site inside an OR makes and every other branch of that OR names."""
    named = C.defaultdict(lambda: C.defaultdict(set))
    for a in body.arguments:
        if a.label is None:
            continue
        for orp, b in a.atom.branch:
            named[orp, a.label][b].add(a.binds)
    out = set()
    for (orp, label), branches in named.items():
        starred = [b for b, flags in branches.items() if True in flags]
        siblings = {b for (o, _), by in named.items() if o == orp for b in by}
        if starred and set(branches) >= siblings:
            out.add((orp, label))
    return out


def _depths(binders, reads):
    """{label: depth}: 0 where nothing makes the label, else 1 plus the greatest depth of the labels that one of its
    binders joins. Labels that depend on each other (a cycle) stand at one depth."""
    labels = set(binders)
    for deps in reads.values():
        labels |= deps
    labels |= set(reads)
    deps = {v: {w for atom in binders.get(v, ()) for w in reads.get(atom, ()) if w != v} for v in labels}
    reach = {}
    for v in labels:
        seen, todo = set(), list(deps[v])
        while todo:
            w = todo.pop()
            if w not in seen:
                seen.add(w)
                todo.extend(deps[w])
        reach[v] = seen
    cls = {v: frozenset({v} | {w for w in reach[v] if v in reach[w]}) for v in labels}
    depth = {}

    def of(v):
        c = cls[v]
        if c in depth:
            return depth[c]
        outside = {w for u in c for w in deps[u] if w not in c}
        d = 1 + max((of(w) for w in outside), default=0) if any(binders.get(u) for u in c) else 0
        depth[c] = d
        return d
    return {v: of(v) for v in labels}


@feature
def g5_connect(p):
    """G5 connectivity of the form. `comps`: connected components of the graph whose nodes are the atoms that name a
    label, two atoms being joined when they share a label; `isolated`: atoms with sites and no label; `parts`:
    comps + isolated; `extra`: parts above 1 (a form with extra parts is a product of independent factors). `joins`:
    the join sites. Over the joins: `mean_depth` and `max_depth` of the joined label (0 where nothing makes it, else 1
    plus the greatest depth of the labels that a binder of it joins), `lib`, the share whose label a library
    relation or macro makes, and `table`, the share whose label a fact or a table read makes (the depth and share keys
    are absent without a join). None without atoms. A later atom can join two parts or deepen a join.

    Needs: full. Monotone: no.
    """
    body = p.clause.body
    if body is None or not body.atoms:
        return None
    atoms = body.atoms
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    owner = {}
    isolated = 0
    for at in atoms:
        labels = {a.label for a in at.arguments if a.label is not None}
        if not labels:
            isolated += bool(at.arguments)
            continue
        parent[id(at)] = id(at)
        for lab in labels:
            if lab in owner:
                parent[find(id(at))] = find(owner[lab])
            else:
                owner[lab] = id(at)
    comps = len({find(i) for i in parent})
    parts = comps + isolated
    out = {'comps': comps, 'isolated': isolated, 'parts': parts, 'extra': max(parts - 1, 0)}
    made = _made(body)
    makes = lambda a: a.label is not None and (a.binds or any((orp, a.label) in made for orp, _ in a.atom.branch))
    binders = C.defaultdict(list)
    for a in body.arguments:
        if makes(a) and a.atom not in binders[a.label]:
            binders[a.label].append(a.atom)
    reads = {at: {a.label for a in at.arguments if a.label is not None and not makes(a)}
             for at in atoms if not at.operator}
    depth = _depths(binders, reads)
    joined = [a for at in reads for a in at.arguments if a.label is not None and not makes(a)]
    out['joins'] = len(joined)
    if joined:
        n = len(joined)
        ds = [depth[a.label] for a in joined]
        out['mean_depth'] = sum(ds) / n
        out['max_depth'] = max(ds)
        out['lib'] = sum(any(b.kind in LIBRARY_KINDS for b in binders[a.label]) for a in joined) / n
        out['table'] = sum(any(b.kind in TABLE_KINDS for b in binders[a.label]) for a in joined) / n
    return out
