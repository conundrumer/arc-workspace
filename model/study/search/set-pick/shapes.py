"""Table shape of a node or of a gold form, and the Ident source of a table. Reads no atom order, atom index or last-atom facts.

Shape levels, finest first:
  L0  (kind, sorted column types, key labels)
  L1  (kind, sorted column types)
  L2  (kind, set of column types)
  L3  (kind, number of columns)
Key labels: for an INIT, the count of `^` labels in its key section (0 where it has no key section); 'x' for any other kind.
Ident source: a table with an Ident column takes the union of the sources of the tables it reads that have an Ident column; where none has one, the table is its own source.
"""


def key_sig(kind, text):
    if kind != 'INIT':
        return 'x'
    i = text.find('(key (')
    if i < 0:
        return 0
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    return text[i:j].count('^')


def levels(kind, types, key):
    t = tuple(sorted(types))
    return ('%s|%s|%s' % (kind, ','.join(t), key), '%s|%s' % (kind, ','.join(t)), '%s|%s' % (kind, ','.join(sorted(set(t)))), '%s|%d' % (kind, len(t)))


def ident_sources(ids, has_ident, parents):
    """{id: frozenset of source ids} for ids in an order where parents come first. has_ident[id] is a bool; parents[id] a list of ids."""
    src = {}
    for i in ids:
        if not has_ident[i]:
            src[i] = frozenset()
            continue
        s = set()
        for p in parents[i]:
            s |= src.get(p, frozenset())
        src[i] = frozenset(s) if s else frozenset([i])
    return src


def ident_class(sa, sb):
    """'same', 'diff' or 'na' for two Ident source sets."""
    if not sa or not sb:
        return 'na'
    return 'same' if sa & sb else 'diff'
