"""Read and rewrite solver source text, and assemble the program each mode runs.

Covers GRID macro expansion, `.comp` and `.decl` analysis, Consts fact
rewriting, and the per-mode IO directives Souffle needs.
"""

import re

# Per-mode IO directives, appended to the built source.
SOLVE_DIRECTIVES = ".input in(IO=stdin)\n.output out(IO=stdout)\n"
FIT_DIRECTIVES = ".input train_in\n.input train_out\n.output fit_diff(IO=stdout)\n"

COMP_HEADER_RE = re.compile(r"\.comp\s+(\w+)")
DECL_RE = re.compile(r"\.decl\s+(\w+)\s*\(([^)]*)\)")
GRID_CALL_RE = re.compile(r"\bGRID_(MASK_|SPARSE_)?(\d+)x(\d+)\s*\(")


def _split_args(s: str) -> list[str]:
    """Split an argument string at top-level commas."""
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur).strip())
    return parts


def _grid_call_facts(policy: str, h: int, w: int, args: list[str]) -> list[str]:
    """Fact lines for one GRID call, one line per grid row.

    Dense (no policy) emits `rel(p, v).` for every cell. `MASK_` emits
    `rel(p).` for nonzero cells; `SPARSE_` emits `rel(p, v).` for nonzero
    cells. Args between the relation name and the h*w cell values pass
    through as leading columns.
    """
    rel, keys, cells = args[0], args[1:len(args) - h * w], args[len(args) - h * w:]
    lead = "".join(f"{k}, " for k in keys)
    rows = []
    for row in range(h):
        facts = []
        for col in range(w):
            v = cells[row * w + col]
            if policy and v == "0":
                continue
            p = f"[{row}, {h - 1 - row}, {col}, {w - 1 - col}]"
            val = "" if policy == "MASK_" else f", {v}"
            facts.append(f"{rel}({lead}{p}{val}).")
        if facts:
            rows.append(" ".join(facts))
    return rows


def expand_grid_macros(source: str) -> str:
    """Replace each GRID call site with the facts it denotes."""
    out, pos = [], 0
    for m in GRID_CALL_RE.finditer(source):
        if m.start() < pos:
            continue
        policy, h, w = m.group(1) or "", int(m.group(2)), int(m.group(3))
        depth, i = 1, m.end()
        while i < len(source) and depth:
            if source[i] == "(":
                depth += 1
            elif source[i] == ")":
                depth -= 1
            i += 1
        args = _split_args(source[m.end():i - 1])
        if len(args) < 1 + h * w:
            raise ValueError(f"GRID call needs rel + {h * w} cells: {source[m.start():i]!r}")
        line_start = source.rfind("\n", 0, m.start()) + 1
        prefix = source[line_start:m.start()]
        indent = prefix if not prefix.strip() else ""
        rows = _grid_call_facts(policy, h, w, args)
        out.append(source[pos:m.start()])
        out.append(f"\n{indent}".join(rows))
        pos = i
    out.append(source[pos:])
    return "".join(out)


def comp_decls(source: str, comp_name: str) -> dict[str, list[str]]:
    """Map relation name -> argument types for `.decl`s directly inside comp `comp_name`."""
    decls: dict[str, list[str]] = {}
    in_comp = False
    depth = 0
    for line in source.splitlines():
        line = line.split("//")[0]
        if not in_comp:
            m = COMP_HEADER_RE.search(line)
            if m and m.group(1) == comp_name and "{" in line:
                in_comp = True
                depth = line.count("{") - line.count("}")
            continue
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break
        m = DECL_RE.search(line)
        if m:
            args = m.group(2).strip()
            decls[m.group(1)] = [
                a.split(":")[1].strip() for a in args.split(",") if ":" in a
            ]
    return decls


def fit_slots(source: str) -> dict[str, int] | None:
    """Fitted slots: Fit decls that mirror a Consts decl. None when no Fit comp."""
    fit = comp_decls(source, "Fit")
    if not fit:
        return None
    consts = comp_decls(source, "Consts")
    return {name: len(types) for name, types in fit.items() if name in consts}


def _comp_span(source: str, comp_name: str) -> tuple[int, int]:
    """[start, end) line indices of comp `comp_name`'s interior; (0, 0) when absent."""
    lines = source.splitlines()
    depth = 0
    start = None
    for i, raw in enumerate(lines):
        code = raw.split("//")[0]
        if start is None:
            if re.search(rf"\.comp\s+{comp_name}\b", code) and "{" in code:
                depth = code.count("{") - code.count("}")
                start = i + 1
            continue
        depth += code.count("{") - code.count("}")
        if depth <= 0:
            return (start, i)
    return (0, 0)


def _consts_fact_lines(source: str) -> list[int]:
    """Line indices inside Consts outside any rule statement.

    A slot atom can also close a Consts rule (`x(N) :- fat(N).`), where it
    reads like a fact; fact matching stays off rule lines.
    """
    lines = source.splitlines()
    s, e = _comp_span(source, "Consts")
    idxs = []
    in_rule = False
    for i in range(s, e):
        code = lines[i].split("//")[0]
        if not in_rule and ":-" in code:
            in_rule = True
        if in_rule:
            if code.rstrip().endswith("."):
                in_rule = False
            continue
        idxs.append(i)
    return idxs


def _slot_atoms(code: str, slot: str) -> list[tuple[int, int, str]]:
    """(start, end, args) for each `slot(...).` fact atom in `code`."""
    spans = []
    for m in re.finditer(rf"\b{slot}\s*\(", code):
        depth, i = 1, m.end()
        while i < len(code) and depth:
            if code[i] == "(":
                depth += 1
            elif code[i] == ")":
                depth -= 1
            i += 1
        rest = code[i:].lstrip()
        if depth == 0 and rest.startswith("."):
            end = len(code) - len(rest) + 1
            spans.append((m.start(), end, code[m.end():i - 1]))
    return spans


def _slot_facts(source: str, slot: str) -> list[list[str]]:
    """Argument lists of `slot`'s Consts facts."""
    lines = source.splitlines()
    return [
        _split_args(args)
        for i in _consts_fact_lines(source)
        for (_, _, args) in _slot_atoms(lines[i].split("//")[0], slot)
    ]


def _render_arg(v) -> str:
    return f"[{', '.join(str(x) for x in v)}]" if isinstance(v, tuple) else str(v)


def swap_fact(source: str, slot: str, values: tuple) -> str:
    """Replace `slot`'s Consts facts with a single fact holding `values`."""
    return swap_facts(source, slot, [values])


def swap_facts(source: str, slot: str, rows: list[tuple]) -> str:
    """Replace `slot`'s Consts facts with one fact per row."""
    lines = source.splitlines()
    _, e = _comp_span(source, "Consts")
    for i in _consts_fact_lines(source):
        code, sep, comment = lines[i].partition("//")
        for start, end, _ in reversed(_slot_atoms(code, slot)):
            code = code[:start] + code[end:]
        lines[i] = code + sep + comment
    for row in rows:
        args = ", ".join(_render_arg(v) for v in row)
        lines.insert(e, f"    {slot}({args}).")
    return "\n".join(lines) + "\n"


def build_source(source: str) -> str:
    """Assemble the solve-mode program from a solver file's source."""
    return f"{expand_grid_macros(source)}\n{SOLVE_DIRECTIVES}"


def build_fit_source(source: str, slots: dict[str, int]) -> str:
    """Assemble the fit-mode program: Fit instance, per-slot diffs, directives."""
    lines = [".init fit = Fit"]
    for name, arity in sorted(slots.items()):
        args = ", ".join(f"A{i}" for i in range(arity))
        lines.append(f'fit_diff("{name}") :- fit.{name}({args}), !c.{name}({args}).')
        lines.append(f'fit_diff("{name}") :- c.{name}({args}), !fit.{name}({args}).')
    appended = "\n".join(lines)
    return f"{expand_grid_macros(source)}\n{appended}\n{FIT_DIRECTIVES}"
