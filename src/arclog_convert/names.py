"""The name map and the column map of one converted solver, which
`arclog_convert.convert` writes under `names/` and `columns/` of
`arclog_convert.out`, and `parity` reads.

The name map gives, for each arclog relation the converted files read and each
relation of an instance of a lib component they write for a Souffle instance,
the Souffle relations whose rows it holds, by their paths from the top level
of the solver's program. The column map gives, for each of those, the arclog
column of each kept leaf of the Souffle relation's columns. Both take their
Souffle side from what the converter recorded as it wrote (`Converter.wrote`,
`Converter.made`) and the names of the lib (`libmap.COMP`).

A Souffle relation whose clauses the converter folds into other arclog
relations (`folded`) has no arclog name of its own. For the row-parity check
alone, the converter converts the solver again with a check relation for each
(`arclog_convert.checks`), and `check_maps` gives the name map entry and the
column map entry of each check relation, or the reason it has none.

An arclog relation the converter adds that holds no Souffle relation of the
solver's program, such as an output of an instance the lib rewrite hoists, or a
copy of a relation of `Parse` that the determination or another instance of
`Parse` takes, has its path in the Souffle text that `parity_text` writes (`parity`, `placed`), and its entry in
the column map (`_parity_columns`); a relation of the text that the determination
run adds is given the component `Determine`. An `equal` line of such a
relation proves that the converter's arclog relation holds the rows that the
text's clauses derive with the solver's program, which says nothing on whether
those clauses hold what the solver means; that rests on the lines of the
solver's relations that read them."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from engine.program import Qualifier, RelationName
from solver.vocabulary import DETERMINE
from souffle.parser import relation_name
from arclog_convert import libmap
from arclog_convert.libmap import rename as libmap_rename
from arclog_convert.libmap.instances import Placement

from arclog_convert.checks import Fold, clauses_of, lint_codes, todo_kinds
from arclog_convert.clauses import Site, site_columns
from arclog_convert.forms import Source, renamed
from arclog_convert.leaves import Converter, FACTS, Written
from arclog_convert.lint import Linter
from arclog_convert.parity_text import ParityText, Place, parity_text
from arclog_convert.solver import Solver


_ARC_TOKEN = re.compile(r"[&$]?[A-Za-z_][\w]*(?:\.[\w]+)*")
_ALTS_CONCEPT = re.compile(r'\(ALTS \$\w+ "(?:[^"\\]|\\.)*" \$(\w+)')
"""The constructor an `ALTS` form gives as its concept alt."""


def _souffle_relation(c: "Converter", w: Written) -> dict:
    """The Souffle relation, or instance, `w`: the component path, its name
    there, and its name from the top level of the solver's program, null
    where no instance at the top level is of the scope's component."""
    path: str | None = w.relation
    if w.scope:
        at = [n for (sc, n), i in c.insts.items() if sc == () and i.component == w.scope[-1]]
        path = f"{at[0]}.{w.relation}" if len(w.scope) == 1 and len(at) == 1 else None
    return {"component": list(w.scope), "relation": w.relation, "path": path}


def _souffle_exists(c: "Converter", w: Written) -> bool:
    """Whether the solver's program with the lib declares the relation, or
    the instance, `w`: an arclog name the converter wrote for a relation or
    an instance it made stands for none."""
    if w.instance:
        return (w.scope, w.relation) in c.souffle_components
    return c.souffle_arity(w.scope, w.relation) is not None


def _renamed_name(name: str, insts: dict[str, str]) -> str:
    """The arclog name `name` the converter writes, as the renames
    `convert_one` applies after it leave it: `renamed`, then
    `libmap_rename.rename` with `insts`."""
    return libmap_rename.rename(renamed(f"({name})"), insts)[1:-1]


def _relations_read(text: str) -> set[str]:
    """Each name the arclog or arcdata `text` reads as a relation or an
    instance: a name with `&` outside a quoted text, and the head of a
    form."""
    from arclog_convert.lint import L, Sym, read
    out: set[str] = set()

    def scan(xs: list) -> None:
        for x in xs:
            if not isinstance(x, L):
                continue
            for i, it in enumerate(x.items):
                if isinstance(it, Sym):
                    t = it.text.lstrip("^*")
                    if _ARC_TOKEN.fullmatch(t) and (t.startswith("&") or i == 0):
                        out.add(t)
            scan(x.items)
    scan(read(text))
    return out


def _inputs_written(text: str) -> set[str]:
    """Each input of an instance, as `&<instance>.<input>`, that an `INIT`
    form of the arclog `text` writes."""
    from arclog_convert.lint import L, Sym, read
    out: set[str] = set()

    def inputs(instance: str, items: list) -> None:
        for it in items:
            if isinstance(it, L) and it.head == "key":
                inputs(instance, it.items[1:])
            elif isinstance(it, L) and it.head:
                out.add(f"{instance}.{it.head}")

    def scan(xs: list) -> None:
        for x in xs:
            if isinstance(x, L):
                if x.head == "INIT" and len(x.items) >= 3 and isinstance(x.items[1], Sym):
                    inputs(x.items[1].text, x.items[3:])
                scan(x.items)
    scan(read(text))
    return out


def _lib_ports(c: "Converter", insts: dict[str, str], arclog: str) -> dict[str, list[Written]]:
    """Each relation of an instance of the signature's component of a lib
    component, which the converter writes for a Souffle instance of the lib
    component, as the arclog name `&<instance>.<relation>` (before the
    renames `convert_one` applies), with the Souffle relation of that instance
    it stands for: each output, and each input that the `INIT` forms of
    `arclog`, the text after the renames, write. The signature's component is
    the one `libmap.COMP` gives the lib component, where the renames apply to
    the instance, and the relation is the one the renames give it there; an
    instance expanded into a shape has its relations in `Converter.made`."""
    written = _inputs_written(arclog)
    components = libmap_rename.instances(arclog)
    out: dict[str, list[Written]] = {}
    for arc, ws in c.written.items():
        for w in ws:
            component = c.souffle_components.get((w.scope, w.relation)) if w.instance else None
            if component is None or component not in c.lib.comps or (w.scope, w.relation) in c.lib_moved:
                continue
            renamed = arc in insts
            if renamed and insts[arc] != component:
                continue   # an instance the converter made, of another component
            sig_component = libmap.COMP[component].name if renamed else component
            if sig_component not in c.sig.comps or components.get(_renamed_name(arc, insts)) != sig_component:
                continue
            sig_relations = {r.name for r in c.sig.relations(sig_component)[1]}
            for r in c.lib.present(component)[1]:
                if r.name in c.lib.extension[component]:
                    continue   # a relation only the signature's component has
                port = f"{arc}.{r.name}"
                if _renamed_name(port, insts).partition(".")[2] in sig_relations and \
                        (not r.is_input or _renamed_name(port, insts) in written):
                    out.setdefault(port, []).append(Written(w.scope, f"{w.relation}.{r.name}", False))
    return out


def _shaped(c: "Converter", insts: dict[str, str]
            ) -> dict[str, tuple[str, list | None, object, tuple[Written, ...]]]:
    """Each relation of an expansion's shape (`Converter.made`) that stands
    for a Souffle relation, by the arclog name the converter writes it
    under (the renames `convert_one` applies after it, `_renamed_name`), with
    that name before the renames, its columns as `Converter.resolve` gives
    them, its instance, and the Souffle relations it stands for."""
    out: dict[str, tuple[str, list | None, object, tuple[Written, ...]]] = {}
    for (scope, shape), ws in c.made.items():
        if not ws or any(w.instance for w in ws):
            continue
        *chain, rel = shape.split(".")
        name, cols, _, inst = c.resolve(RelationName(tuple(chain), rel), scope, c.parse_sub if scope == ("Parse",) else {})
        out[_renamed_name(name, insts)] = (name, cols, inst, ws)
    return out


def name_map(s: "Solver", insts: dict[str, str], arclog: str, arcdata: str) -> dict:
    """Each arclog relation name the written files read, with each Souffle
    relation it was written from, in the order the pass wrote them; each
    instance they read, with each Souffle instance; each `ALT` name, with the Souffle `Choice` constructor; and
    each arclog name with `&` the files read that the renames of this pass
    give no Souffle relation, under `unmapped`; and whether the solver has a
    `@store` line, under `stores`: a relation or an instance the
    converter made that the Souffle program lacks has none. Each name is the one the
    converter recorded as it wrote it (`Converter.wrote`), or a top-level
    lib relation it writes under its own name that the solver declares no
    relation of, under the renames
    `convert_one` applies after it (`_renamed_name`). The relations of an
    instance of a lib component that the converter writes for a Souffle
    instance, and of an expansion's shape, are in the map whether the files
    read them or not: each output, and each input an `INIT` writes."""
    c = s.c
    shaped = _shaped(c, insts)
    named = {arc: [w for w in ws if _souffle_exists(c, w)] for arc, ws in c.written.items()}
    for own in (*sorted(FACTS), *c.lib.top, *c.sig.top):
        if ((), own) not in c.rels:   # else the Souffle name is the solver's own relation
            named.setdefault(own, [Written((), own, False)])
    ports = _lib_ports(c, insts, arclog)
    for arc, ws in ports.items():
        named.setdefault(arc, []).extend(w for w in ws if w not in named[arc])
    rels: dict[str, list[dict]] = {}
    instances: dict[str, list[dict]] = {}
    for arc, ws in named.items():
        for w in ws:
            got = (instances if w.instance else rels).setdefault(_renamed_name(arc, insts), [])
            if (r := _souffle_relation(c, w)) not in got:
                got.append(r)
    for arc, (_, _, _, ws) in shaped.items():
        got = rels.setdefault(arc, [])
        got.extend(r for w in ws if _souffle_exists(c, w) and (r := _souffle_relation(c, w)) not in got)
    read = _relations_read(arclog + "\n" + arcdata)
    wanted = read | {_renamed_name(arc, insts) for arc in ports} | {arc for arc in shaped if "." in arc}
    relations = {n: rels[n] for n in sorted(wanted) if n in rels}
    ctors = {f"${m}": m for m in sorted(set(re.findall(r"\(ALT \$(\w+)", arclog))
                                        | set(_ALTS_CONCEPT.findall(arclog)))}
    insts_read = {n: instances[n] for n in sorted(read) if n in instances}
    written = libmap_rename.instances(arclog)
    unmapped = sorted(n for n in read if n.startswith("&") and n not in relations
                      and n not in insts_read and n not in written)
    return {"relations": relations, "instances": insts_read, "constructors": ctors,
            "unmapped": unmapped, "stores": bool(s.store_points)}


def parity(s: "Solver", names: dict, insts: dict[str, str]) -> ParityText:
    """The Souffle text (`parity_text`) for each arclog relation of the name
    map `names` that holds no Souffle relation of the solver's program: each
    in `unmapped` and each with no Souffle relation."""
    roots = {n for n, sources in names["relations"].items() if not sources} | set(names["unmapped"])
    return parity_text(s.c, lambda n: _renamed_name(n, insts), roots)


def placed(names: dict, text: ParityText) -> dict:
    """The name map `names` with each arclog relation that `text` derives
    given the relation of the text as its one Souffle relation, by its path
    from the top level of the text."""
    relations = dict(names["relations"])
    relations.update({arc: [{"component": [DETERMINE] if at.determined else [], "relation": at.path, "path": at.path}]
                      for arc, at in text.places.items()})
    return {**names, "relations": dict(sorted(relations.items())),
            "unmapped": [n for n in names["unmapped"] if n not in text.places]}


def column_map(s: "Solver", names: dict, insts: dict[str, str], text: ParityText | None = None) -> dict:
    """For each arclog relation of the name map `names`, for each of its
    Souffle relations that has a path from the top level, or is declared in
    `Determine`, by that path, or by its name for a relation of `Determine`: one
    entry per column of the Souffle relation, in its order: the list of the
    kept leaves of that Souffle column that the arclog relation holds, each as
    `{"leaf": <path into the Souffle column's record>, "label": <the arclog
    column>, "field": <the field within the arclog column, or null>,
    "example": <whether the leaf is an Example leaf>}`; the list is empty
    where no arclog column holds a leaf of the Souffle column. The arclog
    columns stand for the Souffle relation's columns by the `Written.columns`
    of the relation of an expansion's shape (`Converter.made`); for a relation
    that lost `TiebreakResolution` columns, by the columns it kept; otherwise
    one to one. A relation whose arclog columns and Souffle columns differ in
    number and whose correspondence the converter does not hold gets no entry.
    The relation is resolved as a read sees it (`Converter.resolve`): from the
    top level by the Souffle relation's path, and a relation of an expansion's
    shape by its own name; the labels are those `site_columns` gives (for the
    `prediction` of a `DEMONSTRATED` form, the labels of the `value` head's
    sites, as its `DEMO_RULE` clause names them), but for a
    relation of `Determine` that is no instance's port, whose entry gives only
    the sites that a read of it names (`_named_sites`). A
    relation whose clauses the converter writes at other arclog columns under
    one ALT than under another, or than at the top level
    (`Converter.writings`), has for entry `{"writings": [...]}`: one
    `{"constructors": [...], "columns": <the entry above>}` for the top level,
    first, with no constructors, and one for each ALT writing whose entry
    differs, with the constructors of its ALTs. In the entry of a writing, a
    Souffle column whose head term is a variable that another column of the
    head holds, and that the writing leaves out of the arclog relation, takes
    that column's label, so that the engine's relation holds a Souffle row
    only where the two columns agree. `insts` are the instance renames
    `convert_one` applies to the names."""
    c = s.c
    shaped = _shaped(c, insts)
    out: dict[str, dict[str, list[list[dict]]]] = {}
    for arc, sources in names["relations"].items():
        for source in sources:
            if text is not None and arc in text.places and source["path"] == text.places[arc].path:
                got = _parity_columns(c, text.places[arc])
                if got is None:
                    continue
            elif arc in shaped:
                written, cols, inst, ws = shaped[arc]
                w = next((w for w in ws if _souffle_relation(c, w) == source), None)
                width = None if w is None else c.souffle_arity(w.scope, w.relation)
                if w is None or w.columns is None or cols is None or width is None or len(cols) != len(w.columns):
                    continue
                got = _souffle_columns(_read_sites(site_columns(c, cols, inst), _named_sites(c, written, w.scope, ())),
                                       w.columns, width)
            else:
                scope, relation = tuple(source["component"]), source["relation"]
                if source["path"] is not None:
                    place = relation_name(source["path"])
                    resolved = c.resolve(place, (), {})
                elif scope == ("Determine",):   # the instance a run adds (`solver.determine.run_program`) has no path in the solver's text
                    place = relation_name(relation)
                    resolved = c.resolve(place, scope, {})
                else:
                    continue
                got = _own_columns(c, resolved, scope, relation, (scope, relation), place.name)
                if got is None:
                    continue
            out.setdefault(arc, {})[source["relation"] if source["path"] is None else source["path"]] = got
    return out


def _entry(writings: dict[frozenset[str], tuple[tuple[Source, ...], ...]], sites: list[list[Site]],
           place: Callable[[list[list[Site]]], list[list[dict]]], named: set[tuple[str, str | None]] | None
           ) -> list[list[dict]] | dict:
    """The entry of a relation whose arclog columns are `sites` (`site_columns`)
    in the column map, with the Souffle columns they are `place`d in, the
    sites of each column but those `named` leaves out (none: all stand): the one
    entry, where the clauses of the relation are written at one set of arclog
    columns in every writing (`Converter.writings`). Otherwise `{"writings":
    [...]}`, one `{"constructors": [...], "columns": <entry>}` for the top
    level, first, and for each ALT writing whose entry differs from it, by
    the constructors of its ALTs. The entry of a writing reads the label of a
    leaf that its clauses drop at the column of the leaf they repeat."""
    def placed(columns: list[list[Site]]) -> list[list[dict]]:
        return place(_read_sites(columns, named))
    fitting = {key: record for key, record in writings.items()
               if tuple(map(len, record)) == tuple(map(len, sites))}
    if len(set(fitting.values())) < 2:
        return placed(sites)
    entries = {key: placed(_read_at(sites, record)) for key, record in fitting.items()}
    top = entries.setdefault(frozenset(), placed(sites))
    written = [{"constructors": sorted(key), "columns": entry}
               for key, entry in sorted(entries.items(), key=lambda kv: (len(kv[0]), sorted(kv[0])))
               if not key or entry != top]
    return {"writings": written} if len(written) > 1 else top


def _named_sites(c: "Converter", written: str, scope: tuple[str, ...], instances: tuple[str, ...]
                 ) -> set[tuple[str, str | None]] | None:
    """The (label, field) sites that a read names of the relation `written`,
    declared in `scope`, where it is a relation of `Determine` that is no
    instance's port (`instances` are its instance path): a `DET` has as its
    columns the labels that a read names, and a label no read names is
    existential. None where the relation is no such `DET`, or no read names it."""
    return c.read_sites.get(written) if scope == (DETERMINE,) and not instances else None


def _read_sites(columns: list[list[Site]], named: set[tuple[str, str | None]] | None) -> list[list[Site]]:
    """`columns` with the sites that `named` (`_named_sites`) leaves out dropped; all stand where it is none."""
    return [[s for s in column if named is None or (s.label, s.field) in named] for column in columns]


def _read_at(sites: list[list[Site]], record: tuple[tuple[Source, ...], ...]) -> list[list[Site]]:
    """`sites` with the label and field of each leaf `record` places at the
    column of another leaf (`Converter.note_writing`) those of that leaf."""
    return [[replace(site, label=sites[i][m].label, field=sites[i][m].field) for site, (i, m) in zip(column, at)]
            for column, at in zip(sites, record)]


def _own_columns(c: "Converter", resolved: tuple, scope: tuple[str, ...], relation: str,
                 dropped: tuple[tuple[str, ...], str], port: str) -> list[list[dict]] | dict | None:
    """The entry of the Souffle relation `relation` declared in `scope`, for
    the arclog relation `resolved` (`Converter.resolve`) whose columns stand
    for those of the Souffle relation one to one, but for the columns the
    converter dropped from `dropped` (`_entry` gives its form); none where
    the columns differ in number. `port` is the name `resolved` was read by,
    which `site_columns` takes for the relation of an instance."""
    written, cols, _, inst = resolved
    width = c.souffle_arity(scope, relation)
    if cols is None or width is None:
        return None
    kept = tuple(j for j in range(width) if j not in c.dropped.get(dropped, ()))
    if len(kept) != len(cols):
        return None
    return _entry(c.writings.get(written, {}), site_columns(c, cols, inst, port),
                  lambda sites: _souffle_columns(sites, kept, width), _named_sites(c, written, scope, ()))


def _parity_columns(c: Converter, at: Place) -> list[list[dict]] | dict | None:
    """The entry (`_entry` gives its form) of the relation of the text at
    `at`: the sites of the arclog relation as `Converter.resolve` gives them
    for the relation the converter holds in the scope of `at`, one to one with
    its columns but those `Converter.dropped` lists; none where their numbers differ."""
    written, cols, _, inst = c.resolve(at.relation, at.scope, c.parse_sub if at.scope == ("Parse",) else {})
    dropped = () if at.relation.instances else c.dropped.get((at.scope, at.relation.name), ())
    kept = tuple(j for j in range(at.width) if j not in dropped)
    if cols is None or len(kept) != len(cols):
        return None
    return _entry(c.writings.get(written, {}), site_columns(c, cols, inst),
                  lambda sites: _souffle_columns(sites, kept, at.width),
                  _named_sites(c, written, at.scope, at.relation.instances))


def _souffle_columns(columns: list[list[Site]], placement: tuple[Placement, ...], width: int) -> list[list[dict]]:
    """The sites of the arclog columns `columns`, as the entries of the
    `width` columns of the Souffle relation they are placed in by
    `placement` (`Written.columns`): each site under the Souffle column that
    holds its leaf, with the leaf's path into that column."""
    out: list[list[dict]] = [[] for _ in range(width)]
    for sites, where in zip(columns, placement):
        for site in sites:
            at, path = where, tuple(site.leaf.path)
            if isinstance(where, tuple):   # a record term: its field holds the leaf
                at, path = where[path[0]], path[1:]
            if at is not None:
                out[at].append({"leaf": list(path), "label": site.label, "field": site.field,
                                "example": site.leaf.kind == "example"})
    return out


def _fold_source(c: "Converter", fold: Fold) -> dict:
    """The Souffle relation `fold`, as `_souffle_relation` gives it."""
    return _souffle_relation(c, Written(fold.scope, fold.relation, False))


def folded(s: "Solver", names: dict) -> list[Fold]:
    """Each Souffle relation that a clause of the solver with a body heads,
    in the top level or in the solver's own `Parse` component, that is not
    declared `inline`, and that no arclog name of the name map `names`
    stands for: the relations the converter folds into other arclog
    relations, such as an input of an expanded instance that its shape reads
    inline, and a relation written as a quantifier."""
    c = s.c
    stood = {r["path"] for ss in names["relations"].values() for r in ss}
    inline = {(r.scope.components, r.name) for r in c.source.relations if Qualifier.INLINE in r.qualifiers}
    out = []
    for fold, units in clauses_of(c.source).items():
        if all(u.body is None for u in units) or (fold.scope, fold.name) in inline and not fold.instances:
            continue
        path = _fold_source(c, fold)["path"]
        if path is not None and path not in stood:
            out.append(fold)
    return out


@dataclass(frozen=True)
class Checks:
    """What the check relations of one converted solver add to its maps."""

    relations: dict[str, list[dict]] = field(default_factory=dict)
    """The name map entry of each check relation that the converted program
    writes: its arclog name, with the Souffle relation it holds the clauses of."""
    columns: dict[str, dict[str, list[list[dict]]]] = field(default_factory=dict)
    """The column map entry of each of them."""
    untranslated: dict[str, str] = field(default_factory=dict)
    """For each other folded relation, by its path from the top level, why
    the converted program has no check relation of it."""


def unchecked(s: "Solver", folds: list[Fold], reason: str) -> Checks:
    """The maps of a solver whose conversion with the check relations of
    `folds` failed for `reason`: no entry, and `reason` for each."""
    return untranslated(s, dict.fromkeys(folds, reason))


def untranslated(s: "Solver", reasons: dict[Fold, str]) -> Checks:
    """The maps of a solver with no check relation of each fold of `reasons`:
    no entry, and the fold's reason, under its path from the top level."""
    at = ((_fold_source(s.c, f)["path"], why) for f, why in reasons.items())
    return Checks(untranslated={p: why for p, why in at if p is not None})


def _check_arclog_name(c: "Converter", fold: Fold, insts: dict[str, str]) -> str | None:
    """The arclog name of the check relation of `fold`, as the files read it
    after the renames `convert_one` applies (`insts`), or None where the
    converter wrote none."""
    check = c.checks.get(fold)
    arc = None if check is None else c.names.get((fold.scope, check))
    return None if arc is None else _renamed_name("&" + arc, insts)


def dropped(s: "Solver", folds: list[Fold], insts: dict[str, str], arclog: str) -> dict[Fold, str]:
    """Each of `folds` whose check relation the converter wrote into the text
    `arclog` (`check_maps` gives the arguments) with a clause with a `TODO`
    line or with a text in which the arclog lint finds a violation, with the
    reason its path is untranslated: the `TODO` kinds and the lint codes."""
    lt = Linter(Path("check.arclog"), arclog)
    lt.run()
    out: dict[Fold, str] = {}
    for fold in folds:
        name = _check_arclog_name(s.c, fold, insts)
        if name is None:
            continue
        found = [f"TODO {k}" for k in todo_kinds(arclog, name)] + [f"lint {c}" for c in lint_codes(arclog, name, lt.errs)]
        if found:
            out[fold] = "the converter cannot write a clause of the relation: " + ", ".join(found)
    return out


def check_maps(s: "Solver", folds: list[Fold], insts: dict[str, str], arclog: str) -> Checks:
    """The maps of the check relations of `folds`, for the solver `s` converted
    with them (`Converter.checks`) into the text `arclog`, after the renames
    `convert_one` applies (`insts`). A relation whose path from the top level
    the solver's text lacks is left out."""
    c = s.c
    read = _relations_read(arclog)
    out = Checks()
    for fold in folds:
        source = _fold_source(c, fold)
        path = source["path"]
        if path is None:
            continue
        check = c.checks.get(fold)
        if check is None:
            out.untranslated[path] = "the converter has no declaration of the relation's columns"
            continue
        name = _check_arclog_name(c, fold, insts)
        if name is None or name not in read:
            out.untranslated[path] = "the converter wrote no clause of the relation"
            continue
        at = path.removesuffix(fold.relation) + check
        place = relation_name(at)
        got = _own_columns(c, c.resolve(place, (), {}), fold.scope, fold.relation, (fold.scope, check), place.name)
        if got is None:
            out.untranslated[path] = "the columns of the clauses the converter wrote do not map onto those of the relation"
            continue
        out.relations[name] = [source]
        out.columns[name] = {path: got}
    return out
