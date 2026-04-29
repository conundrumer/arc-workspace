"""Patch DSL parser for ARC tasks.

Format (line-by-line):
  - line starts with '@'   → section header
  - line contains ': '     → metadata (key: value); only valid before first section
  - exactly '---'          → delete-body separator (only inside @delete bodies)
  - blank                  → decoration, ignored
  - else                   → grid row (whitespace-separated cells)

Section verbs:
  @diff    <set> <idx> <grid>            body: grid (plain + N~M cells)
  @replace <set> <idx> <grid>            body: old grid, '---', new grid (both plain)
  @delete  <set> <idx>                   body: input grid, '---', output grid (both plain)
  @branch  <set> <idx> <kind>            body: grid (plain + N~M cells); kind ∈ {rule, tiebreak}

Cell syntax (within grid rows):
  N      → plain (asserted unchanged from prior state)
  N~M    → change (left = prior, right = new); semantics depend on verb:
             @diff:   N → M (replacement)
             @branch: N (base) and M (alt) both valid

Indices are 0-based.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

type SetT = Literal["train", "test"]
type GridT = Literal["input", "output"]
type KindT = Literal["rule", "tiebreak"]

type Cell = int | tuple[int, int]
type GridRows = list[list[Cell]]


@dataclass
class DiffSection:
    set: SetT
    idx: int
    grid: GridT
    rows: GridRows


@dataclass
class ReplaceSection:
    set: SetT
    idx: int
    grid: GridT
    old: list[list[int]]
    new: list[list[int]]


@dataclass
class DeleteSection:
    set: SetT
    idx: int
    input: list[list[int]]
    output: list[list[int]]


@dataclass
class BranchSection:
    set: SetT
    idx: int
    kind: KindT
    rows: GridRows


type Section = DiffSection | ReplaceSection | DeleteSection | BranchSection


@dataclass
class Patch:
    metadata: dict[str, str] = field(default_factory=dict[str, str])
    sections: list[Section] = field(default_factory=list[Section])


class PatchParseError(Exception):
    pass


def parse(text: str) -> Patch:
    lines = text.splitlines()
    metadata, raw_sections = _split(lines)
    sections = [_parse_section(h, b) for h, b in raw_sections]
    return Patch(metadata=metadata, sections=sections)


def _split(lines: list[str]) -> tuple[dict[str, str], list[tuple[str, list[str]]]]:
    metadata: dict[str, str] = {}
    sections: list[tuple[str, list[str]]] = []
    i = 0
    seen_header = False
    while i < len(lines):
        line = lines[i]
        if line.startswith("@"):
            seen_header = True
            header = line[1:].strip()
            body: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("@"):
                body.append(lines[i])
                i += 1
            sections.append((header, body))
            continue
        s = line.strip()
        if not s:
            i += 1
            continue
        if not seen_header:
            if ": " in s:
                key, _, val = s.partition(": ")
                metadata[key.strip()] = val.strip()
                i += 1
                continue
            raise PatchParseError(
                f"line {i + 1}: unrecognized line before first section: {s!r}"
            )
        i += 1
    return metadata, sections


def _parse_section(header: str, body: list[str]) -> Section:
    parts = header.split()
    if not parts:
        raise PatchParseError("empty section header")
    verb, *args = parts
    if verb == "diff":
        set_, idx, grid = _expect_args(verb, args, 3)
        return DiffSection(_set(set_), _idx(idx), _grid(grid), _grid_body(body))
    if verb == "replace":
        set_, idx, grid = _expect_args(verb, args, 3)
        old_g, new_g = _two_grids_body(body, "@replace")
        return ReplaceSection(_set(set_), _idx(idx), _grid(grid), old_g, new_g)
    if verb == "delete":
        set_, idx = _expect_args(verb, args, 2)
        in_g, out_g = _two_grids_body(body, "@delete")
        return DeleteSection(_set(set_), _idx(idx), in_g, out_g)
    if verb == "branch":
        set_, idx, kind = _expect_args(verb, args, 3)
        return BranchSection(_set(set_), _idx(idx), _kind(kind), _grid_body(body))
    raise PatchParseError(f"unknown verb: @{verb}")


def _expect_args(verb: str, args: list[str], n: int) -> list[str]:
    if len(args) != n:
        raise PatchParseError(f"@{verb} expects {n} args; got {args!r}")
    return args


def _grid_body(body: list[str]) -> GridRows:
    rows: GridRows = []
    for ln, line in enumerate(body, 1):
        s = line.strip()
        if not s:
            continue
        if s == "---":
            raise PatchParseError("'---' separator is only allowed in @delete body")
        rows.append(_parse_row(s, ln))
    return rows


def _two_grids_body(body: list[str], ctx: str) -> tuple[list[list[int]], list[list[int]]]:
    chunks: list[GridRows] = [[]]
    for ln, line in enumerate(body, 1):
        s = line.strip()
        if not s:
            continue
        if s == "---":
            chunks.append([])
            continue
        chunks[-1].append(_parse_row(s, ln))
    if len(chunks) != 2:
        raise PatchParseError(
            f"{ctx} body needs exactly one '---' separator; got {len(chunks) - 1}"
        )
    first = _assert_plain(chunks[0], f"{ctx} first grid")
    second = _assert_plain(chunks[1], f"{ctx} second grid")
    return first, second


def _parse_row(s: str, line_no: int) -> list[Cell]:
    out: list[Cell] = []
    for tok in s.split():
        if "~" in tok:
            a, _, b = tok.partition("~")
            try:
                out.append((int(a), int(b)))
            except ValueError as e:
                raise PatchParseError(f"line {line_no}: invalid cell {tok!r}") from e
        else:
            try:
                out.append(int(tok))
            except ValueError as e:
                raise PatchParseError(f"line {line_no}: invalid cell {tok!r}") from e
    return out


def _assert_plain(rows: GridRows, ctx: str) -> list[list[int]]:
    out: list[list[int]] = []
    for r, row in enumerate(rows):
        new_row: list[int] = []
        for c, cell in enumerate(row):
            if isinstance(cell, tuple):
                raise PatchParseError(
                    f"{ctx}: cell at row {r} col {c} uses change syntax (N~M); not allowed here"
                )
            new_row.append(cell)
        out.append(new_row)
    return out


def _set(s: str) -> SetT:
    if s in ("train", "test"):
        return s
    raise PatchParseError(f"expected 'train' or 'test'; got {s!r}")


def _grid(s: str) -> GridT:
    if s in ("input", "output"):
        return s
    raise PatchParseError(f"expected 'input' or 'output'; got {s!r}")


def _kind(s: str) -> KindT:
    if s in ("rule", "tiebreak"):
        return s
    raise PatchParseError(f"expected 'rule' or 'tiebreak'; got {s!r}")


def _idx(s: str) -> int:
    try:
        n = int(s)
    except ValueError as e:
        raise PatchParseError(f"expected integer index; got {s!r}") from e
    if n < 0:
        raise PatchParseError(f"index must be non-negative; got {n}")
    return n
