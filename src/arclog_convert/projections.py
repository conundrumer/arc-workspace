"""The projection pass on a converted program: it folds each relation that only
projects one earlier relation into the atoms that read it.

A projection clause is a `RULE` or `DET` clause whose body is one positive atom
on a relation Q, each site of it one label marked `*`, or a site on a record
column whose field sites are each one label marked `*`, with no label twice and
no constant. The pass removes the clause of a relation P, and each atom that
reads P from that clause reads Q in its place: its site on a column L of P
becomes a site on the column of Q, and the field of that column, at which P's
atom has L (`docs/arclog/arclog.md#sites` gives how a site is written). The site
on a column that is no label of the clause, the Example site of a lifted read,
stays. The comment lines directly before the removed clause go with it. The
pass repeats until it removes no clause, and leaves the text as it is where it
removes none. Where a removal leaves Q standing under a claim before the first
claim that reads it, the pass moves Q's form, with its comment lines, to the head
of the forms of that first claim.

A clause stays where the rows its readers get would change or the program would
not read:
- P is `&output`, the arcdata contains P's name, or the text contains it other
  than as the relation of an atom or the name of P's clauses.
- No atom reads P from the clause, or one that does stands outside the block of
  the clause, or in another case reads another clause of P
  (`arclog_convert.lint.alt_repeats` gives how a case reads a relation). A reader
  is inactive in a case, and so reads no clause of P there, where a form of the
  reader's own relation stands in a block deeper than the reader's and is held in
  the case: the form of the block of greatest depth derives a relation in a case
  (`docs/arclog/arclog.md#alts`). So another clause d of P does not keep the
  clause for a reader outside d's block where, in each case that holds d's block
  and the reader's, such a form stands. Likewise a reader outside the block of
  the clause itself, other than a `DET`, does not keep it where, in the case
  that holds the clause's block and the reader's, such a form stands: that reader
  derives nothing and reads no clause of P in any case that holds the block. A
  `DET` outside the block reads the derivation of the concept program in every
  case, so it keeps the clause.
- A one-label site of P's atom on a column of a type parameter is one that the
  column-map entry of Q does not settle as a field or as the whole value.
- A reader's clause kind may not read Q, or reads it in another scope than P
  does (`docs/arclog/arclog.md#program`, `docs/arclog/arclog.md#instance`); P
  is a `DET` and Q stands in several blocks; a `DET` reads Q and Q is a chosen
  relation. A reader reads as the kind of its form gives, and an instance's
  input body as the scope of the instance gives. A `CHOOSE` form is an instance
  in this: its `for` clause is its key clause, its other clauses read as an
  instance's input bodies do, and the chosen relation it derives is an instance's output of its
  scope (`docs/arclog/constraints.md#choose`), so a redirect that gives a
  `CHOOSE` form another scope keeps the clause. Q is derived as each form that
  derives it gives, and a rule that holds for one of them keeps the clause.
- A reader stands in a form of a kind the pass does not read, such as
  `RIGID_DET`, or a form of such a kind derives Q.
- After the redirect the lint gives the text a code, other than `stands-under`,
  that it did not give. Where the code is `or-implied` at an `OR` that holds a
  redirected atom, the pass first removes each branch of that `OR` that the lint
  names as holding only where another branch holds: that branch adds no rows. An
  `OR` left with one branch becomes that branch's conjuncts. Where a removed
  branch holds labels marked `^`, the first branch that stays takes the mark at
  its first site of each such label, so the key clause keeps its columns in
  their order (`docs/arclog/arclog.md#instance`); where it lacks a site of one
  of them, or its first sites of them stand in another order, the pass removes no
  branch of that `OR`. The clause stays where the lint, with those branches
  removed, gives any code, other than `stands-under`, in more places than before.

With `keep`, the pass redirects the readers and leaves each clause it would
remove where it stands, and moves no form: this is the copy for the row-parity
check, where the clause stays as a relation that nothing reads. The rows of that
relation P say something of a case only where some reader of P, a form that held
an atom on P before the pass redirected it, derives its own relation in the case
and `&output` reads that relation or is it, or that relation is itself a removed
relation of which this holds (`ReaderForm` gives when a reader derives its
relation). `Projected.readers` gives the readers of each removed relation."""

import re
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal, NamedTuple

from arclog_convert.lint import (
    CLAIMS, FACTS, FORMS, MARKS, OPS, L, Linter, Placed, Sym, alt_points, bare_label, e_site, implied_branches,
    is_const, leaves, placements, read, site_pairs, walk)
from arclog_convert.pull_up import BODIES, OUTPUT, Edit, Reader, applied, atom_sites, readers_by_relation

type Reading = Literal["RULE", "DET"]
"""How a clause reads: per input, or task-wide."""
type Scope = Literal["example", "input", "pooled"]
"""What an instance is per (`docs/arclog/arclog.md#instance`)."""
type Kind = Literal["input", "fact", "lib", "RULE", "DET", "instance"]
"""What derives a relation Q: the fact `input`, `ex_input` or `ex_output`, the lib, a clause, an instance's output or
the relation a `CHOOSE` form chooses."""

INSTANCES = ("INIT", "DEMONSTRATED", "CHOOSE")
"""The forms whose inputs read by the scope of the form."""
KEY_CLAUSES = ("key", "for")
"""The heads of the key clause of an instance and of a `CHOOSE` form."""
READS_AS: dict[str, Reading] = {"RULE": "RULE", "DET": "DET"}
"""The reading of each form that reads as one clause does."""


@dataclass(frozen=True, order=True)
class ReaderForm:
    """A form that held an atom on a relation P before the pass redirected it: the relation the form derives (an
    instance's name for an `INIT` form, the chosen relation for a `CHOOSE` form), the ALT names of its block, and the
    ALT names of the block of each form of that relation that stands deeper than its block. In a case that holds the
    ALT names of its block and, for no deeper block, all of that block's, the form derives its relation and so reads
    the clause of P; in any other case the atom reads nothing of P (`_Program._rederived`)."""

    relation: str
    alts: tuple[str, ...]
    deeper: tuple[tuple[str, ...], ...]


def readers_json(readers: Mapping[str, tuple[ReaderForm, ...]]) -> dict[str, list[dict[str, Any]]]:
    """The readers of each removed relation as the name map holds them (`removed`) and `parity.rerun.case_rows` writes
    them: by the relation, one object per reader with its `relation`, `alts` and `deeper`."""
    return {relation: [asdict(form) for form in forms] for relation, forms in readers.items()}


def readers_of(data: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, tuple[ReaderForm, ...]]:
    """The readers that `readers_json` wrote as `data`."""
    return {relation: tuple(ReaderForm(f["relation"], tuple(f["alts"]), tuple(tuple(b) for b in f["deeper"]))
                            for f in forms) for relation, forms in data.items()}


@dataclass(frozen=True)
class Projected:
    """The text after the pass, and, by each relation whose clause it removed (kept, with `keep`), the forms that held
    an atom on that relation before the pass redirected it."""

    arclog: str
    readers: Mapping[str, tuple[ReaderForm, ...]]


class _Step(NamedTuple):
    """The text after one clause of the pass, the relation of that clause, and the forms that read it."""

    text: str
    relation: str
    readers: frozenset[ReaderForm]


@dataclass(frozen=True)
class _Origin:
    """Where a column of a projection clause's relation reads in the relation it projects: the column of that relation
    and, on a record column, the field. `one` marks a one-label site on a column of a type parameter, which reads a
    field or the whole value as the column-map entry of the projected relation says."""

    label: str
    column: str
    field: str | None
    one: bool = False


@dataclass(frozen=True)
class _Projection:
    relation: str
    origins: Mapping[str, _Origin]
    """By the label, which is the column of the clause's relation."""


@dataclass(frozen=True)
class _Derivation:
    kind: Kind
    per_input: bool


def _fresh(node: object) -> str | None:
    """The label that the site or field site `node` makes, where it holds one fresh label."""
    if isinstance(node, Sym) and node.text.startswith("*") and not is_const(node.text):
        return bare_label(node.text)
    return None


def _origins(node: object) -> tuple[str, list[_Origin]] | None:
    """The column that the site `node` reads and the origin of each label it holds; none where it is no site of fresh labels."""
    if isinstance(node, Sym):
        label = _fresh(node)
        return None if label is None else (label, [_Origin(label, label, None)])
    if not isinstance(node, L) or not node.head or not node.head.startswith(":") or len(node.items) < 2:
        return None
    column, args = node.head[1:], node.items[1:]
    found: list[_Origin] = []
    for arg in args:
        if isinstance(arg, L) and arg.head and arg.head.startswith(":") and len(arg.items) == 2:
            label, field = _fresh(arg.items[1]), arg.head[1:]
        else:
            label = field = _fresh(arg)
        if label is None:
            return None
        found.append(_Origin(label, column, field))
    if len(args) == 1 and isinstance(args[0], Sym):
        return column, [_Origin(found[0].label, column, None, one=not column[0].isupper())]
    return column, found


def _projection(clause: L) -> _Projection | None:
    """The projection that `clause` states, none where it is no projection clause."""
    if clause.head not in BODIES or len(clause.items) != 3:
        return None
    atom = clause.items[2]
    if not isinstance(atom, L) or atom.head is None or atom.head in FORMS | OPS | MARKS:
        return None
    origins: dict[str, _Origin] = {}
    columns: set[str] = set()
    for node in atom.items[1:]:
        found = _origins(node)
        if found is None or found[0] in columns or len({o.field for o in found[1]}) < len(found[1]):
            return None
        columns.add(found[0])
        for origin in found[1]:
            if origin.label in origins:
                return None
            origins[origin.label] = origin
    return _Projection(atom.head, origins)


def _fields(entries: Mapping[str, Any], column: str) -> set[str | None]:
    """The field that each leaf of `column` holds in the column-map entries of a relation: none for a leaf that
    holds the whole value."""
    out: set[str | None] = set()
    for entry in entries.values():
        for part in [w["columns"] for w in entry["writings"]] if isinstance(entry, dict) else [entry]:
            out |= {leaf["field"] for leaves in part for leaf in leaves if leaf["label"] == column}
    return out


def _settled(projection: _Projection, columns: Mapping[str, Mapping[str, Any]]) -> dict[str, _Origin] | None:
    """The origins of `projection` with each one-label site on a column of a type parameter read as a field or as the
    whole value, by the column-map entry of the projected relation; none where an entry does not settle one."""
    out: dict[str, _Origin] = {}
    for label, origin in projection.origins.items():
        if origin.one:
            fields = _fields(columns.get(projection.relation, {}), origin.column)
            if fields == {None}:
                origin = replace(origin, one=False)
            elif None not in fields and label in fields:
                origin = replace(origin, field=label, one=False)
            else:
                return None
        out[label] = origin
    return out


def _label_text(node: Sym | L) -> str | None:
    """The one label, with its mark, that the site `node` holds."""
    if isinstance(node, Sym):
        return node.text
    return node.items[1].text if len(node.items) == 2 and isinstance(node.items[1], Sym) else None


def _site_text(column: str, members: list[tuple[_Origin, str]]) -> str:
    """The site on `column` that reads the fields of `members`, each with its label as the atom writes it, or the whole value."""
    if len(members) == 1 and members[0][0].field is None:
        label = members[0][1]
        return label if column[0].isupper() and bare_label(label) == column else f"(:{column} {label})"
    fields = [label if bare_label(label) == origin.field else f"(:{origin.field} {label})" for origin, label in members]
    return f"(:{column} {' '.join(fields)})"


def _extent(text: str, form: L) -> tuple[int, int]:
    """The span of `form` with its line's indentation and the comment lines directly before it."""
    start = text.rfind("\n", 0, form.start) + 1
    if text[start:form.start].strip():
        return form.start, form.end
    while start > 0:
        before = text.rfind("\n", 0, start - 1) + 1
        if not text[before:start - 1].lstrip().startswith(";;"):
            break
        start = before
    return start, form.end


def _removal(text: str, form: L) -> Edit:
    """The edit that removes `form` with the comment lines directly before it, and leaves one blank line between
    the forms around it."""
    start, end = _extent(text, form)
    rest = re.match(r"[ \t]*(\n|$)", text[end:])
    if rest is None:   # closing parentheses follow on its line: they join the line before
        return len(text[:start].rstrip()), end, ""
    end += rest.end()
    if not text[end:].strip():
        return len(text[:start].rstrip()), len(text), "\n"
    if text[:start].endswith("\n\n") or start == 0:
        while text[end:end + 1] == "\n":
            end += 1
    return start, end, ""


def _example_key(form: L) -> bool:
    """Whether the key clause of the instance `form`, the `for` clause of a `CHOOSE`, holds a label marked `^` at a
    site on an Example column."""
    return any(isinstance(atom, L) and atom.head and not atom.head.startswith(":")
               and any(column == "E" and label.startswith("^") for node in atom.items[1:]
                       for column, label in site_pairs(node))
               for key in form.items[2:] if isinstance(key, L) and key.head in KEY_CLAUSES and len(key.items) > 1
               for atom in walk(key.items[1]))


class _Program:
    """A program text with what the removal of a projection clause reads of it."""

    def __init__(self, text: str, arcdata: str, columns: Mapping[str, Mapping[str, Any]], chosen: frozenset[str]):
        self.text, self.arcdata, self.columns, self.chosen = text, arcdata, columns, chosen
        forms = read(text)
        self.placed = placements(forms)
        self.points = alt_points(forms)[0]
        self.readers = readers_by_relation(self.placed)
        self.decls: dict[str, list[Placed]] = defaultdict(list)
        for p in self.placed:
            if p.name:
                self.decls[p.name].append(p)
        self.heads: dict[str, set[int]] = defaultdict(set)   # the position of each atom's relation, by the relation
        for form in forms:
            for x in walk(form):
                if isinstance(x, L) and x.items and isinstance(x.items[0], Sym):
                    self.heads[x.items[0].text].add(x.items[0].pos)
        self.scopes_of: dict[int, frozenset[Scope]] = {}

    def step(self, keep: bool) -> _Step | None:
        """The text after the first projection clause that may go, with its relation and the forms that read it: its
        readers redirected, and the clause removed unless `keep`; none where no clause may go. A clause that gives the
        lint another code than the text has stays, other than for an `OR` branch the redirect leaves implied, which
        goes."""
        baseline = None
        for p in self.placed:
            projection = _projection(p.form) if p.name else None
            found = None if projection is None else self._redirects(p, projection)
            if found is None:
                continue
            redirects, readers = found
            edits = redirects if keep else [*redirects, _removal(self.text, p.form)]
            text = applied(self.text, edits)
            baseline = _codes(self.text) if baseline is None else baseline
            if not _codes(text) <= baseline:
                text = _without_implied(text, _landed(edits, redirects))
            if _codes(text) <= baseline:
                return _Step(text, str(p.name), readers)
        return None

    # ---- the rules that keep a clause

    def _redirects(self, p: Placed, projection: _Projection) -> tuple[list[Edit], frozenset[ReaderForm]] | None:
        """The edit of each atom that reads the relation of `p` from it, to read the projected relation, and the forms
        of those atoms; none where the clause stays."""
        relation = projection.relation
        base = relation.partition(".")[0]
        origins = _settled(projection, self.columns)
        derivations = self._derivations(relation)
        if (p.name == OUTPUT or origins is None or derivations is None or self._named(p)
                or p.form.head == "DET" and len({d.alts for d in self.decls[base]}) > 1):
            return None
        active = self._active(p)
        flipped = {id(r.atom) for r, _ in active or ()}
        edits: list[Edit] = []
        for reader, placed in active or ():
            found = atom_sites(reader.atom)
            text = self._redirected(reader.atom, relation, origins)
            readings = self._readings(placed.form)
            if (found is None or text is None or readings is None or placed.name is None
                    or "DET" in readings and base in self.chosen
                    or any(self._blocked(p, placed, readings, d, bool(found.keys() - origins.keys()), flipped)
                           for d in derivations)):
                return None
            edits.append((reader.atom.start, reader.atom.end, text))
        return (edits, frozenset(self._reader_form(placed) for _, placed in active or ())) if edits else None

    def _blocked(self, p: Placed, placed: Placed, readings: frozenset[Reading], derivation: _Derivation,
                 lifted: bool, flipped: set[int]) -> bool:
        """Whether a rule keeps the clause `p`, for a reader in `placed` that reads as `readings` and has a site on a
        column that is no label of the clause where `lifted`, where the projected relation is derived as `derivation`
        says. `flipped` are the atoms that read it in place of the relation of `p`."""
        if ("RULE" in readings and derivation.kind == "fact" or "DET" in readings and derivation.kind == "input"
                or "RULE" in readings and p.form.head == "DET" and derivation.per_input):
            return True
        if lifted and not (derivation.kind == "RULE" or derivation.kind == "instance" and derivation.per_input):
            return True
        if placed.form.head in INSTANCES:
            after = self._scopes(placed.form, lambda a: frozenset({derivation.per_input and not e_site(a)})
                                 if id(a) in flipped else self._per_input(a))
            return after != self._scopes(placed.form)
        return False

    def _active(self, p: Placed) -> list[tuple[Reader, Placed]] | None:
        """The atoms that read the relation of `p` from its clause in some case; none where one stands outside the
        block of the clause, other than a reader that is no `DET` and is inactive in the case that holds that block
        and its own, or reads another clause of the relation in another case where it is active."""
        block = set(p.alts)
        others = [d for d in self.decls[str(p.name)] if d is not p]
        active = []
        for reader, placed in self.readers[str(p.name)]:
            stands = set(placed.alts)
            case = stands | block
            if not self._consistent(case) or any(block < set(d.alts) <= case for d in others):
                continue
            if not block <= stands:
                if placed.form.head != "DET" and self._rederived(placed, case):
                    continue
                return None
            for d in others:
                held = set(d.alts)
                if held <= block:
                    continue
                if placed.form.head == "DET":
                    if held <= stands:
                        return None
                elif self._consistent(case | held) and not self._rederived(placed, case | held):
                    return None
            active.append((reader, placed))
        return active

    def _rederived(self, placed: Placed, case: set[str]) -> bool:
        """Whether a form of the relation of `placed` stands in a block deeper than the block of `placed`, held in
        `case`: that form derives the relation there, so a reader in `placed` is inactive in `case`."""
        return any(block <= case for block in self._deeper(placed))

    def _deeper(self, placed: Placed) -> set[frozenset[str]]:
        """The ALT names of the block of each form of the relation of `placed` that stands deeper than the block of
        `placed`."""
        own = set(placed.alts)
        return {frozenset(e.alts) for e in self.decls[str(placed.name)] if own < set(e.alts)}

    def _reader_form(self, placed: Placed) -> ReaderForm:
        """The form `placed`, as it reads a removed relation."""
        return ReaderForm(str(placed.name), tuple(sorted(placed.alts)), tuple(sorted(tuple(sorted(b)) for b in self._deeper(placed))))

    def _consistent(self, alts: set[str]) -> bool:
        """Whether the alts can hold in one case: no two are alts of one `ALTS` form."""
        return len({self.points[a] for a in alts}) == len(alts)

    def _named(self, p: Placed) -> bool:
        """Whether the arcdata contains the name of the relation of `p`, or the text does other than as the relation of
        an atom, the name of its clauses, or in the comment lines before `p`."""
        pattern = re.compile(re.escape(str(p.name)) + r"(?![\w-]|\.\w)")
        start, end = _extent(self.text, p.form)
        stands = self.heads[str(p.name)] | {d.form.items[1].pos for d in self.decls[str(p.name)]}
        return bool(pattern.search(self.arcdata)) or any(
            m.start() not in stands and not start <= m.start() < end for m in pattern.finditer(self.text))

    # ---- what reads and what is read

    def _readings(self, form: L) -> frozenset[Reading] | None:
        """How the atoms of `form` read; none for a form the pass does not read."""
        reading = READS_AS.get(str(form.head))
        if reading is not None:
            return frozenset({reading})
        if form.head in ("RULE_OR_DET", "DET_OR_RULE"):
            return frozenset({"RULE", "DET"})
        if form.head in INSTANCES:
            return frozenset({"RULE" if s == "input" else "DET" for s in self._scopes(form)})
        return None

    def _derivations(self, relation: str) -> list[_Derivation] | None:
        """How the relation `relation` is derived, once for each form that derives it; none where a form is of a kind
        the pass does not read."""
        if relation == "input":
            return [_Derivation("input", True)]
        if relation in FACTS:
            return [_Derivation("fact", False)]
        if not relation.startswith("&"):
            return [_Derivation("lib", False)]
        base, _, port = relation.partition(".")
        out: list[_Derivation] = []
        for d in self.decls[base]:
            if port and d.form.head == "INIT" or not port and d.form.head == "CHOOSE":
                out += [_Derivation("instance", s == "input") for s in sorted(self._scopes(d.form))]
            elif not port and d.form.head == "RULE":
                out.append(_Derivation("RULE", True))
            elif not port and d.form.head == "DET":
                out.append(_Derivation("DET", False))
            elif not port and d.form.head in ("RULE_OR_DET", "DET_OR_RULE"):
                out += [_Derivation("RULE", True), _Derivation("DET", False)]
            else:
                return None
        return out or None

    def _scopes(self, form: L, per_input: Callable[[L], frozenset[bool]] | None = None) -> frozenset[Scope]:
        """What the instance `form` is, as its bodies read: per example when its key holds an Example label,
        otherwise per input when a body reads `input` or reads, without its Example column, a relation that a `RULE`
        or a per-input instance derives, and pooled in every other case. `per_input` says whether an atom reads so; the
        scopes the answers allow, where it gives both."""
        if per_input is None and form.start in self.scopes_of:
            return self.scopes_of[form.start]
        out: set[Scope]
        if _example_key(form):
            out = {"example"}
        else:
            own = form.items[1].text if len(form.items) > 1 and isinstance(form.items[1], Sym) else None
            values = [(per_input or self._per_input)(a) for a in walk(form) if isinstance(a, L) and a.head
                      and (a.head == "input" or a.head.startswith("&")) and a.head.partition(".")[0] != own]
            out = set()
            if any(True in v for v in values):
                out.add("input")
            if all(False in v for v in values):
                out.add("pooled")
        if per_input is None:
            self.scopes_of[form.start] = frozenset(out)
        return frozenset(out)

    def _per_input(self, atom: L) -> frozenset[bool]:
        """Whether `atom` reads per input: the values it may have where the forms that derive its relation differ. A
        read with an Example column is not per input."""
        if e_site(atom):
            return frozenset({False})
        derivations = self._derivations(str(atom.head))
        return frozenset({d.per_input for d in derivations} if derivations else {True, False})

    # ---- the text of a redirect

    def _redirected(self, atom: L, relation: str, origins: Mapping[str, _Origin]) -> str | None:
        """The atom `atom`, which reads a relation whose columns are the labels of `origins`, as it reads `relation`:
        its sites in order, a site on a label of `origins` at the column and the field of its origin, with the sites on
        one column of `relation` in the place of the first, and each other site as written."""
        found = atom_sites(atom)
        if found is None:
            return None
        parts: list[str | list[tuple[_Origin, str]]] = []
        groups: dict[str, list[tuple[_Origin, str]]] = {}
        for site in found.values():
            origin = origins.get(site.column)
            if origin is None:
                parts.append(self.text[site.node.start:site.node.end] if isinstance(site.node, L)
                             else site.node.text)
                continue
            label = _label_text(site.node)
            if label is None:
                return None
            if origin.column not in groups:
                groups[origin.column] = []
                parts.append(groups[origin.column])
            groups[origin.column].append((origin, label))
        sites = [x if isinstance(x, str) else _site_text(x[0][0].column, x) for x in parts]
        return "(" + " ".join([relation, *sites]) + ")"


def _lint(text: str) -> Linter:
    lint = Linter(Path("-"), text)
    lint.run()
    return lint


def _codes(text: str) -> Counter[str]:
    """The lint codes of `text` but `stands-under`, which the pass repairs, with their counts."""
    return Counter(code for _, code, _ in _lint(text).errs if code != "stands-under")


def _landed(edits: list[Edit], redirects: list[Edit]) -> set[int]:
    """The position, in the text after `edits`, of each of `redirects`, which are among them."""
    out: set[int] = set()
    shift = 0
    for edit in sorted(edits):
        if edit in redirects:
            out.add(edit[0] + shift)
        shift += len(edit[2]) - (edit[1] - edit[0])
    return out


def _sites(branch: L) -> list[Sym]:
    """The labels at the sites of the atoms of the `OR` branch `branch`, in order of the text."""
    return [leaf for atom in walk(branch)
            if isinstance(atom, L) and atom.head and not atom.head.startswith(":")
            and atom.head not in OPS | FORMS | MARKS
            for leaf in leaves(atom)]


def _marks_moved(branches: list[L], dropped: set[int], stays: L) -> list[Edit] | None:
    """The edits that give the branch `stays` of an `OR` the mark `^` at its first site of each label that a branch
    of `dropped` marks, in the order that the dropped branches mark them; none where `stays` lacks a site of one of
    those labels, or its first sites of them stand in another order or hold another mark."""
    labels = list(dict.fromkeys(bare_label(site.text) for i in sorted(dropped) for site in _sites(branches[i])
                                if site.text.startswith("^")))
    first: dict[str, Sym] = {}
    for site in _sites(stays):
        first.setdefault(bare_label(site.text), site)
    chosen = [first.get(label) for label in labels]
    if any(site is None or "*" in site.text for site in chosen):
        return None
    sites = [site for site in chosen if site is not None]
    if [site.pos for site in sites] != sorted(site.pos for site in sites):
        return None
    return [(site.pos, site.pos + len(site.text), "^" + site.text) for site in sites if not site.text.startswith("^")]


def _without_implied(text: str, landed: set[int]) -> str:
    """`text` without the implied branches of each `OR` that holds an atom starting at a position of `landed`, an
    `OR` left with one branch replaced by that branch's conjuncts. The first branch that stays takes the mark `^` of
    each label that a dropped branch marks; an `OR` where it cannot is left as it is."""
    gone: list[tuple[int, int]] = []
    marks: list[Edit] = []

    def before(node: L) -> int:
        return len(text[:node.start].rstrip())

    for form in read(text):
        for node in walk(form):
            if not (isinstance(node, L) and node.head == "OR" and all(isinstance(b, L) for b in node.items[1:])
                    and any(isinstance(x, L) and x.start in landed for x in walk(node))):
                continue
            branches = node.items[1:]
            dropped = {i for i, _ in implied_branches([b.items for b in branches])}
            kept = [b for i, b in enumerate(branches) if i not in dropped]
            moved = _marks_moved(branches, dropped, kept[0]) if dropped else None
            if moved is None:
                continue
            marks += moved
            gone += [(before(branches[i]), branches[i].end) for i in sorted(dropped)]
            if len(kept) == 1:
                gone += [(node.start, node.items[1].start), (before(kept[0]), kept[0].start + 1),
                         (kept[0].end - 1, node.end)]
    spans = _union(gone)
    return applied(text, [*((a, b, "") for a, b in spans),
                          *(m for m in marks if not any(a <= m[0] < b for a, b in spans))])


def _union(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The spans of `spans` with those that overlap or touch joined."""
    out: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def _moved_into(text: str, form: L, claim: L) -> str:
    """`text` with `form`, with its comment lines, moved to the head of the forms of `claim`."""
    start, end = _extent(text, form)
    block = text[start:end]
    heads = [x for x in claim.items[2:] if isinstance(x, L) and x.head != "APPROXIMATED"]
    at = (_extent(text, heads[0])[0], block + "\n\n") if heads else (claim.end - 1, "\n\n" + block)
    return applied(text, [_removal(text, form), (at[0], at[0], at[1])])


def _stands_under(text: str) -> set[int]:
    """The line of each form that the lint reports as standing under a claim before the first claim that reads it."""
    return {line for line, code, _ in _lint(text).errs if code == "stands-under"}


def _restand(text: str) -> str:
    """`text` with each form that the lint's `stands-under` code reports moved to the head of the forms of the first
    claim after its own under which the lint does not report it."""
    while lines := _stands_under(text):
        forms = read(text)
        placed = next((p for p in placements(forms) if p.form.line in lines and not p.alts and p.slug), None)
        claims = [f for f in forms if isinstance(f, L) and f.head in CLAIMS]
        if placed is None:
            return text
        after = claims[[c.items[1].text for c in claims].index(placed.slug) + 1:]
        for claim in after:
            moved = _moved_into(text, placed.form, claim)
            now = [p for p in placements(read(moved)) if p.name == placed.name and not p.alts]
            if now and now[0].form.line not in _stands_under(moved):
                break
        else:
            return text
        text = moved
    return text


def project(arclog: str, arcdata: str, columns: Mapping[str, Mapping[str, Any]], keep: bool = False) -> Projected:
    """`arclog` after the pass, given the `arcdata` of the same program and its column map `columns`
    (`arclog_convert.names.column_map`), with the readers of each relation whose clause the pass removed (left in place
    with `keep`)."""
    chosen = frozenset(_lint(arclog).chosen)
    readers: dict[str, set[ReaderForm]] = defaultdict(set)
    while (step := _Program(arclog, arcdata, columns, chosen).step(keep)) is not None:
        arclog = step.text
        readers[step.relation] |= step.readers
    return Projected(arclog if keep or not readers else _restand(arclog),
                     {relation: tuple(sorted(forms)) for relation, forms in sorted(readers.items())})
