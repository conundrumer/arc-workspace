"""Read and rewrite solver source text, and assemble the program each mode runs.

Covers GRID macro expansion, `.comp` and `.decl` analysis, Consts fact
rewriting, and the per-mode IO directives Souffle needs.
"""

import re

from dl.dlparse import Comp, Decl, ParseError, Rigid, parse

# Per-mode IO directives, appended to the built source.
SOLVE_DIRECTIVES = ".input in(IO=stdin)\n.output out(IO=stdout)\n"
FIT_DIRECTIVES = ".input ex_in\n.input ex_out\n.output fit_diff(IO=stdout)\n"

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


RIGID_CALL_RE = re.compile(r"\bRIGID\s*\(")
RIGID_CHART_PREFIX = "_rigid_"

# The D4 action per RIGID column type. Spatial columns act through their
# type's action relation; Axis kinds act through the induced swap on a
# member direction; the rest pass through by identity.
_RIGID_ACTIONS = {
    "Position": "apply", "Shift": "apply", "Inset": "apply",
    "Dir": "apply_dir", "DiagDir": "apply_diag_dir", "Dir8": "apply_dir8",
}
_RIGID_AXIS_ACTIONS = {
    "Axis": ("axis_of", "apply_dir"),
    "DiagAxis": ("diag_axis_of", "apply_diag_dir"),
}
_RIGID_IDENTITY = {"Color", "number", "Ident", "symbol", "Example"}


def _rigid_rule(head: str, src: str, types: list[str]) -> str:
    """The closure rule deriving `head` — D4 placements of chart `src`."""
    heads, srcs, atoms = [], [], []
    for i, t in enumerate(types):
        if t in _RIGID_ACTIONS:
            heads.append(f"A{i}")
            srcs.append(f"B{i}")
            atoms.append(f"{_RIGID_ACTIONS[t]}(D4, B{i}, A{i})")
        elif t in _RIGID_AXIS_ACTIONS:
            member, act = _RIGID_AXIS_ACTIONS[t]
            heads.append(f"A{i}")
            srcs.append(f"B{i}")
            atoms.append(f"{member}(Bd{i}, B{i}), {act}(D4, Bd{i}, Ad{i}), "
                         f"{member}(Ad{i}, A{i})")
        elif t in _RIGID_IDENTITY:
            heads.append(f"A{i}")
            srcs.append(f"A{i}")
        else:
            raise ValueError(f"RIGID column type {t!r} has no D4 action")
    body = ", ".join([f"{src}({', '.join(srcs)})", "d4_elem(D4)", *atoms])
    return f"{head}(D4, {', '.join(heads)}) :- {body}."


def expand_rigid_macros(source: str) -> str:
    """Replace each RIGID block with its chart under generated names and
    the placed forms the solver reads."""
    out, pos = [], 0
    for m in RIGID_CALL_RE.finditer(source):
        if m.start() < pos:
            continue
        depth, i = 1, m.end()
        while i < len(source) and depth:
            depth += source[i] == "("
            depth -= source[i] == ")"
            i += 1
        inner = source[m.end():i - 1]
        block, _, body = inner.partition(",")
        block = block.strip()
        line_start = source.rfind("\n", 0, m.start()) + 1
        indent = source[line_start:m.start()]
        indent = indent if not indent.strip() else ""
        generated = []
        for dm in DECL_RE.finditer(body):
            rel, fields = dm.group(1), dm.group(2).strip()
            types = [a.split(":")[1].strip() for a in _split_args(fields)]
            body = re.sub(rf"\b{rel}\b", f"{RIGID_CHART_PREFIX}{block}_{rel}", body)
            generated += [
                f".decl {block}_{rel}(d4: D4, {fields})",
                _rigid_rule(f"{block}_{rel}",
                            f"{RIGID_CHART_PREFIX}{block}_{rel}", types),
            ]
        out.append(source[pos:m.start()])
        out.append(body.strip())
        out.append("\n" + "\n".join(f"{indent}{g}" for g in generated))
        pos = i
    out.append(source[pos:])
    return "".join(out)


def expand_macros(source: str) -> str:
    """Both macro expansions; RIGID first, so its inner GRID calls expand."""
    return expand_grid_macros(expand_rigid_macros(source))


def public_slot(name: str) -> str:
    """The placed name of a RIGID chart relation; other names pass through."""
    return name.removeprefix(RIGID_CHART_PREFIX)


def rigid_decls(source: str) -> dict[str, tuple[str, list[str]]]:
    """Placed-name -> (block, chart column types) for each RIGID chart
    relation of Consts, from raw (unexpanded) source."""
    try:
        comp = parse(source).comps().get("Consts")
    except ParseError:
        return {}
    out: dict[str, tuple[str, list[str]]] = {}
    for it in comp.items if comp else []:
        if isinstance(it, Rigid):
            for sub in it.items:
                if isinstance(sub, Decl):
                    out[f"{it.name}_{sub.name}"] = (
                        it.name, [f.type for f in sub.fields]
                    )
    return out


def _comp(source: str, comp_name: str) -> Comp | None:
    return parse(source).comps().get(comp_name)


def comp_decls(source: str, comp_name: str) -> dict[str, list[str]]:
    """Map relation name -> argument types for `.decl`s directly inside comp `comp_name`."""
    comp = _comp(source, comp_name)
    if comp is None:
        return {}
    return {
        it.name: [f.type for f in it.fields]
        for it in comp.items
        if isinstance(it, Decl)
    }


def rigid_slot_decls(source: str, consts: dict[str, list[str]]) -> dict[str, list[str]]:
    """Placed name -> declared (chart) column types for each RIGID slot.

    Raw source states the block, so `rigid_decls` reads the chart decls off
    it. Expanded source has no block left, but the chart survives under its
    generated name beside the placed relation, so `consts` carries it.
    """
    declared = {name: types for name, (_, types) in rigid_decls(source).items()}
    declared |= {
        public_slot(name): types
        for name, types in consts.items()
        if name.startswith(RIGID_CHART_PREFIX)
    }
    return declared


def fit_slots(source: str) -> dict[str, list[str]] | None:
    """Fitted slots (name -> Consts arg types): Fit decls that mirror a
    Consts decl. None when no Fit comp. A RIGID chart relation mirrors
    under its placed name, with the chart's types — the Fit derives the
    chart in a pose of its own, and the runner compares up to pose. The
    placed schema's leading D4 column stays out of the comparison, so the
    source may be raw or macro-expanded.

    Mirroring is by name, so a Fit helper must not take a slot's name: a
    name match with a different schema raises rather than misclassify."""
    fit = comp_decls(source, "Fit")
    if not fit:
        return None
    consts = comp_decls(source, "Consts")
    consts |= rigid_slot_decls(source, consts)
    for name in fit:
        if name in consts and fit[name] != consts[name]:
            raise ValueError(
                f"Fit relation '{name}' matches a Consts slot by name but "
                f"not by schema ({', '.join(fit[name])} vs "
                f"{', '.join(consts[name])}); rename the helper"
            )
    return {name: consts[name] for name in fit if name in consts}


def _comp_span(source: str, comp_name: str) -> tuple[int, int]:
    """[start, end) line indices of comp `comp_name`'s interior; (0, 0) when absent."""
    comp = _comp(source, comp_name)
    if comp is None:
        return (0, 0)
    return (comp.line, max(comp.line, comp.end_line - 1))


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
    return f"{expand_macros(source)}\n{SOLVE_DIRECTIVES}"


def build_fit_source(source: str, slots: dict[str, list[str]]) -> str:
    """Assemble the fit-mode program: Fit instance, per-slot diffs, directives.

    A slot with an Ident column gets no diff rules — its ids are arbitrary,
    so both sides relay to output relations and the runner compares them
    modulo id renaming. A RIGID slot gets no diff rules either: both sides
    relay as placed forms — the stored side is already placed; the Fit's
    chart closes through the same rule — and the runner compares orbits.
    """
    rigid = rigid_decls(source)
    lines = [".init fit = Fit"]
    for name, types in sorted(slots.items()):
        args = ", ".join(f"A{i}" for i in range(len(types)))
        if name in rigid:
            typed = "d4: D4, " + ", ".join(f"a{i}: {t}" for i, t in enumerate(types))
            lines += [
                f".decl fit_rigid_{name}({typed})",
                _rigid_rule(f"fit_rigid_{name}", f"fit.{name}", types),
                f".output fit_rigid_{name}(IO=stdout)",
                f".decl c_rigid_{name}({typed})",
                f"c_rigid_{name}(D4, {args}) :- c.{name}(D4, {args}).",
                f".output c_rigid_{name}(IO=stdout)",
            ]
        elif "Ident" in types:
            typed = ", ".join(f"a{i}: {t}" for i, t in enumerate(types))
            for side in ("fit", "c"):
                lines += [
                    f".decl {side}_ident_{name}({typed})",
                    f"{side}_ident_{name}({args}) :- {side}.{name}({args}).",
                    f".output {side}_ident_{name}(IO=stdout)",
                ]
        else:
            lines.append(f'fit_diff("{name}") :- fit.{name}({args}), !c.{name}({args}).')
            lines.append(f'fit_diff("{name}") :- c.{name}({args}), !fit.{name}({args}).')
    appended = "\n".join(lines)
    return f"{expand_macros(source)}\n{appended}\n{FIT_DIRECTIVES}"
