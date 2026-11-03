"""Candidate cuts of one form of a program over its body as a DAG. Pure text: nothing here runs the engine.

  splits(lines, i, bits) gives Split(shape, forms, atoms, sites, est, rank) for the RULE or DET at lines[i]: a helper that takes any subset of the atoms before the first ONE or SET, whose bindings close, and the form that reads it. Written order plays no part: the bits of a form sum over its atom orders (gold_dag_bits.py), so one text stands for the chain cut and the chain-tail cut of every written order.
  dag_candidates(lines, i, bits) gives the splits, then the other shapes of gold_shapecut_cuts.all_candidates with chain, chain-tail and chain-tail+carry left out. An INIT takes those other shapes only.

A split of the atoms A (the helper's) and B (the rest, the marks ONE and SET among them):
  1. A is connected in the join graph (an edge where two atoms share a label), and at least one movable atom stays in B. A subset with no join is the shape split-groups.
  2. A is ordered by taking, one at a time, an atom that leaves needs(current + [atom]) empty.
  3. If no such order exists, A needs a label from outside. take = carried(B, A) gives the atoms of B that bind it. Their projections lead the helper's body, and the atoms stay in the form as well. Shape dag-carry. With take None, A has no cut.
  4. Otherwise the helper body is closed(A). Shape dag-split.
  5. sites are the labels of the body that B or a later form reads. No sites, no cut. A body that is one read of a derived relation (alias) is no cut.
  6. The form is the read, then B with the marks of the sites' labels removed. The read goes first, so that the modes of B have their inputs.
  7. The helper stands on the line before the form, named by Fresh.
A body of at most EXACT_ATOMS movable atoms takes every subset. A larger body takes the connected subsets that grow by breadth from each atom, RAW_CAP of them at most, with atoms in sorted-text order. SPLIT_CAP splits per form go on, in the order of est: the tokens of each side times the form's bits, and SITE_BITS for each site on the form's side, then the count of sites, then the text of A.
"""
import collections, itertools, re
from gold_chain import parse, reads, show
from gold_orcut_cuts import Fresh, alias, carried, closed, flatten, helper_kind, labels, made, needs, plain, project, read, rule
import gold_shapecut_cuts as SC
from gold_dag_orders import Body

RAW_CAP, SPLIT_CAP, EXACT_ATOMS, SITE_BITS = 4096, 64, 12, 2.0
CHAIN_SHAPES = ('chain', 'chain-tail', 'chain-tail+carry')
Split = collections.namedtuple('Split', 'shape forms atoms sites est rank')
TOKEN = re.compile(r'\(|\)|[^\s()]+')


def tokens(atoms):
    return sum(len(TOKEN.findall(show(a))) for a in atoms)


def key(atom):
    return show(plain(atom))


def unstar(x, names):
    """A copy of x with the star or caret of each label in names removed."""
    if isinstance(x, list):
        return [unstar(y, names) for y in x]
    return x[1:] if isinstance(x, str) and len(x) > 1 and x[0] in '*^' and x[1:] in names else x


def first_marks(atoms):
    """atoms with the mark of each label that they bind moved to the label's first occurrence in their order. The order of a helper's body is not the written one, so a mark may stand after a use."""
    return Body(list(atoms)).reordered(tuple(range(len(atoms))))


def ordered(a):
    """The atoms a in an order whose every prefix needs nothing from outside, and whether there is one. Atoms go by sorted text, so that the order reads no written place. Where there is none, the atoms taken so far, then the rest by text."""
    left = sorted(range(len(a)), key=lambda j: key(a[j]))
    cur = []
    while left:
        for j in left:
            if not needs(cur + [a[j]]):
                cur.append(a[j])
                left.remove(j)
                break
        else:
            return cur + [a[j] for j in left], False
    return cur, True


def split_text(kind, head, atoms, A, keep):
    """(shape, helper body, B with its marks removed, sites) of the split with atoms A (a set of indexes), or None."""
    a = [atoms[j] for j in sorted(A)]
    B = [x for j, x in enumerate(atoms) if j not in A]
    a, ok = ordered(a)
    a = first_marks(a)
    if ok:
        shape, body = 'dag-split', closed(a)
    else:
        take = carried(B, a)
        if take is None:
            return None
        need = needs(a)
        counts = [l for j in take for l in labels(B[j])]
        want = set(labels(a)) | need | {l for l in counts if counts.count(l) > 1}
        front = [project(B[j], want) for j in take]
        if needs(front + a):
            return None
        shape, body = 'dag-carry', closed(first_marks(front + a))
    if body is None or alias(body):
        return None
    later = set(labels(B)) | keep
    sites = [l for l in labels(body) if l in later]
    if not sites:
        return None
    return shape, body, [unstar(x, set(sites)) for x in B], sites, a


def subsets(atoms, n):
    """The index sets that the join graph and the cap leave: connected, with at least one movable atom outside."""
    labs = [set(labels(atoms[j])) for j in range(n)]
    near = [{k for k in range(n) if k != j and labs[j] & labs[k]} for j in range(n)]
    by = sorted(range(n), key=lambda j: (key(atoms[j]), j))
    if n <= EXACT_ATOMS:
        for mask in range(1, (1 << n) - 1):
            A = {j for j in range(n) if mask >> j & 1}
            seen, todo = set(), [next(iter(A))]
            while todo:
                j = todo.pop()
                if j not in seen:
                    seen.add(j)
                    todo += [k for k in near[j] if k in A]
            if seen == A:
                yield frozenset(A)
        return
    seen, queue, count = set(), collections.deque(frozenset([j]) for j in by), 0
    while queue and count < RAW_CAP:
        A = queue.popleft()
        if A in seen or len(A) >= n:
            continue
        seen.add(A)
        count += 1
        yield A
        for k in sorted({k for j in A for k in near[j]} - A, key=lambda k: (key(atoms[k]), k)):
            queue.append(A | {k})


def splits(ls, i, bits):
    """The splits of the RULE or DET at ls[i], best estimate first, at most SPLIT_CAP. bits is the form's bits."""
    if not ls[i].startswith(('(RULE', '(DET')):
        return []
    f = parse(ls[i])
    kind, head, atoms = f[0], f[1], f[2:]
    if not atoms or any(not isinstance(a, list) for a in atoms):
        return []
    n = next((k for k, a in enumerate(atoms) if a[0] in ('ONE', 'SET')), len(atoms))
    if n < 2 or (len(atoms) == 1 and atoms[0][0] == 'OR'):
        return []
    keep = reads(ls[i + 1:], head)
    total = max(1, tokens(atoms))
    got, seen = [], set()
    for A in subsets(atoms, n):
        try:
            made_ = split_text(kind, head, atoms, A, keep)
        except (IndexError, ValueError, StopIteration, TypeError, KeyError):
            continue
        if made_ is None:
            continue
        shape, body, B2, sites, a = made_
        name = Fresh(ls)()
        forms = [rule(helper_kind(body, kind), name, body), rule(kind, head, [read(name, [(l, '*' + l) for l in sites])] + B2)]
        text = re.sub(r'&wc\d+', '&w', '\n'.join(forms))
        if text in seen:
            continue
        seen.add(text)
        b = bits if isinstance(bits, (int, float)) else 0.0
        est_a = b * tokens(body) / total
        est_b = b * tokens([x for j, x in enumerate(atoms) if j not in A]) / total + SITE_BITS * len(sites)
        got.append((Split(shape, forms, tuple(sorted(A)), tuple(sites), round(max(est_a, est_b), 3), None), [key(x) for x in a]))
    got.sort(key=lambda g: (g[0].est, len(g[0].sites), g[1]))
    got = [g[0] for g in got]
    return [s._replace(rank=r) for r, s in enumerate(got[:SPLIT_CAP])]


def dag_candidates(ls, i, bits):
    """The splits of ls[i], then its other shapes. A cut of another shape has rank None."""
    out = list(splits(ls, i, bits))
    seen = {re.sub(r'&wc\d+', '&w', '\n'.join(c.forms)) for c in out}
    for c in SC.all_candidates(ls, i):
        if c.shape in CHAIN_SHAPES:
            continue
        t = re.sub(r'&wc\d+', '&w', '\n'.join(c.forms))
        if t not in seen:
            seen.add(t)
            out.append(Split(c.shape, c.forms, None, None, None, None))
    return out
