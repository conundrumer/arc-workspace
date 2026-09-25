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

`Space.resolve` reads one name of a witness group, in the forms
docs/handbook/solver-file.md (Witness file) gives, and also a case written
out: `[A, B]`, the record of each field's constructor, or `Recolor(Box,
Size)`, a constructor applied to its fields' constructors. A constructor
with fields written without them makes the name the runner's label
(`case_label`), which stands for every case under that constructor, and
whose outcome is the first grid of those cases. The forms are tried in this
order: `concept`, the runner-held forms, `A & B`, a written-out case, a
constructor, a slug.

A `Choice` no name spells in full falls back to `Coarse`, where a name, a
slug in CamelCase included, resolves to the runner's label of its case.

The verdict of a `@witness`, `@derive` or `@store` line reads as a name
does (`dl.witness.verdict_case`).
"""

import re
from dataclasses import dataclass, field
from itertools import product

from dl.annotations import derive_ids, store_ids
from dl.dlparse import ParseError, TypeDecl, parse
from dl.features_run import NO_CHOICE, _split, case_label

CONCEPT = "concept"
"""The name of the concept case."""

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


def model_label(name: str, resolution: bool = False) -> str:
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
    return re.sub(r"\s*,\s*", ", ", head)


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


@dataclass
class Space:
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
    runner: set[str] = field(default_factory=set)
    sites: dict[str, list[Site]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        queue = [((i,), t, (), (t,)) for i, t in enumerate(self.roots)]
        while queue:
            node, typ, above, chain = queue.pop(0)
            for ctor, fts in self.types[typ].items():
                self.sites.setdefault(ctor, []).append(
                    Site(node, typ, ctor, above))
                for j, ft in enumerate(fts):
                    if ft in self.types and ft not in chain:
                        queue.append((node + (j,), ft,
                                      above + ((node, ctor),), chain + (ft,)))

    def spell(self, forced: Forced) -> str | None:
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

        parts = [term((i,), t, (t,)) for i, t in enumerate(self.roots)]
        if any(p is None for p in parts):
            return None
        return f"[{', '.join(parts)}]" if self.record else parts[0]

    @property
    def concept(self) -> str | None:
        return self.spell({})

    def cases(self) -> list[str]:
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
            return parts[0] if parts else []
        return [f"[{', '.join(c)}]" for c in product(*parts)]

    def _sites(self, name: str) -> list[Site]:
        """The places of the constructor a name gives, verbatim or as a
        slug."""
        if name in self.sites:
            return self.sites[name]
        if SLUG_RE.match(name):
            return self.sites.get(camel(name), [])
        return []

    def _conjunction(self, names: list[str]) -> str | None:
        """The case with each named branch: the first choice of places at
        which the constructors on the way to each agree."""
        places = [self._sites(n.strip()) for n in names]
        if not all(places):
            return None
        for combo in product(*places):
            forced: Forced = {}
            if all(forced.setdefault(node, ctor) == ctor
                   for site in combo
                   for node, ctor in (*site.above, (site.node, site.ctor))):
                return self.spell(forced)
        return None

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

    def _written(self, name: str) -> str | None:
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

    def resolve(self, name: str) -> str | None:
        """The case a witness group's name denotes, spelled as `spell`
        spells it, or the runner's case id; None when it denotes none."""
        if name == CONCEPT:
            return self.concept
        if "=" in name:
            return name if name in self.runner else None
        if "&" in name:
            return self._conjunction(name.split("&"))
        if name.strip().startswith("[") or "(" in name:
            return self._written(name)
        return self._conjunction([name])

    def nodes(self, case: str) -> Forced | None:
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

    def nearest(self, required: Forced, cases: list[str]) -> list[str]:
        """The cases of `cases` that take the required constructors and
        differ from the concept case at the fewest choice points. A choice
        point differs when it takes a constructor other than its type's
        first. Ties keep every case, in the order `cases` gives them."""
        found: list[tuple[int, str]] = []
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

    def short_name(self, case: str) -> str:
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

    def models(self) -> dict[str, str]:
        """Each branch model by its name: `concept`, then one model per
        constructor per place, for each constructor that is not its type's
        first, in the order the choice points stand. A choice point under a
        branch is its own point (principles.md, Choice points), so a type
        that is the field of more than one constructor gives a model at
        each place; `_site_name` names them."""
        return {name: label for name, label, _ in self.model_sites()}

    def model_sites(self) -> list[tuple[str, str, Site | None]]:
        """Each branch model as `models` gives it, with the place of the
        constructor it takes; None for the concept case."""
        out: list[tuple[str, str, Site | None]] = []
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


class NoChoice:
    """The case space of a solver without a `Choice`: the one case."""

    runner: set[str]

    def __init__(self, runner: set[str]) -> None:
        self.runner = runner

    @property
    def concept(self) -> str:
        return NO_CHOICE

    def resolve(self, name: str) -> str | None:
        if name in (CONCEPT, NO_CHOICE, ""):
            return NO_CHOICE
        if "=" in name:
            return name if name in self.runner else None
        return None

    def models(self) -> dict[str, str]:
        return {CONCEPT: NO_CHOICE}


class Coarse:
    """The case space of a solver whose `Choice` no name spells in full, as
    when a field's type holds no branches: a name resolves to the case of
    the runner's label, a slug to that of its constructor in CamelCase, and
    the models are the cases the solver states."""

    def __init__(self, cases: list[str], concept: str,
                 runner: set[str]) -> None:
        self.cases = cases
        self._concept = concept
        self.runner = runner

    @property
    def concept(self) -> str | None:
        return self._concept or None

    def resolve(self, name: str) -> str | None:
        if name == CONCEPT:
            return self.concept
        if "=" in name:
            return name if name in self.runner else None
        label = case_label(camel(name) if SLUG_RE.match(name) else name)
        return label if label in self.cases else None

    def models(self) -> dict[str, str]:
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


def case_space(source: str, cases: list[str] | None = None) -> Cases:
    """The case space `source` declares. `cases` holds the case labels the
    solver states, which a `Choice` no name spells falls back to."""
    from dl.lint import concept_case

    runner = derive_ids(source) | store_ids(source)
    try:
        items = parse(source).items
    except ParseError:
        return Coarse(cases or [], "", runner)
    decls = {it.name: it for it in items if isinstance(it, TypeDecl)}
    choice = decls.get("Choice")
    if choice is None:
        return NoChoice(runner)
    adts = _adts(items)
    if choice.branches:
        record, roots = False, ["Choice"]
    elif m := RECORD_RE.match(choice.rhs.strip()):
        record, roots = True, FIELD_TYPE_RE.findall(m.group(1))
    else:
        record, roots = False, []
    space = Space(record, roots, adts, runner)
    if roots and all(r in adts for r in roots) and space.concept is not None:
        return space
    return Coarse(cases or [], concept_case(source), runner)
