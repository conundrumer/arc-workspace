"""Reads of the solver files, the reports beside them, and the callouts
those reports carry."""

import hashlib
import re
from collections.abc import Iterator
from pathlib import Path

from dl.dlparse import Bool, Comp, ParseError, Program, Rigid, Rule, body_literals, parse

from . import config


def solver_path(item_id: str) -> Path:
    return config.SOLVERS / f"{item_id}.dl"


def solver_hash(item_id: str) -> str:
    p = solver_path(item_id)
    return hashlib.sha1(p.read_bytes()).hexdigest() if p.exists() else ""


def solver_text(item_id: str) -> str:
    p = solver_path(item_id)
    return p.read_text() if p.exists() else ""


def file_hash(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest() if p.exists() else ""


def watched_paths(item_id: str) -> dict[str, Path]:
    """The files a pass shares with every other pass, by repo-relative name.
    Hashed at launch and checked at landing, so a write that bypasses the
    edit tools (a Bash heredoc, a script) still surfaces."""
    paths = {"programs/lib.dl": config.LIB,
             f"data/tasks/{item_id}.json": config.TASKS / f"{item_id}.json"}
    for p in sorted(config.DOCS.glob("*.md")):
        paths[f"docs/wf-solver/{p.name}"] = p
    for p in sorted(config.AGENT_DIR.glob("*.md")):
        paths[f".claude/agents/{p.name}"] = p
    return paths


def watched_hashes(item_id: str) -> dict[str, str]:
    return {rel: file_hash(p) for rel, p in watched_paths(item_id).items()}


PROP_DIR = "docs/wf-solver/proposals"


def prop_path(rel: str) -> Path:
    """The entry file a repo-relative path names."""
    return config.DOCS / "proposals" / Path(rel).name


def prop_files() -> dict[str, str]:
    """Every entry under docs/wf-solver/proposals/, by repo-relative path."""
    d = config.DOCS / "proposals"
    if not d.is_dir():
        return {}
    return {f"{PROP_DIR}/{p.name}": p.read_text() for p in sorted(d.glob("*.md"))}


def prop_text() -> str:
    """The entries as one text, for a word match."""
    return "\n".join(prop_files().values())


def report_path(item_id: str, stage: str) -> Path:
    return config.REPORT_DIR / item_id / f"{stage}.md"


def save_report(item_id: str, stage: str, text: str) -> None:
    p = report_path(item_id, stage)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def report_of(it: dict, stage: str) -> str:
    """A stage's handoff report, from state or from the file that outlives it."""
    text = ((it.get("reports") or {}).get(stage) or "").strip()
    if text:
        return text
    p = report_path(it["id"], stage)
    return p.read_text().strip() if p.exists() else ""


CALLOUT_HEAD = re.compile(r"^\s{0,3}#{1,6}\s*callouts\b.*$", re.I | re.M)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s", re.M)
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
# a lone emphasized word: `*tink*`, `_pop_`, `**glass**` — a message sign-off
SIGNOFF = re.compile(r"^(\*{1,2}|_{1,2})\w+\1$")


def parse_callouts(text: str) -> list[str]:
    """The entries of a report's `## Callouts` section.

    Written by hand at the end of a long turn, so the shape is read loosely:
    any heading level, list items when the section uses them and plain lines
    when it does not, and `none` for a stage with nothing to raise. An entry
    that is only an emphasized word is a sign-off, not a callout."""
    head = None
    for head in CALLOUT_HEAD.finditer(text or ""):
        pass  # a report that wrote the section twice is read on its last one
    if head is None:
        return []
    body = text[head.end():]
    nxt = HEADING.search(body)
    if nxt:
        body = body[:nxt.start()]
    bullets, lines = [], []
    for line in body.splitlines():
        if not line.strip():
            continue
        item = BULLET.match(line)
        if item:
            bullets.append(item.group(1).strip())
        else:
            lines.append(line.strip())
    return [e for e in (bullets or lines)
            if e.strip(" .*_`").lower() != "none" and not SIGNOFF.match(e)]


# tolerates emphasis around the mark: `[P1]`, `**[P1]** …`, `**[P1] …`
RANK_MARK = re.compile(r"^[*_`]{0,2}\[?[Pp]([0-3])\]?[*_`]{0,2}\s")


def callout_rank(entries: list[str]) -> int | None:
    """The most urgent P-rank among the entries, when any carries one."""
    ranks = [int(m.group(1)) for e in entries if (m := RANK_MARK.match(e))]
    return min(ranks) if ranks else None


# What a rank is worth to the triage sort. A P3 is a note the worker left, not
# a ruling it wants, so it lands in the same band as a report that raised
# nothing, where comps and the acting callouts order it.
CALLOUT_WEIGHT = {0: 0, 1: 1, 2: 2, 3: 9}
NO_CALLOUT = 9


def callout_weight(rank: int | None) -> int:
    return CALLOUT_WEIGHT.get(rank, NO_CALLOUT)


def callout_act(entries: list[str]) -> int:
    """How many entries ask the user for something. A P3 does not."""
    return sum(1 for e in entries
               if not ((m := RANK_MARK.match(e)) and m.group(1) == "3"))


def report_stages(item_id: str) -> list[str]:
    """Stages the task has a persisted report for."""
    d = config.REPORT_DIR / item_id
    return sorted(p.stem for p in d.glob("*.md")) if d.is_dir() else []


def task_callouts(item_id: str) -> list[str]:
    """Callouts from the task's most recent persisted report."""
    d = config.REPORT_DIR / item_id
    try:
        files = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime)
        return parse_callouts(files[-1].read_text()) if files else []
    except OSError:
        return []


# The components the style doc gives every solver. Any other one is a
# proposal comp, legal only while its proposal entry is open.
STOCK_COMPS = ("Consts", "Fit", "Parse")


def comps_of(item_id: str) -> list[str]:
    """Proposal comp names the solver declares."""
    return [name for name in
            re.findall(r"^\.comp\s+([A-Za-z_]\w*)", solver_text(item_id), re.M)
            if name not in STOCK_COMPS]


def unproposed(names: list[str], proposals: str) -> list[str]:
    return [n for n in names
            if not re.search(rf"\b{re.escape(n)}\b", proposals)]


def title_of(item_id: str) -> str:
    p = solver_path(item_id)
    if not p.exists():
        return ""
    for line in p.read_text().splitlines()[:4]:
        m = re.match(r"//\s*((concept|family):.*)", line)
        if m:
            return m.group(1)
    return ""


def ts_sizes() -> dict[str, int]:
    """Reference TS solver complexity by task id: gzipped bytes of the
    minified source, read from the cache scripts/queue.ts maintains. The
    cache refreshes when that script runs, so an unlisted or stale id
    waits for the next run."""
    try:
        text = config.QUEUE_CACHE.read_text()
    except OSError:
        return {}
    out: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2].isdigit():
            out[parts[0]] = int(parts[2])
    return out


def _rules(items: list) -> Iterator[Rule]:
    for it in items:
        if isinstance(it, Rule):
            yield it
        elif isinstance(it, (Comp, Rigid)):
            yield from _rules(it.items)


def _literal_count(program: Program) -> int:
    """One per rule head and one per body atom, negation, or comparison,
    disjunction branches expanded and aggregate bodies included. Facts count
    their head. Declarations, types, inits, and the terms inside a literal
    add nothing: the measure follows the program, not the code around it."""
    return sum(1 + sum(1 for lit in body_literals(r) if not isinstance(lit, Bool))
               for r in _rules(program.items))


_DL_SIZE: dict[str, tuple[float, int | None]] = {}


def dl_size(item_id: str) -> int | None:
    """Solver complexity: the literal count of the parsed rules. None for
    a missing file or one outside the parser's dialect."""
    p = solver_path(item_id)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None
    hit = _DL_SIZE.get(item_id)
    if hit is None or hit[0] != mtime:
        try:
            hit = (mtime, _literal_count(parse(p.read_text())))
        except (OSError, ParseError):
            hit = (mtime, None)
        _DL_SIZE[item_id] = hit
    return hit[1]
