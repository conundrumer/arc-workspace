"""Apply a parsed Patch to a Task, returning a new Task.

Semantics:
  - @diff:    asserts plain cells, applies N~M cells (replacement). Dims preserved.
  - @replace: asserts old grid matches, swaps to new grid. Dims may change.
  - @delete:  asserts input + output grids match the example, then drops it.
  - @branch:  asserts plain cells against base output, sets task[set][idx].alt
              from base + (base~alt) cells. Errors if the example already has an alt.

Index semantics:
  Indices refer to the pre-patch state. Non-structural ops apply first;
  deletes apply last in reverse-index order, so they don't shift earlier
  sections' targets.
"""

from __future__ import annotations

import copy

from .patch import (
    BranchSection,
    DeleteSection,
    DiffSection,
    Patch,
    ReplaceSection,
    Section,
)
from .task import Alt, Example, Grid, Task


class PatchApplyError(Exception):
    pass


def apply_patch(task: Task, patch: Patch) -> Task:
    result = copy.deepcopy(task)

    deletes: list[DeleteSection] = []
    for sec in patch.sections:
        if isinstance(sec, DeleteSection):
            deletes.append(sec)
        else:
            _apply_nonstructural(result, sec)

    for sec in sorted(deletes, key=lambda d: -d.idx):
        _apply_delete(result, sec)

    return result


def _examples(task: Task, set_: str) -> list[Example]:
    return task.train if set_ == "train" else task.test


def _example(task: Task, set_: str, idx: int, ctx: str) -> Example:
    arr = _examples(task, set_)
    if idx < 0 or idx >= len(arr):
        raise PatchApplyError(
            f"{ctx}: index {idx} out of range for {set_} (len {len(arr)})"
        )
    return arr[idx]


def _grid_of(ex: Example, grid: str) -> Grid:
    return ex.input if grid == "input" else ex.output


def _set_grid(ex: Example, grid: str, value: Grid) -> None:
    if grid == "input":
        ex.input = value
    else:
        ex.output = value


def _apply_nonstructural(task: Task, sec: Section) -> None:
    if isinstance(sec, DiffSection):
        ctx = f"@diff {sec.set} {sec.idx} {sec.grid}"
        ex = _example(task, sec.set, sec.idx, ctx)
        cur = _grid_of(ex, sec.grid)
        new = _apply_diff_rows(cur, sec.rows, ctx)
        _set_grid(ex, sec.grid, new)
        return

    if isinstance(sec, ReplaceSection):
        ctx = f"@replace {sec.set} {sec.idx} {sec.grid}"
        ex = _example(task, sec.set, sec.idx, ctx)
        cur = _grid_of(ex, sec.grid)
        if cur != sec.old:
            raise PatchApplyError(f"{ctx}: old grid does not match current state")
        _set_grid(ex, sec.grid, [list(row) for row in sec.new])
        return

    if isinstance(sec, BranchSection):
        ctx = f"@branch {sec.set} {sec.idx} {sec.kind}"
        ex = _example(task, sec.set, sec.idx, ctx)
        if ex.alt is not None:
            raise PatchApplyError(f"{ctx}: example already has an alt; only one allowed")
        alt_grid = _apply_branch_rows(ex.output, sec.rows, ctx)
        ex.alt = Alt(kind=sec.kind, grid=alt_grid)
        return

    raise PatchApplyError(f"unhandled section type: {type(sec).__name__}")


def _apply_delete(task: Task, sec: DeleteSection) -> None:
    ctx = f"@delete {sec.set} {sec.idx}"
    arr = _examples(task, sec.set)
    if sec.idx < 0 or sec.idx >= len(arr):
        raise PatchApplyError(
            f"{ctx}: index {sec.idx} out of range for {sec.set} (len {len(arr)})"
        )
    ex = arr[sec.idx]
    if ex.input != sec.input:
        raise PatchApplyError(f"{ctx}: input grid does not match current state")
    if ex.output != sec.output:
        raise PatchApplyError(f"{ctx}: output grid does not match current state")
    del arr[sec.idx]


def _apply_diff_rows(cur: Grid, rows: list[list[int | tuple[int, int]]], ctx: str) -> Grid:
    if len(rows) != len(cur):
        raise PatchApplyError(
            f"{ctx}: row count {len(rows)} != grid height {len(cur)}"
        )
    out: Grid = []
    for r, (cur_row, diff_row) in enumerate(zip(cur, rows, strict=True)):
        if len(diff_row) != len(cur_row):
            raise PatchApplyError(
                f"{ctx}: row {r} col count {len(diff_row)} != grid width {len(cur_row)}"
            )
        new_row: list[int] = []
        for c, (cur_val, cell) in enumerate(zip(cur_row, diff_row, strict=True)):
            if isinstance(cell, tuple):
                old, new = cell
                if cur_val != old:
                    raise PatchApplyError(
                        f"{ctx}: row {r} col {c}: expected {old}, got {cur_val}"
                    )
                new_row.append(new)
            else:
                if cur_val != cell:
                    raise PatchApplyError(
                        f"{ctx}: row {r} col {c}: expected {cell}, got {cur_val}"
                    )
                new_row.append(cur_val)
        out.append(new_row)
    return out


def _apply_branch_rows(base: Grid, rows: list[list[int | tuple[int, int]]], ctx: str) -> Grid:
    if len(rows) != len(base):
        raise PatchApplyError(
            f"{ctx}: row count {len(rows)} != base output height {len(base)}"
        )
    out: Grid = []
    any_change = False
    for r, (base_row, branch_row) in enumerate(zip(base, rows, strict=True)):
        if len(branch_row) != len(base_row):
            raise PatchApplyError(
                f"{ctx}: row {r} col count {len(branch_row)} != base width {len(base_row)}"
            )
        new_row: list[int] = []
        for c, (base_val, cell) in enumerate(zip(base_row, branch_row, strict=True)):
            if isinstance(cell, tuple):
                claimed_base, alt = cell
                if base_val != claimed_base:
                    raise PatchApplyError(
                        f"{ctx}: row {r} col {c}: expected base {claimed_base}, got {base_val}"
                    )
                new_row.append(alt)
                any_change = True
            else:
                if base_val != cell:
                    raise PatchApplyError(
                        f"{ctx}: row {r} col {c}: expected {cell}, got {base_val}"
                    )
                new_row.append(base_val)
        out.append(new_row)
    if not any_change:
        raise PatchApplyError(f"{ctx}: branch has no N~M cells; alt is identical to base")
    return out
