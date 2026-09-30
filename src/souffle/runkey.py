"""The digest of a parsed program that a run's cache key holds, computed
without rendering the program.

The text a run renders is a function of the program's fields and its
layout: `expand` and the renderer read nothing else. They read a part's id
only to place the part: a part whose id the layout holds renders at that
place, and every other part, one an operation wrote, renders after the
placed parts of its scope, in the order of its id. An operation writes each
new part with the next id past every id the program and its layout hold,
so the same part can come with different ids, and the digest reads a
written part's id only as its rank among the written parts' ids.

The digest is the SHA-256 of the layout's digest and, for each field that
holds parts, its length and a record per part in the order the field holds
them, then the digest of each other field. A placed part's record holds
the SHA-256 of its `repr`, which states every field of the part. A written
part's holds its rank and the SHA-256 of its `repr` with its id left out;
a RIGID call that holds a written unit states that unit by its rank. Two programs with equal digests therefore have equal layouts, equal
placed parts at equal places, and written parts equal but for ids in the
same order, and render the same text.

A program an operation derives shares its layout, the fields the operation
did not change and the parts it kept with its source, and each digest is
held by the identity of the object it digests: the derived program digests
only the parts the operation wrote, and looks up each other part once."""

import hashlib
from collections.abc import Callable
from dataclasses import fields, replace

from engine.program import DeclId, Program, RigidCall, UnitId
from souffle.layout import IncludeBlock, Key, Layout, Segment, layout_keys, layout_of

PART_CAP = 1 << 17
"""The most part records held at once; past it the held records are
dropped."""
FIELD_CAP = 1 << 11
"""The most field, program and layout digests held at once."""

_PARTS = ("types", "relations", "components", "instances", "functors", "units", "macros")
"""The fields that hold parts, each with an id."""
_OTHERS = tuple(f.name for f in fields(Program) if f.name not in _PARTS)

PLACED, WRITTEN, HOLDS_WRITTEN = 0, 1, 2
"""What a part is under a layout: placed; written; or a placed RIGID call
that holds a written unit."""

_parts: dict[int, tuple[object, Layout, int, bytes]] = {}
"""Per part, under the layout it was last read with: what it is, and its
record where placed, else its digest with its id left out."""
_fields: dict[int, tuple[object, bytes]] = {}
_programs: dict[int, tuple[object, bytes]] = {}
_layouts: dict[int, tuple[Layout, bytes, tuple[str, ...], frozenset[Key]]] = {}


def _held(memo: dict[int, tuple[object, bytes]], cap: int, obj: object,
          compute: Callable[[], bytes]) -> bytes:
    """The digest held for `obj`, computed once while it is held. Each
    entry holds its object, so that no other object takes its id."""
    got = memo.get(id(obj))
    if got is not None and got[0] is obj:
        return got[1]
    digest = compute()
    if len(memo) >= cap:
        memo.clear()
    memo[id(obj)] = (obj, digest)
    return digest


def _sha(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def _part(part: object, layout: Layout,
          placed: frozenset[Key]) -> tuple[object, Layout, int, bytes]:
    key = part.id  # type: ignore[attr-defined]
    if key not in placed:
        blank = DeclId(-1) if isinstance(key, DeclId) else UnitId(-1)
        entry = (part, layout, WRITTEN, _sha(repr(replace(part, id=blank))))  # type: ignore[type-var]
    elif isinstance(part, RigidCall) and any(k not in placed for k in part.body):
        entry = (part, layout, HOLDS_WRITTEN, b"")
    else:
        entry = (part, layout, PLACED, b"p" + bytes(4) + _sha(repr(part)))
    if len(_parts) >= PART_CAP:
        _parts.clear()
    _parts[id(part)] = entry
    return entry


def _field(values: tuple[object, ...]) -> bytes:
    return _held(_fields, FIELD_CAP, values,
                 lambda: _sha(repr(values)))


def _included(segments: tuple[Segment, ...]) -> list[str]:
    out: list[str] = []
    for s in segments:
        if isinstance(s, IncludeBlock):
            out.append(s.path)
            out += _included(s.body)
        elif hasattr(s, "body"):
            out += _included(s.body)  # type: ignore[attr-defined]
    return out


def _layout(layout: Layout) -> tuple[bytes, tuple[str, ...], frozenset[Key]]:
    """The layout's digest, the path of each file it includes, and the
    key of every part it places."""
    got = _layouts.get(id(layout))
    if got is not None and got[0] is layout:
        return got[1], got[2], got[3]
    held = (_sha(repr(layout)), tuple(_included(layout.segments)),
            frozenset(layout_keys(layout.segments)))
    if len(_layouts) >= FIELD_CAP:
        _layouts.clear()
    _layouts[id(layout)] = (layout, *held)
    return held


def included_files(program: Program) -> tuple[str, ...]:
    """The path of each file the program's layout includes, in the order
    the layout holds them."""
    return _layout(layout_of(program))[1]


def _order(key: Key) -> tuple[int, int]:
    """Declarations first, then units, each in the order of its id, as the
    renderer places written parts."""
    return (0 if isinstance(key, DeclId) else 1, key.index)


def program_digest(program: Program) -> bytes:
    def compute() -> bytes:
        layout = layout_of(program)
        digest, _, placed = _layout(layout)
        get = _parts.get
        groups: list[list[tuple[object, Layout, int, bytes]]] = []
        written: list[Key] = []
        for name in _PARTS:
            group = []
            for p in getattr(program, name):
                e = get(id(p))
                if e is None or e[0] is not p or e[1] is not layout:
                    e = _part(p, layout, placed)
                if e[2] == WRITTEN:
                    written.append(p.id)
                group.append(e)
            groups.append(group)
        rank = {key: i for i, key in enumerate(sorted(written, key=_order))}
        out = [digest]
        for group in groups:
            out.append(len(group).to_bytes(4, "big"))
            for p, _, kind, got in group:
                if kind == PLACED:
                    out.append(got)
                elif kind == WRITTEN and not isinstance(p, RigidCall):
                    out.append(b"w" + rank[p.id].to_bytes(4, "big") + got)  # type: ignore[attr-defined]
                else:
                    assert isinstance(p, RigidCall)
                    r = rank.get(p.id)
                    body = tuple(UnitId(-1 - rank[k]) if k in rank else k for k in p.body)
                    at = UnitId(-1 - r) if r is not None else p.id
                    out.append(b"r" + (r if r is not None else 0).to_bytes(4, "big")
                               + _sha(repr(replace(p, id=at, body=body))))
        for name in _OTHERS:
            out.append(_field(getattr(program, name)))
        return hashlib.sha256(b"".join(out)).digest()

    return _held(_programs, FIELD_CAP, program, compute)
