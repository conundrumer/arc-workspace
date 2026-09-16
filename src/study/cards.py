"""Standalone HTML cards the user rules on.

A card states one question, shows the code slices it is about, shows the
grids a solver produces for a witness input, and ends with a numbered list
of options. The user answers by index.

A card is one file under .scratch/cards/ and needs no server: the ARC
palette and the grid CSS are copied from the console's UI into the page.
"""

import html
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from arc.task import load as load_task
from dl import solve
from dl.dlparse import TypeDecl, parse
from dl.facts import Candidate, parse_grid
from dl.paths import REPO_ROOT, SOLVERS_DIR
from dl.source import _param_facts, comp_decls

type LineRange = tuple[int, int]

CARDS_DIR = REPO_ROOT / ".scratch" / "cards"

# Copied from tools/console/ui/panels/grid.js.
ARC = [
    "#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
    "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25",
]


@dataclass
class CodeSlice:
    """A run of lines from one file, with some of them highlighted.

    `lines` is a 1-based inclusive [start, end] range; `highlight` holds
    1-based line numbers inside that range.
    """

    label: str
    path: str
    lines: LineRange
    highlight: list[int] = field(default_factory=list[int])


@dataclass
class Table:
    """A small table of text cells shown under the code."""

    title: str
    headers: list[str]
    rows: list[list[str]]


@dataclass
class Card:
    """One question for the user.

    `witnesses` are paths to grid text files (the format `parse_grid`
    reads); with none, the task's first train input is the witness.
    `solver` names the `.dl` file to run, defaulting to the task's own.
    `dropped` names the cases the shipped solver lacks; a witness is kept
    only when a dropped case's output differs from every kept case's, unless
    `all_witnesses` is set, which keeps every witness the card lists.
    """

    name: str
    kind: str
    task_id: str
    question: str = ""
    codes: list[CodeSlice] = field(default_factory=list[CodeSlice])
    witnesses: list[str] = field(default_factory=list[str])
    options: list[str] = field(default_factory=list[str])
    tables: list[Table] = field(default_factory=list[Table])
    solver: str | None = None
    dropped: list[str] = field(default_factory=list[str])
    quote: str = ""
    quote_source: str = ""
    all_witnesses: bool = False


def card_from_dict(data: dict) -> Card:
    """A Card from its JSON form."""
    fields = dict(data)
    codes = [
        CodeSlice(
            label=c["label"],
            path=c["path"],
            lines=(c["lines"][0], c["lines"][1]),
            highlight=list(c.get("highlight", [])),
        )
        for c in fields.pop("codes", [])
    ]
    tables = [
        Table(title=t["title"], headers=list(t["headers"]),
              rows=[list(r) for r in t["rows"]])
        for t in fields.pop("tables", [])
    ]
    return Card(codes=codes, tables=tables, **fields)


def load_card(path: str | Path) -> Card:
    return card_from_dict(json.loads(Path(path).read_text()))


# --- corpus scan ---


def equal_literal_params(source: str) -> list[tuple[int, list[str]]]:
    """Groups of the source's Params relations that hold one single-number
    fact each and state the same literal, as (literal, relation names).
    A relation read by no group is left out; so is a group of one."""
    values: dict[str, int] = {}
    for name, types in comp_decls(source, "Params").items():
        if types != ["number"]:
            continue
        facts = _param_facts(source, name)
        if len(facts) != 1 or len(facts[0]) != 1:
            continue
        try:
            values[name] = int(facts[0][0].strip())
        except ValueError:
            continue
    groups: dict[int, list[str]] = {}
    for name, value in values.items():
        groups.setdefault(value, []).append(name)
    return [(v, names) for v, names in sorted(groups.items()) if len(names) > 1]


def equal_literal_corpus() -> list[tuple[str, int, list[str]]]:
    """(stem, literal, relation names) for every solver under
    programs/solvers/ carrying such a group, sorted by stem."""
    found = []
    for path in sorted(SOLVERS_DIR.glob("*.dl")):
        if path.name.startswith("."):
            continue
        for value, names in equal_literal_params(path.read_text()):
            found.append((path.stem, value, names))
    return found


# --- rendering ---

STYLE = """
:root { color-scheme: light; --well-line:#2A2F36; }
body { margin:0; padding:24px 28px; background:#F6F7F8; color:#14171B;
       font:13px/1.55 ui-sans-serif,system-ui,sans-serif; max-width:1000px; }
h1 { font-size:16px; margin:0 0 2px; }
h2 { font-size:12px; margin:26px 0 8px; letter-spacing:.06em;
     text-transform:uppercase; color:#5A636B; }
.meta { color:#5A636B; font-family:ui-monospace,Menlo,monospace; font-size:11px; }
.q { margin:14px 0 0; font-size:14px; }
.slice { margin:0 0 16px; }
.sl-label { font-family:ui-monospace,Menlo,monospace; font-size:11px;
            color:#5A636B; margin-bottom:4px; }
pre { margin:0; padding:8px 0; background:#fff; border:1px solid #DDE1E5;
      border-radius:4px; overflow-x:auto;
      font:11.5px/1.5 ui-monospace,Menlo,monospace; }
pre .ln { display:block; padding:0 10px; white-space:pre; }
pre .ln.hl { background:#FFF3BF; }
pre .num { display:inline-block; width:34px; text-align:right;
           margin-right:12px; color:#9AA3AB; }
.grids { display:flex; flex-wrap:wrap; gap:18px; align-items:flex-start; }
.gwrap { display:flex; flex-direction:column; gap:4px; }
.glabel { font-size:9.5px; color:#7C8791; font-family:ui-monospace,Menlo,monospace;
          letter-spacing:.05em; }
.agrid { display:grid; gap:1px; background:var(--well-line); width:max-content;
         border:1px solid var(--well-line); }
.agrid div { width:var(--cell); height:var(--cell); }
.agrid div.miss { background:repeating-linear-gradient(45deg,#fff 0 2px,#C2185B 2px 4px); }
.cap { font-size:10px; color:#C2185B; font-family:ui-monospace,Menlo,monospace; }
.err { border:1px solid #C2185B; border-radius:4px; padding:8px 10px;
       background:#FFF5F7; font-family:ui-monospace,Menlo,monospace; font-size:11px; }
table { border-collapse:collapse; font-size:11.5px; }
th, td { border:1px solid #DDE1E5; padding:3px 8px; text-align:left;
         font-family:ui-monospace,Menlo,monospace; }
th { background:#EDEFF1; }
blockquote { margin:0 0 4px; padding:8px 12px; border-left:3px solid #C7CCD1;
             background:#fff; }
ol { padding-left:22px; }
ol li { margin:6px 0; }
"""


def _cell_px(w: int, h: int) -> int:
    m = max(w, h)
    return 16 if m <= 10 else 12 if m <= 15 else 9 if m <= 22 else 7


def render_grid(grid: list[list[int]], label: str) -> str:
    """One grid as colored cells. A cell of -1 is missing, and is hatched."""
    h = len(grid)
    w = len(grid[0]) if h else 0
    px = _cell_px(w, h)
    cells = []
    for row in grid:
        for v in row:
            if v < 0:
                cells.append('<div class="miss"></div>')
            else:
                cells.append(f'<div style="background:{ARC[v]}"></div>')
    style = f"--cell:{px}px;grid-template-columns:repeat({w},{px}px)"
    return (
        '<div class="gwrap">'
        f'<div class="glabel">{html.escape(label)} · {h}×{w}</div>'
        f'<div class="agrid" style="{style}">{"".join(cells)}</div>'
        "</div>"
    )


def render_code(code: CodeSlice) -> str:
    start, end = code.lines
    path = Path(code.path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    lines = path.read_text().splitlines()
    marked = set(code.highlight)
    out = []
    for n in range(start, min(end, len(lines)) + 1):
        cls = "ln hl" if n in marked else "ln"
        out.append(
            f'<span class="{cls}"><span class="num">{n}</span>'
            f"{html.escape(lines[n - 1])}</span>"
        )
    label = f"{code.label} — {code.path}:{start}-{end}"
    return (
        '<div class="slice">'
        f'<div class="sl-label">{html.escape(label)}</div>'
        f'<pre>{"".join(out)}</pre>'
        "</div>"
    )


def render_table(table: Table) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in table.headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>"
        for row in table.rows
    )
    return (
        f"<h2>{html.escape(table.title)}</h2>"
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def case_of(cand: Candidate) -> str:
    """The case name a candidate's variant column carries, without its `$`."""
    return cand.variant.strip("$").split("(")[0]


def _candidate_html(cand: Candidate, card: Card) -> str:
    case = case_of(cand)
    label = cand.variant or "out"
    if card.dropped:
        label += " · dropped" if case in card.dropped else " · kept"
    if cand.error:
        return (
            '<div class="gwrap">'
            f'<div class="glabel">{html.escape(label)}</div>'
            f'<div class="err">{html.escape(cand.error)}</div>'
            "</div>"
        )
    parts = [render_grid(cand.grid, label)]
    if cand.missing:
        parts.append(f'<div class="cap">undefined: {len(cand.missing)} missing</div>')
    if cand.conflicts:
        parts.append(
            f'<div class="cap">undefined: {len(cand.conflicts)} conflicting</div>'
        )
    return '<div class="gwrap">' + "".join(parts) + "</div>"


@dataclass
class Run:
    """One witness input with what the card's solver made of it."""

    label: str
    grid: list[list[int]]
    candidates: list[Candidate] = field(default_factory=list[Candidate])
    error: str = ""


def witness_grids(card: Card) -> list[tuple[str, list[list[int]]]]:
    """(label, grid) per witness. With no witness file listed, the task's
    first train input is the witness."""
    if not card.witnesses:
        task = load_task(card.task_id)
        return [("train[0] input", task.train[0].input)]
    grids = []
    for spec_path in card.witnesses:
        path = Path(spec_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        grids.append((path.name, parse_grid(path.read_text())))
    return grids


def run_witnesses(card: Card) -> list[Run]:
    """The card's solver run on each witness input."""
    stem = card.solver or card.task_id
    runs = []
    for label, grid in witness_grids(card):
        try:
            candidates = solve.run_dl(card.task_id, grid, stem=stem)
        except Exception as e:  # the solver may not compile; the card still renders
            runs.append(Run(label, grid, error=f"{type(e).__name__}: {e}"))
        else:
            runs.append(Run(label, grid, candidates))
    return runs


def diverges(run: Run, dropped: list[str]) -> bool:
    """Whether a dropped case's grid differs from every kept case's grid."""
    kept = [c.grid for c in run.candidates if case_of(c) not in dropped]
    return any(
        c.grid not in kept for c in run.candidates if case_of(c) in dropped
    )


def render_run(run: Run, card: Card) -> str:
    parts = [render_grid(run.grid, f"input · {run.label}")]
    if run.error:
        parts.append(f'<div class="err">{html.escape(run.error)}</div>')
    parts.extend(_candidate_html(c, card) for c in run.candidates)
    return '<div class="grids">' + "".join(parts) + "</div>"


def witness_section(card: Card) -> list[str]:
    """The witness blocks, and for a card with dropped cases a note when no
    witness input separates a dropped case from the kept ones."""
    runs = run_witnesses(card)
    if not card.dropped or card.all_witnesses:
        return [render_run(run, card) for run in runs]
    diverging = [run for run in runs if diverges(run, card.dropped)]
    if diverging:
        return [render_run(run, card) for run in diverging]
    note = (
        "<p>No candidate input separates the dropped case from the kept ones. "
        "The task's first train input follows.</p>"
    )
    fallback = Card(**{**card.__dict__, "witnesses": []})
    return [note] + [render_run(run, card) for run in run_witnesses(fallback)]


def render(card: Card) -> str:
    """The card as one standalone HTML page."""
    body = [
        f"<h1>{html.escape(card.name)}</h1>",
        f'<div class="meta">{html.escape(card.kind)} · task {html.escape(card.task_id)}</div>',
    ]
    if card.question:
        body.append(f'<p class="q">{html.escape(card.question)}</p>')
    if card.codes:
        body.append("<h2>Code</h2>")
        body.extend(render_code(c) for c in card.codes)
    if card.quote:
        body.append("<h2>Recorded reason</h2>")
        body.append(
            f'<blockquote>{html.escape(card.quote)}</blockquote>'
            f'<div class="meta">{html.escape(card.quote_source)}</div>'
        )
    body.append("<h2>Witness</h2>")
    body.extend(witness_section(card))
    body.extend(render_table(t) for t in card.tables)
    if card.options:
        body.append("<h2>Options</h2><ol>")
        body.extend(f"<li>{html.escape(o)}</li>" for o in card.options)
        body.append("</ol>")
    return (
        "<!doctype html>\n<html><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(card.name)}</title>"
        f"<style>{STYLE}</style></head><body>{''.join(body)}</body></html>\n"
    )


def write(card: Card) -> Path:
    """Render `card` to .scratch/cards/<name>.html and return that path."""
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    path = CARDS_DIR / f"{card.name}.html"
    path.write_text(render(card))
    return path


# --- the Θ card ---


def theta_card() -> Card:
    """The Θ card for 5d2a5c43: its Params comp states `gap(1)` and
    `divide_gap(1)`, and the user rules on whether that is one parameter."""
    path = "programs/solvers/5d2a5c43.dl"
    corpus = equal_literal_corpus()
    rows = [
        [stem, ", ".join(names), str(value)]
        for stem, value, names in corpus[:10]
    ]
    table = Table(
        title=f"Solvers with equal-literal Params numbers: {len(corpus)} of "
              f"{len(list(SOLVERS_DIR.glob('*.dl')))}",
        headers=["stem", "relations", "literal"],
        rows=rows,
    )
    return Card(
        name="theta-5d2a5c43",
        kind="theta",
        task_id="5d2a5c43",
        solver=path,
        question=(
            "`gap(1)` and `divide_gap(1)` state the same literal in the same "
            "Params comp: one parameter or two?"
        ),
        codes=[
            CodeSlice("Params comp", path, (32, 73), [43, 55]),
            CodeSlice("reads gap: Params.tile_decompose", path, (44, 48), [47]),
            CodeSlice("reads params.divide_gap: decompose $Count, $Size",
                      path, (89, 99), [93, 97]),
        ],
        options=[
            "One parameter: the two facts state one value, and the second is "
            "derived from the first.",
            "Two parameters: a sibling task could assign them different values.",
        ],
        tables=[table],
    )


# --- the calibration card ---

REPORTS_DIR = REPO_ROOT / "tools" / "console" / "state" / "reports"
MARKER_RE = re.compile(r"^\s*//\s*---\s*(.+?)\s*---\s*$")
FEATURE_COLUMNS = [
    "case", "atoms", "shared_atoms", "reach_atoms", "facts", "negations",
    "disjunctions", "lib_instances", "reach_atoms_ratio_min",
]


def case_names(source: str) -> list[str]:
    """The branches of the `Choice` type, in the order the file states them."""
    for item in parse(source).items:
        if isinstance(item, TypeDecl) and item.name == "Choice":
            return item.branches
    return []


def case_sections(source: str, case: str) -> list[LineRange]:
    """1-based [start, end] line ranges the case's `// --- <Case> ---`
    markers open. With no marker, the ranges of the rules whose head carries
    `$<Case>()`, one line each."""
    lines = source.splitlines()
    marks = [(i, m.group(1)) for i, line in enumerate(lines)
             if (m := MARKER_RE.match(line))]
    spans = []
    for k, (i, name) in enumerate(marks):
        if name != case:
            continue
        end = marks[k + 1][0] - 1 if k + 1 < len(marks) else len(lines) - 1
        for j in range(i + 1, end + 1):  # a section stops at the comp's close
            if lines[j].startswith("}"):
                end = j - 1
                break
        while end > i and not lines[end].strip():
            end -= 1
        spans.append((i + 1, end + 1))
    if spans:
        return spans
    hit = re.compile(rf"^out\(.*\${case}\(\)")
    return [(i + 1, i + 1) for i, line in enumerate(lines) if hit.match(line)]


def case_slices(peer_path: str, source: str, dropped: list[str]) -> list[CodeSlice]:
    """One slice per case section, labeled kept or dropped."""
    slices = []
    for case in case_names(source):
        state = "dropped" if case in dropped else "kept"
        for span in case_sections(source, case):
            slices.append(CodeSlice(f"{case} — {state}", peer_path, span))
    return slices


def features_table(peer_path: str) -> Table:
    """The cases' features, from `scripts/run_dl.py features <peer file>`."""
    run = subprocess.run(
        ["uv", "run", "python", "scripts/run_dl.py", "features", peer_path],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    lines = [ln for ln in run.stdout.splitlines() if "\t" in ln]
    if not lines:
        return Table("Case features", ["case"], [[run.stderr.strip() or "no output"]])
    header = lines[0].split("\t")
    idx = [header.index(c) for c in FEATURE_COLUMNS]
    rows = [[ln.split("\t")[i] for i in idx] for ln in lines[1:]]
    return Table("Case features", FEATURE_COLUMNS, rows)


def report_paragraph(task_id: str, case: str) -> tuple[str, str]:
    """The paragraph of the task's reports that drops the case, with the file
    and line it sits at. A paragraph that opens on the case and states a drop
    is preferred; with none, the first paragraph naming the case."""
    best = None
    for name in ("retro.md", "refine.md", "create.md"):
        path = REPORTS_DIR / task_id / name
        if not path.exists():
            continue
        line_no = 1
        for para in path.read_text().split("\n\n"):
            text = para.strip()
            if case in text:
                score = (case in text[:40], "drop" in text.lower())
                if best is None or score > best[0]:
                    best = (score, text, f"{path.relative_to(REPO_ROOT)}:{line_no}")
            line_no += para.count("\n") + 2
    return (best[1], best[2]) if best else ("", "")


def calibration_card(task_id: str, peer_path: str, dropped: list[str]) -> Card:
    """The card for one peer file: its dropped cases beside its kept ones."""
    path = Path(peer_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    source = path.read_text()
    quote, source_ref = report_paragraph(task_id, dropped[0])
    names = " and ".join([", ".join(dropped[:-1]), dropped[-1]] if len(dropped) > 1
                         else dropped)
    heading = "the cases" if len(dropped) > 1 else "the case"
    verb, parse = ("They fit", "parse") if len(dropped) > 1 else ("It fits", "parses")
    return Card(
        name=f"calibration-{task_id}-{dropped[0]}",
        kind="calibration",
        task_id=task_id,
        solver=peer_path,
        dropped=dropped,
        question=(
            f"Task {task_id} dropped {heading} {names} under peer-priors. "
            f"{verb} every pair and {parse} the task as the shipped cases do."
        ),
        codes=case_slices(peer_path, source, dropped),
        witnesses=sorted(str(p.relative_to(REPO_ROOT)) for p in path.parent.glob("w*.txt")),
        quote=quote,
        quote_source=source_ref,
        tables=[features_table(peer_path)],
        options=[
            "Keep: a person could form this reading of the task.",
            "Drop: no person forms this reading; it is a construction.",
            "Restatement: it is the same model as a kept case.",
        ],
    )


def parse_candidates(text: str) -> list[tuple[str, str, str, str]]:
    """The rows of the "Calibration candidates" table of a compare.md, as
    (task_id, path, case, stratum). A (task_id, case) seen before is left
    out, so the first path listed for it wins."""
    rows: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    in_table = False
    for line in text.splitlines():
        if line.strip().startswith("#"):
            in_table = "Calibration candidates" in line
            continue
        if not in_table:
            continue
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] in ("task_id", "") or set(cells[0]) <= set(":-"):
            continue
        key = (cells[0], cells[2])
        if key in seen:
            continue
        seen.add(key)
        rows.append((cells[0], cells[1], cells[2], cells[3]))
    return rows


def calibration_cards(compare_md: str | Path) -> list[Path]:
    """Render one card per candidate of a compare.md. A task's other dropped
    cases, named by no row, ride along on the card of the first."""
    rows = parse_candidates(Path(compare_md).read_text())
    by_task: dict[str, list[tuple[str, str]]] = {}
    for task_id, path, case, _ in rows:
        by_task.setdefault(task_id, []).append((path, case))
    written = []
    for task_id, entries in by_task.items():
        peer_path = entries[0][0]
        source = (REPO_ROOT / peer_path).read_text()
        named = [case for _, case in entries]
        shipped = shipped_cases(task_id)
        dropped = named + [c for c in case_names(source)
                           if c not in named and c not in shipped]
        written.append(write(calibration_card(task_id, peer_path, dropped)))
    return written


def shipped_cases(task_id: str) -> list[str]:
    """The cases of the solver that ships for the task."""
    path = SOLVERS_DIR / f"{task_id}.dl"
    return case_names(path.read_text()) if path.exists() else []
