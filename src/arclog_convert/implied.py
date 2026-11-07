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
An atom B on an orientation-type relation (`ELEM`, such as `d4_elem`) with one site that names a label without a mark
is implied also by an atom A on a lib relation that names that label at a column whose type is that orientation type or
a type below it (`BELOW`): A holds only values of that type, whether an algebra relation enumerates the column or
another atom binds it, so B tests nothing. `d4_inverse` at its `D_inv` column and `axis_inversion` at its `T` column
imply `d4_elem`, and `split` at its `A` column implies `axis_elem`. A may be an algebra relation, which the same-relation rule
leaves alone.
The pass removes B, with the white space before it.

An atom B on an `ELEM` relation that makes its label (`(dir_elem *D)`) is removed also where a later atom A of the same
conjunction reads that label, without a mark, at a column whose type is that orientation type or a type below it, and
can make the label itself, and some order of the conjuncts has A make the label before each conjunct that reads it. Each
value at that column is a member, so B removes no row, and A makes the label B made. The rule is the static prune's
`membership.implied_later` (`makes_membership_redundant` and `last_can_make_before_uses` in
`engine/arclog/src/program/static_prune.rs`, with its proof in `engine/arclog/src/program/static_prune/proofs.md`): the
decoder refuses a program that holds such a pair (`check_static_prune` in `engine/arclog/src/decode/mod.rs`). A can make
the label where its relation is a lib relation with no mode (`lib.ALGEBRA_MODES`), or has a mode whose columns leave out the
column and that each hold, in A, a label without a mark or `0`. The type of the column is that of `lib-signature.dl`
(`LIB.top`). An atom on a relation of the program has no type in Python: `drop_typed_membership` takes the types from the
checker, for a case program (`convert._typed_membership`), by the path of the site, and the pass in `drop_implied` leaves
B as it is.
The order exists, as the engine decides it, where A depends on no conjunct that reads the label. The conjuncts are those of
the list but B and the other atoms that make the label as a membership. A conjunct that makes labels, with `*` or `^`, is
a maker of them, and A depends on the makers of the labels A joins, other than the label of B, and on the makers of the
labels that those read, and so on. A `NOT` makes no label. Where a conjunct that reads the label is a conjunct that A
depends on, no order exists, the label is read before it is made, and B stays.
Where the order exists, the pass removes B and writes the label at the first site of A that names it as `*D`. The conjuncts
between B and A that read the label stand after A, with each conjunct between them that reads a label that one of those
makes, in their order. The other conjuncts between B and A stay before A.
The order in which a `RULE` or `DET` body makes its labels is the order of the columns of the clause's table, and the
pass changes it. In a key clause of an `INIT`, the `^` labels are the key's columns in their order of appearance
(`docs/arclog/arclog.md#instance`), so the pass keeps that order: it leaves B where the order of the `^` labels from B
to A would change. The label of B is a `*` label, which is no column of the key.
The engine counts the labels of a list by the identifier that its resolver gives, and the pass counts them by name.

An atom E that makes no label is removed also where a later atom A of the same conjunction on the same relation has each
site of E: the same column and the same label, without a mark. A reads whatever E reads, so E removes no row. The rule is the
static prune's `atom.implies_earlier` (`makes_earlier_redundant` in `engine/arclog/src/program/static_prune.rs`). The pass
reads atoms on relations with no mode (`lib.ALGEBRA_MODES`) here.
Where a `NOT` or `ALL` between E and A names a label of E that no other atom before it names, that conjunct would stand
before the atom that binds its labels without E. A then stands in the place of E, and is removed from where it stood,
where A makes no label that a node between them names, joins no label that a node between them makes, and, in a list that
keeps the order of its `^` labels, does not pass a node that makes one; otherwise the pass leaves E.

An atom B on an `ELEM` relation that joins a label (`(diag_dir_elem (:D C))`) is removed also where an earlier atom of the
same conjunction on a relation of the program makes that label at a column whose type is that orientation type or a type
below it: the column holds only members, so B tests nothing. The rule is the static prune's `membership.subtype`. As for an
atom on a relation of the program in the rule above, `drop_typed_membership` takes the column types from the checker.

An atom A is folded into an earlier atom E of the same conjunction on the same relation where the relation has a key
(`registry.sexpr`: `input`, `ex_input` and `ex_output` among them, and the lib relations with no mode) and the two hold the same
label at each column of the key. The relation has one row for each value of the key, so the two atoms read one row. The
rule is the static prune's `atom.same_row` (`reads_an_earlier_row` in `engine/arclog/src/program/static_prune.rs`). E gets
the sites of A on the columns it has no site on, and A goes (`_same_row_step` gives the conditions).

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

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import cache
from typing import NamedTuple

from arclog_convert.lib import ALGEBRA_MODES, REGISTRY, pascal
from arclog_convert.lint import FORMS, LIB, MARKS, OPS, bare_label, is_const, site_pairs
from arclog_convert.lint_alts import placements
from arclog_convert.lint_read import L, Sym, read, walk

BODIES = ("RULE", "DET")
"""The clauses with a body."""

ELEM = {"dir_elem": "Dir", "axis_elem": "Axis", "diag_dir_elem": "DiagDir", "diag_axis_elem": "DiagAxis",
        "d4_elem": "D4", "c4_elem": "C4", "sense_elem": "Sense", "sym_elem": "Sym", "dir8_elem": "Dir8",
        "axis4_elem": "Axis4"}
"""The relation that tests membership in each orientation type, by name, with that type."""

BELOW = {"D4": {"C4"}, "Dir8": {"Dir", "DiagDir"}, "Axis4": {"Axis", "DiagAxis"}}
"""The types below each orientation type that has some (`lib-signature.dl`), apart from itself."""


@dataclass(frozen=True)
class Implied:
    """The text after the pass, and the number of atoms it removed."""

    arclog: str
    removed: int


type NodePath = tuple[int, ...]
"""The path of a node of a form, as the engine counts it: the index of each node among the children of the node above."""


def _conjunctions(form: L, picks: bool = False) -> Iterator[tuple[list, bool, NodePath | None]]:
    """The lists of `form` that are a conjunction, each with whether it is the body of a clause, whose labels are
    the columns of the clause's relation, and the path of the list in the form; none where the pass reads no path of
    that list. With `picks`, the lists of a `CHOOSE` and a `RIGID_DET` form too, which have no path."""
    if form.head in BODIES:
        yield from _lists(form.items[2:], True, (0,))
    elif form.head == "INIT":
        for i, c in enumerate(form.items[3:]):
            if not isinstance(c, L) or len(c.items) < 2 or not isinstance(c.items[1], L):
                continue
            if c.head == "key":
                yield from _lists(c.items[1].items, False, (i, 0))
                for j, x in enumerate(c.items[2:], 1):
                    if isinstance(x, L) and len(x.items) > 1 and isinstance(x.items[1], L):
                        yield from _lists(x.items[2:], False, (i, j, len(x.items[1].items)))
            else:
                yield from _lists(c.items[2:], False, (i, len(c.items[1].items)))
    elif picks and form.head == "CHOOSE":
        for c in form.items[2:]:
            if not isinstance(c, L):
                continue
            if c.head == "for" and len(c.items) > 1 and isinstance(c.items[1], L):
                yield from _lists(c.items[1].items, False, None)
                for x in c.items[2:]:
                    if isinstance(x, L) and x.head == "from":
                        yield from _lists(x.items[1:], False, None)
            elif c.head == "never":
                yield from _lists(c.items[1:], False, None)
    elif picks and form.head == "RIGID_DET":
        for c in form.items[2:]:
            if isinstance(c, L) and c.head == "instance" and len(c.items) > 1 and isinstance(c.items[1], L):
                yield from _lists(c.items[1].items, False, None)
                yield from _lists(c.items[2:], False, None)


def _lists(items: list, clause: bool, at: NodePath | None) -> Iterator[tuple[list, bool, NodePath | None]]:
    """`items`, and the conjunctions under its `OR`, `IF` and `ALL` forms. `at` is the path of `items` in the form."""
    yield items, clause, at
    for k, x in enumerate(items):
        if isinstance(x, L) and x.head in ("OR", "IF", "ALL"):
            for p, part in enumerate(x.items[1:]):
                if isinstance(part, L):
                    yield from _lists(part.items, False, None if at is None else (*at, k, p))


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


def _typed(a: L, b: L) -> bool:
    """Whether the lib atom `a` names the label of the one site of `b`, an atom of `ELEM`, at a column whose type is
    that of `b` or below it. The label of `b` has no mark."""
    tested = ELEM[b.head]
    sb = _sites(b)
    if sb is None or len(sb) != 1:
        return False
    (label,) = sb.values()
    if label.startswith(("*", "^")):
        return False
    types = dict((pascal(name), ty) for name, ty in LIB.top[a.head])
    sa = _sites(a)
    return sa is not None and any(
        bare_label(held) == label and (ty := types.get(path)) is not None and (ty == tested or ty in BELOW.get(tested, ()))
        for path, held in sa.items())


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
        for items, clause, _ in _conjunctions(form):
            atoms = _readable(items)
            typed = [x for x in items if isinstance(x, L) and x.head in LIB.top]
            for b in reversed(atoms):
                peers = [a for a in atoms if a is not b and a.head == b.head]
                named = _names(form, b) if peers else set()
                if any(_implies(a, b, named, clause) and _binds_before(items, a, b) for a in peers) or \
                        b.head in ELEM and any(a is not b and _typed(a, b) and _binds_before(items, a, b) for a in typed):
                    start = b.start
                    while text[start - 1].isspace():
                        start -= 1
                    return text[:start] + text[b.end:]
    return None


def _joined(label: str) -> bool:
    """Whether `label`, as written at a site, joins a variable or is `0`: it has no mark and is no constant but `0`."""
    return label == "0" or not (label.startswith(("*", "^")) or is_const(label))


def _binds(atom: L, column: str, sites: dict[str, str]) -> bool:
    """Whether the lib atom `atom`, whose sites are `sites`, can make the label at `column`: its relation has no mode
    (`ALGEBRA_MODES`), or has one whose columns leave out `column` and that `sites` each give a label that joins or `0`
    (`makes_membership_redundant` takes this from `binds_column` in `engine/arclog/src/decode/mod.rs`)."""
    modes = ALGEBRA_MODES.get(atom.head)
    return not modes or any(
        column not in {pascal(c) for c in mode} and all(_joined(sites.get(pascal(c), "*")) for c in mode)
        for mode in modes)


def _made(atom: L) -> str | None:
    """The label that the `ELEM` atom `atom` makes at its one site, which is a site of one label; none where it has no
    such site or the label has a mark other than `*`."""
    sites = _sites(atom)
    if sites is None or len(sites) != 1:
        return None
    (label,) = sites.values()
    return label[1:] if label.startswith("*") and not is_const(label) else None


SiteOk = Callable[[NodePath, tuple[str, ...]], bool]
"""Whether a site of a program relation's atom is at a column of one of the types: the path of the site in the text, as the
engine counts it (the index of the form among the forms of the text, the path of the list in the form, the index of the
atom in the list and of the site in the atom), and the types."""


def _flow(node) -> tuple[set[str], set[str]]:
    """The labels that `node` makes, with `*` or `^`, and the labels it joins, at any depth. A constant and `0` are no
    label."""
    made, joined = set(), set()
    for x in walk(node):
        if isinstance(x, L):
            for y in x.items[1:]:
                if isinstance(y, Sym) and not is_const(y.text):
                    (made if y.text[0] in "*^" else joined).add(bare_label(y.text))
    return made, joined


def _is_maker(node, label: str) -> bool:
    """Whether `node` is an `ELEM` atom that makes `label` at its one site."""
    return isinstance(node, L) and node.head in ELEM and _made(node) == label


def _can_make_first(items: list, flows: list[tuple[set[str], set[str]]], at: int, label: str) -> bool:
    """Whether some order of `items[:at + 1]`, less the `ELEM` atoms that make `label`, has `items[at]` make `label`
    before each conjunct that reads it, with each other label made before it is read. The atom `items[at]` follows the
    makers of the labels it joins, and a conjunct that reads `label` and that `items[at]` depends on, through those
    makers, rules every such order out. This is `last_can_make_before_uses` in `engine/arclog/src/program/static_prune.rs`."""
    kept = [k for k in range(at) if not _is_maker(items[k], label)] + [at]
    last = len(kept) - 1
    depends = [False] * len(kept)
    pending = [last]
    while pending:
        item = pending.pop()
        for read in flows[kept[item]][1] - {label}:
            for maker, k in enumerate(kept):
                if maker != item and not depends[maker] and read in flows[k][0]:
                    depends[maker] = True
                    pending.append(maker)
    return not any(i != last and depends[i] and label in flows[k][1] for i, k in enumerate(kept))


def _moved(flows: list[tuple[set[str], set[str]]], bi: int, ai: int, label: str) -> list[int]:
    """The indices of the items between `bi` and `ai` that stand after `items[ai]` where it makes `label`: each that
    reads `label`, and each that reads a label that one of those makes, in the order of the items."""
    moved, made = [], set()
    for k in range(bi + 1, ai):
        if label in flows[k][1] or flows[k][1] & made:
            moved.append(k)
            made |= flows[k][0]
    return moved


def _reading(a: L, label: str, tested: str, ok: Callable[[int, tuple[str, ...]], bool] | None = None) -> Sym | None:
    """The label of the first site of the atom `a` that reads `label`, without a mark, at a column whose type is `tested`
    or below it and that `a` can make, where that site has one label; none where `a` has no such site, or has a site of a
    shape the pass does not read. `a` is an atom on a relation of `LIB.top`, whose column types are those of
    `lib-signature.dl`, or an atom on a relation of the program, where `ok` says whether the column of the site with an
    index is of one of the types."""
    sites = _sites(a)
    if sites is None or a.head in ELEM:
        return None
    types = (tested, *BELOW.get(tested, ()))
    if a.head in LIB.top:
        columns = {pascal(n): ty for n, ty in LIB.top[a.head]}
        typed = lambda column, j: columns.get(column) in types
    elif ok is not None and a.head.startswith("&"):
        typed = lambda column, j: ok(j, types)
    else:
        return None
    for j, node in enumerate(a.items[1:]):
        for column, held in site_pairs(node):
            if held == label and "." not in column and typed(column, j) and _binds(a, column, sites):
                return node if isinstance(node, Sym) else node.items[-1]
    return None


class Pair(NamedTuple):
    """A membership atom `items[b]` that makes `label`, and the first atom after it, `items[a]`, that makes the static
    prune's rule `membership.implied_later` refuse it, with the label of the site `name` of `items[a]`, and whether the
    form keeps the order of its `^` labels, and whether it is a `CHOOSE` or `RIGID_DET` form, whose lists the pass leaves
    as they are."""

    form: int
    items: list
    b: int
    a: int
    label: str
    name: Sym
    ordered: bool
    pick: bool


def pairs(text: str, site_ok: SiteOk | None = None) -> Iterator[Pair]:
    """The pairs of `text` that the static prune's rule `membership.implied_later` refuses, as the pass models it (see the
    module's text). A relation of the program has a type where `site_ok` says so."""
    forms = read(text)
    top = [x for x in forms if isinstance(x, L)]
    for placed in placements(forms):
        form = next((i for i, x in enumerate(top) if x is placed.form), -1)
        for items, clause, at in _conjunctions(placed.form, True):
            flows = [_flow(x) if isinstance(x, L) else (set(), set()) for x in items]
            for bi, b in enumerate(items):
                if not isinstance(b, L) or b.head not in ELEM or (label := _made(b)) is None:
                    continue
                for ai in range(bi + 1, len(items)):
                    a = items[ai]
                    if not isinstance(a, L) or not a.head:
                        continue
                    ok = (lambda j, types, ai=ai: site_ok((form, *at, ai, j), types)) if site_ok and at is not None and form >= 0 else None
                    name = _reading(a, label, ELEM[b.head], ok)
                    if name is not None and _can_make_first(items, flows, ai, label):
                        yield Pair(form, items, bi, ai, label, name, placed.form.head not in BODIES,
                                   placed.form.head in ("CHOOSE", "RIGID_DET"))
                        break


def _later_step(text: str, site_ok: SiteOk | None = None) -> str | None:
    """`text` without one `ELEM` atom that a later atom of its conjunction makes redundant, and with the label of the
    removed atom made at that later atom, where the later atom is the first node that names the label; none where there
    is no such atom (see the module's text). The atom may be one on a relation of the program, where `site_ok` says the type
    of a site. The items between the two that read the label, and the items that read what those make, stand after the
    later atom."""
    for pair in pairs(text, site_ok):
        if pair.pick:
            continue
        items, bi, ai = pair.items, pair.b, pair.a
        a = items[ai]
        if next(x for x in walk(a) if isinstance(x, Sym) and bare_label(x.text) == pair.label) is not pair.name:
            continue
        flows = [_flow(x) if isinstance(x, L) else (set(), set()) for x in items]
        moved = _moved(flows, bi, ai, pair.label)
        placed = [k for k in range(bi + 1, ai) if k not in moved] + [ai] + moved
        # the key's `^` labels stay in the order they are in; a `RULE` or `DET` makes its labels in any order
        if pair.ordered and _caret(items[bi + 1:ai + 1]) != _caret([items[k] for k in placed]):
            continue
        b = items[bi]
        # B goes with the white space before it, or after it where it stands right after a `(`
        start = b.start
        while text[start - 1].isspace():
            start -= 1
        after_paren = text[start - 1] == "("
        if after_paren:
            start = b.start
        parts = []
        for n, k in enumerate(placed):
            gap = "" if n == 0 and after_paren else text[items[k - 1].end:items[k].start]
            node = text[items[k].start:items[k].end]
            if k == ai:
                at = pair.name.pos - items[k].start
                node = node[:at] + "*" + node[at:]
            parts.append(gap + node)
        return text[:start] + "".join(parts) + text[a.end:]
    return None


def _marked(nodes: list, marks: str) -> set[str]:
    """The labels that `nodes` make with a mark of `marks`."""
    return {bare_label(x.text) for n in nodes for x in walk(n) if isinstance(x, Sym) and x.text[:1] in marks and len(x.text) > 1}


def _named(nodes: list) -> set[str]:
    """The labels that `nodes` name, with a mark or without."""
    return {bare_label(x.text) for n in nodes for x in walk(n) if isinstance(x, Sym)}


def _caret(nodes: list) -> list[str]:
    """The labels that `nodes` make with `^`, in the order of the text."""
    return [x.text for n in nodes for x in walk(n) if isinstance(x, Sym) and x.text[:1] == "^" and len(x.text) > 1]


def _unbound(items: list, first: int, k: int, e: L) -> bool:
    """Whether `items[k]`, after the atom `e` at `items[first]`, is a `NOT` or `ALL` that names a label of `e` which no
    other atom before `items[k]` names: without `e`, that conjunct would stand before the atom that binds its labels."""
    x = items[k]
    if not (isinstance(x, L) and x.head in ("NOT", "ALL")):
        return False
    others = _named([y for j, y in enumerate(items[:k]) if j != first and isinstance(y, L) and y.head not in FORMS | OPS])
    return bool((_named([x]) & _named([e])) - others)


def _earlier_step(text: str) -> str | None:
    """`text` without one atom that makes no label and that a later atom of its conjunction on the same relation
    implies by holding each of its sites; none where there is no such atom. A `NOT` or `ALL` between the two would stand
    before the atom that binds its labels, so the later atom stands in the place of the earlier one then, and is moved
    where it makes no label that a node between them names, joins no label that a node between them makes, and, in a
    list that keeps the order of its `^` labels, does not pass a node that makes one."""
    for placed in placements(read(text)):
        for items, _, _ in _conjunctions(placed.form):
            atoms = _readable(items)
            for at, e in enumerate(atoms):
                held = _sites(e)
                if held is None or any(label.startswith(("*", "^")) for label in held.values()):
                    continue
                for a in atoms[at + 1:]:
                    sites = _sites(a)
                    if a.head != e.head or sites is None or not all(sites.get(path) == label for path, label in held.items()):
                        continue
                    start = e.start
                    while text[start - 1].isspace():
                        start -= 1
                    first = items.index(e)
                    between = items[first + 1:items.index(a)]
                    if not any(_unbound(items, first, k, e) for k in range(first + 1, first + 1 + len(between))):
                        return text[:start] + text[e.end:]
                    made, named = _flow(a)[0], _named([a])
                    if _named(between) & made or _marked(between, "*^") & named \
                            or placed.form.head not in BODIES and _caret(between) and _caret([a]):
                        continue
                    gap = a.start
                    while text[gap - 1].isspace():
                        gap -= 1
                    return text[:e.start] + text[a.start:a.end] + text[e.end:gap] + text[a.end:]
    return None


@cache
def _keys() -> dict[str, list[list[str]]]:
    """The keys of each relation that has no mode: its `(key ...)` items in the `refines` form of
    `engine/lib/registry.sexpr`, as column names. The facts `input`, `ex_input` and `ex_output` have one each."""
    keys: dict[str, list[list[str]]] = {}
    for m in re.finditer(r"^\(refines ([A-Za-z0-9_]+) (.*)\)\s*$", REGISTRY.read_text(), re.M):
        for item in read(m.group(2)):
            if isinstance(item, L) and item.head == "key":
                keys.setdefault(m.group(1), []).append([x.text for x in item.items[1:] if isinstance(x, Sym)])
    return keys


def _same_row_step(text: str) -> str | None:
    """`text` with one atom folded into an earlier atom of its conjunction that reads the same row: both are positive
    atoms on a relation that has a key (`_keys`), and hold the same label or `0` at each column of that key. The relation
    has at most one row for each value of the key, so the two atoms match one row, and one atom with the sites of both
    reads it. This is the static prune's rule `atom.same_row` (`reads_an_earlier_row` in
    `engine/arclog/src/program/static_prune.rs`). The sites of the later atom at columns the earlier one has no site on
    are added to the earlier atom, which keeps its place, where the labels they join are not made between the two, no
    label they make is named between them and, in a list that keeps the order of its `^` labels, the later atom and the
    nodes between make no `^` label together; the later atom goes. The two hold the same label at each column both have a
    site on, or the pass leaves them as they are."""
    for placed in placements(read(text)):
        for items, _, _ in _conjunctions(placed.form):
            atoms = _readable(items)
            for at, e in enumerate(atoms):
                keys = _keys().get(e.head or "")
                sites = _sites(e)
                if not keys or sites is None or any("." in c for c in sites):
                    continue
                for a in atoms[at + 1:]:
                    held = _sites(a)
                    if a.head != e.head or held is None or any("." in c for c in held):
                        continue
                    if not any(all(c in sites and c in held and bare_label(sites[c]) == bare_label(held[c]) for c in key) for key in keys):
                        continue
                    if any(c in sites and bare_label(sites[c]) != bare_label(held[c]) for c in held) or \
                            any(is_const(v) and v != "0" for v in (*sites.values(), *held.values())):
                        continue
                    extra = [node for node in a.items[1:] if all(c not in sites for c, _ in site_pairs(node))]
                    between = items[items.index(e) + 1:items.index(a)]
                    made = _marked(extra, "*^")
                    joined = _named(extra) - made
                    if _marked(between, "*^") & joined or _named(between) & made \
                            or placed.form.head not in BODIES and _caret(between) and _caret(extra):
                        continue
                    texts = [text[node.start if isinstance(node, L) else node.pos:node.end if isinstance(node, L) else node.pos + len(node.text)]
                             for node in extra]
                    start = a.start
                    while text[start - 1].isspace():
                        start -= 1
                    folded = text[:e.end - 1] + "".join(" " + t for t in texts) + text[e.end - 1:start] + text[a.end:]
                    return folded
    return None


def _bound_step(text: str, site_ok: SiteOk) -> str | None:
    """`text` without one `ELEM` atom that joins a label an earlier atom of its conjunction on a relation of the program
    makes at a column whose type is that of the `ELEM` atom or below it (`site_ok`): the column holds only members, so the
    atom tests nothing (the static prune's rule `membership.subtype`); none where there is no such atom."""
    forms = read(text)
    top = [x for x in forms if isinstance(x, L)]
    for placed in placements(forms):
        form = next((i for i, x in enumerate(top) if x is placed.form), -1)
        for items, _, at in _conjunctions(placed.form):
            if at is None or form < 0:
                continue
            for bi, b in enumerate(items):
                sites = _sites(b) if isinstance(b, L) and b.head in ELEM else None
                if sites is None or len(sites) != 1:
                    continue
                (label,) = sites.values()
                if label.startswith(("*", "^")) or is_const(label):
                    continue
                types = (ELEM[b.head], *BELOW.get(ELEM[b.head], ()))
                for ai, a in enumerate(items[:bi]):
                    if not isinstance(a, L) or not (a.head or "").startswith("&") or (held := _sites(a)) is None:
                        continue
                    for j, node in enumerate(a.items[1:]):
                        if any(column.count(".") == 0 and value[:1] in "*^" and bare_label(value) == label
                               for column, value in site_pairs(node)) and site_ok((form, *at, ai, j), types):
                            start = b.start
                            while text[start - 1].isspace():
                                start -= 1
                            return text[:start] + text[b.end:]
    return None


def drop_typed_membership(arclog: str, site_ok: SiteOk) -> str | None:
    """`arclog`, a case program, without one `ELEM` atom that an atom of its conjunction on a relation of the program
    makes redundant, where the checker types the column of that atom's site (`site_ok`): a later atom that reads the
    label of the `ELEM` atom (`membership.implied_later`), or an earlier atom that makes it (`membership.subtype`); none
    where there is no such atom. A step changes the indices that `site_ok` reads, so a caller asks again for the text it
    gets."""
    return _later_step(arclog, site_ok) or _bound_step(arclog, site_ok)


def has_program_membership(arclog: str) -> bool:
    """Whether `arclog` holds an `ELEM` atom that an atom on a relation of the program may make redundant, which
    `drop_typed_membership` decides with the types of the columns."""
    return drop_typed_membership(arclog, lambda *_: True) is not None


def drop_implied(arclog: str) -> Implied:
    """`arclog` after the pass, with the number of atoms it removed."""
    removed = 0
    while (step := _step(arclog) or _later_step(arclog) or _earlier_step(arclog) or _same_row_step(arclog)) is not None:
        arclog, removed = step, removed + 1
    return Implied(arclog, removed)
