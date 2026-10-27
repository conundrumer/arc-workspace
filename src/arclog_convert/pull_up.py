"""The pull-up pass on a converted program: it moves each unjoined factor of a
clause body into the clauses that join its columns, so that each clause body
is one connected join.

In a `RULE` or `DET` clause, the components of the body are its top-level
conjuncts grouped by the labels they share, and a `NOT` atom, a comparison, an
`OR` and an `IF` each count as one conjunct. A component other than the one
that stays is a factor. A factor moves where every reader of the clause's
relation either joins each column the factor holds, with a label that stands in
another conjunct of the reader's body, or reads none of them. On a move the
factor's atoms follow each joining reader's atom, at the reader's labels for
those columns and with fresh labels for the factor's other labels, the
reader's sites on those columns go, and the clause loses the factor. A factor
that is one atom, each label once, stays in the clause as an existence test,
with its label sites dropped, so that the relation holds no row where the factor
holds none; a factor that is no such atom moves only where every reader joins
it. The pass repeats until no factor moves, and leaves the text as it is where
none does.

A factor stays where moving it would rewrite a form the pass leaves as
written: the `&output` clause, a clause with a `ONE` or `SET` mark or a
comment, a `DET` whose rows the arcdata gives, a reader outside a `RULE` or
`DET` body or under `NOT`, `ALL` or the test of an `IF`; where a reader of
another kind (`docs/arclog/arclog.md#program`) would read a relation of the
factor that its kind may not read; and where the relation has several clauses.
It stays as well where it is a broadcast: each atom of the component reads at
most one distinct row of its relation, over the columns the atom reads, on
each pair of the cases that `parity.rerun.cases_to_run` gives (`Single`).

`Pulled.blocked` says whether a rule on blocks keeps a factor in the last scan of the
pass: the factor's relation has clauses in more than one block, or a reader of it stands in an `ALT` block, is a line
of two readings (`READINGS`), or derives a relation that a deeper block derives again (it reads nothing in a case that
holds that block), or the factor's clause is a line of two readings. A factor so kept may move in the flat program of
a case, where each relation has one deriving form and no `ALT` block stands."""

import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from engine import Rows as EngineRows
from arclog_convert.lib import REGISTRY
from arclog_convert.lint import (
    FACTS, FORMS, LIB, MARKS, OPS, L, Linter, Placed, Sym, bare_label, form_labels, is_const, placements, read, walk)

BODIES = ("RULE", "DET")
"""The clauses with a body that the pass reads and rewrites."""
READINGS = ("RULE_OR_DET", "DET_OR_RULE")
"""The lines that are an `ALTS` form on their relation, whose two readings are a case's (`docs/arclog/arclog.md#alts`)."""
OUTPUT = "&output"
FINITE = frozenset(re.findall(r"^\(relation (\w+) \(columns \(\w+ (?:[\w-]+|\([^()]*\))\)\)\)$",
                              REGISTRY.read_text(), re.M))
"""The lib relations of one column that `engine/lib/registry.sexpr` declares with no `modes` form: a relation over
a finite domain."""
WHOLE = -1
"""The index of a level of a `Reader`'s chain whose list holds no item of the chain."""

type Single = Callable[[str, frozenset[str]], bool]
"""Whether the arclog relation, by its name, has at most one distinct row over
the arclog columns on each pair of the cases of `parity.rerun.cases_to_run`
at the solver's stored parameters; false where the rows are unknown."""

type Edit = tuple[int, int, str]
"""The text from the first offset to the second, replaced."""

type Chain = tuple[tuple[list, int], ...]
"""The lists from a clause's body down to an atom's, each with the index of the item that holds the atom."""


@dataclass(frozen=True)
class Pulled:
    """The text after the pass, and for each relation it moved a factor out of, the arclog columns the moves took away."""

    arclog: str
    dropped: Mapping[str, frozenset[str]]
    blocked: bool
    """Whether a rule on blocks keeps a factor in the text."""


@dataclass(frozen=True)
class Site:
    """A site of an atom: its column, its label (none where it holds a constant or several labels), the label's mark and the site's node."""

    column: str
    label: str | None
    mark: str
    node: Sym | L


@dataclass(frozen=True)
class Reader:
    """An atom that reads a relation, with the `RULE`, `DET` or `INIT` clause whose body holds it where the pass can
    rewrite the atom (none elsewhere), and the lists from the clause's body down to the atom's, each with the index of
    the item that holds the atom (`WHOLE` for the key clause's body above an input inside the key clause). Where
    the atom stands under a `NOT`, `negation` is the number of those lists down to the one that holds the `NOT`."""

    atom: L
    clause: L | None
    chain: Chain
    negation: int | None = None

    def joined(self) -> frozenset[str]:
        """The labels of the items beside the atom's at each level."""
        return frozenset().union(*(_labels(x) for x in _beside(self.chain)))

    def conjuncts(self) -> Iterator[L]:
        """The items beside the atom's at each level outside the `NOT` the atom stands under."""
        return _beside(self.chain if self.negation is None else self.chain[:self.negation])


@dataclass(frozen=True)
class _Plan:
    edits: list[Edit]
    gone: frozenset[str]


def _labels(x: L) -> frozenset[str]:
    return frozenset(bare_label(t) for t in form_labels(x))


def _beside(levels: Chain) -> Iterator[L]:
    """The items that are lists, beside the item that holds the atom at each of `levels`."""
    for items, i in levels:
        yield from (x for j, x in enumerate(items) if j != i and isinstance(x, L))


def atom_sites(atom: L) -> dict[str, Site] | None:
    """The sites of `atom` by column; none where a site has a shape the pass does not read."""
    out: dict[str, Site] = {}
    for node in atom.items[1:]:
        if isinstance(node, Sym) and not is_const(node.text):
            column = bare_label(node.text)
            out[column] = Site(column, column, node.text[:len(node.text) - len(column)], node)
        elif isinstance(node, L) and node.head and node.head.startswith(":"):
            args = node.items[1:]
            one = args[0] if len(args) == 1 and isinstance(args[0], Sym) and not is_const(args[0].text) else None
            label = None if one is None else bare_label(one.text)
            out[node.head[1:]] = Site(node.head[1:], label, "" if one is None else one.text[:len(one.text) - len(label or "")], node)
        else:
            return None
    return out


def _items(clause: L) -> list[L] | None:
    """The conjuncts of the body of `clause`; none where it has no body, a proposer, a gloss or a mark."""
    body = clause.items[2:]
    if not body or any(not isinstance(x, L) or x.head in MARKS for x in body):
        return None
    return body


def _components(items: list[L]) -> list[list[int]]:
    """The indexes of the conjuncts grouped by shared labels, each group in order, the groups by first index."""
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner: dict[str, int] = {}
    for i, item in enumerate(items):
        for label in sorted(_labels(item)):
            parent[find(i)] = find(owner.setdefault(label, i))
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(items)):
        groups[find(i)].append(i)
    return sorted(groups.values())


def _atoms(x: L) -> Iterator[L]:
    """Each atom in `x`, at any depth."""
    if x.head in OPS:
        return
    if x.head is None or x.head in FORMS:
        for y in x.items:
            if isinstance(y, L):
                yield from _atoms(y)
    else:
        yield x


def _readable(group: list[L], producer: str, reader: str) -> bool:
    """Whether a clause of kind `reader` may read what `group`, from a clause of kind `producer`, reads: a clause
    of another kind reads the lib's relations alone."""
    return producer == reader or all(a.head not in FACTS and not str(a.head).startswith("&") for x in group
                                     for a in _atoms(x))


def _single(group: list[L]) -> L | None:
    """The atom that `group` is, where it is one atom."""
    return group[0] if len(group) == 1 and group[0].head is not None and group[0].head not in FORMS | OPS else None


def _existence_test(group: list[L]) -> L | None:
    """The atom of `group` where it is one atom with each label once and every label at a site of its own."""
    atom = _single(group)
    found = None if atom is None else atom_sites(atom)
    if atom is None or found is None or any(s.label is None and form_labels(s.node) for s in found.values()):
        return None
    labels = form_labels(atom)
    return atom if len(set(labels)) == len(labels) else None


def applied(text: str, edits: list[Edit]) -> str:
    """`text` with the non-overlapping `edits` made."""
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def _cut(text: str, node: Sym | L) -> Edit:
    """The edit that removes `node` with the white space before it."""
    start, end = (node.pos, node.pos + len(node.text)) if isinstance(node, Sym) else (node.start, node.end)
    while text[start - 1].isspace():
        start -= 1
    return start, end, ""


def readers(clause: L) -> Iterator[Reader]:
    """Each atom under `clause` that reads a relation by a name with `&`."""
    bodies = _bodies(clause)
    if bodies is None:
        yield from (Reader(a, None, ()) for a in walk(clause) if isinstance(a, L) and str(a.head).startswith("&"))
    else:
        for items, above in bodies:
            yield from _body_readers(clause, items, above, True, None)


def _bodies(clause: L) -> list[tuple[list, Chain]] | None:
    """The bodies of `clause` that the pass reads, each with the levels above it; none where it reads no body."""
    if clause.head in BODIES:
        body = _items(clause)
        return None if body is None else [(body, ())]
    if clause.head != "INIT":
        return None
    clauses = clause.items[3:]
    if not all(isinstance(c, L) and len(c.items) > 1 and isinstance(c.items[1], L) for c in clauses):
        return None
    out: list[tuple[list, Chain]] = []
    for c in clauses:
        if c.head == "key":
            out.append((c.items[1].items, ()))
            out += [(x.items[2:], ((c.items[1].items, WHOLE),)) for x in c.items[2:] if isinstance(x, L)]
        else:
            out.append((c.items[2:], ()))
    return out


def _body_readers(clause: L, items: list, above: Chain, rewritable: bool,
                  negation: int | None) -> Iterator[Reader]:
    for i, item in enumerate(items):
        if not isinstance(item, L):
            continue
        level = (*above, (items, i))
        head = item.head
        if head in OPS:
            continue
        if head is None:
            yield from _body_readers(clause, item.items, level, rewritable, negation)
        elif head == "OR":
            for branch in item.items[1:]:
                if isinstance(branch, L):
                    yield from _body_readers(clause, branch.items, level, rewritable, negation)
        elif head == "IF":
            for k, part in enumerate(p for p in item.items[1:] if isinstance(p, L)):
                yield from _body_readers(clause, part.items, level, rewritable and k > 0, negation)
        elif head == "NOT" and negation is None:
            yield from _body_readers(clause, item.items[1:], level, rewritable, len(level))
        elif head in FORMS:
            yield from _body_readers(clause, item.items[1:], level, False, negation)
        elif head.startswith("&"):
            yield Reader(item, clause if rewritable else None, level, negation)


def readers_by_relation(placed: list[Placed]) -> dict[str, list[tuple[Reader, Placed]]]:
    """Each atom under a placed form that reads a relation by a name with `&`, once, with the form, by the name."""
    out: dict[str, list[tuple[Reader, Placed]]] = defaultdict(list)
    seen: set[int] = set()
    for p in placed:
        for r in readers(p.form):
            if r.atom.start not in seen:
                seen.add(r.atom.start)
                out[str(r.atom.head)].append((r, p))
    return out


def given_rows(arcdata: str) -> frozenset[str]:
    """The relations whose rows the arcdata gives: a `param` form's, and a witness's `assign`."""
    return frozenset(x.items[1].text for f in read(arcdata) for x in walk(f)
                     if isinstance(x, L) and x.head in ("param", "assign") and len(x.items) > 1
                     and isinstance(x.items[1], Sym))


def _renamed(text: str, group: list[L], new: Mapping[str, tuple[str, bool]], star: frozenset[str]) -> list[str]:
    """The text of each item of `group` with each label that `new` names replaced by its new label, whose `*` mark
    stays where the pair's flag holds; a site elided to its label is written out (a one-label site on `key` is a field of the
    key's record, elided), and a site whose label becomes
    its column's name is elided. Each label of `star` gets one `*` mark in the group."""
    edits: list[list] = []   # the item's index, the node's span, the label it replaces, its new text

    def visit(k: int, x: L) -> None:
        elided = x.head is not None and (x.head.startswith(":") and (len(x.items) > 2 or x.head == ":key")
                                         or not x.head.startswith(":") and x.head not in FORMS | OPS)
        for i, y in enumerate(x.items):
            if isinstance(y, L):
                visit(k, y)
            elif isinstance(y, Sym) and not (i == 0 and x.head is not None) and not is_const(y.text):
                label = bare_label(y.text)
                if label not in new:
                    continue
                mark = "*" if y.text.startswith("*") and new[label][1] else ""
                span = (y.pos, y.pos + len(y.text))
                if x.head is not None and x.head.startswith(":") and len(x.items) == 2 and new[label][0] == x.head[1:]:
                    span = (x.start, x.end)   # (:C *C) elides to *C
                edits.append([k, span, label, mark, f"(:{label} {{}})" if elided and new[label][0] != label else "{}"])
    for k, item in enumerate(group):
        visit(k, item)
    made = {new[e[2]][0] for e in edits if e[3]}
    for e in edits:
        if new[e[2]][0] in star and new[e[2]][0] not in made:
            made.add(new[e[2]][0])
            e[3] = "*"
    out = []
    for k, item in enumerate(group):
        snippet = text[item.start:item.end]
        for _, (start, end), label, mark, shape in sorted((e for e in edits if e[0] == k), key=lambda e: e[1], reverse=True):
            snippet = snippet[:start - item.start] + shape.format(mark + new[label][0]) + snippet[end - item.start:]
        out.append(snippet)
    return out


def _dropped(text: str, sites: dict[str, Site], columns: frozenset[str]) -> list[Edit]:
    """The edits that remove the sites of `columns` from an atom."""
    return [_cut(text, sites[c].node) for c in sorted(columns)]


def _holds(reader: Reader, sites: dict[str, Site], group: list[L], columns: frozenset[str]) -> bool:
    """Whether `group` is one atom and an item beside the atom of `reader` outside any `NOT` it stands under reads
    the same relation, with the reader's label at each of `columns` and a site at each other column of the atom.
    False where a site of the reader on `columns` makes its label (`*`), which the reader's loss of the site would
    leave unbound for the item."""
    atom = _single(group)
    found = None if atom is None else atom_sites(atom)
    if atom is None or found is None or any(sites[c].mark == "*" for c in columns):
        return False
    for x in reader.conjuncts():
        have = atom_sites(x) if x.head == atom.head else None
        if have is not None and all(
                s.label is not None and (s.column in have and (s.label not in columns
                                                               or have[s.column].label == sites[s.label].label))
                for s in found.values()):
            return True
    return False


def _aligned(text: str, pos: int) -> str:
    """The white space as wide as the text from the start of the line to `pos`."""
    return " " * (pos - (text.rfind("\n", 0, pos) + 1))


def _indented(text: str, item: L, snippet: str, indent: str) -> str:
    """`snippet`, the text of `item`, with the lines after its first moved to `indent`."""
    start = text.rfind("\n", 0, item.start) + 1
    line = text[start:item.start]
    base = len(line) - len(line.lstrip())
    lines = snippet.split("\n")
    return "\n".join([lines[0]] + [" " * (len(indent) + max(len(x) - len(x.lstrip()) - base, 0)) + x.lstrip()
                                  for x in lines[1:]])


class _Program:
    """A program text with what a move reads of it."""

    def __init__(self, text: str, given: frozenset[str], single: Single):
        self.text, self.given, self.single = text, given, single
        forms = read(text)
        self.placed = placements(forms)
        linter = Linter(Path("-"), text)
        linter.run()
        self.columns = linter.cols
        self.broadcast = {line for line, code, _ in linter.errs if code == "broadcast-inside"}
        self.declared = Counter(p.name for p in self.placed if p.name)
        by_relation = readers_by_relation(self.placed)
        self.readers: dict[str, list[Reader]] = defaultdict(list, {name: [r for r, _ in found] for name, found in by_relation.items()})
        self.blocks: dict[str, set[tuple[str, ...]]] = defaultdict(set)
        for p in self.placed:
            if p.name:
                self.blocks[p.name].add(tuple(sorted(p.alts)))
        self.read_in_block = {name for name, found in by_relation.items() if any(
            placed.alts or placed.form.head in READINGS or len(self.blocks[str(placed.name)]) > 1 for _, placed in found)}
        self.blocked = False

    def move(self) -> tuple[str, str, frozenset[str]] | None:
        """The text after the first move of a factor, the relation it left and the columns that took away, none where
        no factor moves; `blocked` says, once a scan has found none, whether a rule on blocks kept a factor."""
        self.blocked = False
        for p in self.placed:
            clause = p.form
            if clause.head in READINGS:
                self.blocked |= len(_components([x for x in clause.items[2:] if isinstance(x, L)])) > 1
            if not self._editable(clause):
                continue
            items = _items(clause)
            assert items is not None
            comps = _components(items)
            if self.declared[str(p.name)] != 1:
                self.blocked |= len(comps) > 1 and len(self.blocks[str(p.name)]) > 1
                continue
            plans = [self._plan(clause, items, [items[i] for i in comp]) for comp in comps]
            self.blocked |= len(comps) > 1 and None in plans and str(p.name) in self.read_in_block
            moving = [plan for plan in plans if plan is not None]
            if len(moving) == len(plans):
                moving = moving[1:]
            moving = [plan for plan in moving if plan.edits]
            if moving:
                return applied(self.text, moving[0].edits), str(p.name), moving[0].gone
        return None

    def relocated(self) -> str | None:
        """The text after the first move of an input out of the key clause of an `INIT` that holds no comment, where
        the lint finds that it reads no key label and no output of its instance: the input stands after the key
        clause, after the last input that stands there and that the component declares before it. None where no
        input moves."""
        for p in self.placed:
            form = p.form
            if form.head != "INIT" or not self._plain(form) or len(form.items) < 4:
                continue
            comp = form.items[2].text if isinstance(form.items[2], Sym) else None
            clauses = [c for c in form.items[3:] if isinstance(c, L)]
            if comp not in LIB.comps or not clauses or clauses[0].head != "key":
                continue
            order = [r.name for r in LIB.relations(comp)[1] if r.is_input]
            key = clauses[0]
            for x in key.items[2:]:
                if not isinstance(x, L) or x.line not in self.broadcast or x.head not in order:
                    continue
                after = [c for c in clauses[1:] if c.head in order and order.index(c.head) < order.index(x.head)]
                after_end = (after[-1] if after else key).end
                indent = _aligned(self.text, key.start)
                moved = _indented(self.text, x, self.text[x.start:x.end], indent)
                return applied(self.text, [_cut(self.text, x), (after_end, after_end, "\n" + indent + moved)])
        return None

    def _editable(self, clause: L) -> bool:
        """Whether `clause` is a `RULE` or `DET` with a body that the pass may rewrite."""
        return (clause.head in BODIES and _items(clause) is not None and len(clause.items) > 1
                and isinstance(clause.items[1], Sym) and clause.items[1].text not in {OUTPUT, *self.given}
                and self._plain(clause))

    def _plain(self, clause: L) -> bool:
        """Whether `clause` holds no comment."""
        return ";;" not in self.text[clause.start:clause.end]

    def _rewritable(self, clause: L) -> bool:
        """Whether the pass may rewrite a reader in `clause`: it is editable, or an `INIT` that holds no comment."""
        return self._editable(clause) or clause.head == "INIT" and self._plain(clause)

    def _plan(self, clause: L, items: list[L], group: list[L]) -> _Plan | None:
        """The edits that move `group`, a component of the body of `clause`, or none where it stays. A component with no
        label could move, and has no edit."""
        name, kind = clause.items[1].text, clause.head
        used = frozenset().union(*map(_labels, group))
        if not used:
            return _Plan([], frozenset())
        sites_of = [(r, atom_sites(r.atom)) for r in self.readers[name]]
        if any(sites is None for _, sites in sites_of):
            return None
        made = used & self.columns[name]
        read_by_some = frozenset().union(*(frozenset(sites) for _, sites in sites_of if sites is not None))
        columns = made if kind == "RULE" else made & read_by_some
        test = _existence_test(group)
        joins: list[tuple[Reader, dict[str, Site], bool]] = []   # each with whether its body holds the factor
        silent = not sites_of
        for r, sites in sites_of:
            assert sites is not None
            if not columns & sites.keys():
                silent = True
                continue
            if (columns - sites.keys() or r.clause is None or not self._rewritable(r.clause)
                    or any(sites[c].label is None or sites[c].label not in r.joined() or sites[c].mark == "^"
                           for c in columns)
                    or made - columns and r.clause.head == "RULE"):
                return None
            holds = _holds(r, sites, group, columns)
            if not holds and (r.negation is not None or not _readable(group, str(kind), str(r.clause.head))):
                return None
            joins.append((r, sites, holds))
        if (silent and test is None) or self._broadcast(group):
            return None
        edits: list[Edit] = []
        if test is not None and test.head not in FINITE:
            edits += [_cut(self.text, s.node) for s in (atom_sites(test) or {}).values() if s.label is not None]
        else:
            edits += [_cut(self.text, x) for x in group]
        taken: dict[int, set[str]] = {}
        for r, sites, holds in joins:
            assert r.clause is not None
            if holds:
                edits += _dropped(self.text, sites, columns)
            else:
                edits += self._copy(r, sites, group, columns, used,
                                    taken.setdefault(r.clause.start, set(_labels(r.clause))))
        return _Plan(edits, made)

    def _copy(self, reader: Reader, sites: dict[str, Site], group: list[L], columns: frozenset[str],
              used: frozenset[str], taken: set[str]) -> list[Edit]:
        """The edits that drop the sites of `columns` from the atom of `reader` and write `group` after it, each
        item on a line of its own at the column of the atom, its labels of `columns` as the reader's, and its other
        labels fresh, in the `taken` labels of the reader's clause."""
        new = {c: (str(sites[c].label), sites[c].mark == "*") for c in columns}
        for label in sorted(used - columns):
            n = 2
            while f"{label}{n}" in taken:
                n += 1
            taken.add(f"{label}{n}")
            new[label] = (f"{label}{n}", True)
        star = frozenset(str(sites[c].label) for c in columns if sites[c].mark == "*")
        atom = reader.atom
        indent = _aligned(self.text, atom.start)
        written = "".join("\n" + indent + _indented(self.text, x, snippet, indent)
                          for x, snippet in zip(group, _renamed(self.text, group, new, star)))
        return [*_dropped(self.text, sites, columns), (atom.end, atom.end, written)]

    def _broadcast(self, group: list[L]) -> bool:
        """Whether every atom of `group` reads at most one distinct row (`Single`), and `group` holds an atom."""
        atoms = 0
        for x in group:
            if x.head in OPS or x.head == "NOT":
                continue
            found = None if x.head in FORMS else atom_sites(x)
            if found is None or not self.single(str(x.head), frozenset(found)):
                return False
            atoms += 1
        return atoms > 0


def pull_up(arclog: str, arcdata: str, single: Single) -> Pulled:
    """`arclog` after the pass, with the columns it took away from each relation and whether a rule on blocks kept a
    factor, given the `arcdata` of the same program and the rows `single` gives."""
    given = given_rows(arcdata)
    dropped: dict[str, set[str]] = defaultdict(set)
    while True:
        program = _Program(arclog, given, single)
        if (moved := program.move()) is not None:
            arclog, name, gone = moved
            dropped[name] |= gone
        elif (relocated := program.relocated()) is not None:
            arclog = relocated
        else:
            break
    return Pulled(arclog, {name: frozenset(gone) for name, gone in dropped.items()}, program.blocked)


def drop_columns(columns: Mapping[str, Mapping[str, object]], dropped: Mapping[str, frozenset[str]]
                 ) -> dict[str, dict[str, object]]:
    """The column map `columns` (`arclog_convert.names.column_map`) with the leaves that `dropped` gives, a set of
    labels for each relation, left out of its entries."""
    def kept(entry: object, gone: frozenset[str]) -> object:
        if isinstance(entry, dict):
            return {"writings": [{**w, "columns": kept(w["columns"], gone)} for w in entry["writings"]]}
        assert isinstance(entry, list)
        return [[leaf for leaf in column if leaf["label"] not in gone] for column in entry]
    return {name: {path: kept(entry, dropped.get(name, frozenset())) for path, entry in entries.items()}
            for name, entries in columns.items()}


class Rows:
    """Souffle's rows of one solver's relations on each pair of the cases that `parity.rerun.cases_to_run` gives,
    answering `Single`. Each call of `ask` runs those cases on every pair, outputs only the relations asked about,
    and keeps one flag for each question: no rows stay in memory. The runs stop at the first case after which every
    answer is no."""

    def __init__(self, stem: str, columns: Mapping[str, Mapping[str, object]]):
        self.stem, self.columns = stem, columns
        self.answers: dict[tuple[str, frozenset[str]], bool] = {}

    def single(self, relation: str, read: frozenset[str]) -> bool:
        """Whether `relation` has at most one distinct row over the arclog columns `read` on every pair of every case,
        and a row set in some case. False where the column map does not place a column of `read`."""
        if (relation, read) not in self.answers:
            self.ask({(relation, read)})
        return self.answers[relation, read]

    def ask(self, questions: set[tuple[str, frozenset[str]]]) -> None:
        """Answer `questions`, each a relation and the arclog columns read, that `single` has not answered."""
        from cli.common import solver_path
        from parity import case_name, relation_names, rerun
        from solver.pair_runs import examples
        asked = {q: leaves for q in questions - self.answers.keys() if (leaves := self._leaves(*q)) is not None}
        self.answers.update({q: False for q in questions - self.answers.keys() if q not in asked})
        seen = dict.fromkeys(asked, False)
        single = dict.fromkeys(asked, True)
        loaded = rerun.load_once(self.stem, solver_path(self.stem)) if asked else None
        if isinstance(loaded, rerun.Loaded):
            wanted = {relation for relation, _ in asked}
            souffle = [r for r in rerun.every_relation(loaded.eng, loaded.solver.program)
                       if wanted & set(relation_names(loaded.names, r))]
            for case in rerun.cases_to_run(loaded):
                taken = loaded.taking(case)
                held = {q: (seen[q], single[q]) for q in asked}
                for _, ex in examples(loaded.solver.given_task):
                    got = loaded.run(taken, case, ex, souffle)
                    if not isinstance(got, Mapping):
                        held = {q: (seen[q], single[q]) for q in asked}
                        break
                    by_name = {name: rows for r, rows in got.items() for name in relation_names(loaded.names, r)}
                    for q, leaves in asked.items():
                        if q[0] in by_name:
                            held[q] = (True, held[q][1] and self._distinct(by_name[q[0]], leaves) <= 1)
                else:
                    seen, single = {q: held[q][0] for q in asked}, {q: held[q][1] for q in asked}
                    if not any(single.values()):
                        break   # every answer is no
        self.answers.update({q: seen[q] and single[q] for q in asked})

    def _leaves(self, relation: str, read: frozenset[str]) -> list[tuple[int, tuple[int, ...]]] | None:
        """The Souffle column and the path in it of each leaf of `relation` that an arclog column of `read` holds;
        none where the column map has not one entry of columns for the relation or lacks a column of `read`."""
        entries = self.columns.get(relation, {})
        if len(entries) != 1:
            return None
        (entry,) = entries.values()
        if not isinstance(entry, list):
            return None
        leaves = [(j, tuple(leaf["leaf"]), leaf["label"]) for j, column in enumerate(entry) for leaf in column
                  if leaf["label"] in read and not leaf["example"]]
        return [(j, path) for j, path, _ in leaves] if {label for _, _, label in leaves} == read else None

    @staticmethod
    def _distinct(rows: EngineRows, leaves: list[tuple[int, tuple[int, ...]]]) -> int:
        """The distinct rows of `rows` over `leaves`; two where a row lacks a leaf."""
        from parity import rerun
        distinct = set()
        for row in rows:
            values = [rerun.leaves_at(row[j], path) for j, path in leaves]
            if any(v is None for v in values):
                return 2
            distinct.add(json.dumps(values))
        return len(distinct)
