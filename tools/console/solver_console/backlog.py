"""The unfinalized solvers: every solver on disk the user has not ruled
on. The finalize lens lists them, and sorts the finalize passes in flight
by the same rows. It lists the ruled solvers too, so a ruling can be read
again."""

import subprocess
import time

from . import config, ledger, prompts, solvers, store, workers

# A solver is unfinalized from the moment it is written until a finalize pass
# takes it up; the pass runs, and the user's approval ends it — the draft tag
# leaves the file. A dismissal ends it too, as a ledger line. The finalize lens
# lists the passes in flight over the unfinalized solvers, and they run to
# hundreds, so a row is built from its files once and reused until one of them
# changes; what the ledger says of a task — its passes and its entries — is
# joined on every request, as is each need's reach across the rows.

# task id -> (the file state the row was built from, the row)
ROW_CACHE: dict[str, tuple[tuple, dict]] = {}


def backlog_row(item_id: str, proposals: str, ts_size: int | None,
                no_solver: bool = False) -> dict:
    """What a row holds from the task's files."""
    comps = solvers.comps_of(item_id)
    calls = solvers.task_callouts(item_id)
    return {"id": item_id, "title": solvers.title_of(item_id), "comps": comps,
            "comps_unproposed": solvers.unproposed(comps, proposals),
            "header": solvers.header_of(item_id), "needs": solvers.needs_of(item_id),
            "callouts": calls, "callout_n": len(calls),
            "callout_rank": solvers.callout_rank(calls),
            "callout_act": solvers.callout_act(calls),
            "ts_size": ts_size, "dl_size": solvers.dl_size(item_id),
            "reports": solvers.report_stages(item_id), "no_solver": no_solver}


def file_state(item_id: str) -> tuple:
    """The solver and report files as they stand, and the docs, which carry
    the row's pending citations: what a cached row is keyed on."""
    out = [solvers.docs_state()]
    try:
        st = solvers.solver_path(item_id).stat()
        out.append((st.st_mtime_ns, st.st_size))
    except OSError:
        out.append(None)
    d = config.REPORT_DIR / item_id
    if d.is_dir():
        for p in sorted(d.glob("*.md")):
            try:
                st = p.stat()
                out.append((p.name, st.st_mtime_ns, st.st_size))
            except OSError:
                pass
    return tuple(out)


def cached_row(item_id: str, proposals: str, prop_key: int, ts_size: int | None,
               no_solver: bool = False) -> dict:
    key = (file_state(item_id), prop_key, ts_size, no_solver)
    hit = ROW_CACHE.get(item_id)
    if hit is None or hit[0] != key:
        hit = (key, backlog_row(item_id, proposals, ts_size, no_solver))
        ROW_CACHE[item_id] = hit
    return hit[1]


def entries_by_task(rows: list[dict]) -> dict[str, set[str]]:
    """The entries each task's sessions added: the ledger lines carry them,
    and an item still in the console holds its own."""
    out = ledger.entries_of(rows)
    for it in store.STATE["items"]:
        out.setdefault(it["id"], set()).update(it.get("entries", []))
    return out


# HEAD the table was read at, and the table: task id -> when its solver was
# first committed.
AGES: dict = {"head": None, "at": {}}


def solver_ages() -> dict[str, int]:
    """When each solver was first committed, from git. A solver not yet
    committed has no age, and a solver directory outside the repo has
    none for any."""
    try:
        rel = config.SOLVERS.relative_to(config.ROOT)
    except ValueError:
        return {}
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.ROOT,
                              capture_output=True, text=True, timeout=10).stdout.strip()
        if not head or head == AGES["head"]:
            return AGES["at"]
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%x00%ct",
                              "--name-only", "--", str(rel)],
                             cwd=config.ROOT, capture_output=True, text=True,
                             timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return AGES["at"]
    table: dict[str, int] = {}
    ts = 0
    # newest first, so the last add seen for a path is its earliest
    for line in out.splitlines():
        if line.startswith("\0"):
            ts = int(line[1:] or 0)
        elif line.endswith(".dl"):
            table[line.rsplit("/", 1)[-1][:-3]] = ts
    AGES.update(head=head, at=table)
    return table


def backlog_scan(ages: dict[str, int] | None = None) -> list[dict]:
    """A row per unfinalized solver, each joined with what the ledger says of
    its task. `ages` stands in for the git read of when each solver was
    added, for a caller that took that read before it held the lock. Caller
    holds LOCK."""
    lines = ledger.ledger_rows()
    settled = ledger.ruled(lines)
    passes = ledger.passes_of(lines)
    entries = entries_by_task(lines)
    proposals = solvers.prop_text()
    prop_key = hash(proposals)
    ts = solvers.ts_sizes()
    rows = []
    for path in sorted(config.SOLVERS.glob("*.dl")):
        # a running souffle drops `.tmp*.dl` scratch files into the directory
        if path.name.startswith("."):
            continue
        item_id = path.stem
        # an approved solver carries no draft tag, and a dismissal is a
        # ledger line; either way the user has ruled and the row is gone
        if item_id in settled or not solvers.is_draft(item_id):
            continue
        rows.append(cached_row(item_id, proposals, prop_key, ts.get(item_id)))
    # A pass that wrote no solver leaves the glob nothing to find, so the task
    # needing a ruling most is the one the scan cannot reach. The reports carry
    # it: the stage landed, and its account of why stands in for the file.
    rows += [cached_row(it["id"], proposals, prop_key, ts.get(it["id"]), no_solver=True)
             for it in store.STATE["items"]
             if it.get("landed") and it["id"] not in settled
             and not solvers.solver_path(it["id"]).exists()]
    ages = solver_ages() if ages is None else ages
    out = []
    for row in rows:
        row = dict(row)
        row["entries"] = solvers.entry_names(sorted(entries.get(row["id"], ())))
        row["passes"] = passes.get(row["id"], [])
        row["added"] = ages.get(row["id"])
        out.append(row)
    return out


def finalize_ready(it: dict) -> bool:
    """The wave chain has landed everything before finalize, so the task ranks
    among the unfinalized solvers while the item still sits in the console — no
    approval or commit required."""
    nxt = store.next_stage(it, it["phase"])
    return (it["state"] in (store.NEEDS_REVIEW, store.APPROVED) and not store.active(it)
            and nxt is not None and nxt["name"] == "finalize"
            and bool(solvers.report_of(it, it["phase"])))


# The review order. A missing solver leads: it is not a reading of the task
# but the absence of one. Then the rows holding the kind in priority: the
# widest key first, one key's rows together, and among them the rows waiting
# on the fewest keys of the kind first; then the rest. The solver's
# rule-literal count breaks ties, the larger first, and the id the last.
def review_key(priority: str):
    def key(row: dict) -> tuple:
        reach = row["reach"].get(priority, 0)
        keys = row["keys"].get(priority)
        widest = min((k for k, n in keys if n == reach), default="") if keys else ""
        waits = len(keys) if keys is not None else reach
        return (0 if row["no_solver"] else 1,
                0 if reach else 1,
                -reach,
                widest,
                waits,
                -(row["dl_size"] if row["dl_size"] is not None else -1),
                row["id"])
    return key


# The key of a principle need: what the line names before the dash, a rule
# of principles.md or an open question.
def _heading(text: str) -> str:
    return text.split(" — ", 1)[0].strip()


def reach_of(rows: list[dict]) -> None:
    """Each row's keys per kind, and its reach. A principle line's key is the
    rule or open question it names; a proposal's key is its comp. A key's
    reach is the rows that share it, and the row's reach in the kind is its
    widest key's. A workaround, a sweep, or a cite has no shared key, so the
    row's lines are its reach. A row without the kind reaches 0."""
    headings: dict[str, int] = {}
    comps: dict[str, int] = {}
    for row in rows:
        for text in set(map(_heading, row["needs"]["principle"])):
            headings[text] = headings.get(text, 0) + 1
        for name in set(row["needs"]["proposal"]):
            comps[name] = comps.get(name, 0) + 1
    for row in rows:
        needs = row["needs"]
        # each key once, in the order its lines come
        pkeys = [[h, headings[h]] for h in dict.fromkeys(map(_heading, needs["principle"]))]
        ckeys = [[n, comps[n]] for n in dict.fromkeys(needs["proposal"])]
        row["keys"] = {"principle": pkeys, "proposal": ckeys}
        row["reach"] = {
            "principle": max((n for _, n in pkeys), default=0),
            "proposal": max((n for _, n in ckeys), default=0),
            "workaround": len(needs["workaround"]),
            "sweep": len(needs["sweep"]),
            "cite": len(needs["cite"]),
        }


def lens_view(ages: dict[str, int] | None = None) -> dict:
    """What the finalize lens lists, each list in review order under the
    priority: the unfinalized solvers, and the tasks with a finalize pass in
    flight, whose rows the lens sorts on once the pass's cache is cold.

    The rows are ordered in part by when each solver was added, which is a
    git read. A caller that must not hold LOCK through a subprocess takes
    that read itself and passes it in."""
    with store.LOCK:
        priority = ledger.priority()
        held = {it["id"] for it in store.STATE["items"]
                if it["state"] != store.COMMITTED and not finalize_ready(it)}
        finalizing = {it["id"] for it in store.STATE["items"] if it["phase"] == "finalize"}
        scan = backlog_scan(ages)
    reach_of(scan)
    key = review_key(priority)
    rows = sorted((row for row in scan if row["id"] not in held), key=key)
    passes = sorted((row for row in scan if row["id"] in finalizing), key=key)
    return {"items": rows, "finalizing": passes, "priority": priority}


def ruled_view(ages: dict[str, int] | None = None) -> list[dict]:
    """A row per solver the user has ruled on, the newest solver first. A
    ruling is either an approval, which the solver file carries as the draft
    tag it no longer has, or a dismissal, which is a ledger line. The rows
    are the lens rows, so a ruled solver reads as an unfinalized one does.

    The order comes from when each solver was added, which is a git read; a
    caller that must not hold LOCK through a subprocess takes that read
    itself and passes it in."""
    with store.LOCK:
        lines = ledger.ledger_rows()
        dismissed = ledger.ruled(lines)
        passes = ledger.passes_of(lines)
        entries = entries_by_task(lines)
        proposals = solvers.prop_text()
        prop_key = hash(proposals)
        ts = solvers.ts_sizes()
        rows = []
        for path in sorted(config.SOLVERS.glob("*.dl")):
            if path.name.startswith("."):
                continue
            item_id = path.stem
            if item_id in dismissed:
                ruling = "dismissed"
            elif solvers.is_draft(item_id):
                continue
            else:
                ruling = "approved"
            row = dict(cached_row(item_id, proposals, prop_key, ts.get(item_id)))
            row["ruling"] = ruling
            rows.append(row)
    ages = solver_ages() if ages is None else ages
    for row in rows:
        row["entries"] = solvers.entry_names(sorted(entries.get(row["id"], ())))
        row["passes"] = passes.get(row["id"], [])
        row["added"] = ages.get(row["id"])
    reach_of(rows)
    # a solver not committed yet is the newest there is, so it leads
    rows.sort(key=lambda row: (row["added"] is not None, -(row["added"] or 0), row["id"]))
    return rows


def backlog_view(ages: dict[str, int] | None = None) -> list[dict]:
    """The unfinalized solvers in review order, which the autopilot's
    finalize passes take too."""
    return lens_view(ages)["items"]


def act_dismiss(body: dict) -> dict:
    """Rule that a task needs no finalize pass. The ruling is a ledger line,
    which takes the task off the lens. Deleting that line by hand restores
    it."""
    item_id = str(body.get("id") or "").strip()
    if not item_id or not solvers.solver_path(item_id).exists():
        return {"error": f"no solver for {item_id}"}
    ledger.ledger_append({"task": item_id, "stage": "dismissed", "backend": None,
                          "model": None, "session": None, "ts": int(time.time()),
                          "source": "user"})
    store.bump()
    return {"ok": True}


def act_approve_solver(body: dict) -> dict:
    """Approve a solver from the lens: the tag comes off the file, which is
    where approval stands. An item the console still holds for that solver
    takes the ruling too, a turn in flight included, so nothing it does later
    withdraws it. The docs hold the solver's citations pending until here, so
    approval places them."""
    item_id = str(body.get("id") or "").strip()
    if not item_id or not solvers.solver_path(item_id).exists():
        return {"error": f"no solver for {item_id}"}
    # a landing rewrites the same file under LOCK
    with store.LOCK:
        it = store.find(item_id)
        if it is None or it["state"] in (store.APPROVED, store.COMMITTED):
            solvers.clear_draft(item_id)
        else:
            store.approve(it)
        solvers.place_citations(item_id)
    store.bump()
    return {"ok": True}


def start_finalize(item_id: str) -> dict:
    """Start a finalize pass: advance a wave item that is done up to finalize,
    or, for a solver the console no longer holds, a fresh item whose chain is
    that stage alone, seeded from the reports on disk. Either way the pass
    lands unattended, so its landing asks for the callouts. Caller holds
    LOCK."""
    it = store.find(item_id)
    if it is not None:
        if not finalize_ready(it):
            return {"error": "already in the console"}
        # The wave chain is done up to finalize: advance the item in place.
        # A chain that wrote no solver advances too; the pass writes one.
        it["updated"] = False
        it["auto_finalize"] = True
        workers.advance_stage(it)
        return {"ok": True, "id": item_id, "advanced": True}
    if not solvers.solver_path(item_id).exists():
        return {"error": f"no solver for {item_id}"}
    stage = dict(store.default_chain()[-1])
    pairs = prompts.persisted_reports(item_id, skip=stage["name"])
    it = {"id": item_id, "est": 0, "wave": store.STATE["wave"], "state": store.RUNNING,
          "chain": [stage], "auto_advance": False, "auto_finalize": True,
          "sessions": {stage["name"]: None}, "phase": stage["name"],
          "landed": [], "dirty": False, "updated": False, "rev": 0,
          "lastActive": {stage["name"]: None}, "title": solvers.title_of(item_id),
          "feed": [], "append": str(prompts.append_path()), "ver": 0,
          "reports": {}, "diffs": {}}
    store.STATE["items"].append(it)
    seeded = ", ".join(name for name, *_ in pairs)
    store.say(it, store.event("started · "
                              + (f"seeded from {seeded}" if seeded
                                 else "no earlier reports")))
    try:
        workers.launch(it, prompts.finalize_message(item_id, pairs), stage["name"])
    except (store.Reject, OSError) as exc:
        # nothing is in flight, so the item goes rather than sit unstarted
        store.STATE["items"].remove(it)
        return {"error": f"could not start the worker: {exc}"}
    return {"ok": True, "id": item_id, "seeded": [name for name, _ in pairs]}


def act_finalize(body: dict) -> dict:
    """Start a finalize pass on the user's ask."""
    item_id = str(body.get("id") or "").strip()
    if not item_id:
        return {"error": "no solver for "}
    with store.LOCK:
        store.defer_reload()
        res = start_finalize(item_id)
    if "error" not in res:
        store.bump()
    return res
