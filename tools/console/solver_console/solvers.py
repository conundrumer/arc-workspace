"""Reads of the solver files, the reports beside them, and the callouts
those reports carry."""

import hashlib
import json
import re
from pathlib import Path

from dl.annotations import merged_blocks
from dl.annotations import read as read_annotations
from dl.annotations import witness_blocks
from dl.corpus import literal_count
from dl.dlparse import ParseError, parse
from dl.witness import load_witnesses, witness_path

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
    for p in sorted(config.LIB_DIR.glob("*.dl")):
        paths[f"programs/lib/{p.name}"] = p
    for p in sorted(config.DOCS.glob("*.md")):
        paths[f"docs/wf-solver/{p.name}"] = p
    for p in sorted(config.ROLE_DIR.glob("*.md")):
        paths[f".claude/roles/{p.name}"] = p
    return paths


def watched_hashes(item_id: str) -> dict[str, str]:
    return {rel: file_hash(p) for rel, p in watched_paths(item_id).items()}


PROP_DIR = "docs/wf-solver/proposals"


# The console's approval tag, by its complement: a solver the user has not
# approved carries this line in its header block, and approval takes it out.
# The session writes it with the solver; a landing adds it where the session
# left it out.
DRAFT = "// @draft"


# The draft answer per solver path, keyed on the file state it was read from:
# path -> ((size, mtime_ns), the answer). The backlog asks for every solver on
# each request, and a file that has not changed gives the same answer.
DRAFT_CACHE: dict[Path, tuple[tuple[int, int], bool]] = {}


def is_draft(item_id: str) -> bool:
    """Whether the solver stands unapproved."""
    path = solver_path(item_id)
    try:
        st = path.stat()
    except OSError:
        DRAFT_CACHE.pop(path, None)
        return False
    key = (st.st_size, st.st_mtime_ns)
    hit = DRAFT_CACHE.get(path)
    if hit is not None and hit[0] == key:
        return hit[1]
    answer = read_annotations(solver_text(item_id)).is_draft()
    DRAFT_CACHE[path] = (key, answer)
    return answer


def write_solver(item_id: str, text: str) -> None:
    """Put text in the solver file, in one step. The write lands in a file
    beside it and takes its place by a rename, so a reader outside the
    console — a worker session, a souffle run, the ref-note hook — sees
    either the whole old text or the whole new one. The scratch name ends in
    `.swap`, which keeps it out of the `*.dl` solver glob; the dot prefix
    keeps it out of the listings that skip dotfiles."""
    p = solver_path(item_id)
    tmp = p.with_name(f".{p.name}.swap")
    try:
        tmp.write_text(text)
        tmp.replace(p)
    finally:
        tmp.unlink(missing_ok=True)


# The body annotation a session writes above a form that stands in for the
# principled one.
WORKAROUND = re.compile(r"^\s*//\s*@workaround:\s*(.*)$", re.M)
# The kinds of review need, in the order the lens offers them: `principle`
# and `sweep` are read from the file's lines, `workaround` from its body,
# `proposal` from its comps, and `cite` from the docs.
NEED_KINDS = ("principle", "proposal", "workaround", "sweep", "cite")


def header_end(lines: list[str]) -> int:
    """The count of lines in the leading comment block."""
    n = 0
    while n < len(lines) and lines[n].strip().startswith("//"):
        n += 1
    return n


def header_fields(text: str) -> list[tuple[str, str | None, str]]:
    """The header's fields as (word, kind, value), continuation lines joined
    into the value."""
    return [(f.word, f.kind, f.value)
            for f in read_annotations(text).fields]


def header_of(item_id: str) -> dict:
    """The `input:` and `output:` lines of the solver's header."""
    fields = {w: v for w, k, v in header_fields(solver_text(item_id)) if k is None}
    return {"input": fields.get("input", ""), "output": fields.get("output", "")}


def needs_of(item_id: str) -> dict[str, list[str]]:
    """What the solver holds for the user's review, by kind."""
    text = solver_text(item_id)
    out: dict[str, list[str]] = {k: [] for k in NEED_KINDS}
    for word, kind, value in header_fields(text):
        if word == "review" and kind:
            out.setdefault(kind, []).append(value)
    out["proposal"] = comps_of(item_id)
    out["workaround"] = [m.strip() for m in WORKAROUND.findall(text)]
    out["cite"] = pending_cites().get(item_id, [])
    return out


def _review_span(lines: list[str]) -> list[int]:
    """The indices of the header's review lines, continuations included."""
    fields = read_annotations("".join(lines)).fields
    return [n for f in fields if f.word == "review"
            for n in range(f.line - 1, f.end)]


def _cleared() -> dict[str, list[str]]:
    try:
        raw = json.loads(config.REVIEWS_FILE.read_text())
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_cleared(table: dict[str, list[str]]) -> None:
    config.REVIEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.REVIEWS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(table, indent=1))
    tmp.replace(config.REVIEWS_FILE)


def _retag(item_id: str, mark: bool) -> bool:
    """Put the draft line in the header block, or take it out. The line goes
    under the task-id line. The review lines leave with the draft line, held
    aside so they return with it. True when the file changed."""
    p = solver_path(item_id)
    try:
        lines = p.read_text().splitlines(True)
    except OSError:
        return False
    at = [f.line - 1 for f in read_annotations("".join(lines)).fields
          if f.word == "draft"]
    if mark == bool(at):
        return False
    held = _cleared()
    if mark:
        first = 1 if lines and lines[0].startswith("//") else 0
        # the line the tag goes under may be the last one, and a last line
        # carries no newline of its own
        if first and not lines[first - 1].endswith("\n"):
            lines[first - 1] += "\n"
        lines.insert(first, DRAFT + "\n")
        if back := held.pop(item_id, None):
            end = header_end(lines)
            if end and not lines[end - 1].endswith("\n"):
                lines[end - 1] += "\n"
            lines[end:end] = [line + "\n" for line in back]
            _save_cleared(held)
    else:
        gone = _review_span(lines)
        if gone:
            held[item_id] = [lines[n].rstrip("\n") for n in gone]
            _save_cleared(held)
        for n in reversed(sorted(set(at) | set(gone))):
            del lines[n]
    write_solver(item_id, "".join(lines))
    return True


def mark_draft(item_id: str) -> bool:
    """Tag a solver the user has not approved."""
    return _retag(item_id, True)


def clear_draft(item_id: str) -> bool:
    """Take the tag off: the user has approved this solver."""
    return _retag(item_id, False)


def append_review(item_id: str, line: str) -> bool:
    """Put a review line at the end of the header block, where the header
    grammar takes it: `review` is the last field, and the draft line stays
    where it stands. True when the file changed; False when the solver has
    no header, or when the same line already stands in it."""
    p = solver_path(item_id)
    try:
        lines = p.read_text().splitlines(True)
    except OSError:
        return False
    end = header_end(lines)
    if not end:
        return False
    text = line.rstrip("\n")
    if any(held.strip() == text for held in lines[:end]):
        return False
    # a last line carries no newline of its own
    if not lines[end - 1].endswith("\n"):
        lines[end - 1] += "\n"
    lines.insert(end, text + "\n")
    write_solver(item_id, "".join(lines))
    return True


# A citation a doc holds for a solver the user has not approved yet: the line
# names the task and carries the text the doc takes once approval comes.
PENDING_CITE = "^([ \\t]*)<!-- draft: {task} \u2014 (.*) -->$"

# The citation as placed.
PLACED_CITE = "^([ \\t]*)- {task} <!-- (.*) -->$"

# A pending citation read rather than placed: the task it names and its gloss.
ANY_PENDING = re.compile(r"^[ \t]*<!-- draft: (\w+) \u2014 (.*) -->$")
# The heading a marker stands under.
DOC_HEADING = re.compile(r"^#+\s+(.*?)\s*$")

# The pending citations as last read, keyed on the docs' state.
CITE_CACHE: tuple[tuple, dict[str, list[str]]] | None = None


def docs_state() -> tuple:
    """The docs under docs/wf-solver/ as they stand."""
    out = []
    for p in sorted(config.DOCS.glob("*.md")):
        try:
            st = p.stat()
            out.append((p.name, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    return tuple(out)


def pending_cites() -> dict[str, list[str]]:
    """Every pending citation, by task: the doc it waits in, the heading it
    stands under, and the gloss it carries. The marker in the doc is the whole
    record of a citation, so a solver's cite need is read from here and the
    scan is cached on the docs' state."""
    global CITE_CACHE
    state = docs_state()
    if CITE_CACHE is not None and CITE_CACHE[0] == state:
        return CITE_CACHE[1]
    out: dict[str, list[str]] = {}
    for path in sorted(config.DOCS.glob("*.md")):
        head = ""
        for line in path.read_text().splitlines():
            if m := DOC_HEADING.match(line):
                head = m.group(1)
            elif m := ANY_PENDING.match(line):
                out.setdefault(m.group(1), []).append(
                    f"{path.name} {head} \u2014 {m.group(2)}")
    CITE_CACHE = (state, out)
    return out


def place_citations(item_id: str) -> list[Path]:
    """Place the solver's pending citations: in every doc under
    docs/wf-solver/, a line left pending for this task becomes the citation it
    carries. Returns the files changed."""
    pat = re.compile(PENDING_CITE.format(task=re.escape(item_id)), re.M)
    changed: list[Path] = []
    for path in sorted(config.DOCS.glob("*.md")):
        text = path.read_text()
        out = pat.sub(rf"\1- {item_id} <!-- \2 -->", text)
        if out != text:
            path.write_text(out)
            changed.append(path)
    return changed


def withdraw_citations(item_id: str) -> list[Path]:
    """Return the solver's citations to pending: in every doc under
    docs/wf-solver/, a citation of this task becomes the pending line approval
    placed it from. Returns the files changed."""
    pat = re.compile(PLACED_CITE.format(task=re.escape(item_id)), re.M)
    changed: list[Path] = []
    for path in sorted(config.DOCS.glob("*.md")):
        text = path.read_text()
        out = pat.sub(rf"\1<!-- draft: {item_id} — \2 -->", text)
        if out != text:
            path.write_text(out)
            changed.append(path)
    return changed


def witness_view(item_id: str) -> dict | None:
    """The task's witness file as the task strip shows it: its entries as
    the file writes them, each carrying the fields of the solver's
    `@witness` block of the same id. None when the task has no witness
    file, and the error a file off its shape raises in place of the
    entries.

    An entry the solver names in no block keeps the file's fields alone. A
    block that names no entry follows the entries, as an entry that holds
    the block's fields and no grid."""
    path = witness_path(item_id)
    if not path.exists():
        return None
    try:
        load_witnesses(item_id)
        entries = json.loads(path.read_text())["witnesses"]
    except (ValueError, KeyError, TypeError) as exc:
        return {"error": str(exc)}
    blocks = {a.id: a
              for a in merged_blocks(witness_blocks(solver_text(item_id)))}
    for entry in entries:
        block = blocks.pop(entry.get("id"), None)
        if block is not None:
            entry.update(_block_fields(block))
    entries += [{"id": a.id, **_block_fields(a)} for a in blocks.values()]
    return {"entries": entries}


def _block_fields(block) -> dict:
    """The fields of one `@witness` block, as an entry's view carries
    them."""
    return {
        "plausibility": block.plausibility,
        "verdict": block.verdict,
        "approximates": block.approximates or None,
        "relaxed": list(block.relaxed),
        "reassigned": list(block.reassigned),
    }


def prop_path(rel: str) -> Path:
    """The entry file a repo-relative path names."""
    return config.DOCS / "proposals" / Path(rel).name


def prop_files() -> dict[str, str]:
    """Every entry under docs/wf-solver/proposals/, by repo-relative path."""
    d = config.DOCS / "proposals"
    if not d.is_dir():
        return {}
    return {f"{PROP_DIR}/{p.name}": p.read_text() for p in sorted(d.glob("*.md"))}


def entry_names(rels) -> list[str]:
    """The operation names the entry paths carry, for a badge."""
    return sorted({Path(rel).stem for rel in rels})


def prop_text() -> str:
    """The entries as one text, for a word match."""
    return "\n".join(prop_files().values())


def report_path(item_id: str, stage: str) -> Path:
    return config.REPORT_DIR / item_id / f"{stage}.md"


def save_report(item_id: str, stage: str, text: str) -> None:
    """File a stage's report, in one step: the write lands beside the report
    and takes its place by a rename, so a reader that is not under LOCK — the
    retro view, a session reading the file — sees a whole report."""
    p = report_path(item_id, stage)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.swap")
    try:
        tmp.write_text(text)
        tmp.replace(p)
    finally:
        tmp.unlink(missing_ok=True)


def report_of(it: dict, stage: str) -> str:
    """A stage's handoff report, from state or from the file that outlives it."""
    text = ((it.get("reports") or {}).get(stage) or "").strip()
    if text:
        return text
    p = report_path(it["id"], stage)
    return p.read_text().strip() if p.exists() else ""


# A worker's acts are tagged blocks in its turn text: the handoff report
# between `<handoff>` and `</handoff>`, the callouts between `<callouts>` and
# `</callouts>`. Only a closed block counts, and the last one of a name is
# the one read, so a turn cut off mid-report lands nothing.
HANDOFF_TAG = re.compile(r"<handoff>\s*(.*?)\s*</handoff>", re.S | re.I)
CALLOUTS_TAG = re.compile(r"<callouts>\s*(.*?)\s*</callouts>", re.S | re.I)
TAGS = re.compile(r"[ \t]*</?(?:handoff|callouts)>[ \t]*\n?", re.I)


def tagged(text: str, tag: re.Pattern) -> str | None:
    """The inner text of the last closed block, or None when there is none."""
    last = None
    for last in tag.finditer(text or ""):
        pass
    return last.group(1) if last else None


def untagged(text: str) -> str:
    """The text with the block tags removed, for the feed."""
    return TAGS.sub("", text or "")


CALLOUT_HEAD = re.compile(r"^\s{0,3}#{1,6}\s*callouts\b.*$", re.I | re.M)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s", re.M)
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
# a lone emphasized word: `*tink*`, `_pop_`, `**glass**` — a message sign-off
SIGNOFF = re.compile(r"^(\*{1,2}|_{1,2})\w+\1$")


def join_callouts(report: str, section: str) -> str:
    """The report with `section` as its one callouts section: a section it
    already holds, from its heading to the end, gives way."""
    head = CALLOUT_HEAD.search(report or "")
    body = (report[:head.start()] if head else (report or "")).rstrip()
    return body + "\n\n" + section.strip()


def collapse_callouts(text: str) -> str:
    """A report that holds more than one callouts section keeps the last."""
    heads = list(CALLOUT_HEAD.finditer(text or ""))
    if len(heads) < 2:
        return text
    return join_callouts(text, text[heads[-1].start():])


def callout_body(text: str) -> str | None:
    """The callouts a text carries: its `<callouts>` block, or else its
    `## Callouts` section, which is how the reports on disk hold them. None
    when it carries neither."""
    block = tagged(text, CALLOUTS_TAG)
    if block is not None:
        head = CALLOUT_HEAD.search(block)
        return block[head.end():] if head else block
    head = None
    for head in CALLOUT_HEAD.finditer(text or ""):
        pass  # a report that wrote the section twice is read on its last one
    if head is None:
        return None
    body = text[head.end():]
    nxt = HEADING.search(body)
    return body[:nxt.start()] if nxt else body


def parse_callouts(text: str) -> list[str]:
    """The entries of a text's callouts.

    Written by hand at the end of a long turn, so the shape is read loosely:
    list items when the section uses them and plain lines when it does not,
    and `none` for a stage with nothing to raise. An entry that is only an
    emphasized word is a sign-off, not a callout."""
    body = callout_body(text)
    if body is None:
        return []
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


# What a rank is worth to a sort over callouts. A P3 is a note the worker left, not
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


def latest_report(item_id: str) -> Path | None:
    """The task's most recently written persisted report."""
    d = config.REPORT_DIR / item_id
    try:
        files = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    return files[-1] if files else None


def task_callouts(item_id: str) -> list[str]:
    """Callouts from the task's most recent persisted report."""
    p = latest_report(item_id)
    try:
        return parse_callouts(p.read_text()) if p else []
    except OSError:
        return []


# The components the style doc gives every solver. Any other one is a
# proposal comp, legal only while its proposal entry is open.
STOCK_COMPS = ("Params", "Determine", "Parse")


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
    for f in read_annotations(p.read_text()).fields:
        if f.word in ("keywords", "representative"):
            return f"{f.word}: {f.value}"
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


_DL_SIZE: dict[str, tuple[float, int | None]] = {}


def dl_size(item_id: str) -> int | None:
    """Solver complexity by task id: `dl.corpus.literal_count` of the
    parsed file, cached per mtime. None for a missing file or one outside
    the parser's dialect."""
    p = solver_path(item_id)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None
    hit = _DL_SIZE.get(item_id)
    if hit is None or hit[0] != mtime:
        try:
            hit = (mtime, literal_count(parse(p.read_text())))
        except (OSError, ParseError):
            hit = (mtime, None)
        _DL_SIZE[item_id] = hit
    return hit[1]
