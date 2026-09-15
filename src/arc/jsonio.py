"""Custom JSON formatter for materialized task files.

Layout rules:
  - 2-space indent at the top level and most nesting.
  - Lists of dicts use brace-up: '[{' on the open line, '}, {' between items,
    '}]' on the close. Saves one indent level per example body.
  - Grid rows (list[list[int]]) render one row per line, no inter-cell spaces.
  - Lists of plain ints render one-line: [1,0,2]. So does any list whose
    elements are scalars and lists of plain ints: [[0,2,0,2],"D4_LR"].
  - Any other list of lists renders one element per line.
  - Dicts with ≤2 primitive-valued keys render one-line if they fit in 80 cols.
"""

from __future__ import annotations

import json
from typing import Any, TypeGuard


def format_file(d: dict[str, Any]) -> str:
    return _fmt_dict(d, 0) + "\n"


def _fmt_dict(d: dict[str, Any], depth: int) -> str:
    if not d:
        return "{}"
    if depth > 0:
        one_line = _try_compact_dict(d)
        if one_line is not None:
            return one_line
    inner = "  " * (depth + 1)
    items = list(d.items())
    parts: list[str] = ["{"]
    for i, (k, v) in enumerate(items):
        sep = "," if i < len(items) - 1 else ""
        parts.append(f"{inner}{json.dumps(k)}: {_fmt_value(v, depth + 1)}{sep}")
    parts.append("  " * depth + "}")
    return "\n".join(parts)


def _try_compact_dict(d: dict[str, Any]) -> str | None:
    """Return one-line rendering if dict is small + simple; else None."""
    if len(d) > 2:
        return None
    parts: list[str] = []
    for k, v in d.items():
        if _is_dict(v):
            return None
        if _is_list(v):
            if not _is_int_list(v):
                return None
            v_str = "[" + ",".join(str(x) for x in v) + "]"
        else:
            v_str = json.dumps(v)
        parts.append(f"{json.dumps(k)}: {v_str}")
    rendered = "{ " + ", ".join(parts) + " }"
    return rendered if len(rendered) <= 80 else None


def _fmt_value(v: Any, depth: int) -> str:
    if _is_dict(v):
        return _fmt_dict(v, depth)
    if _is_list(v):
        return _fmt_list(v, depth)
    return json.dumps(v)


def _fmt_list(lst: list[Any], depth: int) -> str:
    if not lst:
        return "[]"
    if _is_int_grid(lst):
        return _fmt_grid(lst, depth)
    one_line = _try_compact_list(lst)
    if one_line is not None:
        return one_line
    if _is_list_of_dicts(lst):
        return _fmt_brace_up(lst, depth)
    if all(_is_list(v) for v in lst):
        return _fmt_rows(lst, depth)
    raise NotImplementedError(f"unsupported list element types in {lst!r}")


def _try_compact_list(lst: list[Any]) -> str | None:
    """One-line rendering of a list whose every element is a scalar or a
    list of plain ints; None when some element needs more room."""
    items = [_compact_item(v) for v in lst]
    if any(i is None for i in items):
        return None
    return "[" + ",".join(items) + "]"


def _compact_item(v: Any) -> str | None:
    if _is_scalar(v):
        return json.dumps(v)
    if _is_int_list(v):
        return "[" + ",".join(str(x) for x in v) + "]"
    return None


def _fmt_rows(rows: list[Any], depth: int) -> str:
    """One element per line, for a list of lists no other rule covers."""
    inner = "  " * (depth + 1)
    outer = "  " * depth
    body = ",\n".join(f"{inner}{_fmt_value(r, depth + 1)}" for r in rows)
    return f"[\n{body}\n{outer}]"


def _fmt_grid(grid: list[list[int]], depth: int) -> str:
    inner = "  " * (depth + 1)
    outer = "  " * depth
    rows = ",\n".join(f"{inner}[{','.join(str(c) for c in row)}]" for row in grid)
    return f"[\n{rows}\n{outer}]"


def _fmt_brace_up(items: list[dict[str, Any]], depth: int) -> str:
    """Brace-up list of dicts. Body lines sit at depth+1; the array's brackets
    ('[{', '}, {', '}]') align with the enclosing key at depth."""
    outer = "  " * depth
    inner = "  " * (depth + 1)
    parts: list[str] = []
    for i, item in enumerate(items):
        if i == 0:
            parts.append("[{")
        else:
            parts.append(f"{outer}}}, {{")
        body = list(item.items())
        for j, (k, v) in enumerate(body):
            sep = "," if j < len(body) - 1 else ""
            parts.append(f"{inner}{json.dumps(k)}: {_fmt_value(v, depth + 1)}{sep}")
    parts.append(f"{outer}}}]")
    return "\n".join(parts)


def _is_scalar(v: Any) -> bool:
    return v is None or isinstance(v, (bool, int, float, str))


def _is_dict(v: Any) -> TypeGuard[dict[str, Any]]:
    return isinstance(v, dict)


def _is_list(v: Any) -> TypeGuard[list[Any]]:
    return isinstance(v, list)


def _is_int_list(v: Any) -> TypeGuard[list[int]]:
    return _is_list(v) and all(isinstance(x, int) for x in v)


def _is_int_grid(v: Any) -> TypeGuard[list[list[int]]]:
    return _is_list(v) and all(_is_int_list(r) and len(r) > 0 for r in v)


def _is_list_of_dicts(v: Any) -> TypeGuard[list[dict[str, Any]]]:
    return _is_list(v) and all(_is_dict(x) for x in v)
