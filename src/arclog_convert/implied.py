"""The implied-atom pass on a converted program: it removes from a conjunction
each positive atom that another positive atom of the same conjunction implies.

A conjunction is a `RULE` or `DET` body, the key clause or an input body of an
`INIT`, one branch of an `OR`, a part of an `IF` and one list of an `ALL`: the
atoms in one such list. The pass leaves the atoms under a `NOT`, and the atoms
of a list other than the one that holds the implying atom, as they are. An
atom B on a relation is implied by an atom A on the same relation when each
site of B is a site of A, with the same column and the same label or constant:
B reads only columns that A reads, joined to the variables that A joins them to.
A site of B that makes a label (`*X`) which no other node of the form names
reads nothing, and B needs no site of A at its column. An atom with no sites
stands for the relation's having a row, which any atom on the relation implies.
The pass removes B, with the white space before it.

The pass leaves B where:
- the relation is a lib relation with a mode (`lib.ALGEBRA_MODES`), whose
  columns the atom computes;
- an atom has a site of a shape the pass does not read, or B marks a label `^`;
- B makes a label that another node of the form names, A included: the label
  enters the body at B, and A joins it;
- B stands in the body of a `RULE` or `DET` and makes a label: the label is a
  column of the clause's relation (`docs/arclog/arclog.md#sites`), which
  other forms may read;
- the atom that implies B stands after a `NOT` or an `ALL` that follows B: with B gone, that `NOT` would stand
  before the atom that binds its labels.

The pass repeats until it removes no atom, since an atom it removes no longer
implies another. The text stays as it is where it removes none."""

from collections.abc import Iterator
from dataclasses import dataclass

from arclog_convert.lib import ALGEBRA_MODES
from arclog_convert.lint import FORMS, MARKS, OPS, bare_label, is_const, site_pairs
from arclog_convert.lint_alts import placements
from arclog_convert.lint_read import L, Sym, read, walk

BODIES = ("RULE", "DET")
"""The clauses with a body."""


@dataclass(frozen=True)
class Implied:
    """The text after the pass, and the number of atoms it removed."""

    arclog: str
    removed: int


def _conjunctions(form: L) -> Iterator[tuple[list, bool]]:
    """The lists of `form` that are a conjunction, each with whether it is the body of a clause, whose labels are
    the columns of the clause's relation."""
    if form.head in BODIES:
        yield from _lists(form.items[2:], True)
    elif form.head == "INIT":
        for c in form.items[3:]:
            if not isinstance(c, L) or len(c.items) < 2 or not isinstance(c.items[1], L):
                continue
            if c.head == "key":
                yield from _lists(c.items[1].items, False)
                for x in c.items[2:]:
                    if isinstance(x, L):
                        yield from _lists(x.items[2:], False)
            else:
                yield from _lists(c.items[2:], False)


def _lists(items: list, clause: bool) -> Iterator[tuple[list, bool]]:
    """`items`, and the conjunctions under its `OR`, `IF` and `ALL` forms."""
    yield items, clause
    for x in items:
        if isinstance(x, L) and x.head in ("OR", "IF", "ALL"):
            for part in x.items[1:]:
                if isinstance(part, L):
                    yield from _lists(part.items, False)


def _field(node: L) -> bool:
    """Whether `node` is a site on a column."""
    return bool(node.head and node.head.startswith(":"))


def _sites(atom: L) -> dict[str, str] | None:
    """The label, with its mark, at each column path of `atom`; none where a site has a shape the pass does not
    read."""
    for node in atom.items[1:]:
        if isinstance(node, Sym):
            if is_const(node.text):
                return None
        elif not isinstance(node, L) or not _field(node) or \
                any(isinstance(x, L) and not _field(x) for x in walk(node) if x is not node):
            return None
    return dict(pair for node in atom.items[1:] for pair in site_pairs(node))


def _readable(items: list) -> list[L]:
    """The atoms of `items` that the pass reads: the positive ones on a relation without a mode."""
    return [x for x in items if isinstance(x, L) and x.head and x.head not in FORMS | OPS | MARKS
            and not x.head.startswith(":") and x.head not in ALGEBRA_MODES]


def _names(form: L, atom: L) -> set[str]:
    """The labels that nodes of `form` outside `atom` name."""
    inside = {id(x) for x in walk(atom)}
    return {bare_label(x.text) for x in walk(form) if isinstance(x, Sym) and id(x) not in inside}


def _implies(a: L, b: L, named: set[str], clause: bool) -> bool:
    """Whether `a` implies `b`, given the labels `named` that nodes outside `b` name and whether `b` stands in the
    body of a clause."""
    sa, sb = _sites(a), _sites(b)
    if sa is None or sb is None:
        return False
    held = {(path, bare_label(label)) for path, label in sa.items()}
    for path, label in sb.items():
        if "^" in label:
            return False
        if label.startswith("*"):
            if clause or bare_label(label) in named:
                return False
        elif (path, bare_label(label)) not in held:
            return False
    return True


def _binds_before(items: list, a: L, b: L) -> bool:
    """Whether the atom `a` that implies `b` stands before `b` or has no `NOT` or `ALL` between them: `b` leaves,
    and a `NOT` between would stand before the atom that binds its labels."""
    order = [id(x) for x in items]
    i, j = order.index(id(a)), order.index(id(b))
    return i < j or not any(isinstance(x, L) and x.head in ("NOT", "ALL") for x in items[j:i])


def _step(text: str) -> str | None:
    """`text` without one implied atom; none where no atom is implied."""
    for placed in placements(read(text)):
        form = placed.form
        for items, clause in _conjunctions(form):
            atoms = _readable(items)
            for b in reversed(atoms):
                peers = [a for a in atoms if a is not b and a.head == b.head]
                named = _names(form, b) if peers else set()
                if any(_implies(a, b, named, clause) and _binds_before(items, a, b) for a in peers):
                    start = b.start
                    while text[start - 1].isspace():
                        start -= 1
                    return text[:start] + text[b.end:]
    return None


def drop_implied(arclog: str) -> Implied:
    """`arclog` after the pass, with the number of atoms it removed."""
    removed = 0
    while (step := _step(arclog)) is not None:
        arclog, removed = step, removed + 1
    return Implied(arclog, removed)
