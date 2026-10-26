"""The name map and the column map of one converted solver, which
`arclog_convert.convert` writes under `names/` and `columns/` of
`arclog_convert.out`, and `parity` reads.

The name map gives, for each arclog relation the converted files read and each
relation of an instance of a lib component they write for a Souffle instance,
the Souffle relations whose rows it holds, by their paths from the top level
of the solver's program. The column map gives, for each of those, the arclog
column of each kept leaf of the Souffle relation's columns. Both take their
Souffle side from what the converter recorded as it wrote (`Converter.wrote`,
`Converter.made`) and the names of the lib (`libmap.COMP`)."""

import re

from engine.program import RelationName
from souffle.parser import relation_name
from arclog_convert import libmap
from arclog_convert.libmap import rename as libmap_rename
from arclog_convert.libmap.instances import Placement

from arclog_convert.clauses import Site, site_columns
from arclog_convert.forms import renamed
from arclog_convert.leaves import Converter, FACTS, Written
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


def _shaped(c: "Converter", insts: dict[str, str]) -> dict[str, tuple[list | None, object, tuple[Written, ...]]]:
    """Each relation of an expansion's shape (`Converter.made`) that stands
    for a Souffle relation, by the arclog name the converter writes it
    under (the renames `convert_one` applies after it, `_renamed_name`), with
    its columns as `Converter.resolve` gives them, its instance, and the
    Souffle relations it stands for."""
    out: dict[str, tuple[list | None, object, tuple[Written, ...]]] = {}
    for (scope, shape), ws in c.made.items():
        if not ws or any(w.instance for w in ws):
            continue
        *chain, rel = shape.split(".")
        name, cols, _, inst = c.resolve(RelationName(tuple(chain), rel), scope, c.parse_sub if scope == ("Parse",) else {})
        out[_renamed_name(name, insts)] = (cols, inst, ws)
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
    for arc, (_, _, ws) in shaped.items():
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


def column_map(s: "Solver", names: dict, insts: dict[str, str]) -> dict:
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
    shape by its own name; the labels are those `site_columns` gives, the ones
    every read the converter writes of the relation names. `insts` are the
    instance renames `convert_one` applies to the names."""
    c = s.c
    shaped = _shaped(c, insts)
    out: dict[str, dict[str, list[list[dict]]]] = {}
    for arc, sources in names["relations"].items():
        for source in sources:
            if arc in shaped:
                cols, inst, ws = shaped[arc]
                w = next((w for w in ws if _souffle_relation(c, w) == source), None)
                width = None if w is None else c.souffle_arity(w.scope, w.relation)
                if w is None or w.columns is None or cols is None or width is None or len(cols) != len(w.columns):
                    continue
                got = _souffle_columns(site_columns(c, cols, inst), w.columns, width)
            else:
                scope, relation = tuple(source["component"]), source["relation"]
                if source["path"] is not None:
                    _, cols, _, inst = c.resolve(relation_name(source["path"]), (), {})
                elif scope == ("Determine",):   # the instance a run adds (`solver.determine.run_program`) has no path in the solver's text
                    _, cols, _, inst = c.resolve(relation_name(relation), scope, {})
                else:
                    continue
                width = c.souffle_arity(scope, relation)
                if cols is None or width is None:
                    continue
                kept = tuple(j for j in range(width) if j not in c.dropped.get((scope, relation), ()))
                if len(kept) != len(cols):
                    continue
                got = _souffle_columns(site_columns(c, cols, inst), kept, width)
            out.setdefault(arc, {})[source["relation"] if source["path"] is None else source["path"]] = got
    return out


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
