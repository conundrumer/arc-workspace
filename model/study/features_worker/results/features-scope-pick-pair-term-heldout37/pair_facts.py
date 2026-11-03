"""Pair facts of a scope. They read only what the search has at the draw: the forms' text and reads, and their tables on the task's own data. No gold and no cover enters.

A sketch of one relation is dict(types, cols), one entry of cols per column. An entry maps an example to (distinct values, the smallest K hashes of those values, sorted, as bytes of uint32). A column's value is its cells in a row, 1 int, or 4 for Position, Box and Offset. Rows of all DET assignments of an example are put together. A table with no rows on an example has no entry for it. The example (0, 0) is a task-level table, as a DET's: it counts on every example of the other relation.

Examples compared: the train inputs and the test inputs, which the search has. On the sets of two columns, with sketches of K or fewer values, a count is exact; above K it is the bottom-k estimate.

Facts of a pair of relations a, b:
  coltype   Jaccard of the sets of column types. No table is read.
  ident     1 where each has a column of type Ident. No table is read.
  join      share of compared examples on which a pair of columns of one type has 2 or more values in common. One value in common is a constant filter, not a join.
  overlap   per example and shared column type, the largest Jaccard of the value sets over the column pairs of that type; mean over shared types; mean over examples.
  overlap_P, overlap_C, overlap_N, overlap_I, overlap_O   overlap on one type group: Position; Color; Nat and Int; Ident; the others.
  lineage   1 where the two forms share an ancestor form. A control, not a table fact.

Examples compared for a pair: those where both have rows. With none, join and the overlaps are 0.

A form can have several relations: a fact of a form pair is the largest over its relation pairs.

Facts of a scope: over the pairs of its leaf forms (forms no scope form reads), f_mean and f_max. A leaf pair has no read edge in either direction, since a scope holds all ancestors of its forms. A scope with fewer than 2 leaf forms has no pair facts.
"""
import array
import itertools

K = 64
FACTS = ('coltype', 'ident', 'join', 'overlap', 'overlap_P', 'overlap_C', 'overlap_N', 'overlap_I', 'overlap_O', 'lineage')
MASK = (1 << 64) - 1
GROUP = dict(Position='P', Color='C', Nat='N', Int='N', Ident='I')


def mix(v):
    x = (hash(v) * 0x9E3779B97F4A7C15) & MASK
    x ^= x >> 29
    x = (x * 0xBF58476D1CE4E5B9) & MASK
    return (x ^ (x >> 32)) & 0xffffffff


def sketch_table(tb):
    """The sketch of a table of sample2_col.parse_table."""
    types = [str(t) for t in tb['types']]
    spans, at = [], 0
    for w in tb['widths']:
        spans.append((at, at + w))
        at += w
    vals = [{} for _ in types]
    for ex, _, rows, _, _ in tb['entries']:
        if not len(rows):
            continue
        for c, (a, b) in enumerate(spans):
            s = vals[c].setdefault(ex, set())
            s |= {r[a] if b == a + 1 else r[a:b] for r in rows}
    cols = []
    for c in vals:
        e = {}
        for ex, s in c.items():
            h = sorted({mix(v) for v in s})
            e[ex] = (len(s), array.array('I', h[:K]).tobytes())
        cols.append(e)
    return dict(types=types, cols=cols)


def sketch_bytes(sk):
    """Bytes a sketch holds: its hashes, plus 4 for each count and 2 for each example key."""
    return sum(len(b) + 6 for c in sk['cols'] for _, b in c.values())


def loaded(sk):
    """The sketch with sets of ints in place of bytes, as a run would hold it in memory."""
    out = dict(types=sk['types'], tset=set(sk['types']), cols=[], by=None)
    for c in sk['cols']:
        e = {}
        for ex, (n, b) in c.items():
            q = array.array('I')
            q.frombytes(b)
            e[ex] = (n, frozenset(q))
        out['cols'].append(e)
    by = {}
    for t, c in zip(sk['types'], out['cols']):
        by.setdefault(t, []).append(c)
    out['by'] = by
    return out


def compare(a, b):
    """(shared values, Jaccard) of two value sets (n, set) by their sketches."""
    na, sa = a
    nb, sb = b
    if na <= K and nb <= K:
        i = len(sa & sb)
        return i, i / (na + nb - i)
    u = sorted(sa | sb)[:K]
    i = sum(x in sa and x in sb for x in u)
    j = i / len(u)
    return max(i, j * (na + nb) / (1 + j)), j


def pair_relations(a, b):
    """The facts of two loaded sketches, without lineage."""
    ta, tb = a['tset'], b['tset']
    shared = ta & tb
    out = dict.fromkeys(FACTS, 0.0)
    out['coltype'] = len(shared) / max(len(ta | tb), 1)
    out['ident'] = float('Ident' in shared)
    if not shared:
        return out
    per = {}  # example: {type: largest Jaccard}, and whether the example joins
    joined = {}
    for t in shared:
        for ca, cb in itertools.product(a['by'][t], b['by'][t]):
            if not ca or not cb:
                continue
            if (0, 0) in ca and (0, 0) in cb:
                exs = ca.keys() | cb.keys()
            elif (0, 0) in ca:
                exs = cb.keys()
            elif (0, 0) in cb:
                exs = ca.keys()
            else:
                exs = ca.keys() & cb.keys()
            for ex in exs:
                va, vb = ca.get(ex, ca.get((0, 0))), cb.get(ex, cb.get((0, 0)))
                if va is None or vb is None:
                    continue
                i, j = compare(va, vb)
                q = per.setdefault(ex, {})
                if j > q.get(t, -1.0):
                    q[t] = j
                joined[ex] = joined.get(ex, False) or i >= 2
    if not per:
        return out
    n = len(per)
    out['join'] = sum(joined.values()) / n
    out['overlap'] = sum(sum(q.values()) / len(shared) for q in per.values()) / n
    sums, counts = {}, {}
    for t in shared:
        g = GROUP.get(t, 'O')
        counts[g] = counts.get(g, 0) + 1
        for q in per.values():
            sums[g] = sums.get(g, 0.0) + q.get(t, 0.0)
    for g, s in sums.items():
        out['overlap_' + g] = s / (counts[g] * n)
    return out


def pair_forms(ra, rb, anc_a, anc_b):
    """Facts of two forms: the largest over relation pairs, with lineage from their ancestor sets."""
    out = dict.fromkeys(FACTS, 0.0)
    for x, y in itertools.product(ra, rb):
        q = pair_relations(x, y)
        for k, v in q.items():
            if v > out[k]:
                out[k] = v
    out['lineage'] = float(bool(anc_a & anc_b))
    return out


def leaves(forms, fids):
    """The forms of a scope that no form of it reads."""
    read = set()
    for f in fids:
        read |= set(forms[f].parents)
    return [f for f in fids if f not in read]


def scope_facts(tabs, ancs):
    """{f_mean, f_max} over the pairs of the leaf forms; tabs and ancs are lists by leaf form. None with fewer than 2 leaf forms."""
    n = len(tabs)
    if n < 2:
        return None
    acc = dict.fromkeys(FACTS, 0.0)
    top = dict.fromkeys(FACTS, 0.0)
    m = 0
    for i, j in itertools.combinations(range(n), 2):
        q = pair_forms(tabs[i], tabs[j], ancs[i], ancs[j])
        m += 1
        for k, v in q.items():
            acc[k] += v
            if v > top[k]:
                top[k] = v
    out = {}
    for k in FACTS:
        out[k + '_mean'] = acc[k] / m
        out[k + '_max'] = top[k]
    return out
