"""The Souffle rows of each lib element on the inputs that `arclog-cli
lib-compare` generates, which the engine's lib comparison compares with and
which no check runs Souffle to make: one record per inputs file, beside the
solver records (`parity.snapshot.parity_dir`), under the key of what its
rows depend on (`lib_key`), with the digest of the Souffle sources it was
made from (`sources_digest`). The form of an inputs file is in the module
comment of `engine/arclog-cli/src/lib_compare/inputs.rs`, and that of the
digest in the module comment of `engine/arclog-cli/src/lib_compare/sources.rs`.

An element's Souffle name, and the Souffle names of its columns or its
relations, are the inverse of `REL` and `COMP` of
`arclog_convert.libmap`; a name that neither renames is its own
Souffle name. A Souffle column's name is matched with an arclog column by
its first letter in capitals."""

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any

from arclog_convert import libmap
from cli.common import LIMITS, engine, stamp
from engine import ParseFailure, Program, RelationName, Scope, Tuples, checkout
from engine.engine import LIB_PROBE, LIB_ROWS, lib_domain
from engine.program import NumberTerm, RecordValue, RelationDecl, Rows, TypeName, Value
from parity.snapshot import parity_dir
from solver.vocabulary import LIB_FILE
from souffle.install import binary_identity

INSTANCE = "c"
"""The name a component's instance takes in the program."""


class ElementKind(StrEnum):
    """The kind of the element of an inputs file."""

    RELATION = "relation"
    COMPONENT = "component"


class Kind(StrEnum):
    """The kind of a column's values in an inputs file."""

    NUMBER = "number"
    BOX = "box"
    CONSTANT = "constant"


def lib_dir() -> Path:
    """The lib records, under the solver records."""
    return parity_dir() / "lib"


def inputs_dir() -> Path:
    """The inputs files the engine's command writes."""
    return lib_dir() / "inputs"


@dataclass(frozen=True)
class Renames:
    """An element's Souffle name, and the arclog name of each of its
    columns or relations that is renamed, by its Souffle name."""

    souffle: str
    parts: Mapping[str, str]


def libmap_path() -> Path:
    """The renames of the lib."""
    return Path(libmap.__file__)


def renames(element: str, component: bool) -> Renames:
    """The Souffle name of the arclog element `element`, and its parts'
    renames."""
    table = libmap.COMP if component else libmap.REL
    for souffle, renamed in table.items():
        if renamed.name == element:
            return Renames(souffle, renamed.parts)
    return Renames(element, {})


@cache
def _lib() -> Program:
    got = engine().parse_including("", LIB_FILE, checkout.programs())
    if isinstance(got, ParseFailure):
        raise RuntimeError(got)
    return got


def lib_key(inputs: bytes) -> str:
    """The hash of what the rows of the inputs file `inputs` depend on: its
    bytes, the code and Souffle sources of a run (`cli.common.stamp`), the
    Souffle binary, and the renames of the lib."""
    h = hashlib.sha256(inputs)
    h.update(stamp().encode())
    h.update(binary_identity())
    h.update(libmap_path().read_bytes())
    return h.hexdigest()


FNV_OFFSET_BASIS = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3


def fnv1a64(data: bytes) -> str:
    """64-bit FNV-1a of `data`, as 16 lowercase hex digits."""
    h = FNV_OFFSET_BASIS
    for byte in data:
        h = ((h ^ byte) * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def sources_digest() -> str:
    """The digest of the present Souffle sources of the records."""
    lib = checkout.programs() / "lib"
    sources = [(f"programs/{LIB_FILE}", _lib_path())]
    sources += [(f"programs/lib/{p.name}", p)
                for p in sorted(lib.glob("*.dl"), key=lambda p: p.name.encode())]
    sources.append(("work/arclog/libmap/__init__.py", libmap_path()))
    return fnv1a64(b"".join(shown.encode() + b"\0" + path.read_bytes() + b"\0"
                            for shown, path in sources))


def write_all() -> list[Path]:
    """Writes the record of each inputs file whose record's key or sources
    digest differs from its own, and gives the path of each record
    written."""
    written = []
    sources = sources_digest()
    for path in sorted(inputs_dir().glob("*.json")):
        data = path.read_bytes()
        key = lib_key(data)
        out = lib_dir() / path.name
        if out.exists():
            old = json.loads(out.read_text())
            if old.get("key") == key and old.get("sources") == sources:
                continue
        inputs = json.loads(data)
        record = {"key": key, "sources": sources, "inputs": inputs} | outcome(inputs)
        out.write_text(json.dumps(record) + "\n")
        written.append(out)
    return written


def outcome(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """The Souffle side of an inputs file: `rows`, each mode's rows or each
    output's; `undeclared`, the inputs with rows that the Souffle form does
    not declare; `no_souffle_form`; or `failure`, the kind of the failure
    and its text."""
    match ElementKind(inputs["kind"]):
        case ElementKind.RELATION:
            return _relation(inputs)
        case ElementKind.COMPONENT:
            return _component(inputs)


def _lib_path() -> Path:
    return checkout.programs() / LIB_FILE


@cache
def _numbers() -> dict[str, int]:
    """The number of each constant the lib defines, by its name."""
    return {d.name: int(d.value.value) for d in _lib().defines
            if d.params is None and isinstance(d.value, NumberTerm)}


def _value_in(value: Any) -> Value:
    """A value of an inputs file as the run takes it: a Box as its record,
    and a constant as its number."""
    if isinstance(value, list):
        return RecordValue(tuple(_value_in(v) for v in value))
    if isinstance(value, str):
        return _numbers()[value]
    return value


def _rows_in(rows: Sequence[Sequence[Any]]) -> Rows:
    return tuple(tuple(_value_in(v) for v in row) for row in rows)


def _present(column: str) -> str:
    return column[:1].upper() + column[1:]


def _relation(inputs: Mapping[str, Any]) -> dict[str, Any]:
    names = renames(inputs["element"], component=False)
    decl = next((r for r in _lib().relations
                 if r.name == names.souffle and not r.scope.components), None)
    if decl is None:
        return {"no_souffle_form": True}
    column = {names.parts.get(_present(c.name), _present(c.name)): i
              for i, c in enumerate(decl.columns)}
    arclog = [name for name, _ in inputs["columns"]]
    if any(name not in column for name in arclog) or len(arclog) != len(decl.columns):
        return {"failure": f"columns: the Souffle form {names.souffle} has columns "
                           f"{[c.name for c in decl.columns]}, the element {arclog}"}
    domains = {column[n]: values for n, values in inputs["domains"].items()}
    kinds = [Kind(k) for _, k in inputs["columns"]]
    eng = engine()
    rows = []
    for mode in inputs["modes"]:
        bound = [column[n] for n in mode["mode"]]
        program = eng.lib_probe(_lib_path(), names.souffle, bound, sorted(domains))
        facts = {lib_domain(i): _rows_in([[v] for v in values])
                 for i, values in domains.items() if i not in bound}
        if bound:
            facts[LIB_PROBE] = _rows_in(mode["rows"])
        got = _run(program, facts, [LIB_ROWS])
        if not isinstance(got, list):
            return got
        rows.append(_rows_out(([row[column[n]] for n in arclog] for row in got[0]), kinds))
    return {"rows": rows}


def _component(inputs: Mapping[str, Any]) -> dict[str, Any]:
    names = renames(inputs["element"], component=True)
    eng = engine()
    index = eng.index(_lib())
    comp = index.component(names.souffle, Scope(()))
    if comp is None:
        return {"no_souffle_form": True}
    declared: dict[str, RelationDecl] = {}
    for c in reversed(index.chain(comp)):
        inner = (*c.scope.components, c.name)
        declared |= {r.name: r for r in _lib().relations if r.scope.components == inner}
    souffle = {names.parts.get(r, r): r for r in declared}
    undeclared = [i["port"] for i in inputs["inputs"] if i["rows"] and i["port"] not in souffle]
    if undeclared:
        return {"undeclared": undeclared}
    lacking = [o["port"] for o in inputs["outputs"] if o["port"] not in souffle]
    if lacking:
        return {"failure": f"outputs: the Souffle form {names.souffle} has no relation of "
                           f"{', '.join(lacking)}"}
    widths = [f"{p['port']} has {len(p['columns'])}, {souffle[p['port']]} "
              f"{len(declared[souffle[p['port']]].columns)}"
              for p in (*inputs["inputs"], *inputs["outputs"])
              if p["port"] in souffle
              and len(p["columns"]) != len(declared[souffle[p["port"]]].columns)]
    if widths:
        return {"failure": f"columns: of the Souffle form {names.souffle}: {'; '.join(widths)}"}
    program = eng.lib_instance(_lib_path(), INSTANCE, names.souffle,
                               [TypeName((), t) for t in inputs["type_arguments"]])
    facts = {RelationName((INSTANCE,), souffle[i["port"]]): _rows_in(i["rows"])
             for i in inputs["inputs"] if i["port"] in souffle}
    outs = [RelationName((INSTANCE,), souffle[o["port"]]) for o in inputs["outputs"]]
    got = _run(program, facts, outs)
    if not isinstance(got, list):
        return got
    kinds = [[Kind(k) for _, k in o["columns"]] for o in inputs["outputs"]]
    return {"rows": [_rows_out(rows, ks) for rows, ks in zip(got, kinds, strict=True)]}


def _run(program: Program | ParseFailure, facts: Mapping[RelationName, Rows],
         outs: Sequence[RelationName]) -> list[Rows] | dict[str, Any]:
    """The rows of each of `outs` after a run over `facts`, or the record of
    the failure."""
    if isinstance(program, ParseFailure):
        return {"failure": f"parse: {program}"}
    result = engine().run(program, facts, outs, LIMITS)
    if not isinstance(result, Tuples):
        return {"failure": f"{type(result).__name__}: {result}"}
    return [result.relations[out] for out in outs]


def _rows_out(rows: Iterable[Sequence[Value]], kinds: Sequence[Kind]) -> list[Any]:
    """The rows as an inputs file writes values, in the order of their
    text."""
    names = {n: name for name, n in _numbers().items()}

    def value(v: Value, kind: Kind) -> Any:
        if isinstance(v, RecordValue):
            return [value(f, Kind.NUMBER) for f in v.fields]
        if kind is Kind.CONSTANT:
            assert isinstance(v, int), v
            return names[v]
        return v

    got = {json.dumps([value(v, k) for v, k in zip(row, kinds, strict=True)]) for row in rows}
    return [json.loads(r) for r in sorted(got)]
