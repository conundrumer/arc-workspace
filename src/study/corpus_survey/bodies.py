"""The bodies of an arclog file, each with the form it stands in, and the
parts of a body's items: an item's kind, a site's column paths and labels,
and the labels an item reads.

A body is the body of a `RULE`, `DET`, `DET_OR_RULE`, `RULE_OR_DET` or
`RIGID_DET` form, an instance's key clause or input, or a `CHOOSE` form's
`from` or `never` list."""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

from study.corpus_survey.trees import Node, head, is_list, is_sym

OPS = frozenset({"=", "!=", "<", "<=", ">", ">="})
FACTS = frozenset({"input", "ex_input", "ex_output"})
NESTED = ("NOT", "OR", "IF", "ALL")
BLOCKS = frozenset({"INPUT", "OUTPUT", "ALTS", "ALT", "DEMO_RULE"})


class Kind(StrEnum):
    """The kind of a body: its clause form, or its part of an instance or
    of a `CHOOSE` form."""
    RULE = "RULE"
    DET = "DET"
    DET_OR_RULE = "DET_OR_RULE"
    RULE_OR_DET = "RULE_OR_DET"
    RIGID_DET = "RIGID_DET"
    KEY = "key"
    INPUT = "input"
    FROM = "from"
    NEVER = "never"


CLAUSES = frozenset({Kind.RULE, Kind.DET, Kind.DET_OR_RULE, Kind.RULE_OR_DET,
                     Kind.RIGID_DET})
DETERMINED = (Kind.DET, Kind.DET_OR_RULE)
"""The clause forms whose relation a solver stores on its concept
reading, and which name a proposer."""


def stored(rel: str) -> bool:
    """Whether an atom of `rel` reads a stored relation: a derived relation
    or a fact of the task, no lib relation."""
    return rel.startswith("&") or rel in FACTS


class Item(StrEnum):
    """The kind of an item of a body."""
    ATOM = "atom"
    OP = "op"
    ONE = "ONE"
    NOT = "NOT"
    OR = "OR"
    IF = "IF"
    ALL = "ALL"
    LIST = "list"


@dataclass(frozen=True)
class Frame:
    """A block a form stands in: its head, and for an `ALTS` form its name
    and the concept case's alt, for an `ALT` its alt."""
    head: str
    name: str | None = None
    default: str | None = None


@dataclass(frozen=True)
class Body:
    stem: str
    kind: Kind
    name: str
    """The relation of a clause; the instance, or the `CHOOSE` form, the
    body is part of; an input's name is `<instance>.<input>`."""
    items: list[Node]
    heads: tuple[tuple[str, str], ...]
    """The column paths and labels of an input's head sites."""
    keycols: tuple[str, ...]
    """The key labels an instance's or a `CHOOSE` form's key clause binds,
    which its inputs read bound."""
    form: str
    """The head of the declaration form the body stands in."""
    component: str | None
    stack: tuple[Frame, ...]

    def in_alt(self) -> bool:
        return any(f.head in ("ALT", "DEMO_RULE") for f in self.stack)


def strip(label: str) -> str:
    return label.lstrip("*^")


def is_const(label: str) -> bool:
    t = strip(label)
    return t.lstrip("-").isdigit() or t.startswith(("$", "{")) or t == "_"


def site_pairs(x: Node) -> list[tuple[str, str]]:
    """The (column path, label) pairs of one site of an atom."""
    if is_sym(x):
        assert isinstance(x, str)
        return [(strip(x), x)]
    if not isinstance(x, list) or not x or not is_sym(x[0]):
        return []
    col = str(x[0])[1:]
    args = x[1:]
    if len(args) == 1 and is_sym(args[0]):
        return [(col, str(args[0]))]
    pairs: list[tuple[str, str]] = []
    for a in args:
        if is_sym(a):
            pairs.append((col + "." + strip(str(a)), str(a)))
        else:
            pairs.extend((col + "." + p, lab) for p, lab in site_pairs(a))
    return pairs


def item_kind(it: list[Node]) -> Item:
    h = it[0] if it else None
    if is_list(h):
        return Item.LIST
    if h in OPS:
        return Item.OP
    if h in (Item.ONE, *NESTED):
        return Item(h)
    return Item.ATOM


def flat(x: Node) -> list[str]:
    """Each symbol of `x`."""
    if isinstance(x, list):
        return [t for y in x for t in flat(y)]
    return [x] if is_sym(x) else []


def atom_labels(it: list[Node]) -> list[str]:
    """The labels of an atom's sites, constants aside."""
    return [lab for s in it[1:] for _, lab in site_pairs(s) if not is_const(lab)]


def item_labels(it: list[Node]) -> list[str]:
    """The labels of an atom, a constraint or a `ONE` mark, constants
    aside."""
    if item_kind(it) in (Item.OP, Item.ONE):
        return [x for x in flat(it[1:]) if not is_const(x)]
    return atom_labels(it)


def names(labels: list[str]) -> set[str]:
    return {strip(t) for t in labels if not is_const(t)}


def parts(it: list[Node]) -> Iterator[list[Node]]:
    """The item lists of a nested form: each branch of an `OR`, each part
    of an `IF` or an `ALL`, the items of a `NOT`."""
    for sub in it[1:]:
        if isinstance(sub, list) and sub:
            yield [sub] if is_sym(sub[0]) else sub


def deep_labels(items: list[Node]) -> list[str]:
    """The labels of each atom, constraint and `ONE` mark of `items`, at
    every depth, marks kept."""
    found: list[str] = []
    for it in items:
        if not isinstance(it, list) or not it:
            continue
        k = item_kind(it)
        if k in (Item.ATOM, Item.OP, Item.ONE):
            found += item_labels(it)
        elif k == Item.LIST:
            found += deep_labels(it)
        else:
            for p in parts(it):
                found += deep_labels(p)
    return found


def deep_atoms(items: list[Node]) -> Iterator[list[Node]]:
    """Each atom of `items`, at every depth."""
    for it in items:
        if not isinstance(it, list) or not it:
            continue
        k = item_kind(it)
        if k == Item.ATOM:
            yield it
        elif k == Item.LIST:
            yield from deep_atoms(it)
        elif k in NESTED:
            for p in parts(it):
                yield from deep_atoms(p)


def exported(it: list[Node]) -> set[str]:
    """The labels an `OR` or an `IF` form exports: those every branch
    names, or both the `then` and the `else` part."""
    k = item_kind(it)
    if k == Item.OR:
        sets = [names(deep_labels(b)) for b in it[1:] if isinstance(b, list)]
        return set.intersection(*sets) if len(sets) >= 2 else set()
    if k == Item.IF and len(it) == 4 and isinstance(it[2], list) and isinstance(it[3], list):
        return names(deep_labels(it[2])) & names(deep_labels(it[3]))
    return set()


def columns(items: list[Node]) -> frozenset[str]:
    """A body's columns: its top-level labels, with what its `OR` and `IF`
    forms export."""
    cols: set[str] = set()
    for it in items:
        if not isinstance(it, list) or not it or not is_sym(it[0]):
            continue
        if item_kind(it) in (Item.ATOM, Item.OP, Item.ONE):
            cols |= names(item_labels(it))
        else:
            cols |= exported(it)
    return frozenset(cols)


def key_labels(x: Node) -> tuple[str, ...]:
    """The `^` labels of a key clause, each once, in the order of the
    text."""
    found: list[str] = []
    for s in flat(x):
        if s.startswith("^") and strip(s) not in found:
            found.append(strip(s))
    return tuple(found)


def bodies(stem: str, tree: list[Node]) -> list[Body]:
    """Each body of the arclog file `tree`, in the order of the text."""
    found: list[Body] = []

    def add(kind: Kind, name: str, items: list[Node], f: list[Node], stack: tuple[Frame, ...],
            keycols: tuple[str, ...] = (), heads: tuple[tuple[str, str], ...] = ()) -> None:
        component = str(f[2]) if f[0] == "INIT" else None
        found.append(Body(stem, kind, name, items, heads, keycols, str(f[0]), component, stack))

    def add_input(f: list[Node], inp: list[Node], keycols: tuple[str, ...],
                  stack: tuple[Frame, ...]) -> None:
        sites = inp[1] if len(inp) > 1 and isinstance(inp[1], list) else []
        heads = tuple(p for s in sites for p in site_pairs(s))
        add(Kind.INPUT, f"{f[1]}.{inp[0]}", inp[2:], f, stack, keycols, heads)

    def walk(forms: list[Node], stack: tuple[Frame, ...]) -> None:
        for f in forms:
            h = head(f)
            if h is None:
                continue
            assert isinstance(f, list)
            if h == "ALTS":
                default = f[3] if len(f) > 3 and is_sym(f[3]) else None
                walk(f[1:], (*stack, Frame(h, str(f[1]), None if default is None else str(default))))
            elif h == "ALT":
                walk(f[2:], (*stack, Frame(h, str(f[1]))))
            elif h in BLOCKS:
                walk(f[1:], (*stack, Frame(h)))
            elif h in Kind.__members__ and Kind(h) in CLAUSES:
                add(Kind(h), str(f[1]), [x for x in f[2:] if is_list(x)], f, stack)
            elif h in ("INIT", "DEMONSTRATED"):
                for x in f[3:] if h == "INIT" else f[2:]:
                    if not isinstance(x, list) or not x:
                        continue
                    if x[0] == "key":
                        keyb = x[1] if isinstance(x[1], list) else []
                        keycols = key_labels(keyb)
                        add(Kind.KEY, str(f[1]), keyb, f, stack)
                        for inp in x[2:]:
                            if isinstance(inp, list) and inp:
                                add_input(f, inp, keycols, stack)
                    elif x[0] == "DEMO_RULE":
                        walk([x], stack)
                    else:
                        add_input(f, x, (), stack)
            elif h == "CHOOSE":
                for x in f[2:]:
                    if not isinstance(x, list) or not x:
                        continue
                    if x[0] == "for":
                        keyb = x[1] if isinstance(x[1], list) else []
                        keycols = key_labels(keyb)
                        add(Kind.KEY, str(f[1]), keyb, f, stack)
                        for inp in x[2:]:
                            if isinstance(inp, list) and inp:
                                add(Kind(str(inp[0])), str(f[1]), inp[1:], f, stack, keycols)
                    else:
                        add(Kind(str(x[0])), str(f[1]), x[1:], f, stack)

    walk(tree, ())
    return found
