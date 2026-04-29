"""Custom JSON formatter for materialized task files.

Layout rules:
  - 2-space indent at the top level and most nesting.
  - Lists of dicts use brace-up: '[{' on the open line, '}, {' between items,
    '}]' on the close. Saves one indent level per example body.
  - Grid rows (list[list[int]]) render one row per line, no inter-cell spaces.
  - Lists of plain ints render one-line: [1,0,2].
  - Dicts with ≤2 primitive-valued keys render one-line if they fit in 80 cols.
"""

from __future__ import annotations

import json
from typing import Any


def format_file(d: dict[str, Any]) -> str:
    return _fmt_dict(d, 0) + "\n"


def _fmt_dict(d: dict, depth: int) -> str:
    if not d:
        return "{}"
    if depth > 0:
        one_line = _try_compact_dict(d)
        if one_line is not None:
            return one_line
    inner = "  " * (depth + 1)
    items = list(d.items())
    parts = ["{"]
    for i, (k, v) in enumerate(items):
        sep = "," if i < len(items) - 1 else ""
        parts.append(f"{inner}{json.dumps(k)}: {_fmt_value(v, depth + 1)}{sep}")
    parts.append("  " * depth + "}")
    return "\n".join(parts)


def _try_compact_dict(d: dict) -> str | None:
    """Return one-line rendering if dict is small + simple; else None."""
    if len(d) > 2:
        return None
    parts = []
    for k, v in d.items():
        if isinstance(v, dict):
            return None
        if isinstance(v, list):
            if not all(isinstance(x, int) for x in v):
                return None
            v_str = "[" + ",".join(str(x) for x in v) + "]"
        else:
            v_str = json.dumps(v)
        parts.append(f"{json.dumps(k)}: {v_str}")
    rendered = "{ " + ", ".join(parts) + " }"
    return rendered if len(rendered) <= 80 else None


def _fmt_value(v: Any, depth: int) -> str:
    if isinstance(v, dict):
        return _fmt_dict(v, depth)
    if isinstance(v, list):
        return _fmt_list(v, depth)
    return json.dumps(v)


def _fmt_list(lst: list, depth: int) -> str:
    if not lst:
        return "[]"
    if all(isinstance(r, list) and r and all(isinstance(c, int) for c in r) for r in lst):
        return _fmt_grid(lst, depth)
    if all(isinstance(v, int) for v in lst):
        return "[" + ",".join(str(v) for v in lst) + "]"
    if all(isinstance(v, dict) for v in lst):
        return _fmt_brace_up(lst, depth)
    raise NotImplementedError(f"unsupported list element types in {lst!r}")


def _fmt_grid(grid: list[list[int]], depth: int) -> str:
    inner = "  " * (depth + 1)
    outer = "  " * depth
    rows = ",\n".join(f"{inner}[{','.join(str(c) for c in row)}]" for row in grid)
    return f"[\n{rows}\n{outer}]"


def _fmt_brace_up(items: list[dict], depth: int) -> str:
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
