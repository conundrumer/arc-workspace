"""The append-only record of stage landings and rulings, and the lens's
priority kept beside it."""
import json
import sys

from . import config, solvers, store

# One line per stage landing, append-only, and one per `dismissed` ruling,
# which the user makes when a solver needs no pass. Other writers add lines of
# the same shape — a backfill pass records the passes made before the ledger
# existed, under stage `legacy` — so readers take the fields they know and
# skip the rest.
#
# Approval is not here: it stands in the solver file, as the draft tag the
# console takes out. The `approved` rows earlier rounds wrote are read as
# rulings still, so they never count as landings.

# The stage names a ruling writes, which are not landings: `dismissed`, and
# `approved` from the rounds that recorded approval here.
RULINGS = ("approved", "dismissed")
STAGE_ORDER = {"legacy": 0, "create": 1, "refine": 2, "finalize": 3}


def ledger_append(row: dict) -> None:
    try:
        config.LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with config.LEDGER.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError as exc:
        print(f"ledger append failed: {exc}", file=sys.stderr)


def ledger_rows() -> list[dict]:
    rows = []
    try:
        text = config.LEDGER.read_text(errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("task"):
            rows.append(row)
    return rows


def ruled(rows: list[dict]) -> set[str]:
    """Tasks the user has ruled off the lens, by a dismissal. Approval is the
    solver file's own, so it is not read here."""
    return {row["task"] for row in rows if row.get("stage") == "dismissed"}


def model_word(row: dict) -> str:
    """The model a landing ran on, as the console names it: opus, fable,
    codex."""
    if row.get("backend") == "codex":
        return "codex"
    m = str(row.get("model") or "")
    return m.removeprefix("claude-").split("-")[0] or "?"


def passes_of(rows: list[dict]) -> dict[str, list[dict]]:
    """The passes each task has had: one per stage, with the model of its
    latest landing, in stage order."""
    latest: dict[str, dict[str, tuple[int, str]]] = {}
    for row in rows:
        stage = row.get("stage")
        if not stage or stage in RULINGS:
            continue
        ts = int(row.get("ts") or 0)
        by = latest.setdefault(row["task"], {})
        if stage not in by or ts >= by[stage][0]:
            by[stage] = (ts, model_word(row))
    return {task: [{"stage": stage, "model": word}
                   for stage, (_, word) in sorted(
                       by.items(), key=lambda kv: (STAGE_ORDER.get(kv[0], 9), kv[1][0]))]
            for task, by in latest.items()}


def entries_of(rows: list[dict]) -> dict[str, set[str]]:
    """The entries each task's sessions added, as the ledger lines carry
    them."""
    out: dict[str, set[str]] = {}
    for row in rows:
        if row.get("entries"):
            out.setdefault(row["task"], set()).update(row["entries"])
    return out


def seed_entries() -> None:
    """An item from before the console kept entries takes its list from the
    ledger, once; from then on its landings keep it."""
    table = None
    for it in store.STATE["items"]:
        if "entries" in it:
            continue
        if table is None:
            table = entries_of(ledger_rows())
        it["entries"] = sorted(table.get(it["id"], ()))


# ---------- priority ----------
#
# The kind of review need the lens puts first. The lens sets it, and the
# admitter reads the same order.

PRIORITY: str | None = None


def priority() -> str:
    global PRIORITY
    if PRIORITY is None:
        try:
            raw = json.loads(config.PRIORITY_FILE.read_text())
        except (OSError, ValueError):
            raw = {}
        kind = raw.get("kind") if isinstance(raw, dict) else None
        PRIORITY = kind if kind in solvers.NEED_KINDS else solvers.NEED_KINDS[0]
    return PRIORITY


def act_priority(body: dict) -> dict:
    global PRIORITY
    kind = str(body.get("kind") or "").strip()
    if kind not in solvers.NEED_KINDS:
        return {"error": "kind must be one of " + ", ".join(solvers.NEED_KINDS)}
    with store.LOCK:
        PRIORITY = kind
        config.PRIORITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = config.PRIORITY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"kind": kind}))
        tmp.replace(config.PRIORITY_FILE)
    store.bump()
    return {"ok": True, "kind": kind}


# ---------- retro ----------
#
# When the callouts were last read across tasks. A retro takes the tasks
# whose latest report was written after this mark, with the callouts it
# carries. A callout turn rewrites the report, so a task comes back into the
# window when it has new callouts, and a turn that files nothing, such as a
# conversation with a finalize session, brings it back with none.

def retro_mark() -> int:
    try:
        raw = json.loads(config.RETRO_FILE.read_text())
    except (OSError, ValueError):
        return 0
    return int(raw.get("ts") or 0) if isinstance(raw, dict) else 0


def mark_retro() -> dict:
    ts = int(store.now())
    with store.LOCK:
        config.RETRO_FILE.parent.mkdir(parents=True, exist_ok=True)
        # a reader mid-write would read a mark of 0, which widens the retro
        # window to every task there is
        tmp = config.RETRO_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"ts": ts}))
        tmp.replace(config.RETRO_FILE)
    return {"ok": True, "ts": ts}


def retro_view() -> dict:
    mark = retro_mark()
    items = []
    try:
        dirs = sorted(d for d in config.REPORT_DIR.iterdir() if d.is_dir())
    except OSError:
        dirs = []
    for d in dirs:
        report = solvers.latest_report(d.name)
        if report is None:
            continue
        try:
            ts = int(report.stat().st_mtime)
            callouts = solvers.parse_callouts(report.read_text())
        except OSError:
            continue
        # a report filed before its callout turn lands carries none yet, and
        # comes back once the turn rewrites it
        if ts > mark and callouts:
            items.append({"id": d.name, "title": solvers.title_of(d.name),
                          "ts": ts, "callouts": callouts})
    return {"retro_mark": mark, "items": items}
