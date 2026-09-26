"""A solver's branch models, and the names a witness file gives them.

A branch's model is what principles.md (Choice points) defines. A
choice point stands at `Choice` itself, at a field of a record-typed
`Choice`, or at a field of a constructor, where the field's type holds the
branches and its first constructor is the one the parent branch's model
takes.

A model is spelled as the run spells the case it emits, with the fields of
each constructor kept: `Recolor(Box, Size)`, `[Derived(Own), Cells]`.
`model_label` spells a run's variant name the same way, so a model's
outcome is read off the run by that spelling.

`CaseSpace.resolve` reads one name of a witness group, in the forms
docs/handbook/solver-file.md (Witness file) gives, and also a case written
out: `[A, B]`, the record of each field's constructor, or `Recolor(Box,
Size)`, a constructor applied to its fields' constructors. A constructor
with fields written without them makes the name the runner's label
(`case_label`), which stands for every case under that constructor, and
whose outcome is the first grid of those cases. The `Choice` forms are
tried in this order: `concept`, `A & B`, a written-out case, a
constructor, a slug. A name may join the name of a `@derive` or `@store`
line's branch (`<param>=<Proposer>`, `<rel>=stored`) to them with `&`, in
any order, and `<param>=stored`, the stored value at a `@derive` line's
point (`CaseSpace.branch_test`).

`enumeration` gives every case the runner holds for a solver: the held
`Choice` cases and, for each `@derive` and `@store` line, the cases that
take its branch.

A `Choice` no name spells in full falls back to `Coarse`, where a name, a
slug in CamelCase included, resolves to the runner's label of its case.

The verdict of a `@witness`, `@derive` or `@store` line reads as a name
does (`dl.witness.verdict_cases`).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations, product
from typing import NewType

from dl.annotations import (
    DERIVE,
    STORE,
    STORED,
    Branch,
    Ignore,
    branch_lines,
    ignore_lines,
)
from dl.dlparse import ParseError, TypeDecl, parse

CaseId = NewType("CaseId", str)
"""A case as the runner holds it: a case spelled in full
(`Recolor(Box, Size)`, `[Derived(Own), Cells]`), the runner's label of a
case (`case_label`), `NO_CHOICE`, or the name of a case that takes a
`@derive` or `@store` line's branch (`CaseSpace.case_id`). A name a
witness file writes is no case id until `resolve` reads it as one."""

CONCEPT = "concept"
"""The name of the concept case."""

NO_CHOICE = CaseId("(out)")
"""The case name of a solver without a `Choice`: `out` carries no case
column, and the whole file is one case."""

BRANCH_RE = re.compile(r"(\w+)\s*\{([^}]*)\}")
FIELD_TYPE_RE = re.compile(r"\w+\s*:\s*(\w+)")
RECORD_RE = re.compile(r"^=\s*\[(.*)\]\s*$", re.S)
SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
TERM_RE = re.compile(r"^\$?(\w+)\s*(?:\((.*)\))?$", re.S)

type Node = tuple[int, ...]
"""A choice point's place: the root's index, then the field index at each
constructor on the way down."""

type Forced = dict[Node, str]
"""The constructor a case takes at each node it fixes. Every other node
takes its type's first constructor."""


def model_label(name: str, resolution: bool = False) -> CaseId:
    """The case a run's variant name stands for, with each constructor's
    fields kept: `$Recolor($Box, $Size)` is `Recolor(Box, Size)`. `out` may
    carry columns past the case, and a resolution solver's last column is
    its `TiebreakResolution`; neither is part of the case."""
    parts = name.split("\t")
    if resolution:
        parts = parts[:-1]
    head = parts[0].strip() if parts else ""
    if not head:
        return NO_CHOICE
    head = head.replace("$", "").replace("()", "")
    return CaseId(re.sub(r"\s*,\s*", ", ", head))


def _ctor(text: str) -> str:
    """One constructor of a case name, without its `$` and its arguments."""
    return text.strip().removeprefix("$").split("(", 1)[0]


def _split(body: str) -> list[str]:
    """A record body split at the commas between its members. A comma inside
    a constructor's arguments stands inside that member."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def case_members(case: str) -> list[str]:
    """The constructors one case label stands for: the members of a record
    label, and otherwise the label itself."""
    if case.startswith("[") and case.endswith("]"):
        body = case[1:-1].strip()
        return [_ctor(m) for m in _split(body)] if body else []
    return [case]


def case_label(name: str, resolution: bool = False) -> CaseId:
    """The case a variant name stands for.

    `out` may carry columns past the case, tab-joined into the name. A
    resolution solver carries its `TiebreakResolution` term last, and that
    term is no case; what leads the name is. Every constructor of the name
    drops its `$` and its arguments: `$Ctor` and `$Ctor(args)` stand for
    `Ctor`, and a record case keeps its brackets and commas around the
    constructors it holds, `[Table, Lookup]`. A name with nothing left is
    the one case of a solver without a `Choice`.
    """
    parts = name.split("\t")
    if resolution:
        parts = parts[:-1]
    head = parts[0] if parts else ""
    if not head:
        return NO_CHOICE
    if head.startswith("[") and head.endswith("]"):
        return CaseId(f"[{', '.join(case_members(head))}]")
    return CaseId(_ctor(head))


def camel(slug: str) -> str:
    """A branch slug as a constructor name: `bbox-region` is `BboxRegion`."""
    return "".join(p[:1].upper() + p[1:] for p in slug.split("-"))


@dataclass(frozen=True)
class Site:
    """Where one constructor stands: the node whose type holds it, and the
    constructor each node above it takes on the way to it."""

    node: Node
    type: str
    ctor: str
    above: tuple[tuple[Node, str], ...]


@dataclass(frozen=True)
class HeldCase:
    """A case that takes one or more `@derive` or `@store` branches: the
    `Choice` case it takes elsewhere (`base`), spelled in full, and its
    branches in file order. `values` holds, for each store branch in that
    order, the finding whose value it stores (`dl.store.Found`)."""

    base: CaseId
    branches: tuple[Branch, ...]
    values: tuple = field(default=(), compare=False)


@dataclass(frozen=True)
class Drop:
    """One `@ignore: derive <name>` or `@ignore: store <name>` line: the
    branch it stands under, the case `<name>` denotes with that branch
    (`case`), the held cases it excludes (`cases`), and where it excludes
    none, why."""

    ignore: Ignore
    branch: Branch | None
    case: CaseId | None
    why: str = ""
    cases: tuple[CaseId, ...] = ()


class CaseSpace:
    """What each kind of case space shares: the names of the `@derive` and
    `@store` branches, and, once `enumeration` fills them, the held
    `Choice` cases (`plain`), the cases that take a branch (`runner`), the
    named ignore lines (`drops`), and the cases those lines exclude, each
    with the numbers of the lines that exclude it (`excluded`)."""

    lines: list[Branch]
    plain: list[CaseId]
    runner: dict[CaseId, HeldCase]
    drops: list[Drop]
    excluded: dict[CaseId, tuple[int, ...]]

    def _held_init(self) -> None:
        self.lines, self.plain, self.runner, self.drops = [], [], {}, []
        self.excluded = {}

    @property
    def concept(self) -> CaseId | None:
        raise NotImplementedError

    def _choice(self, name: str) -> CaseId | None:
        """The `Choice` case a name without a branch denotes."""
        raise NotImplementedError

    def held(self) -> list[CaseId]:
        """Every case the runner holds: the held `Choice` cases, then the
        cases that take a branch."""
        return self.plain + list(self.runner)

    def branch_parts(self, name: str
                     ) -> tuple[tuple[Branch, ...], frozenset[str]] | None:
        """What the parts of `<name> & <name>` that hold `=` give: the
        branches they name, in file order, and the parameters they keep at
        the stored value. A part that is a line's branch name gives that
        branch; `<param>=stored`, where `<param>` has a `@derive` line and
        no line's branch has that name, keeps `<param>` stored. None when a
        part is neither, or two parts give values at one point."""
        by_name = {b.name: b for b in self.lines}
        derived = {b.target for b in self.lines if b.kind == DERIVE}
        branches: set[Branch] = set()
        kept: set[str] = set()
        for part in (p.strip() for p in name.split("&")):
            if "=" not in part:
                continue
            target, _, reading = part.partition("=")
            if part in by_name:
                branches.add(by_name[part])
            elif reading == STORED and target in derived:
                kept.add(target)
            else:
                return None
        ordered = sorted(branches, key=lambda b: b.line)
        points = {(b.kind, b.target) for b in ordered}
        if len(points) != len(ordered) or any(
                (DERIVE, t) in points for t in kept):
            return None
        return tuple(ordered), frozenset(kept)

    def parse(self, name: str) -> tuple[CaseId, tuple[Branch, ...]] | None:
        """The `Choice` case and the branches a name gives. The parts of
        `<name> & <name>` that hold `=` give the branches, in any order
        (`branch_parts`); the rest give the `Choice` case, the concept case
        where no part does. A parameter a part keeps stored takes no branch,
        so it adds none. None when the parts that hold `=` give no case, or
        the rest denotes no case."""
        parts = [p.strip() for p in name.split("&")]
        if not any("=" in p for p in parts):
            base = self._choice(name.strip())
            return None if base is None else (base, ())
        named = self.branch_parts(name)
        if named is None:
            return None
        rest = [p for p in parts if "=" not in p]
        base = self._choice(" & ".join(rest)) if rest else self.concept
        return None if base is None else (base, named[0])

    def branch_test(self, name: str) -> Callable[[HeldCase], bool] | None:
        """Whether a held case takes what the parts of a name that hold `=`
        give: every branch they name, and no branch at the point of a
        parameter they keep stored (`branch_parts`). None when those parts
        give no case."""
        named = self.branch_parts(name)
        if named is None:
            return None
        branches, kept = named
        return lambda held: set(branches) <= set(held.branches) and not any(
            b.kind == DERIVE and b.target in kept for b in held.branches)

    def case_id(self, base: CaseId, branches: tuple[Branch, ...]) -> CaseId:
        """The id of the case that takes `branches` and the `Choice` case
        `base` elsewhere: `base` itself without a branch, and otherwise
        its name, the base's shortest name (none for the concept case)
        then the branch names in file order, joined by ` & `."""
        if not branches:
            return base
        head = [] if base == self.concept else [self.short_name(base)]
        return CaseId(" & ".join(head + [b.name for b in branches]))

    def matching(self, name: str,
                 runner: dict[CaseId, HeldCase]) -> list[CaseId] | None:
        """The cases of `runner` that take every branch a name lists: what
        the parts that hold `=` give (`branch_test`), and the `Choice` case
        or the constructors the rest gives (`_taking`). A full case name
        gives the one case it denotes. None when the name denotes no case
        (`parse`)."""
        test = self.branch_test(name)
        if test is None or self.parse(name) is None:
            return None
        takes = self._taking(
            [p.strip() for p in name.split("&") if "=" not in p])
        return [c for c, h in runner.items() if test(h) and takes(h.base)]

    def _taking(self, parts: list[str]) -> Callable[[CaseId], bool]:
        """Whether a held `Choice` case takes what the `Choice` parts of a
        name give: any case when there are none, and otherwise the case
        they denote."""
        if not parts:
            return lambda _base: True
        case = self._choice(" & ".join(parts))
        return lambda base: base == case

    def denoted(self, name: str) -> CaseId | None:
        """The case a name denotes, whether or not the runner holds it."""
        parsed = self.parse(name)
        return None if parsed is None else self.case_id(*parsed)

    def resolve(self, name: str) -> CaseId | None:
        """The case a witness group's name denotes: a `Choice` case spelled
        as `spell` spells it, or a case that takes a branch, when the
        runner holds it; None when it denotes neither."""
        parsed = self.parse(name)
        if parsed is None:
            return None
        case = self.case_id(*parsed)
        return case if not parsed[1] or case in self.runner else None

    def short_name(self, case: CaseId) -> str:
        """The name of a case: the case itself."""
        return case

    def name_of(self, case: CaseId) -> str:
        """The name a finding gives a case: `concept` for the concept case,
        and its shortest name otherwise."""
        return CONCEPT if case == self.concept else self.short_name(case)

    def _stand_ins(self, case: CaseId,
                   held: list[CaseId] | None) -> list[CaseId]:
        """The held `Choice` cases that stand for a `Choice` case: the case
        itself."""
        return [case]

    def stand_ins(self, name: str,
                  held: list[CaseId] | None) -> list[CaseId]:
        """The held cases that stand for the case a name denotes
        (`denoted`); a case id is such a name. `held` holds the `Choice`
        cases the solver holds, spelled in full, and is None when every
        case is held. A `Choice` case gives way as `Space._stand_ins` gives.
        A case that takes a branch the runner does not hold gives way to the
        held cases that take what the name's parts that hold `=` give
        (`branch_test`), at the `Choice` cases that stand for its own among
        theirs, with the fewest branches beside its own."""
        parsed = self.parse(name)
        if parsed is None:
            return self._stand_ins(CaseId(name), held)
        if not parsed[1]:
            return self._stand_ins(
                parsed[0] if "=" in name else CaseId(name), held)
        case = self.case_id(*parsed)
        if case in self.runner:
            return [case]
        base = parsed[0]
        test = self.branch_test(name)
        assert test is not None
        taking = [(c, h) for c, h in self.runner.items() if test(h)]
        bases = self._stand_ins(base, list(dict.fromkeys(
            h.base for _c, h in taking)))
        found = [(len(h.branches), c) for c, h in taking if h.base in bases]
        if not found:
            return []
        least = min(n for n, _c in found)
        return [c for n, c in found if n == least]


@dataclass
class Space(CaseSpace):
    """The cases one solver's `Choice` spells.

    `types` holds each ADT the `Choice` reaches, its constructors in
    declaration order, each with its field types. `roots` holds the type at
    each root node: `Choice` itself, or each field of a record `Choice`.
    `sites` holds each constructor's places, in the order the choice points
    stand; a type that is the field of more than one constructor stands at
    more than one place."""

    record: bool
    roots: list[str]
    types: dict[str, dict[str, list[str]]]
    sites: dict[str, list[Site]] = field(default_factory=dict)
    _short: dict[CaseId, str] = field(default_factory=dict, repr=False,
                                      compare=False)

    def __post_init__(self) -> None:
        self._held_init()
        queue: list[tuple[Node, str, tuple[tuple[Node, str], ...],
                          tuple[str, ...]]] = [
            ((i,), t, (), (t,)) for i, t in enumerate(self.roots)]
        while queue:
            node, typ, above, chain = queue.pop(0)
            for ctor, fts in self.types[typ].items():
                self.sites.setdefault(ctor, []).append(
                    Site(node, typ, ctor, above))
                for j, ft in enumerate(fts):
                    if ft in self.types and ft not in chain:
                        queue.append((node + (j,), ft,
                                      above + ((node, ctor),), chain + (ft,)))

    def spell(self, forced: Forced) -> CaseId | None:
        """The case that takes the forced constructors and each type's
        first constructor at every other node. None when a constructor on
        the way has a field whose type holds no branches, which no name
        spells."""
        def term(node: Node, typ: str, chain: tuple[str, ...]) -> str | None:
            ctor = forced.get(node) or next(iter(self.types[typ]))
            subs: list[str] = []
            for j, ft in enumerate(self.types[typ][ctor]):
                if ft not in self.types or ft in chain:
                    return None
                sub = term(node + (j,), ft, chain + (ft,))
                if sub is None:
                    return None
                subs.append(sub)
            return f"{ctor}({', '.join(subs)})" if subs else ctor

        parts: list[str] = []
        for i, t in enumerate(self.roots):
            part = term((i,), t, (t,))
            if part is None:
                return None
            parts.append(part)
        return CaseId(f"[{', '.join(parts)}]" if self.record else parts[0])

    @property
    def concept(self) -> CaseId | None:
        return self.spell({})

    def cases(self) -> list[CaseId]:
        """Every case, each combination of constructors at every node,
        spelled as `spell` spells one. Empty when a constructor on the way
        has a field whose type holds no branches."""
        def terms(typ: str, chain: tuple[str, ...]) -> list[str]:
            out: list[str] = []
            for ctor, fts in self.types[typ].items():
                if any(ft not in self.types or ft in chain for ft in fts):
                    return []
                subs = [terms(ft, chain + (ft,)) for ft in fts]
                out += [f"{ctor}({', '.join(c)})" if c else ctor
                        for c in product(*subs)]
            return out

        parts = [terms(t, (t,)) for t in self.roots]
        if not self.record:
            return [CaseId(c) for c in parts[0]] if parts else []
        return [CaseId(f"[{', '.join(c)}]") for c in product(*parts)]

    def _sites(self, name: str) -> list[Site]:
        """The places of the constructor a name gives, verbatim or as a
        slug."""
        if name in self.sites:
            return self.sites[name]
        if SLUG_RE.match(name):
            return self.sites.get(camel(name), [])
        return []

    def _placings(self, names: list[str]) -> list[Forced]:
        """The nodes each choice of places for the named constructors
        fixes, one per choice at which the constructors on the way to each
        agree, in the order the places stand."""
        places = [self._sites(n.strip()) for n in names]
        if not all(places):
            return []
        out: list[Forced] = []
        for combo in product(*places):
            forced: Forced = {}
            if all(forced.setdefault(node, ctor) == ctor
                   for site in combo
                   for node, ctor in (*site.above, (site.node, site.ctor))):
                out.append(forced)
        return out

    def _conjunction(self, names: list[str]) -> CaseId | None:
        """The case with each named branch: the first choice of places at
        which the constructors on the way to each agree."""
        placings = self._placings(names)
        return self.spell(placings[0]) if placings else None

    def _taking(self, parts: list[str]) -> Callable[[CaseId], bool]:
        """Whether a held `Choice` case takes what the `Choice` parts of a
        name give. Constructor names give each case that takes every one of
        them, at some choice of places `_placings` gives; `concept` and a
        case written out give the one case they denote."""
        if (not parts or len(parts) == 1 and (
                parts[0] == CONCEPT or parts[0].startswith("[")
                or "(" in parts[0])):
            return super()._taking(parts)
        placings = self._placings(parts)

        def takes(base: CaseId) -> bool:
            nodes = self.nodes(base)
            return nodes is not None and any(
                all(nodes.get(n) == c for n, c in forced.items())
                for forced in placings)
        return takes

    def _term(self, text: str, node: Node, typ: str, forced: Forced,
              bare: list[str]) -> bool:
        """Put the constructor a written term names at `node`, and its
        written fields below it; a constructor with fields written without
        them goes into `bare`. False when the term is not one of `typ`."""
        m = TERM_RE.match(text.strip())
        if m is None or m.group(1) not in self.types.get(typ, {}):
            return False
        ctor, args = m.group(1), m.group(2)
        forced[node] = ctor
        fts = self.types[typ][ctor]
        if not args or not args.strip():
            if fts:
                bare.append(ctor)
            return True
        members = _split(args)
        if len(members) != len(fts):
            return False
        return all(self._term(a, node + (j,), ft, forced, bare)
                   for j, (a, ft) in enumerate(zip(members, fts, strict=True)))

    def _written(self, name: str) -> CaseId | None:
        """A case written out: a record of constructors, or a constructor
        applied to its fields' constructors. A constructor with fields
        written without them makes the name the runner's label, which
        stands for every case under that constructor."""
        forced: Forced = {}
        bare: list[str] = []
        text = name.strip()
        if text.startswith("["):
            body = text[1:-1]
            members = _split(body) if body.strip() else []
            if not self.record or len(members) != len(self.roots):
                return None
            ok = all(self._term(m, (i,), t, forced, bare)
                     for i, (m, t) in enumerate(
                         zip(members, self.roots, strict=True)))
        else:
            m = TERM_RE.match(text)
            sites = self.sites.get(m.group(1), []) if m else []
            if not sites:
                return None
            site = sites[0]
            forced.update(site.above)
            ok = self._term(text, site.node, site.type, forced, bare)
        if not ok:
            return None
        return case_label(text) if bare else self.spell(forced)

    def _choice(self, name: str) -> CaseId | None:
        """The case a name without a branch denotes, spelled as `spell`
        spells it; None when it denotes none."""
        if name == CONCEPT:
            return self.concept
        if "&" in name:
            return self._conjunction(name.split("&"))
        if name.strip().startswith("[") or "(" in name:
            return self._written(name)
        return self._conjunction([name])

    def nodes(self, case: CaseId) -> Forced | None:
        """The constructor a case spelled in full takes at each node, the
        nodes that take their type's first constructor included. None when
        the text spells no case in full."""
        forced: Forced = {}
        bare: list[str] = []
        text = case.strip()
        if self.record:
            if not (text.startswith("[") and text.endswith("]")):
                return None
            members = _split(text[1:-1]) if text[1:-1].strip() else []
            if len(members) != len(self.roots):
                return None
            ok = all(self._term(m, (i,), t, forced, bare)
                     for i, (m, t) in enumerate(
                         zip(members, self.roots, strict=True)))
        else:
            ok = bool(self.roots) and self._term(
                text, (0,), self.roots[0], forced, bare)
        return forced if ok and not bare else None

    def _first(self, ctor: str) -> bool:
        """The constructor is its type's first."""
        typ = self.sites[ctor][0].type
        return ctor == next(iter(self.types[typ]))

    def _departures(self, forced: Forced) -> list[tuple[Node, str]]:
        """The nodes whose constructor is not its type's first, with that
        constructor, in the order the choice points stand."""
        return sorted(((n, c) for n, c in forced.items()
                       if not self._first(c)),
                      key=lambda nc: (len(nc[0]), nc[0]))

    def required(self, site: Site) -> Forced:
        """The nodes a case fixes to take a constructor at one of its
        places: that place, and each node on the way to it."""
        return dict(site.above) | {site.node: site.ctor}

    def nearest(self, required: Forced, cases: list[CaseId]) -> list[CaseId]:
        """The cases of `cases` that take the required constructors and
        differ from the concept case at the fewest choice points. A choice
        point differs when it takes a constructor other than its type's
        first. Ties keep every case, in the order `cases` gives them."""
        found: list[tuple[int, CaseId]] = []
        for case in cases:
            forced = self.nodes(case)
            if forced is None or any(forced.get(n) != c
                                     for n, c in required.items()):
                continue
            found.append((len(self._departures(forced)), case))
        if not found:
            return []
        least = min(d for d, _ in found)
        return [c for d, c in found if d == least]

    def _stand_ins(self, case: CaseId,
                   held: list[CaseId] | None) -> list[CaseId]:
        """The held cases that stand for `case`. `held` holds the cases the
        solver holds, spelled in full, and is None when every case is held.
        A case that is held, or that is not spelled in full, stands for
        itself. Any other case gives way to the nearest held cases
        (`nearest`) that take the constructors it takes where it differs
        from the concept case, and each constructor on the way to them."""
        forced = self.nodes(case)
        if held is None or case in held or forced is None:
            return [case]
        required: Forced = {}
        for node, _ctor in self._departures(forced):
            for depth in range(1, len(node) + 1):
                required[node[:depth]] = forced[node[:depth]]
        return self.nearest(required, held)

    def short_name(self, case: CaseId) -> str:
        """`_short_name`, kept per case."""
        if case not in self._short:
            self._short[case] = self._short_name(case)
        return self._short[case]

    def _short_name(self, case: CaseId) -> str:
        """The shortest name of a case spelled in full: `concept`, or the
        conjunction of the constructors at the choice points where it
        differs from the concept case, in the order the choice points
        stand. A case that conjunction does not resolve to is named by the
        case written out."""
        forced = self.nodes(case)
        if forced is None:
            return case
        ctors = [c for _, c in self._departures(forced)]
        name = " & ".join(ctors) if ctors else CONCEPT
        return name if self.resolve(name) == case else case

    def _site_name(self, site: Site) -> str:
        """The name of a constructor at one of its places. The first place
        takes the bare name, which resolves there. Any other place takes
        the conjunction with the constructor above it, or, when that
        resolves elsewhere, with every constructor on the way to it. A
        place at a second root of one type is named by the case written
        out."""
        if site is self.sites[site.ctor][0]:
            return site.ctor
        own = self.spell(dict(site.above) | {site.node: site.ctor}) or ""
        if not site.above:
            return own
        name = f"{site.above[-1][1]} & {site.ctor}"
        if self._conjunction(name.split("&")) == own:
            return name
        return " & ".join([c for _, c in site.above] + [site.ctor])

    def models(self) -> dict[str, CaseId]:
        """Each branch model by its name: `concept`, then one model per
        constructor per place, for each constructor that is not its type's
        first, in the order the choice points stand. A choice point under a
        branch is its own point (principles.md, Choice points), so a type
        that is the field of more than one constructor gives a model at
        each place; `_site_name` names them."""
        return {name: label for name, label, _ in self.model_sites()}

    def model_sites(self) -> list[tuple[str, CaseId, Site | None]]:
        """Each branch model as `models` gives it, with the place of the
        constructor it takes; None for the concept case."""
        out: list[tuple[str, CaseId, Site | None]] = []
        if (c := self.concept) is not None:
            out.append((CONCEPT, c, None))
        for ctor, sites in self.sites.items():
            for site in sites:
                if ctor == next(iter(self.types[site.type])):
                    continue
                label = self.spell(self.required(site))
                if label is not None:
                    out.append((self._site_name(site), label, site))
        return out


class NoChoice(CaseSpace):
    """The case space of a solver without a `Choice`: the one case."""

    def __init__(self) -> None:
        self._held_init()

    @property
    def concept(self) -> CaseId:
        return NO_CHOICE

    def _choice(self, name: str) -> CaseId | None:
        return NO_CHOICE if name in (CONCEPT, NO_CHOICE, "") else None

    def models(self) -> dict[str, CaseId]:
        return {CONCEPT: NO_CHOICE}


class Coarse(CaseSpace):
    """The case space of a solver whose `Choice` no name spells in full, as
    when a field's type holds no branches: a name resolves to the case of
    the runner's label, a slug to that of its constructor in CamelCase, and
    the models are the cases the solver states."""

    def __init__(self, cases: list[CaseId], concept: CaseId | None) -> None:
        self.cases = cases
        self._concept = concept
        self._held_init()

    @property
    def concept(self) -> CaseId | None:
        return self._concept or None

    def _choice(self, name: str) -> CaseId | None:
        if name == CONCEPT:
            return self.concept
        label = case_label(camel(name) if SLUG_RE.match(name) else name)
        return label if label in self.cases else None

    def models(self) -> dict[str, CaseId]:
        return {c: c for c in self.cases}


type Cases = Space | NoChoice | Coarse


def _adts(items) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for it in items:
        if isinstance(it, TypeDecl) and it.branches:
            fields = {m.group(1): FIELD_TYPE_RE.findall(m.group(2))
                      for m in BRANCH_RE.finditer(it.rhs)}
            out[it.name] = {b: fields.get(b, []) for b in it.branches}
    return out


def case_space(source: str, cases: list[CaseId] | None = None) -> Cases:
    """The `Choice` case space `source` declares, with the names of its
    `@derive` and `@store` branches and no held case: `enumeration` gives
    the held cases. `cases` holds the case labels the solver states, which a
    `Choice` no name spells falls back to."""
    space = _choice_space(source, cases)
    space.lines = branch_lines(source)
    return space


def _choice_space(source: str, cases: list[CaseId] | None) -> Cases:
    from dl.lint import concept_case

    try:
        items = parse(source).items
    except ParseError:
        return Coarse(cases or [], None)
    decls = {it.name: it for it in items if isinstance(it, TypeDecl)}
    choice = decls.get("Choice")
    if choice is None:
        return NoChoice()
    adts = _adts(items)
    if choice.branches:
        record, roots = False, ["Choice"]
    elif m := RECORD_RE.match(choice.rhs.strip()):
        record, roots = True, FIELD_TYPE_RE.findall(m.group(1))
    else:
        record, roots = False, []
    space = Space(record, roots, adts)
    if roots and all(r in adts for r in roots) and space.concept is not None:
        return space
    return Coarse(cases or [], concept_case(source))


def held_choice(source: str, space: Cases) -> list[CaseId]:
    """The held `Choice` cases, spelled in full: the ones `impl_choice`
    holds on the empty input, or every case the `Choice` spells when the
    solver declares no `impl_choice`, or for a `Choice` no name spells, the
    cases it states; the one case of a solver without a `Choice`."""
    from dl.features import case_branches, held_cases

    try:
        held = held_cases(parse(source), source, full=True)
    except ParseError:
        held = None
    if held is not None:
        return held
    if isinstance(space, Space):
        return space.cases()
    if isinstance(space, Coarse):
        return case_branches("", source)
    return [space.concept]


@lru_cache(maxsize=32)
def enumeration(source: str) -> Cases:
    """Every case the runner holds for the solver `source`, on its case
    space: the held `Choice` cases (`held_choice`), and the cases that take
    one or more `@derive` or `@store` branches.

    Each `@derive` or `@store` line is a branch of a choice point on its
    parameter or relation, whose first branch is the stored value or the
    derived value, and lines on one parameter are branches of one point. A
    point stands under a held `Choice` case that reads its parameter
    (`dl.store.case_reads`), or that reads its relation and takes a value
    found for it at the stored assignment (`dl.store.found_values`). Under
    a store branch whose program puts the relation's facts in place of its
    clauses (`dl.store.replaces_clauses`), what only that relation reads
    is not read. The cases are, per held `Choice` case, the product of the
    points standing under it, less the cases a named `@ignore: derive` or
    `@ignore: store` line excludes: each case that takes the branch of the
    line it stands under and every branch `<name>` lists (`Drop`,
    `CaseSpace.matching`). A space whose parse fails holds none."""
    from dl.store import (
        _ignored,
        _names,
        _reads,
        _takes,
        case_reads,
        found_values,
        replaces_clauses,
    )

    space = case_space(source)
    space.plain = held_choice(source, space)
    if not space.lines:
        return space
    derives: dict[str, list[Branch]] = {}
    for b in space.lines:
        if b.kind == DERIVE:
            derives.setdefault(b.target, []).append(b)
    stores = [b for b in space.lines if b.kind == STORE]
    found = found_values(source) if stores else ()
    reads: dict[frozenset[str], dict[CaseId, tuple[set[str], set[str]]]] = {}

    def read_at(case: CaseId, cut: frozenset[str]) -> tuple[set[str],
                                                            set[str]]:
        if cut not in reads:
            reads[cut] = case_reads(
                source, space, space.plain if not cut else [case], cut)
        if case not in reads[cut]:
            reads[cut] |= case_reads(source, space, [case], cut)
        return reads[cut][case]

    def value(branch: Branch, case: CaseId, read: set[str]):
        return next((f for f in found if _names(branch.target, f.rel)
                     and _reads(f.rel, read) and _takes(case, f)), None)

    replaced: dict[int, bool] = {}

    def cut_of(values) -> frozenset[str]:
        out = set()
        for f in values:
            if id(f) not in replaced:
                replaced[id(f)] = replaces_clauses(source, f)
            if replaced[id(f)]:
                out.add(f.rel)
        return frozenset(out)

    whole: dict[CaseId, HeldCase] = {}
    for case in space.plain:
        full = read_at(case, frozenset())[0]
        first = {b: v for b in stores
                 if (v := value(b, case, full)) is not None}
        for k in range(len(first) + 1):
            for chosen in combinations(first, k):
                picked = {b: first[b] for b in chosen}
                if any(value(b, case, read_at(case, cut_of(
                        v for o, v in picked.items() if o != b))[0]) is None
                       for b in chosen):
                    continue
                params = read_at(case, cut_of(picked.values()))[1]
                points = [[None, *lines] for param, lines in derives.items()
                          if param in params]
                for taken in product(*points):
                    branches = tuple(sorted(
                        [b for b in taken if b is not None] + list(chosen),
                        key=lambda b: b.line))
                    if not branches:
                        continue
                    values = tuple(picked[b] for b in branches
                                   if b.kind == STORE)
                    whole[space.case_id(case, branches)] = HeldCase(
                        case, branches, values)
    space.runner = whole
    drops: list[Drop] = []
    for ig in ignore_lines(source):
        if not ig.name:
            continue
        if ig.kind == DERIVE:
            branch = next((b for b in space.lines
                           if b.kind == DERIVE and b.line == ig.under), None)
        else:
            branch = next((b for b in stores
                           if ig.site and _ignored({ig.site}, b.target)),
                          None)
        if branch is None:
            drops.append(Drop(ig, None, None, NO_LINE))
            continue
        name = f"{ig.name} & {branch.name}"
        cases = space.matching(name, whole)
        if cases is None:
            drops.append(Drop(ig, branch, None, NO_CASE))
            continue
        drops.append(Drop(ig, branch, space.denoted(name),
                          "" if cases else NOT_HELD, tuple(cases)))
    excluded: dict[CaseId, tuple[int, ...]] = {}
    for d in drops:
        for c in d.cases:
            excluded[c] = (*excluded.get(c, ()), d.ignore.line)
    space.runner = {c: h for c, h in whole.items() if c not in excluded}
    space.drops = drops
    space.excluded = excluded
    return space


NO_LINE = "no line"
"""A `Drop`'s `why` for a line that stands under no line of its kind."""

NO_CASE = "no case"
"""A `Drop`'s `why` for a `<name>` that denotes no case of the solver."""

NOT_HELD = "not held"
"""A `Drop`'s `why` for a `<name>` whose branches, with the line's branch,
no held case takes."""
