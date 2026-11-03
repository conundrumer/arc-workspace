"""What the scripts of the unread-forms read share (item 14): the sets of forms at a pick, from the pick's scope and its downset. Reads a scope and a downset as sets: no line's place, no atom's place, no mark.

A scope S is the list of form texts of a point (`cut`: the forms before the target in the seed's order of its non-descendants). A form is named by its content key (ProgramDag.content), the key of the `D:<content key>.<port>` of an option.
`read` below is the direct reading of a form by a form: a form that names `&rN` reads the form with head `&rN`.

Sets at a pick of target f, with scope S and downset D:
- unread_scope: forms of S that no form of S reads.
- unread_pick: those, less the forms that an atom of D reads.
- unread_only: forms of S that f alone reads in the program (no other form of the program reads them). An oracle of the program DAG, kept as the ceiling: a search does not have it.
"""
import re

import features_dag_order as D

SETS = ('unread_scope', 'unread_pick', 'unread_only')
KNOWN = ('unread_scope', 'unread_pick')  # what a search has at the pick
NAME = re.compile(r'&r\d+')
BAR = 25.0


class PointSets:
    """The sets of one point: scope S (list of texts), the full program's DAG for the oracle, and the target key."""

    def __init__(self, scope, full: 'D.ProgramDag', key):
        self.cp = D.ProgramDag(list(scope))
        self.keys = [k for k in self.cp.lines if k != 'OUT']
        self.ck = {k: self.cp.content[k] for k in self.keys}
        readers = {k: set() for k in self.keys}
        for k in self.keys:
            for p in self.cp.parent_ids[k]:
                if p in readers:
                    readers[p].add(k)
        self.scope_forms = {self.ck[k] for k in self.keys}
        self.unread_scope = frozenset(self.ck[k] for k in self.keys if not readers[k])
        self.name_ck = self.ck
        only = set()
        for k in self.keys:
            if k in full.lines and full.child_ids.get(k, set()) == {key}:
                only.add(self.ck[k])
        self.unread_only = frozenset(only & self.scope_forms)
        self.atom_cache = {}

    def atom_reads(self, atom_text):
        """The content keys of the forms of S that an atom (its text after the path) names."""
        got = self.atom_cache.get(atom_text)
        if got is None:
            got = self.atom_cache[atom_text] = frozenset(self.name_ck[n] for n in NAME.findall(atom_text) if n in self.name_ck)
        return got

    def at(self, downset):
        """{set name: frozenset of content keys} at a pick with downset ids D."""
        read = set()
        for x in downset:
            read |= self.atom_reads(x.split('|', 1)[1])
        return dict(unread_scope=self.unread_scope, unread_pick=self.unread_scope - read, unread_only=self.unread_only)


def mix_bits(rel_bits, w, n_set, in_set):
    """Bits of a pick under the mixture: weight w uniform over a set of n_set options, 1-w on the prior of rel_bits. With an empty set the pick stays as it is."""
    import math
    if not n_set:
        return rel_bits
    p = 2.0 ** -rel_bits
    q = (1 - w) * p + (w / n_set if in_set else 0.0)
    return -math.log2(q)
