"""Standalone HTML cards the user rules on.

A card states one question, shows the task's pairs, shows the code slices
the question is about, shows the grids a solver produces for a witness
input, and ends with a numbered list of options. The user answers by index.

`study.card_spec` holds what a card spec may state.

A card is one file under .scratch/cards/ and needs no server: the ARC
palette and the grid CSS are copied from the console's UI into the page.
"""

import html
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from arc.task import Example, pair_name
from arc.task import load as load_task
from cli.common import LIMITS, parse_grid
from cli.common import engine as _engine
from engine import AdtValue, Grid, RecordValue, Value, checkout, value_text
from solver.model import (
    Case,
    Solver,
    cases as cases_of,
    load,
)
from solver.solve import Assignment, Grids, examples, outcomes
from study.card_spec import Card, CodeSlice, Table

REPO_ROOT = checkout.ROOT

CARDS_DIR = REPO_ROOT / ".scratch" / "cards"

# Copied from tools/console/ui/panels/grid.js.
ARC = [
    "#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
    "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25",
]


# --- corpus scan ---


def equal_literal_params(solver: Solver) -> list[tuple[int, list[str]]]:
    """Groups of the solver's Params parameters that hold one single-number
    row each and state the same number, as (number, parameter names).
    A parameter read by no group is left out; so is a group of one."""
    values: dict[str, int] = {}
    for param in solver.params.parameters:
        if [c.type for c in param.columns] != ["number"]:
            continue
        rows = param.stored
        if not isinstance(rows, tuple) or len(rows) != 1 \
                or len(rows[0]) != 1 or not isinstance(rows[0][0], int):
            continue
        values[param.name] = rows[0][0]
    groups: dict[int, list[str]] = {}
    for name, value in values.items():
        groups.setdefault(value, []).append(name)
    return [(v, names) for v, names in sorted(groups.items()) if len(names) > 1]


def equal_literal_corpus() -> list[tuple[str, int, list[str]]]:
    """(stem, literal, relation names) for every solver under
    programs/solvers/ carrying such a group, sorted by stem."""
    found = []
    engine = _engine()
    for path in sorted(checkout.solvers().glob("*.dl")):
        if path.name.startswith("."):
            continue
        for value, names in equal_literal_params(load(path.stem, engine)):
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
.pair { display:flex; gap:10px; align-items:flex-start; padding:7px 9px;
        background:#fff; border:1px solid #DDE1E5; border-radius:4px; }
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


def render_grid(grid: Sequence[Sequence[int]], label: str) -> str:
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


def render_pair(label: str, example: Example) -> str:
    """One example as its input beside its output. An example that states no
    output shows its input alone."""
    parts = [render_grid(example.input, f"{label} in")]
    if example.output:
        parts.append(render_grid(example.output, f"{label} out"))
    return '<div class="pair">' + "".join(parts) + "</div>"


def render_task(task_id: str) -> str:
    """Every train pair of the task, then every test pair."""
    return '<div class="grids">' + "".join(
        render_pair(pair_name(pair.section, pair.index), example)
        for pair, example in examples(load_task(task_id))
    ) + "</div>"


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


@dataclass(frozen=True)
class Candidate:
    """One case's output on a witness input: its case, and its grid, or
    the reason it gives none."""

    case: Case
    grid: Grid
    error: str | None = None

    @property
    def label(self) -> str:
        """The case as Souffle prints the `out` column; `''` where `out`
        has none."""
        return "" if self.case.base is None else value_text(self.case.base)


def souffle_order(value: Value) -> tuple[object, ...]:
    """A value's place in the order Souffle prints `out` in: an ADT by its
    constructor's name, then its arguments; a record by its fields."""
    match value:
        case AdtValue(constructor=c, args=args):
            return (c, *(souffle_order(a) for a in args))
        case RecordValue(fields=fields):
            return tuple(souffle_order(f) for f in fields)
        case _:
            return (value,)


def solver_file(card: Card) -> Path:
    """The card's solver file: its `solver` as a path from the repository
    root where a file stands there, else the file of that name under
    `programs/solvers/`; the task's solver where the card names none."""
    arg = card.solver or card.task_id
    name = arg if arg.endswith(".dl") else f"{arg}.dl"
    path = Path(name)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path if path.exists() else checkout.solvers() / Path(name).name


def outside_solvers(path: Path) -> bool:
    """The file stands outside `programs/solvers/`, which
    `solver.model.load` reads alone."""
    return path.resolve().parent != checkout.solvers().resolve()


def run_solver(path: Path, grid: Grid) -> list[Candidate]:
    """Each case of the solver without a `@derive` or `@store` branch of the solver
    at `path`, a file under `programs/solvers/`, run on `grid` at the
    stored assignment, in the order Souffle prints the cases' values
    in."""
    engine = _engine()
    solver = load(path.stem, engine)
    cases = cases_of(solver, engine, LIMITS)
    if not isinstance(cases, tuple):
        raise RuntimeError(str(cases))
    bases = sorted((c for c in cases if not c.branches),
                   key=lambda c: () if c.base is None
                   else souffle_order(c.base))
    got = outcomes(engine, solver, bases, grid, Assignment(()), LIMITS)
    out: list[Candidate] = []
    for case in bases:
        outcome = got[case]
        if isinstance(outcome, Grids):
            out += [Candidate(case, g) for g in outcome.grids]
        else:
            out.append(Candidate(case, (), "undefined"))
    return out


def case_of(cand: Candidate) -> str:
    """The constructor of a candidate's `Choice` value, as a card's
    `dropped` names it; the value as Souffle prints it where it is a
    record, and `''` where `out` has no case column."""
    base = cand.case.base
    return base.constructor if isinstance(base, AdtValue) else cand.label


def _candidate_html(cand: Candidate, card: Card) -> str:
    case = case_of(cand)
    label = cand.label or "out"
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
    return '<div class="gwrap">' + "".join(parts) + "</div>"


@dataclass
class Run:
    """One witness input with what the card's solver made of it."""

    label: str
    grid: Grid
    candidates: list[Candidate] = field(default_factory=list[Candidate])
    error: str = ""


def witness_grids(card: Card) -> list[tuple[str, Grid]]:
    """(label, grid) per witness. With no witness file listed, the task's
    first train input is the witness."""
    if not card.witnesses:
        pair, example = next(examples(load_task(card.task_id)))
        return [(f"{pair_name(pair.section, pair.index)} input",
                 tuple(tuple(r) for r in example.input))]
    grids = []
    for spec_path in card.witnesses:
        path = Path(spec_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        grid = parse_grid(path.read_text())
        if grid is None:
            raise ValueError(f"{path} holds no grid")
        grids.append((path.name, grid))
    return grids


def run_witnesses(card: Card) -> list[Run]:
    """The card's solver run on each witness input."""
    path = solver_file(card)
    runs = []
    for label, grid in witness_grids(card):
        try:
            candidates = run_solver(path, grid)
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
    body.append("<h2>Task</h2>")
    body.append(render_task(card.task_id))
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
              f"{len(list(checkout.solvers().glob('*.dl')))}",
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
