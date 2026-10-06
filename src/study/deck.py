"""The page of a concept-decision deck: its cards, each the task's pairs,
the numbered options, and a table with each witness's input, the output of
the pass's verdict where one is recorded, and the options' outputs, where
outputs that agree share one cell, an option's output that is the
verdict's is marked, and the cells on which an output differs from the
verdict's, or from the other options, are outlined. The page is written to
work/decks/<name>.html in the form the Artifact tool publishes as it
stands."""

import html
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from arc.task import Example
from engine import Grid, checkout
from engine.program import as_grid
from solver.solve import examples
from study.deck_grids import Cell, contested, size, svg
from study.deck_runs import (CardRuns, NoGrid, Output, Slot, Witness,
                             witness_root)
from study.deck_spec import Option

DECKS_DIR = checkout.work() / "decks"

# The deck is one column of cards. A card is its header, the task's pairs
# in a wrapping row, the options as a numbered list, and one table whose
# first columns are the witness input and the verdict's output and whose other
# columns are the options. Every grid of the table is drawn at one cell size.
STYLE = """
:root {
  --bg: #F2F3F5; --surface: #FFFFFF; --ink: #171A1F; --muted: #636C78;
  --rule: #D9DDE3; --line: #2A2F36; --accent: #4C58CF; --on-accent: #FFFFFF;
  --tag: #E9EBF0; --bad: #B4235A;
  --sans: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #131619; --surface: #1B1F24; --ink: #E6E8EB; --muted: #98A1AB;
    --rule: #2B3139; --line: #3B424C; --accent: #8C95F2; --on-accent: #131619;
    --tag: #262C34; --bad: #E05C8C; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #131619; --surface: #1B1F24; --ink: #E6E8EB; --muted: #98A1AB;
  --rule: #2B3139; --line: #3B424C; --accent: #8C95F2; --on-accent: #131619;
  --tag: #262C34; --bad: #E05C8C; color-scheme: dark;
}
body { margin: 0; padding-block: 28px 72px; padding-inline: clamp(16px, 3vw, 40px);
       background: var(--bg); color: var(--ink); font: 14px/1.5 var(--sans); }
.deck { max-width: 1320px; margin: 0 auto; }
h1 { font: 600 22px/1.2 var(--sans); margin: 0 0 6px; text-wrap: balance; }
.lede { color: var(--muted); margin: 0 0 16px; max-width: 70ch; }
.toc { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.toc li { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.toc a { color: var(--ink); text-decoration: none; font: 500 13px/1 var(--mono);
         display: inline-flex; align-items: center; gap: 8px; }
.toc a:hover { text-decoration: underline; }
.toc .q { color: var(--muted); }
.n { display: inline-grid; place-items: center; width: 22px; height: 22px;
     border-radius: 50%; background: var(--accent); color: var(--on-accent);
     font: 600 11px/1 var(--mono); flex: none; }
.card { background: var(--surface); border: 1px solid var(--rule); border-radius: 6px;
        padding: 22px 24px 28px; margin-top: 28px;
        --fit: calc((100vw - 48px) / var(--dim));
        --row-fit: calc((100vw - var(--chrome)) / var(--row));
        --cell: clamp(5px, var(--row-fit), var(--cell-max)); }
.pairs { --cell: min(var(--task-max), var(--fit)); }
@supports (width: round(down, 1px, 1px)) {
  .card { --cell: round(down, clamp(5px, var(--row-fit), var(--cell-max)), 1px); }
  .pairs { --cell: round(down, min(var(--task-max), var(--fit)), 1px); }
}
.eyebrow { font: 500 11px/1 var(--mono); letter-spacing: .06em; color: var(--muted); }
.card h2 { font: 500 18px/1.35 var(--sans); margin: 8px 0 0; max-width: 64ch;
           text-wrap: balance; }
h3 { font: 500 11px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase;
     color: var(--muted); margin: 30px 0 14px; display: flex; align-items: center; gap: 12px; }
h3::after { content: ""; flex: 1; height: 1px; background: var(--rule); }
.pairs { display: flex; flex-wrap: wrap; gap: 18px 32px; align-items: flex-start; }
.pair { margin: 0; display: flex; flex-wrap: wrap; gap: 8px 10px; align-items: center; }
.pair figcaption { flex-basis: 100%; font: 11px/1 var(--mono); color: var(--muted); }
.arrow { color: var(--muted); font-size: 15px; }
svg.g { display: block; height: auto; max-width: 100%; border: 1px solid var(--line);
        background: var(--line); }
.gl { stroke: var(--line); stroke-width: 1; vector-effect: non-scaling-stroke; fill: none; }
.dk { stroke: #000; stroke-width: 4; vector-effect: non-scaling-stroke; fill: none;
      stroke-linecap: square; }
.dw { stroke: #fff; stroke-width: 2; vector-effect: non-scaling-stroke; fill: none;
      stroke-linecap: square; }
.options { margin: 0; padding: 0; list-style: none; display: grid; gap: 12px; max-width: 84ch; }
.options li { display: grid; grid-template-columns: 22px 1fr; gap: 12px; align-items: start; }
.options b { font-weight: 600; }
.scroll { margin-inline: -24px; padding-inline: 24px; overflow-x: auto; }
.note { font: 12px/1.5 var(--sans); color: var(--muted); margin: -6px 0 10px; }
table.w { border-collapse: separate; border-spacing: 0; width: 100%; }
table.w svg.g { max-width: none; }
table.w th { background: var(--surface); text-align: left; font: 500 13px/1.2 var(--sans);
             padding: 8px 12px 10px; border-bottom: 1px solid var(--rule); }
table.w th .n { margin-right: 8px; vertical-align: -5px; }
table.w th.in { color: var(--muted); font-weight: 500; }
table.w td { padding: 8px 12px 16px; vertical-align: top; border-bottom: 1px solid var(--rule); }
tr.lab td { padding: 16px 12px 6px; border-bottom: 0; font: 12px/1.5 var(--sans);
            color: var(--muted); max-width: 0; }
tr.lab .id { color: var(--ink); font: 500 12px/1 var(--mono); margin-right: 10px; }
tr.lab .d { color: var(--ink); margin-right: 10px; }
.tag { display: inline-block; font: 11px/1 var(--mono); background: var(--tag);
       color: var(--muted); padding: 3px 6px; border-radius: 3px; margin-right: 6px; }
.slot { display: grid; gap: 6px; justify-items: start; }
.slot .sz, .who { font: 10.5px/1 var(--mono); color: var(--muted); letter-spacing: .04em; }
.who { margin-bottom: 6px; }
.who .eq { color: var(--accent); margin-left: 8px; }
td.same { background: color-mix(in srgb, var(--tag) 55%, transparent); }
table.w th.judged, table.w td.judged { border-right: 1px solid var(--rule); }
td.hit .slot svg.g { outline: 3px solid var(--accent); outline-offset: 1px; }
.who .hit { color: var(--accent); font-weight: 500; margin-left: 8px; }
.who .hit::before { content: "✓ "; }
.nog { display: grid; place-content: center; gap: 4px; min-width: 92px; min-height: 60px;
       padding: 10px 12px; border: 1px dashed var(--rule); border-radius: 4px; color: var(--muted);
       font: 12px/1.3 var(--sans); text-align: center; }
.nog small { font: 10.5px/1.35 var(--mono); max-width: 26ch; white-space: pre-line; }
.nog.failed { border-color: var(--bad); color: var(--bad); }
tr.div td { padding: 26px 12px 4px; border-bottom: 0; font: 500 11px/1 var(--mono);
            letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
"""

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600'
         '&display=swap">')


def esc(text: str) -> str:
    return html.escape(text, quote=True)


# The rows of the table

@dataclass(frozen=True)
class Span:
    """Options next to each other in a row that give one output: the index
    of the first, how many, their output, and the index of the first option
    of an earlier span with the same output, where one is."""

    first: int
    count: int
    slot: Slot
    same_as: int | None

    @property
    def numbers(self) -> str:
        return " · ".join(str(i + 1) for i in range(self.first,
                                                   self.first + self.count))


def same(a: Slot, b: Slot) -> bool:
    """Whether two options give one output: the same grids, or both
    undefined. A run that gave no result or does not apply is like no
    other."""
    if isinstance(a, Output) and isinstance(b, Output):
        return a.grids == b.grids
    return isinstance(a, NoGrid) and isinstance(b, NoGrid) \
        and a.kind == b.kind == "undefined"


def spans(slots: Sequence[Slot]) -> list[Span]:
    out: list[Span] = []
    i = 0
    while i < len(slots):
        j = i + 1
        while j < len(slots) and same(slots[i], slots[j]):
            j += 1
        earlier = next((s.first for s in out if same(s.slot, slots[i])), None)
        out.append(Span(i, j - i, slots[i], earlier))
        i = j
    return out


def agree(slots: Sequence[Slot]) -> bool:
    return all(same(slots[0], s) for s in slots[1:])


def defined(slots: Sequence[Slot]) -> list[Grid]:
    """The first grid of each option that gives one."""
    return [s.grids[0] for s in slots if isinstance(s, Output)]


def marks(slots: Sequence[Slot], judged: Grid | None
          ) -> frozenset[Cell] | None:
    """The cells outlined on this row's outputs where no output is judged:
    those on which the defined outputs differ, where two or more are
    defined and of one size. With a judged output, each output is outlined
    against it (`marks_against`)."""
    if judged is not None:
        return None
    grids = defined(slots)
    return contested(grids) if len(grids) > 1 else None


def marks_against(slot: Slot, judged: Grid | None) -> frozenset[Cell] | None:
    """The cells on which an option's output differs from the judged one,
    where both are of one size."""
    if judged is None or not isinstance(slot, Output):
        return None
    return contested([slot.grids[0], judged])


def hits(slot: Slot, judged: Grid | None) -> bool:
    """Whether an option's output is the judged one."""
    return judged is not None and isinstance(slot, Output) \
        and slot.grids == (judged,)


_NOGRID_WORD = {"undefined": "undefined", "failed": "no result",
                "inapplicable": "not applicable"}
_NOGRID_PHRASE = {"undefined": "undefined for", "failed": "no result for",
                  "inapplicable": "not applicable to"}


def difference(slots: Sequence[Slot]) -> str:
    """How the options' outputs stand apart on a row, in a few words."""
    if agree(slots):
        return "all options agree" + (
            ", undefined" if isinstance(slots[0], NoGrid) else "")
    parts: list[str] = []
    grids = defined(slots)
    if len(grids) > 1:
        cells = contested(grids)
        if cells is None:
            parts.append("sizes differ")
        elif len(cells) == 1:
            parts.append("1 cell differs")
        elif cells:
            parts.append(f"{len(cells)} cells differ")
    for kind, phrase in _NOGRID_PHRASE.items():
        numbers = [str(i + 1) for i, s in enumerate(slots)
                   if isinstance(s, NoGrid) and s.kind == kind]
        if numbers:
            parts.append(f"{phrase} {', '.join(numbers)}")
    return " · ".join(parts)


def grid_html(grid: Grid, marked: frozenset[Cell] | None, label: str = ""
              ) -> str:
    h, w = size(grid)
    m = marked if marked is not None else frozenset[Cell]()
    sz = f"{h}×{w}" + (f" · {label}" if label else "")
    return f'<div class="slot">{svg(grid, m)}<span class="sz">{sz}</span></div>'


def slot_html(slot: Slot, marked: frozenset[Cell] | None) -> str:
    if isinstance(slot, NoGrid):
        return (f'<div class="nog {slot.kind}"><span>{_NOGRID_WORD[slot.kind]}'
                f'</span><small>{esc(slot.text)}</small></div>')
    first = size(slot.grids[0])
    return "".join(
        grid_html(g, marked if size(g) == first else None,
                  f"resolution {k + 1}" if len(slot.grids) > 1 else "")
        for k, g in enumerate(slot.grids))


def row_html(witness: Witness, slots: Sequence[Slot], columns: int,
             with_judged: bool) -> str:
    tags = "".join(f'<span class="tag">reassigns {esc(n)}</span>'
                   for n in witness.reassigns)
    label = (f'<tr class="lab"><td colspan="{columns}">'
             f'<span class="id">{esc(witness.id)}</span>'
             f'<span class="d">{esc(difference(slots))}</span>{tags}</td></tr>')
    judged = witness.judged
    mutual = marks(slots, judged)
    cells = [f'<td class="in">{grid_html(witness.input, None)}</td>']
    if with_judged:
        shown = grid_html(judged, None) if judged is not None \
            else '<div class="nog"><span>no verdict</span></div>'
        cells.append(f'<td class="judged">{shown}</td>')
    for span in spans(slots):
        hit = hits(span.slot, judged)
        eq = (f'<span class="eq">same as {span.same_as + 1}</span>'
              if span.same_as is not None else "")
        mark = '<span class="hit">verdict</span>' if hit else ""
        who = f'<div class="who">{span.numbers}{eq}{mark}</div>'
        classes = (["same"] if span.count > 1 else []) + (["hit"] if hit else [])
        cls = f' class="{" ".join(classes)}"' if classes else ""
        marked = mutual if judged is None else marks_against(span.slot, judged)
        cells.append(f'<td colspan="{span.count}"{cls}>{who}'
                     f'{slot_html(span.slot, marked)}</td>')
    return label + f'<tr class="out">{"".join(cells)}</tr>'


def has_judged(runs: CardRuns) -> bool:
    return any(w.judged is not None for w in runs.witnesses)


def judged_by(runs: CardRuns) -> str:
    """Whose judgment the verdicts are: the pass on the solver of
    the option whose checkout holds the witness file, else the pass that
    wrote the file."""
    root = witness_root(runs.spec).resolve()
    for i, o in enumerate(runs.spec.options):
        if o.root.resolve() == root:
            return f"the pass on option {i + 1}’s solver"
    return "the pass that wrote the witness file"


def table_html(runs: CardRuns) -> str:
    options = runs.spec.options
    judged = has_judged(runs)
    columns = len(options) + 1 + judged
    note = (f'<p class="note">The verdict is the output {judged_by(runs)} '
            'judged the generator to pair with the input.</p>' if judged else "")
    head = '<th class="in">input</th>' + (
        '<th class="in judged">verdict</th>' if judged else "") + "".join(
        f'<th><span class="n">{i + 1}</span>{esc(o.name)}</th>'
        for i, o in enumerate(options))
    rows = list(zip(runs.witnesses, runs.slots, strict=True))
    apart = [row_html(w, s, columns, judged) for w, s in rows if not agree(s)]
    alike = [row_html(w, s, columns, judged) for w, s in rows if agree(s)]
    if alike:
        alike.insert(0, f'<tr class="div"><td colspan="{columns}">'
                        'the options agree on these</td></tr>')
    return (f'{note}<div class="scroll"><table class="w"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(apart + alike)}</tbody></table></div>')


# The other blocks of a card

def pair_html(label: str, ex: Example) -> str:
    inp, out = as_grid(ex.input), as_grid(ex.output)
    hi, wi = size(inp)
    ho, wo = size(out)
    return (f'<figure class="pair">{svg(inp)}<span class="arrow">→</span>{svg(out)}'
            f'<figcaption>{esc(label)} · {hi}×{wi} → {ho}×{wo}</figcaption></figure>')


def task_html(runs: CardRuns) -> str:
    return '<div class="pairs">' + "".join(
        pair_html(pair.text, ex) for pair, ex in examples(runs.task)) + "</div>"


def options_html(options: Sequence[Option]) -> str:
    items = [f'<li><span class="n">{i + 1}</span><div><b>{esc(o.name)}</b> '
             f'{esc(o.text)}</div></li>' for i, o in enumerate(options)]
    return '<ol class="options">' + "".join(items) + "</ol>"


def cell_size(runs: CardRuns) -> tuple[int, int, int, int]:
    """The cell size in pixels of the card's witness table, its largest
    grid extent, the cells across the table, each column at its widest
    grid, and the table's columns: one size for every grid of the table,
    the largest at which the largest grid of the card stays within about
    440px and the table, with its cells' padding and least widths, within
    about 1150px. The page shrinks it further where the viewport is
    narrower than that."""
    grids: list[Grid] = [w.input for w in runs.witnesses]
    grids += [w.judged for w in runs.witnesses if w.judged is not None]
    for _, ex in examples(runs.task):
        grids += [as_grid(ex.input), as_grid(ex.output)]
    for row in runs.slots:
        grids += [g for s in row if isinstance(s, Output) for g in s.grids]
    dim = max(max(size(g)) for g in grids)
    columns = len(runs.spec.options) + 1 + has_judged(runs)
    widest = [0] * columns
    for witness, row in zip(runs.witnesses, runs.slots, strict=True):
        widths = [size(witness.input)[1]]
        if has_judged(runs):
            widths.append(size(witness.judged)[1] if witness.judged else 0)
        for span in spans(row):
            width = max(size(g)[1] for g in span.slot.grids) \
                if isinstance(span.slot, Output) else 0
            widths += [width] * span.count
        widest = [max(a, b) for a, b in zip(widest, widths, strict=True)]
    for cell in range(min(20, 440 // dim), 5, -1):
        if sum(max(w * cell, _SLOT_MIN) + 24 for w in widest) <= 1150:
            break
    return cell, dim, sum(widest), columns


_SLOT_MIN = 110
"""The least width a table cell takes, in pixels, for its labels or its
box for no grid."""


def task_cell_size(dim: int) -> int:
    """The cell size of the task's pairs, drawn as context: the largest at
    which a card's largest grid stays within about 260px."""
    return max(4, min(12, 260 // dim))


def card_html(number: int, runs: CardRuns) -> str:
    cell, dim, row, columns = cell_size(runs)
    task = task_cell_size(dim)
    spec = runs.spec
    # The width beside the grids of a row: the body's and the card's
    # padding, each cell's, and room for a cell's labels.
    chrome = f"calc(6vw + 100px + {24 * columns}px)"
    return (f'<section class="card" id="card-{number}" '
            f'style="--cell-max:{cell}px;--task-max:{task}px;--dim:{dim};'
            f'--row:{row};--chrome:{chrome}">'
            f'<div class="eyebrow">Card {number} · {esc(spec.task_id)}</div>'
            f'<h2>{esc(spec.question)}</h2>'
            f'<h3>Task</h3>{task_html(runs)}'
            f'<h3>Options</h3>{options_html(spec.options)}'
            f'<h3>Witnesses</h3>{table_html(runs)}'
            '</section>')


# The deck

def render_deck(title: str, cards: Sequence[CardRuns]) -> str:
    toc = "".join(
        f'<li><a href="#card-{i + 1}"><span class="n">{i + 1}</span>'
        f'{esc(c.spec.task_id)}</a><span class="q">{esc(c.spec.question)}</span></li>'
        for i, c in enumerate(cards))
    body = "".join(card_html(i + 1, c) for i, c in enumerate(cards))
    return (f"<title>{esc(title)}</title>\n<style>{STYLE}</style>\n{FONTS}\n"
            f'<div class="deck"><h1>{esc(title)}</h1>'
            '<p class="lede">Answer each card by the number of the option whose model '
            'is the task’s concept. Option 1 is the model the solver has today. '
            'The verdict column is the output the annotator of a pass judged the '
            'generator to pair with the input; where that verdict was '
            '`concept`, it repeats that pass’s own model. An option that gives '
            'the verdict’s output is marked, and outlines mark the cells on '
            'which an output differs from it, or from the other options where '
            'there is no verdict.</p>'
            f'<ol class="toc">{toc}</ol>{body}</div>\n')


def deck_path(name: str) -> Path:
    """work/decks/<name>.html. A name that is not one file name is a
    `ValueError`."""
    if Path(name).name != name or name in ("", ".", ".."):
        raise ValueError(f"{name!r}: a deck's name is one file name")
    return DECKS_DIR / f"{name}.html"


def write_deck(name: str, title: str, cards: Sequence[CardRuns]) -> Path:
    path = deck_path(name)
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(render_deck(title, cards))
    return path
