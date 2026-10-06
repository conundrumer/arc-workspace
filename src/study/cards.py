"""The HTML pages of the cards the user rules on, and the page that bundles
several of them.

A card states one question, shows the task's pairs, shows the code slices
the question is about, shows the grids a solver produces for a witness
input, and ends with a numbered list of options. The user answers by index.

`study.card_spec` holds what a card spec may state.

A card is one file under work/cards/ that the Artifact tool publishes as it
stands. The tool wraps the file in its own document skeleton, so the page
opens with its `<title>` and its `<style>`, and holds no `<html>`, `<head>`
or `<body>` tag. The ARC palette and the grid CSS are copied from the
console's UI into the page.

A bundle composes card pages as they stand and runs no solver, so it takes
only a page the current renderer wrote: one in `PAGE_FORM` under the
current `STYLE`.
"""

import html
import re
from collections.abc import Sequence
from pathlib import Path

from arc.task import Example
from arc.task import load as load_task
from engine import checkout
from solver.solve import examples
from study.card_runs import (Candidate, Run, check_captions,
                             check_option_cases, drawn_runs)
from study.card_spec import (Card, CodeSlice, Table, from_root, options_of,
                             options_phrase)

CARDS_DIR = checkout.work() / "cards"

# Copied from tools/console/ui/panels/grid.js.
ARC = [
    "#000000", "#0074D9", "#FF4136", "#2ECC40", "#FFDC00",
    "#AAAAAA", "#F012BE", "#FF851B", "#7FDBFF", "#870C25",
]


# At a phone's width the body never scrolls sideways: rows of grids wrap,
# long words break, and a code slice or a table scrolls in its own box.
STYLE = """
:root { color-scheme: light; --well-line:#2A2F36; background:#F6F7F8; }
body { margin:0; padding:24px 28px; background:#F6F7F8; color:#14171B;
       font:13px/1.55 ui-sans-serif,system-ui,sans-serif; max-width:1000px;
       overflow-wrap:anywhere; }
a { color:#0B5CAD; }
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
.pair { display:flex; flex-wrap:wrap; gap:10px; align-items:flex-start; padding:7px 9px;
        background:#fff; border:1px solid #DDE1E5; border-radius:4px; }
.gwrap { display:flex; flex-direction:column; gap:4px; }
.glabel { font-size:9.5px; color:#7C8791; font-family:ui-monospace,Menlo,monospace;
          letter-spacing:.05em; }
.agrid { display:grid; gap:1px; background:var(--well-line); width:max-content;
         border:1px solid var(--well-line); }
.agrid div { width:var(--cell); height:var(--cell); }
.agrid div.miss { background:repeating-linear-gradient(45deg,#fff 0 2px,#C2185B 2px 4px); }
.cap { font-size:11.5px; color:#14171B; max-width:240px; }
.err { border:1px solid #C2185B; border-radius:4px; padding:8px 10px;
       background:#FFF5F7; font-family:ui-monospace,Menlo,monospace; font-size:11px; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; font-size:11.5px; overflow-wrap:normal; }
th, td { border:1px solid #DDE1E5; padding:3px 8px; text-align:left;
         font-family:ui-monospace,Menlo,monospace; }
th { background:#EDEFF1; }
blockquote { margin:0 0 4px; padding:8px 12px; border-left:3px solid #C7CCD1;
             background:#fff; }
ol { padding-left:22px; }
ol li { margin:6px 0; }
.bundle > section { margin-top:40px; padding-top:16px;
                    border-top:2px solid #C7CCD1; }
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
        render_pair(pair.text, example)
        for pair, example in examples(load_task(task_id))
    ) + "</div>"


def render_code(code: CodeSlice) -> str:
    start, end = code.lines
    lines = from_root(code.path).read_text().splitlines()
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
        f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )

def _candidate_html(cand: Candidate, card: Card, witness: str) -> str:
    label = cand.label
    if card.dropped:
        label += " · dropped" if cand.label in card.dropped else " · kept"
    numbers = options_of(card, cand.label)
    if numbers:
        label += f" · {options_phrase(numbers)}"
    if cand.error:
        parts = [
            f'<div class="glabel">{html.escape(label)}</div>'
            f'<div class="err">{html.escape(cand.error)}</div>'
        ]
    else:
        parts = [render_grid(cand.grid, label)]
    caption = card.captions.get(witness, {}).get(cand.label)
    if caption is not None:
        parts.append(f'<div class="cap">{html.escape(caption)}</div>')
    return '<div class="gwrap">' + "".join(parts) + "</div>"

def render_run(run: Run, card: Card) -> str:
    parts = [render_grid(run.grid, f"input · {run.label}")]
    if run.error:
        parts.append(f'<div class="err">{html.escape(run.error)}</div>')
    parts.extend(_candidate_html(c, card, run.label) for c in run.candidates)
    return '<div class="grids">' + "".join(parts) + "</div>"

def witness_section(card: Card) -> list[str]:
    """The witness blocks, and for a card with dropped cases a note when no
    witness input separates a dropped case from the kept ones."""
    runs, fell_back = drawn_runs(card)
    check_captions(card, runs)
    check_option_cases(card, runs)
    note = (
        "<p>No candidate input separates the dropped case from the kept ones. "
        "The task's first train input follows.</p>"
    )
    blocks = [render_run(run, card) for run in runs]
    return [note] + blocks if fell_back else blocks


def render(card: Card) -> str:
    """The card as one page in `PAGE_FORM`, titled by the card's name."""
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
        body.extend(f"<li>{html.escape(o.text)}</li>" for o in card.options)
        body.append("</ol>")
    return _page(html.escape(card.name),
                 f"{CARD_OPEN}{''.join(body)}{CARD_CLOSE}")


CARD_OPEN = '<article class="card">'
CARD_CLOSE = "</article>"

PAGE_FORM = re.compile(
    r"<title>(?P<title>[^<]*)</title>\n<style>(?P<style>.*?)</style>\n"
    r"(?P<body>.*)\n",
    re.DOTALL,
)
"""A page: its escaped title, its style, then its body. A card's body is
one `CARD_OPEN` ... `CARD_CLOSE`, and a bundle's opens with its list of
cards."""


def _page(title: str, body: str) -> str:
    """A page in `PAGE_FORM` under `STYLE`, from its escaped title."""
    return f"<title>{title}</title>\n<style>{STYLE}</style>\n{body}\n"


def page_path(name: str) -> Path:
    """The file work/cards/<name>.html. A name that is not one file name is
    an error, since its file would stand outside work/cards/."""
    if Path(name).name != name or name in ("", ".", ".."):
        raise ValueError(f"{name!r}: a page's name is one file name")
    return CARDS_DIR / f"{name}.html"


def write(card: Card) -> Path:
    """Render `card` to work/cards/<name>.html and return that path."""
    path = page_path(card.name)
    return _write(path, render(card))


def _write(path: Path, text: str) -> Path:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _card_of(path: Path) -> tuple[str, str]:
    """The escaped title and the body of the card page at `path`. A page
    this renderer did not write in `PAGE_FORM`, a bundle among them, is an
    error that names the page."""
    try:
        text = path.read_text()
    except OSError as e:
        raise ValueError(f"{path}: {e.strerror}") from None
    match = PAGE_FORM.fullmatch(text)
    body = match["body"] if match else ""
    if not (body.startswith(CARD_OPEN) and body.endswith(CARD_CLOSE)):
        raise ValueError(f"{path}: not a card page this renderer writes")
    if match is None or match["style"] != STYLE:
        raise ValueError(f"{path}: a card page rendered under another style")
    return match["title"], body


def bundle(name: str, paths: Sequence[Path]) -> str:
    """The pages at `paths` as one page titled `name`: a list of links to
    the cards by `#card-<n>`, the one fragment form the Artifact tool's
    viewer passes on, then each card in the order of `paths`. A bundle
    takes two pages or more, since the tool publishes one card's page as
    it stands."""
    if len(paths) < 2:
        raise ValueError("a bundle takes two card pages or more: publish "
                         "one card's page as it stands")
    cards = [_card_of(p) for p in paths]
    links = "".join(
        f'<li><a href="#card-{n}">{title}</a></li>'
        for n, (title, _) in enumerate(cards, 1)
    )
    sections = "".join(
        f'<section id="card-{n}">{body}</section>'
        for n, (_, body) in enumerate(cards, 1)
    )
    return _page(html.escape(name),
                 f'<div class="bundle"><ol>{links}</ol>{sections}</div>')


def write_bundle(name: str, paths: Sequence[Path]) -> Path:
    """Bundle the pages at `paths` into work/cards/<name>.html and return
    that path. A name whose file is one of those pages is an error."""
    path = page_path(name)
    for p in paths:
        if p.resolve() == path.resolve():
            raise ValueError(f"{p}: the bundle {name!r} would overwrite it")
    return _write(path, bundle(name, paths))
