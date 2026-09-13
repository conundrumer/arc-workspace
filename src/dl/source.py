"""Read and rewrite solver source text, and assemble the program each mode
runs."""

import bisect
import re

from dl.dlparse import SECTION_RE, Comp, Decl, ParseError, Rigid, parse
from dl.paths import REPO_ROOT

# Per-mode IO directives, appended to the built source.
SOLVE_DIRECTIVES = ".input in(IO=stdin)\n.output out(IO=stdout)\n"
DETERMINE_DIRECTIVES = ".input ex_in\n.input ex_out\n.output _determination_diff(IO=stdout)\n"

COMP_HEADER_RE = re.compile(r"\.comp\s+(\w+)")
DECL_RE = re.compile(r"\.decl\s+(\w+)\s*\(([^)]*)\)")
GRID_CALL_RE = re.compile(r"\bGRID_(STAMP_)?(MASK_|SPARSE_)?(\d+)x(\d+)\s*\(")

# One piece of an expansion's output: where in the input it came from, the
# text it contributes, and whether that text is the input's own, copied.
type Chunk = tuple[int, str, bool]


def _join(chunks: list[Chunk]) -> str:
    return "".join(text for _, text, _ in chunks)


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


def _call_label(macro: str, rel: str, keys: list[str]) -> str:
    """How an expansion error names the call: its macro, relation, and keys."""
    return f"{macro}({', '.join([rel, *keys])})"


def _cell_token(tok: str, sparse: bool, label: str) -> str | None:
    """The cell value a token states, or None when it states no cell.

    `_` states no cell. A member cell is `1` under a mask name and a color
    digit under a sparse name; any other token is an expansion error.
    """
    if tok == "_":
        return None
    if sparse:
        if len(tok) == 1 and tok.isdigit():
            return tok
        raise ValueError(f"{label}: cell {tok!r} is not a color digit or '_'")
    if tok == "1":
        return tok
    raise ValueError(f"{label}: cell {tok!r} is not '1' or '_'")


def _grid_call_facts(policy: str, h: int, w: int, args: list[str],
                     macro: str) -> list[str]:
    """Fact lines for one GRID call, one line per grid row.

    Dense (no policy) emits `rel(p, v).` for every cell. `MASK_` emits
    `rel(p).` for each member cell; `SPARSE_` emits `rel(p, v).` for each
    cell that holds a color. Args between the relation name and the h*w
    cell values pass through as leading columns.
    """
    rel, keys, cells = args[0], args[1:len(args) - h * w], args[len(args) - h * w:]
    lead = "".join(f"{k}, " for k in keys)
    label = _call_label(macro, rel, keys)
    rows = []
    for row in range(h):
        facts = []
        for col in range(w):
            tok = cells[row * w + col]
            if policy:
                v = _cell_token(tok, policy == "SPARSE_", label)
                if v is None:
                    continue
            else:
                v = tok
            p = f"[{row}, {h - 1 - row}, {col}, {w - 1 - col}]"
            val = "" if policy == "MASK_" else f", {v}"
            facts.append(f"{rel}({lead}{p}{val}).")
        if facts:
            rows.append(" ".join(facts))
    return rows


def _stamp_call_facts(policy: str, h: int, w: int, args: list[str],
                      macro: str) -> list[str]:
    """Fact lines for one GRID_STAMP call, one line per grid row.

    The picture marks its anchor with an `@` prefix on one token, and each
    member cell is emitted as its Offset from that anchor. The mask
    form emits `rel(delta).`; the sparse form emits `rel(delta, v).`
    """
    rel, keys, cells = args[0], args[1:len(args) - h * w], args[len(args) - h * w:]
    lead = "".join(f"{k}, " for k in keys)
    label = _call_label(macro, rel, keys)
    sparse = policy == "SPARSE_"
    values = [_cell_token(c.removeprefix("@"), sparse, label) for c in cells]
    anchors = [i for i, c in enumerate(cells) if c.startswith("@")]
    if len(anchors) != 1:
        raise ValueError(f"{label}: {len(anchors)} '@' anchor cells, need 1")
    row_a, col_a = divmod(anchors[0], w)
    rows = []
    for row in range(h):
        facts = []
        for col in range(w):
            v = values[row * w + col]
            if v is None:
                continue
            dr, dc = row - row_a, col - col_a
            delta = f"[{dr}, {-dr}, {dc}, {-dc}]"
            val = "" if not sparse else f", {v}"
            facts.append(f"{rel}({lead}{delta}{val}).")
        if facts:
            rows.append(" ".join(facts))
    return rows


def _grid_chunks(source: str) -> list[Chunk]:
    """The pieces `expand_grid_macros` joins."""
    out: list[Chunk] = []
    pos = 0
    for m in GRID_CALL_RE.finditer(source):
        if m.start() < pos:
            continue
        line_start = source.rfind("\n", 0, m.start()) + 1
        prefix = source[line_start:m.start()]
        # A call inside a line comment is prose. Expanding it would put the
        # rows after the first outside the comment, as live facts.
        if "//" in prefix:
            continue
        stamp, policy = bool(m.group(1)), m.group(2) or ""
        h, w = int(m.group(3)), int(m.group(4))
        macro = source[m.start():m.end() - 1].rstrip()
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
        indent = prefix if not prefix.strip() else ""
        facts = _stamp_call_facts if stamp else _grid_call_facts
        rows = facts(policy, h, w, args, macro)
        out.append((pos, source[pos:m.start()], True))
        out.append((m.start(), f"\n{indent}".join(rows), False))
        pos = i
    out.append((pos, source[pos:], True))
    return out


def expand_grid_macros(source: str) -> str:
    """Replace each GRID call site with the facts it denotes."""
    return _join(_grid_chunks(source))


RIGID_CALL_RE = re.compile(r"\bRIGID\s*\(")
RIGID_CHART_PREFIX = "_rigid_"

# The D4 action per RIGID column type. Spatial columns act through their
# type's action relation; Axis kinds act through the induced swap on a
# member direction; the rest pass through by identity.
_RIGID_ACTIONS = {
    "Box": "apply", "Position": "apply", "Offset": "apply",
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


def _rigid_chunks(source: str) -> list[Chunk]:
    """The pieces `expand_rigid_macros` joins."""
    out: list[Chunk] = []
    pos = 0
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
        out.append((pos, source[pos:m.start()], True))
        out.append((m.start(), body.strip(), False))
        out.append((m.start(),
                    "\n" + "\n".join(f"{indent}{g}" for g in generated), False))
        pos = i
    out.append((pos, source[pos:], True))
    return out


def expand_rigid_macros(source: str) -> str:
    """Replace each RIGID block with its chart under generated names and
    the placed forms the solver reads."""
    return _join(_rigid_chunks(source))


LIB_INCLUDE = '#include "../lib.dl"'
INCLUDE_RE = re.compile(r'^\s*#include\s+"', re.M)


def with_lib(source: str) -> str:
    """The source under the lib include. A solver holds no include of its
    own; one that does keeps it."""
    return source if INCLUDE_RE.search(source) else f"{LIB_INCLUDE}\n{source}"


def expand_macros(source: str) -> str:
    """The lib include, then both macro expansions; RIGID first, so its inner
    GRID calls expand."""
    return expand_grid_macros(expand_rigid_macros(with_lib(source)))


def _chunk_line_starts(chunks: list[Chunk]) -> list[int]:
    """Input offset each output line starts at, one entry per output line.

    A verbatim chunk carries its text across unchanged, so a line inside it
    keeps its own offset. A generated chunk stands for the call it replaced,
    so every line of it takes that call's offset.
    """
    starts: list[int] = []
    fresh = True
    for off, text, verbatim in chunks:
        for j, ch in enumerate(text):
            if fresh:
                starts.append(off + j if verbatim else off)
            fresh = ch == "\n"
    return starts


def _line_map(text: str, chunks: list[Chunk]) -> list[int]:
    """Input line for each output line of `chunks` over `text`, 1-based."""
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]
    return [
        bisect.bisect_left(newlines, off) + 1
        for off in _chunk_line_starts(chunks)
    ]


def macro_line_map(source: str) -> list[int]:
    """Source line for each line of `expand_macros(source)`, 1-based both
    ways, indexed from 0. A generated line maps to its call site, and an
    added include line to the first line."""
    added = not INCLUDE_RE.search(source)
    source = with_lib(source)
    rigid = _rigid_chunks(source)
    placed = _join(rigid)
    to_source = _line_map(source, rigid)
    lines = [
        to_source[min(line, len(to_source)) - 1]
        for line in _line_map(placed, _grid_chunks(placed))
    ]
    return [max(line - 1, 1) for line in lines] if added else lines


def public_param(name: str) -> str:
    """The placed name of a RIGID chart relation; other names pass through."""
    return name.removeprefix(RIGID_CHART_PREFIX)


def rigid_decls(source: str) -> dict[str, tuple[str, list[str]]]:
    """Placed-name -> (block, chart column types) for each RIGID chart
    relation of Params, from raw (unexpanded) source."""
    try:
        comp = parse(source).comps().get("Params")
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


def shared_params(source: str) -> set[str]:
    """The Params relations that every case reads.

    A shared parameter sits above the case markers, and a parameter under
    a case marker serves that case alone; a Params with no case marker is
    shared throughout. A solver with no `Choice` has no cases, so it has
    no shared parameters.
    """
    if not re.search(r"^\.type\s+Choice\b", source, re.M):
        return set()
    start, end = _comp_span(source, "Params")
    names: set[str] = set()
    for line in source.splitlines()[start:end]:
        if SECTION_RE.match(line.lstrip()):
            break
        if d := re.match(r"\s*\.decl\s+(\w+)", line):
            names.add(d.group(1))
    return names


def rigid_param_decls(source: str, params: dict[str, list[str]]) -> dict[str, list[str]]:
    """Placed name -> declared (chart) column types for each RIGID parameter.

    Raw source states the block, so `rigid_decls` reads the chart decls off
    it. Expanded source has no block left, but the chart survives under its
    generated name beside the placed relation, so `params` carries it.
    """
    declared = {name: types for name, (_, types) in rigid_decls(source).items()}
    declared |= {
        public_param(name): types
        for name, types in params.items()
        if name.startswith(RIGID_CHART_PREFIX)
    }
    return declared


def determined_params(source: str) -> dict[str, list[str]] | None:
    """Determined parameters (name -> Params arg types): Determine decls
    that mirror a Params decl. None when no Determine comp. A RIGID chart
    relation mirrors under its placed name, with the chart's types — the
    determination derives the chart in a pose of its own, and the runner
    compares up to pose. The placed schema's leading D4 column stays out of
    the comparison, so the source may be raw or macro-expanded.

    Mirroring is by name, so a Determine helper must not take a parameter's
    name: a name match with a different schema raises rather than
    misclassify."""
    determine = comp_decls(source, "Determine")
    if not determine:
        return None
    params = comp_decls(source, "Params")
    params |= rigid_param_decls(source, params)
    for name in determine:
        if name in params and determine[name] != params[name]:
            raise ValueError(
                f"determination relation '{name}' matches a Params parameter "
                f"by name but not by schema ({', '.join(determine[name])} vs "
                f"{', '.join(params[name])}); rename the helper"
            )
    return {name: params[name] for name in determine if name in params}


def _comp_span(source: str, comp_name: str) -> tuple[int, int]:
    """[start, end) line indices of comp `comp_name`'s interior; (0, 0) when absent."""
    comp = _comp(source, comp_name)
    if comp is None:
        return (0, 0)
    return (comp.line, max(comp.line, comp.end_line - 1))


def _params_fact_lines(source: str) -> list[int]:
    """Line indices inside Params outside any rule statement.

    A parameter atom can also close a Params rule (`x(N) :- fat(N).`), where
    it reads like a fact; fact matching stays off rule lines.
    """
    lines = source.splitlines()
    s, e = _comp_span(source, "Params")
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


def _param_atoms(code: str, param: str) -> list[tuple[int, int, str]]:
    """(start, end, args) for each `param(...).` fact atom in `code`."""
    spans = []
    for m in re.finditer(rf"\b{param}\s*\(", code):
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


def _param_facts(source: str, param: str) -> list[list[str]]:
    """Argument lists of `param`'s Params facts."""
    lines = source.splitlines()
    return [
        _split_args(args)
        for i in _params_fact_lines(source)
        for (_, _, args) in _param_atoms(lines[i].split("//")[0], param)
    ]


def _render_arg(v) -> str:
    return f"[{', '.join(str(x) for x in v)}]" if isinstance(v, tuple) else str(v)


def swap_fact(source: str, param: str, values: tuple) -> str:
    """Replace `param`'s Params facts with a single fact holding `values`."""
    return swap_facts(source, param, [values])


def swap_facts(source: str, param: str, rows: list[tuple]) -> str:
    """Replace `param`'s Params facts with one fact per row."""
    lines = source.splitlines()
    _, e = _comp_span(source, "Params")
    for i in _params_fact_lines(source):
        code, sep, comment = lines[i].partition("//")
        for start, end, _ in reversed(_param_atoms(code, param)):
            code = code[:start] + code[end:]
        lines[i] = code + sep + comment
    for row in rows:
        args = ", ".join(_render_arg(v) for v in row)
        lines.insert(e, f"    {param}({args}).")
    return "\n".join(lines) + "\n"


def build_source(source: str) -> str:
    """Assemble the solve-mode program from a solver file's source."""
    return f"{expand_macros(source)}\n{SOLVE_DIRECTIVES}"


def build_determine_source(source: str, params: dict[str, list[str]]) -> str:
    """Assemble the determination-mode program: Determine instance,
    per-parameter diffs, directives.

    A parameter with an Ident column gets no diff rules — its ids are
    arbitrary, so both sides relay to output relations and the runner
    compares them modulo id renaming. A RIGID parameter gets no diff rules
    either: both sides relay as placed forms — the stored side is already
    placed; the determination's chart closes through the same rule — and the
    runner compares orbits.
    """
    rigid = rigid_decls(source)
    lines = [".init determine = Determine"]
    for name, types in sorted(params.items()):
        args = ", ".join(f"A{i}" for i in range(len(types)))
        if name in rigid:
            typed = "d4: D4, " + ", ".join(f"a{i}: {t}" for i, t in enumerate(types))
            lines += [
                f".decl determine_rigid_{name}({typed})",
                _rigid_rule(f"determine_rigid_{name}", f"determine.{name}", types),
                f".output determine_rigid_{name}(IO=stdout)",
                f".decl params_rigid_{name}({typed})",
                f"params_rigid_{name}(D4, {args}) :- params.{name}(D4, {args}).",
                f".output params_rigid_{name}(IO=stdout)",
            ]
        elif "Ident" in types:
            typed = ", ".join(f"a{i}: {t}" for i, t in enumerate(types))
            for side in ("determine", "params"):
                lines += [
                    f".decl {side}_ident_{name}({typed})",
                    f"{side}_ident_{name}({args}) :- {side}.{name}({args}).",
                    f".output {side}_ident_{name}(IO=stdout)",
                ]
        else:
            lines.append(
                f'_determination_diff("{name}") :- '
                f'determine.{name}({args}), !params.{name}({args}).'
            )
            lines.append(
                f'_determination_diff("{name}") :- '
                f'params.{name}({args}), !determine.{name}({args}).'
            )
    appended = "\n".join(lines)
    return f"{expand_macros(source)}\n{appended}\n{DETERMINE_DIRECTIVES}"


KEYWORDS_DOC = REPO_ROOT / "docs" / "wf-solver" / "keywords.md"

KEYWORD_FIELD_RE = re.compile(r"^// (keywords): (.*)$")
KEYWORD_BULLET_RE = re.compile(r"^- `([^`]+)`")


def doc_keywords(text: str) -> dict[str, list[str]]:
    """The keywords of keywords.md, in doc order, per `##` section. A
    keyword is the leading code span of a bullet."""
    sections: dict[str, list[str]] = {}
    held: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            held = sections.setdefault(line[3:].strip(), [])
        elif m := KEYWORD_BULLET_RE.match(line):
            held.append(m.group(1))
    return sections


def header_keywords(source: str) -> list[str]:
    """The keywords of a solver's `// keywords:` line. A field's second
    line is not read. The header is the leading comment block, so the first
    line that is not a comment ends it."""
    fields: dict[str, list[str]] = {}
    for line in source.splitlines():
        if not line.strip().startswith("//"):
            break
        if (m := KEYWORD_FIELD_RE.match(line)) and m.group(1) not in fields:
            fields[m.group(1)] = m.group(2).split()
    return [word for words in fields.values() for word in words]
