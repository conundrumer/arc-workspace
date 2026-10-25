"""The output forms of a converted solver (`Form`, `Dead`, `Todo`), the parameter
writers, the text of a comment or a quoted gloss, and the passes on the output
text: the merge of forms, the fold of `or` lines, the drop of key sites, the
relabeling and the hoist of shared forms."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace as dc_replace
from engine.program import Atom, AtomLiteral, RelationName, Unit, Variable

from arclog_convert.lib import pascal


# --------------------------------------------------------------------------
# Output forms


def wrap_param(head: str, rest: str) -> str:
    """A one-line param over 80 columns, one row per line."""
    if "\n" in rest or len(head) + len(rest) <= 80:
        return head + rest
    body = rest.strip()
    assert body.endswith(")")
    body = body[:-1].strip()
    rows, depth, start = [], 0, None
    for j, ch in enumerate(body):
        if ch == "(":
            if depth == 0:
                start = j
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                rows.append(body[start:j + 1])
    return "\n".join([head, *("  " + r for r in rows)]) + ")"


def grid_param(head: str, types: list[str], rest: str) -> str | None:
    """A relation with a Position column, its rows given as grids of the
    first such column: the
    rows that agree on the columns before the position are one grid, each
    cell its position's value after it, `1` where it has none, `_` where no
    row holds the position. None where the rows are not grids so: a row
    that gives several values after its position, two rows at one cell, or
    positions of different frames in one grid."""
    from arclog_convert.lint import L, read, flat
    if "Position" not in types:
        return None
    pi = types.index("Position")
    try:
        rows = read("(x" + rest)[0].items[1:]
    except (SyntaxError, IndexError):
        return None
    groups: dict[tuple, dict[tuple[int, int], str]] = {}
    frames: dict[tuple, set] = defaultdict(set)
    for row in rows:
        if not isinstance(row, L) or len(row.items) != len(types) or len(types) - pi > 2:
            return None
        b = (0, 0, 0, 0) if flat(row.items[pi]) == "ZERO" else box(flat(row.items[pi]))
        after = row.items[pi + 1:]
        if b is None or min(b) < 0:
            return None
        key = tuple(flat(x) for x in row.items[:pi])
        cells = groups.setdefault(key, {})
        if (b[0], b[2]) in cells:
            return None
        cells[(b[0], b[2])] = flat(after[0]) if after else "1"
        frames[key].add(extent(b))
    if not groups or any(len(f) != 1 for f in frames.values()):
        return None
    lines = [head]
    for key, cells in groups.items():
        (v, h), = frames[key]
        lines.append("  (" + " ".join(key) + " (grid" if key else "  (grid")
        lines += ["    (" + " ".join(cells.get((i, j), "_") for j in range(h)) + ")" for i in range(v)]
        lines[-1] += "))" if key else ")"
    lines[-1] += ")"
    return "\n".join(lines)


def box(text: str) -> tuple[int, int, int, int] | None:
    m = re.fullmatch(r"\((-?\d+) (-?\d+) (-?\d+) (-?\d+)\)", text)
    return tuple(int(x) for x in m.groups()) if m else None


def extent(b) -> tuple[int, int]:
    t, bo, l, r = b
    return t + bo + 1, l + r + 1


def tile_frames_split(prog):
    """The program with each Params clause that places a tiled frame
    (`helpers.tile_pos`) in a larger one, by `compose` with a box the
    parameters give, as two clauses: the tiled frame, a table of its own
    named `<relation>_tiles`, and the clause that places it, which reads
    that table; and each such table's name with the relation it was split
    from."""
    from engine.program import DeclId, Scope, UnitId
    units, rels, split = list(prog.units), list(prog.relations), {}
    next_unit = 1 + max((u.id.index for u in units), default=0)
    next_decl = 1 + max((d.id.index for d in prog.declarations), default=0)
    for k, u in enumerate(units):
        if u.scope.components != ("Params",) or not u.body or u.head.relation.instances:
            continue
        tp = [i for i, l in enumerate(u.body) if isinstance(l, AtomLiteral) and not l.negated
              and l.atom.relation == RelationName(("helpers",), "tile_pos")]
        if len(tp) != 1:
            continue
        lit = u.body[tp[0]]
        frame = lit.atom.args[3]
        head_vars = {t.name for t in u.head.args if isinstance(t, Variable)}
        if not isinstance(frame, Variable) or frame.name in head_vars:
            continue
        places = [l for l in u.body if isinstance(l, AtomLiteral) and l.atom.relation == RelationName((), "compose")
                  and l.atom.args[0] == frame and isinstance(l.atom.args[2], Variable)
                  and l.atom.args[2].name in head_vars]
        if len(places) != 1:
            continue
        ins = {v for t in lit.atom.args[:3] for v in term_vars(t)}
        mine = [l for i, l in enumerate(u.body) if i == tp[0] or (
            set(term_vars(l)) and set(term_vars(l)) <= ins)]
        rest = [l for l in u.body if not any(l is m for m in mine)]
        name = u.head.relation.name + "_tiles"
        if any(r.name == name and r.scope.components == ("Params",) for r in rels):
            continue
        decl = next(r for r in rels if r.name == u.head.relation.name and r.scope.components == ("Params",))
        pos = decl.columns[0].type
        cols = tuple(dc_replace(decl.columns[0], name=n, type=pos) for n in ("p_frame", "p_tile", "p_intile"))
        rels.append(dc_replace(decl, id=DeclId(next_decl), name=name, columns=cols))
        next_decl += 1
        tiles_head = Atom(RelationName((), name), (frame, lit.atom.args[4], lit.atom.args[5]), lit.atom.line)
        units.append(dc_replace(u, id=UnitId(next_unit), head=tiles_head, body=tuple(mine)))
        next_unit += 1
        units[k] = dc_replace(u, body=(AtomLiteral(tiles_head, False), *rest))
        split[name] = u.head.relation.name
    if not split:
        return prog, split
    return dc_replace(prog, units=tuple(units), relations=tuple(rels)), split


def term_vars(t) -> list[str]:
    from arclog_convert.libmap.instances import term_vars as tv
    return tv(t, [])


def unplaced_rows(rows: list[list[str]]) -> list[list[str]]:
    """The rows of a placed tiled frame with each placed position taken back
    to the tiled frame: its margins less the least margin on each side,
    since the tiled frame's cells reach each of its edges."""
    boxes = [box(r[0]) for r in rows]
    if not rows or any(b is None for b in boxes):
        return []
    least = [min(b[i] for b in boxes if b) for i in range(4)]
    return [["(" + " ".join(str(x - m) for x, m in zip(b, least)) + ")", *r[1:]]
            for b, r in zip(boxes, rows) if b]


def derived_param(amp: str, rows: list[list[str]], proposer: str | None) -> str | None:
    """The values a helper table derives from, where the table is every
    cell of one frame, or that frame cut into equal tiles: the extent on
    each axis, or the tile count, tile size and gap on each axis; None
    otherwise."""
    boxes = [[box(x) for x in row] for row in rows]
    if not boxes or any(b is None for row in boxes for b in row):
        return None
    width = len(boxes[0])
    if any(len(row) != width for row in boxes):
        return None
    frames = [{extent(row[i]) for row in boxes} for i in range(width)]
    if any(len(f) != 1 for f in frames):
        return None
    dims = [next(iter(f)) for f in frames]
    if width == 1:
        v, h = dims[0]
        if len({row[0] for row in boxes}) != v * h:
            return None
        vals = [("AXIS_V", (f"(:N {v})",)), ("AXIS_H", (f"(:N {h})",))]
    elif width in (2, 3):
        (gv, gh), (iv, ih) = dims[0], dims[-1]
        # the tiles reach each edge of the frame
        if any(min(row[0][i] for row in boxes) for i in range(4)):
            return None
        # the tile count on an axis: the lines the cells cover over the tile size
        lines_v, lines_h = len({row[0][0] for row in boxes}), len({row[0][2] for row in boxes})
        if lines_v % iv or lines_h % ih:
            return None
        ov, oh = lines_v // iv, lines_h // ih
        if width == 3 and dims[1] != (ov, oh):
            return None
        if len({row[0] for row in boxes}) != ov * oh * iv * ih:
            return None
        vals = []
        for a, g, o, i in (("AXIS_V", gv, ov, iv), ("AXIS_H", gh, oh, ih)):
            gap = 0 if o == 1 else (g - o * i) // (o - 1)
            if o * i + (o - 1) * gap != g or gap < 0:
                return None
            vals.append((a, (f"(:Count {o})", f"(:Size {i})", f"(:Gap {gap})")))
    else:
        return None
    rows_text = ["(" + " ".join([f"(:A {a})", *map(str, xs)]) + ")" for a, xs in vals]
    if proposer is None and width == 1:
        proposer = "Frame2D"
    if proposer == "Frame2D" and width != 1:
        return None
    if proposer:
        return "\n".join([f"(param {amp} ({proposer}", *("  " + r for r in rows_text)]) + "))"
    return f"(param {amp} " + " ".join(rows_text) + ")"


def head_renames(u: Unit, r) -> dict[str, str]:
    """Each variable of `u`'s head renamed to the column of `r`, its
    relation's declaration, that it stands at, where the names differ."""
    cols = [pascal(col.name) for col in r.columns]
    return {t.name: cols[k] for k, t in enumerate(u.head.args) if isinstance(t, Variable) and t.name != cols[k]}


def mask_param(amp: str, rows: list[list[str]]) -> str | None:
    """A cell set as a mask grid: `1` at each cell, `_` elsewhere, in the
    frame the cells give; None where the rows are not the cells of one
    frame."""
    cells = []
    for row in rows:
        m = re.fullmatch(r"\((-?\d+) (-?\d+) (-?\d+) (-?\d+)\)", row[0]) if len(row) == 1 else None
        if not m:
            return None
        cells.append(tuple(int(x) for x in m.groups()))
    frames = {(t + b + 1, l + r + 1) for t, b, l, r in cells}
    if len(frames) != 1 or any(min(c) < 0 for c in cells):
        return None
    (v, h), = frames
    on = {(t, l) for t, _, l, _ in cells}
    lines = [f"(param {amp}", "  (grid"]
    lines += ["    (" + " ".join("1" if (i, j) in on else "_" for j in range(h)) + ")" for i in range(v)]
    lines[-1] += "))"
    return "\n".join(lines)


@dataclass
class Form:
    """One arclog form: its lines, the relation it derives, the relations it
    reads, and the comments above it."""
    lines: list[str]
    name: str
    reads: set[str]
    comments: list[str] = field(default_factory=list)
    branches: tuple[str, ...] = ()   # the constructors its head fixes
    line: int = 0
    claim_slugs: list[str] = field(default_factory=list)  # from @claim
    src: tuple | None = None          # (unit, side, scope, sub, name_scope) of a clause
    top_pos: set[str] = field(default_factory=set)
    top_neg: set[str] = field(default_factory=set)
    nested: set[str] = field(default_factory=set)
    src_inst: tuple | None = None
    body: list[str] | None = None     # a clause's body lines, for a merge
    cols: list[str] = field(default_factory=list)   # a clause's head columns
    col_labels: list[list[str]] = field(default_factory=list)   # per column of the relation, the head columns its leaves make
    side: str = ""
    concept_dead: bool = False        # reads at its top level a relation only alts derive
    concept_form: "Form | None" = None   # an instance without its inputs that are dead in the concept
    dead_reads: frozenset = frozenset()
    demo: list = field(default_factory=list)   # a DEMONSTRATED form's (rule, text, &prediction lines, reads)
    demo_head: list = field(default_factory=list)
    demo_input_reads: set = field(default_factory=set)
    marks: list[str] = field(default_factory=list)   # a clause's ONE marks, after its body
    head_repeat: list = field(default_factory=list)   # (column, the column its head repeats)
    demo_rule: str = ""               # the demonstrated rule a clause's head names

    def __setattr__(self, key, value):
        # `&output` is the tail's: no claim holds it
        if key == "claim_slugs" and getattr(self, "name", None) == "&out":
            value = []
        super().__setattr__(key, value)


class Dead(Exception):
    """A clause that reads a relation the current alt leaves empty."""


class Todo:
    def __init__(self) -> None:
        self.kinds: Counter[str] = Counter()
        self.pending: list[str] = []

    def add(self, kind: str, detail: str) -> None:
        self.kinds[kind] += 1
        self.pending.append(f";; TODO {kind}: {detail}")

    def take(self) -> list[str]:
        out, self.pending = self.pending, []
        return out




def demo_lines(rules, helpers: dict[str, list["Form"]]) -> list[str]:
    """A DEMONSTRATED form's DEMO_RULE blocks, each with the forms that only
    its `&prediction` reads, and the form's closing parenthesis."""
    out: list[str] = []
    for rule, text, rule_lines, _, head in rules:
        block = [f"  (DEMO_RULE {head}" + (f" {quote(text)}" if text else "")]
        body = render_forms(topo(helpers.get(rule, [])), "    ")
        block += body
        if body:
            block.append("")
        block += ["    " + l for l in rule_lines]
        close(block, ")")
        out += block
    close(out, ")")
    return out


def nest_keyed(key_body: list[str] | None, blocks: list[list[str]], knames, head: str,
               own: str | None = None, broadcast: set[int] | frozenset[int] = frozenset()) -> list[str]:
    """The key clause with the inputs that read a key label or the instance's
    own outputs inside it, then the inputs that read neither, and the blocks
    at the `broadcast` indices, whose inputs have no key column."""
    if key_body is None or "^" not in " ".join(key_body):
        return [l for b in blocks for l in b]
    pats = [re.compile(rf"(?<![\w:&.*^]){re.escape(k)}(?!\w)") for k in knames]
    lead = f"  ({head} ("
    out = [lead + key_body[0]] + [" " * len(lead) + l for l in key_body[1:]]
    close(out, ")")
    broad = []
    for bi, b in enumerate(blocks):
        text = " ".join(l for l in b if not l.lstrip().startswith(";;"))
        if bi not in broadcast and (any(p.search(text) for p in pats) or (own and f"({own}." in text)):
            out.extend("  " + l for l in b)
        else:
            broad.append(b)
    close(out, ")")
    return out + [l for b in broad for l in b]


def close(lines: list[str], parens: str) -> None:
    """Append `parens` to the last line that is no comment, and to the
    form's line when a comment ends the form."""
    for i in range(len(lines) - 1, -1, -1):
        if not lines[i].lstrip().startswith(";;"):
            j = lines[i].find(" ;;")
            lines[i] += parens
            return
    lines.append(parens)


def wrap(head: str, groups: list[list[str]]) -> list[str]:
    """`head` then each group in parentheses, one group per line, aligned."""
    pad = " " * len(head)
    out: list[str] = []
    for gi, g in enumerate(groups):
        if not g:
            g = []
        lines = []
        for li, line in enumerate(g):
            lines.append(("(" if li == 0 else " ") + line)
        if not lines:
            lines = ["("]
        close(lines, ")")
        prefix = head if gi == 0 else pad
        out.append(prefix + lines[0])
        out.extend(pad + l for l in lines[1:])
    close(out, ")")
    return out


# --------------------------------------------------------------------------
# Comment text


HEADER_RE = re.compile(r"^\s*@(scene|rule|approximated|representative|witness|keywords|draft|claim|store|derive|ignore|relaxed|reassigned)\b:?\s*(.*)$")



def directives(comment_lines: list[str]) -> list[tuple[str, str, int]]:
    """(directive, rest, indent) per directive line, continuation lines
    joined: a continuation is a line that opens with two spaces and no `@`."""
    out: list[list] = []
    for raw in comment_lines:
        m = re.match(r"^(\s*)@(\w[\w-]*)(.*)$", raw)
        if m and m.group(2) in ("relaxed", "reassigned") and out:
            out[-1][1] += f" @{m.group(2)} {m.group(3).strip()}"
        elif m:
            out.append([m.group(2), m.group(3).lstrip(":").strip() if m.group(2) not in ("scene", "rule") else m.group(3).strip(), len(m.group(1))])
        elif out and raw.startswith(" ") and raw.strip():
            out[-1][1] += " " + raw.strip()
        elif raw.strip().startswith("---"):
            continue
        else:
            out.append(["", raw.strip(), 0])
    return [(a, b, c) for a, b, c in out]


def comment_text(line: str) -> str | None:
    s = line.strip()
    if s.startswith("//"):
        return s[2:][1:] if s[2:3] == " " else s[2:]
    return None


def params_to_amp(text: str) -> str:
    return re.sub(r"params\.(\w+)", r"&\1", text)


def or_gloss(gloss: str) -> str:
    """The gloss of a DET_OR_RULE or RULE_OR_DET line, a space then the
    quoted prose above the declaration, or nothing where it has none."""
    return f" {quote(params_to_amp(gloss))}" if gloss.strip() else ""


def quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


MERGES: Counter[str] = Counter()


def label_names(lines: list[str]) -> set[str]:
    """The labels the lines name, comment lines aside."""
    out: set[str] = set()

    def note(mark: str, x: str) -> str:
        out.add(x)
        return mark + x
    relabel(lines, note)
    return out


def made_at_site(lines: list[str], x: str) -> bool:
    return any(re.search(rf"(?<!\(= )\*{re.escape(x)}(?!\w)", l) for l in lines if not l.lstrip().startswith(";;"))


OPS_ = {"=", "!=", "<", "<=", ">", ">="}


def without_repeats(f: "Form", drop: dict[str, str]) -> "Form":
    """The form without the `(= *X Y)` lines that repeat a dropped column
    X, and without those columns, its body reading Y for X."""
    lines: list[str] = []
    for l in f.lines:
        m = next((re.fullmatch(rf"\s*\(= \*{x} {y}\)(\)*)", l) for x, y in drop.items()
                  if re.fullmatch(rf"\s*\(= \*{x} {y}\)(\)*)", l)), None)
        if m is None:
            lines.append(l)
        elif m.group(1):
            lines[-1] += m.group(1)   # the form's closers move to the line before
    # the body reads the column the dropped one repeats
    lines = relabel(lines, lambda mark, v: drop[v] if v in drop else mark + v)
    new = dc_replace(f, lines=lines)
    new.cols = [c_ for c_ in f.cols if c_ not in drop]
    return new


def read_without(lines: list[str], rel: str, drop: dict[str, str]) -> list[str] | None:
    """The lines with each one-line read of `rel` leaving out the dropped
    columns, and the label each named relabeled to the label at the column
    it repeats, or, where the read names no label there, standing at that
    column; None where a read is not one line."""
    ren: dict[str, str] = {}
    out = []
    for l in lines:
        i = l.find(f"({rel} ")
        if i < 0:
            out.append(l)
            continue
        depth, j = 0, i
        while j < len(l):
            depth += {"(": 1, ")": -1}.get(l[j], 0)
            if depth == 0:
                break
            j += 1
        if depth:
            return None
        atom = l[i + 1:j]
        items, k, d, cur = [], len(rel) + 1, 0, ""
        for ch in atom[k:]:
            if ch == "(":
                d += 1
            elif ch == ")":
                d -= 1
            if ch == " " and d == 0:
                if cur:
                    items.append(cur)
                cur = ""
            else:
                cur += ch
        if cur:
            items.append(cur)

        def col_lab(it):
            m = re.fullmatch(r"\(:(\w+) ([*^]?)(\w+)\)", it)
            if m:
                return m.group(1), m.group(3), m.group(2)
            m = re.fullmatch(r"([*^]?)(\w+)", it)
            return (m.group(2), m.group(2), m.group(1)) if m else (None, None, "")
        labs = {col_lab(it)[0]: col_lab(it)[1] for it in items}
        kept = []
        for it in items:
            col, lab, mark = col_lab(it)
            if col in drop:
                if drop[col] not in labs:
                    # the read takes the label at the column the dropped one repeats
                    kept.append(f"(:{drop[col]} {mark}{lab})")
                    continue
                ren[lab] = labs[drop[col]]
                continue
            kept.append(it)
        out.append(l[:i] + "(" + " ".join([rel] + kept) + l[j:])
    if not ren:
        return out
    return relabel(out, lambda mark, v: (mark if v not in ren else "") + ren.get(v, v))


def relabel(lines: list[str], fn) -> list[str]:
    """The lines with each label `[*^]X` replaced by `fn(mark, X)`; a bare
    site whose label changes keeps its column, `(:X new)`, and a record's
    field elided to its label keeps its field the same way."""
    stack: list[str | None] = []
    out = []
    for l in lines:
        if l.lstrip().startswith(";;"):
            out.append(l)
            continue
        parts, i = [], 0
        for m in re.finditer(r"[()]|[^\s()]+", l):
            tok = m.group()
            if tok == "(":
                stack.append(None)
                continue
            if tok == ")":
                if stack:
                    stack.pop()
                continue
            if stack and stack[-1] is None:
                stack[-1] = tok
                continue
            lm = re.fullmatch(r"([*^]?)([A-Z]\w*)", tok)
            if not lm:
                continue
            new = fn(lm.group(1), lm.group(2))
            if new == tok:
                continue
            head = stack[-1] if stack else None
            bare = head is not None and not head.startswith(":") and head not in OPS_
            field_ = head is not None and re.fullmatch(r":[a-z]\w*", head) is not None
            if bare and new.lstrip("*^") != lm.group(2):
                new = f"(:{lm.group(2)} {new})"
            elif field_ and new.lstrip("*^") != lm.group(2):
                new = f"(:\0{lm.group(2)} {new})"
            parts.append(l[i:m.start()])
            parts.append(new)
            i = m.end()
        parts.append(l[i:])
        # a site of one label on a type-parameter column is no record, a key's aside
        line = re.sub(r"\((:(?!key\b)[a-z]\w*) \(:\0\w+ ([^()\s]+)\)\)", r"(\1 \2)", "".join(parts))
        out.append(line.replace(":\0", ":"))
    return out


def or_body(bodies: list[tuple[list[str], list[str]]], cols: set[str], outer: set[str]) -> list[str]:
    """The lines of one OR with a branch per (comments, body lines): first
    a branch that makes every column at a site, where one does; each later
    branch names the columns, and its other labels that an earlier branch
    names are renamed with a digit. Each branch's comments stand above it.
    A body that an earlier branch already holds is no branch."""
    uniq: list[tuple[list[str], list[str]]] = []
    for cm, ls in bodies:
        if not any(ls == ls2 for _, ls2 in uniq):
            uniq.append((cm, ls))
    kept = drop_implied([ls for _, ls in uniq])
    bodies = [b for b in uniq if any(b[1] is k for k in kept)]
    if len(bodies) == 1:
        return [*bodies[0][0], *bodies[0][1]]

    def rank(k: int):
        ls = bodies[k][1]
        # a `(= *X Y)` whose Y the branch makes: Y's site could make X
        same = sum(1 for l in ls for m in re.finditer(r"\(= \*(\w+) ([A-Z]\w*)\)", l)
                   if m.group(1) in cols and m.group(2) not in outer)
        return (same, -sum(made_at_site(ls, x) for x in cols), k)
    k0 = min(range(len(bodies)), key=rank)
    bodies = [bodies[k0], *(b for k, b in enumerate(bodies) if k != k0)]
    taken = set(outer) | set(cols)
    for _, ls in bodies:
        taken |= label_names(ls)
    seen = label_names(bodies[0][1])
    groups = [bodies[0]]
    for cm, ls in bodies[1:]:
        ren: dict[str, str] = {}
        for x in sorted(label_names(ls) - cols - outer):
            if x in seen:
                n = 2
                while f"{x}{n}" in taken:
                    n += 1
                ren[x] = f"{x}{n}"
                taken.add(ren[x])

        def sub(mark: str, x: str) -> str:
            return x if x in cols else mark + ren.get(x, x)
        ls = relabel(ls, sub)
        seen |= label_names(ls)
        groups.append((cm, ls))
    head, pad = "(OR ", "    "
    out: list[str] = []
    for gi, (cm, g) in enumerate(groups):
        lines = [("(" if li == 0 else " ") + l for li, l in enumerate(g)] or ["("]
        close(lines, ")")
        out.extend(cm if gi == 0 else [pad + x for x in cm])
        out.append((head if gi == 0 else pad) + lines[0])
        out.extend(pad + l for l in lines[1:])
    close(out, ")")
    return out


def drop_implied(bodies: list[list[str]]) -> list[list[str]]:
    """The union's bodies less each that holds only where another holds,
    the earlier of two that each imply the other kept."""
    from arclog_convert.lint import implies, read
    try:
        parsed = [read("\n".join(b)) for b in bodies]
    except SyntaxError:
        return bodies
    gone: set[int] = set()
    for i in range(len(bodies)):
        for j in range(len(bodies)):
            if i == j or j in gone:
                continue
            if implies(parsed[i], parsed[j]) and not (implies(parsed[j], parsed[i]) and j > i):
                gone.add(i)
                break
    return [b for k, b in enumerate(bodies) if k not in gone]


def merge_forms(forms: list[Form]) -> list[Form]:
    """Each relation's clauses in one block as one clause whose body is an OR,
    a branch per clause."""
    names: dict[str, list[Form]] = defaultdict(list)
    for f in forms:
        names[f.name].append(f)
    out: list[Form] = []
    done: set[str] = set()
    for f in forms:
        if f.name in done:
            continue
        done.add(f.name)
        out.extend(g for g in names[f.name] if g.body is None)
        fs = [g for g in names[f.name] if g.body is not None]
        if len(fs) <= 1:
            out.extend(fs)
            continue
        if len({g.side for g in fs}) != 1 or len({tuple(g.cols) for g in fs}) != 1:
            MERGES["unmerged"] += 1
            MERGES_UNMERGED.append(f.name)
            out.extend(fs)
            continue
        MERGES["relation"] += 1
        body = or_body([(g.comments, g.body or []) for g in fs], set(fs[0].cols), set())
        g = Form([f"({fs[0].side} {f.name}"] + ["  " + l for l in body + fs[0].marks], f.name,
                 set().union(*(x.reads for x in fs)), line=min(x.line for x in fs))
        close(g.lines, ")")
        g.claim_slugs = [s for x in fs for s in x.claim_slugs]
        g.branches = tuple(sorted(set().union(*(x.branches for x in fs))))
        g.cols, g.side = list(fs[0].cols), fs[0].side
        g.marks = list(fs[0].marks)
        out.append(g)
    return out


MERGES_UNMERGED: list[str] = []


def exported(lines: list[str]) -> set[str]:
    """The labels a list of atoms makes in its own scope: at its sites, and
    those an OR or IF in it exports."""
    from arclog_convert.lint import L, Sym, leaves as lint_leaves, read
    try:
        items = read("\n".join(lines))
    except SyntaxError:
        return set(re.findall(r"[*^](\w+)", " ".join(lines)))

    def named(x) -> set[str]:
        return {t.text.lstrip("*^") for t in lint_leaves(x) if isinstance(t, Sym)} if isinstance(x, L) else set()

    def made(items) -> set[str]:
        out: set[str] = set()
        for a in items:
            if not isinstance(a, L):
                continue
            if a.head == "OR":
                brs = [b for b in a.items[1:] if isinstance(b, L)]
                if brs:
                    first = made(brs[0].items)
                    out |= {x for x in first if all(x in named(b) for b in brs[1:])}
            elif a.head == "IF":
                parts = [p_ for p_ in a.items[1:] if isinstance(p_, L)]
                if len(parts) == 3:
                    out |= made(parts[1].items) & named(parts[2])
            elif a.head in ("ALL", "NOT"):
                continue
            elif a.head == "=":
                if len(a.items) == 3 and isinstance(a.items[1], Sym) and a.items[1].text[:1] == "*":
                    out.add(a.items[1].text[1:])
            else:
                out |= {t.text[1:] for t in lint_leaves(a) if isinstance(t, Sym) and t.text[:1] in "*^"}
        return out
    return made(items)


def fold_or_lines(text: str) -> str:
    """Each RULE_OR_DET or DET_OR_RULE line on a relation that a clause of
    the same block derives, folded into that clause: the clause takes the
    line's head, gloss and proposers, and the line goes, so one form
    derives the relation. A `(SET)` mark of the line goes with it: a clause
    with a body gives one value."""
    from arclog_convert.lint import L, Str, Sym, read, flat
    try:
        items = read(text)
    except SyntaxError:
        return text
    lines_: list[tuple[object, L]] = []
    clauses: dict[tuple, list[L]] = defaultdict(list)
    side_of = {"RULE_OR_DET": "RULE", "DET_OR_RULE": "DET"}

    def walk_(xs, block) -> None:
        for x in xs:
            if not isinstance(x, L):
                continue
            named = len(x.items) >= 2 and isinstance(x.items[1], Sym)
            after = x.items[3:] if named and isinstance(x.items[2:3] and x.items[2], Str) else x.items[2:]
            if x.head in side_of and named and all(isinstance(y, Sym) or y.head in ("ONE", "SET") for y in after):
                lines_.append((block, x))
            elif x.head in ("RULE", "DET") and named and any(isinstance(y, L) and y.head != "ONE" for y in x.items[2:]):
                clauses[(block, x.head, x.items[1].text)].append(x)
            elif x.head in ("INPUT", "OUTPUT", "ALTS"):
                walk_(x.items[1:], block)
            elif x.head == "ALT":
                walk_(x.items[1:], id(x))
    walk_(items, None)
    edits: list[tuple[int, int, str]] = []
    for block, f in lines_:
        cs = clauses.get((block, side_of[f.head], f.items[1].text), [])
        if len(cs) != 1:
            continue
        g = cs[0]
        glossed = len(f.items) > 2 and isinstance(f.items[2], Str)
        rest_ = f.items[2 + glossed:]
        props = [y.text for y in rest_ if isinstance(y, Sym)]
        marks = {flat(y) for y in rest_ if isinstance(y, L) and y.head == "ONE"}   # a SET mark goes with the line
        if not marks <= {flat(y) for y in g.items[2:] if isinstance(y, L) and y.head == "ONE"}:
            continue
        a = text.rfind("\n", 0, f.start) + 1
        b = text.find("\n", f.end)
        b = len(text) if b < 0 else b
        tail = text[f.end:b]
        prev = text[text.rfind("\n", 0, max(a - 1, 0)) + 1:max(a - 1, 0)]
        if text[a:f.start].strip() or tail.strip(" )") or (tail.strip() and prev.lstrip().startswith(";;")):
            continue
        head_end = g.items[1].pos + len(g.items[1].text)
        edits.append((g.start, head_end, " ".join([f"({f.head} {f.items[1].text}",
                                                     *([f.items[2].text] if glossed else []), *props])))
        # the line goes with its own line break and a blank line after it;
        # parens after it on its line close an enclosing form
        if tail.strip():
            p_ = a - 1
            while p_ > 0 and text[p_ - 1] == "\n":
                p_ -= 1
            edits.append((p_, b, tail.strip()))
        else:
            end = b + 1
            if text[end:end + 1] == "\n":
                end += 1
            elif text[a - 2:a] == "\n\n":
                a -= 1
            edits.append((a, end, ""))
    for a, b, new in sorted(edits, reverse=True):
        text = text[:a] + new + text[b:]
    return text


def share_labels(branches: list[list[str]]) -> list[list[str]]:
    """OR branches with the labels the first branch makes named, not made,
    in each later branch that makes them, so they are exported."""
    made = exported(branches[0])
    out = [branches[0]]
    for br in branches[1:]:
        out.append([re.sub(r"[*^](\w+)", lambda m: m.group(1) if m.group(1) in made else m.group(0), l)
                    for l in br])
    return out


def mark_key(lines: list[str], knames: list[str]) -> list[str]:
    """Turn the first `*K` of each key label into `^K`."""
    out = []
    left = set(knames)
    for line in lines:
        for k in list(left):
            pat = re.compile(r"\*" + re.escape(k) + r"(?![\w])")
            if pat.search(line):
                line = pat.sub("^" + k, line, count=1)
                left.discard(k)
        out.append(line)
    return out


def topo(forms: list[Form]) -> list[Form]:
    """The forms with each relation's forms together, after the relations
    they read."""
    names: dict[str, list[Form]] = defaultdict(list)
    for f in forms:
        names[f.name].append(f)
    done: set[str] = set()
    visiting: set[str] = set()
    out: list[Form] = []

    def visit(name: str) -> None:
        if name in done or name in visiting:
            return
        visiting.add(name)
        for f in names[name]:
            for r in sorted(f.reads):
                if r != name and r in names:
                    visit(r)
        visiting.discard(name)
        done.add(name)
        out.extend(names[name])

    for f in sorted(forms, key=lambda f: f.line):
        visit(f.name)
    return out


def render_forms(forms: list[Form], ind: str) -> list[str]:
    out = []
    forms = merge_forms(forms)
    for i, f in enumerate(forms):
        if i:
            out.append("")
        out.extend(ind + c for c in f.comments)
        out.extend(ind + l if l else l for l in f.lines)
    return out


RENAMED = {"in": "input", "ex_in": "ex_input", "ex_out": "ex_output"}


def renamed(text: str) -> str:
    """The grid relations under arclog's names, `input`, `ex_input`,
    `ex_output` and `&output`, and a choice's candidates clause as `from`."""
    text = re.sub(r"(?<=\()(in|ex_in|ex_out)(?=[\s)])", lambda m: RENAMED[m.group(1)], text)
    text = re.sub(r"&out(?![\w.])", "&output", text)
    return text.replace("(@@in ", "(from ")




def hoist_shared(text: str) -> str:
    """The text with each form that several alts state with one meaning,
    and that only their cases read, stated once in the concept: at the end
    of the concept's block of the slug it stands under, or of a later block
    that declares a relation it reads."""
    from arclog_convert.lint import alt_repeats, placements, read, reads
    forms = read(text)
    pl = placements(forms)
    groups: dict[int, tuple] = {}
    for kind, p, ref, shared in alt_repeats(pl):
        if kind == "shared" and not shared:
            groups.setdefault(id(ref), (ref, []))[1].append(p)
    if not groups:
        return text
    lines = text.split("\n")
    blocks = {f.items[1].text: f for f in forms if f.head in ("INPUT", "OUTPUT")}
    order = list(blocks)
    block_of = {p.name: p.slug for p in pl if p.name and not p.alts}
    own_end: dict[int, str] = {}   # a form's last line, less the parens after it

    def span(f) -> tuple[int, int, str] | None:
        """The form's first line, with the comments above it, its last
        line, and the closing parens after it there, where only those
        follow it."""
        a, b = f.line - 1, text.count("\n", 0, f.end)
        tail = text[f.end:].split("\n", 1)[0]
        if tail.strip(")") or text[:f.start].rsplit("\n", 1)[-1].strip():
            return None
        while a > 0 and lines[a - 1].strip().startswith(";;"):
            a -= 1
        own_end[b] = lines[b][:len(lines[b]) - len(tail)]
        return a, b, tail

    moves: dict[str, list[list[str]]] = defaultdict(list)   # a block's slug -> the forms it takes
    cuts = []
    for ref, reps in sorted(groups.values(), key=lambda g: g[0].form.line):
        spans = [span(x.form) for x in [ref, *reps]]
        rs = reads(ref.form, ref.name.partition(".")[0])
        if any(x is None for x in spans) or any(block_of.get(r, "") is None for r in rs) \
                or any(r not in block_of and any(r == p.name for p in pl) for r in rs):
            continue   # it reads a form of the tail, which stands after the ALTS forms, or one of an alt
        at = [order.index(sl) for sl in [ref.slug, *(block_of.get(r) for r in rs)] if sl in order]
        slug = order[max(at)] if at else order[-1]
        a, b, tail = spans[0] or (0, 0, "")
        ind = len(lines[ref.form.line - 1]) - len(lines[ref.form.line - 1].lstrip())
        body = [l[ind:] for l in lines[a:b + 1]]
        body[-1] = body[-1][:len(body[-1]) - len(tail)]
        moves[slug].append(["  " + l if l else l for l in body])
        block_of[ref.name] = slug
        cuts += [x for x in spans if x is not None]
    # each alt's copy, bottom up; the parens after it close the blocks above it
    for a, b, tail in sorted(cuts, reverse=True):
        tail = lines[b][len(own_end[b]):]   # a later copy's parens may have come up to it
        del lines[a:b + 1]
        k = a - 1
        while k > 0 and not lines[k].strip():
            k -= 1
        if tail:
            lines[k] += tail
            del lines[k + 1:a]
        elif a < len(lines) and not lines[a].strip():
            del lines[a]   # the blank line that parted it from the next form
        elif not lines[a - 1].strip():
            del lines[a - 1]
    for slug in sorted(moves, key=order.index, reverse=True):
        e = text.count("\n", 0, blocks[slug].end)
        lines[e] = lines[e][:-1]
        new = [""]
        for body in moves[slug]:
            new += body + [""]
        new[-2] += ")"
        lines[e + 1:e + 1] = new[:-1]
    return "\n".join(lines)


