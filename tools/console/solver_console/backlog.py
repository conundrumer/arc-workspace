"""The unfinalized solvers: every solver on disk the user has not ruled
on. The finalize lens lists them, and sorts the finalize passes in flight
by the same rows."""

import subprocess
import time

from . import config, ledger, prompts, solvers, store, workers

# A solver is unfinalized from the moment it is written until a finalize pass
# takes it up; the pass runs, and the user's approval ends it. A dismissal ends
# it too. The finalize lens lists the passes in flight over the unfinalized
# solvers, and they run to hundreds, so a row is built from its files once and
# reused until one of them changes; what the ledger says of a task — its
# passes and its entries — is joined on every request, as is the flag table.

# task id -> (the file state the row was built from, the row)
ROW_CACHE: dict[str, tuple[tuple, dict]] = {}


def backlog_row(item_id: str, proposals: str, ts_size: int | None,
                no_solver: bool = False) -> dict:
    """What a row holds from the task's files."""
    comps = solvers.comps_of(item_id)
    calls = solvers.task_callouts(item_id)
    return {"id": item_id, "title": solvers.title_of(item_id), "comps": comps,
            "comps_unproposed": solvers.unproposed(comps, proposals),
            "callouts": calls, "callout_n": len(calls),
            "callout_rank": solvers.callout_rank(calls),
            "callout_act": solvers.callout_act(calls),
            "ts_size": ts_size, "dl_size": solvers.dl_size(item_id),
            "reports": solvers.report_stages(item_id), "no_solver": no_solver}


def file_state(item_id: str) -> tuple:
    """The solver and report files as they stand: what a cached row is keyed
    on."""
    out = []
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


def backlog_scan() -> list[dict]:
    """A row per unfinalized solver, each joined with what the ledger says of
    its task. Caller holds LOCK."""
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
        if item_id in settled:
            continue
        rows.append(cached_row(item_id, proposals, prop_key, ts.get(item_id)))
    # A pass that wrote no solver leaves the glob nothing to find, so the task
    # needing a ruling most is the one the scan cannot reach. The reports carry
    # it: the stage landed, and its account of why stands in for the file.
    rows += [cached_row(it["id"], proposals, prop_key, ts.get(it["id"]), no_solver=True)
             for it in store.STATE["items"]
             if it.get("landed") and it["id"] not in settled
             and not solvers.solver_path(it["id"]).exists()]
    ages = solver_ages()
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


# The triage order. A missing solver leads: it outranks a flag because it is
# not a reading of the task but the absence of one. A P0 — broken tooling —
# follows it, ahead of the flags, since the breakage may hold up other passes
# too. A task whose sessions added an entry comes next: the entry waits on a
# judgment, and the pass that made it is the one to read with it.
# -callout_n runs late, so a report carrying only P3s still edges out one
# that raised nothing once everything ahead of it ties. The oldest commit
# breaks the last tie, so a task does not wait behind newer ids; a solver
# not committed yet is the newest of all.
def triage_key(row: dict) -> tuple:
    return (0 if row["no_solver"] else 1,
            0 if row["callout_rank"] == 0 else 1,
            0 if row["entries"] else 1,
            row["flag"] or 9,
            solvers.callout_weight(row["callout_rank"]),
            0 if row["comps"] else 1,
            -row["callout_act"], -row["callout_n"],
            row["added"] if row["added"] is not None else float("inf"),
            row["id"])


def lens_view() -> dict:
    """What the finalize lens lists, each list in triage order: the
    unfinalized solvers, and the tasks with a finalize pass in flight, whose
    rows the lens sorts on once the pass's cache is cold."""
    with store.LOCK:
        table = ledger.flags()
        held = {it["id"] for it in store.STATE["items"]
                if it["state"] != store.COMMITTED and not finalize_ready(it)}
        finalizing = {it["id"] for it in store.STATE["items"] if it["phase"] == "finalize"}
        scan = backlog_scan()
        for row in scan:
            row["flag"] = (table.get(row["id"]) or {}).get("level", 0)
    rows = sorted((row for row in scan if row["id"] not in held), key=triage_key)
    passes = sorted((row for row in scan if row["id"] in finalizing), key=triage_key)
    return {"items": rows, "finalizing": passes}


def backlog_view() -> list[dict]:
    """The unfinalized solvers in triage order."""
    return lens_view()["items"]


def rule(body: dict, stage: str) -> dict:
    """Record the user's ruling on a solver as a ledger line, which takes it
    off the lens. Deleting that line by hand restores it."""
    item_id = str(body.get("id") or "").strip()
    if not item_id or not solvers.solver_path(item_id).exists():
        return {"error": f"no solver for {item_id}"}
    ledger.ledger_append({"task": item_id, "stage": stage, "backend": None,
                          "model": None, "session": None, "ts": int(time.time()),
                          "source": "user"})
    store.bump()
    return {"ok": True}


def act_dismiss(body: dict) -> dict:
    """Rule that a task needs no finalize pass."""
    return rule(body, "dismissed")


def act_approve_solver(body: dict) -> dict:
    """Approve a solver from the lens, one no item holds."""
    return rule(body, "approved")


def act_finalize(body: dict) -> dict:
    """Start a finalize pass: advance a wave item that is done up to finalize,
    or, for a solver the console no longer holds, a fresh item whose chain is
    that stage alone, seeded from the reports on disk."""
    item_id = str(body.get("id") or "").strip()
    with store.LOCK:
        store.defer_reload()
        if not item_id or not solvers.solver_path(item_id).exists():
            return {"error": f"no solver for {item_id}"}
        it = store.find(item_id)
        if it is not None:
            if not finalize_ready(it):
                return {"error": "already in the console"}
            # the wave chain is done up to finalize: advance the item in place
            it["updated"] = False
            workers.advance_stage(it)
            seeded_names = None
        else:
            stage = dict(store.default_chain()[-1])
            pairs = prompts.persisted_reports(item_id, skip=stage["name"])
            it = {"id": item_id, "est": 0, "wave": store.STATE["wave"], "state": store.RUNNING,
                  "chain": [stage], "auto_advance": False,
                  "sessions": {stage["name"]: None}, "phase": stage["name"],
                  "landed": [], "dirty": False, "updated": False, "rev": 0,
                  "lastActive": {stage["name"]: None}, "title": solvers.title_of(item_id),
                  "feed": [], "append": str(prompts.append_path()), "ver": 0,
                  "reports": {}}
            store.STATE["items"].append(it)
            seeded = ", ".join(name for name, _ in pairs)
            store.say(it, store.event("started · "
                                      + (f"seeded from {seeded}" if seeded
                                         else "no earlier reports")))
            try:
                workers.launch(it, prompts.finalize_message(item_id, pairs), stage["name"])
            except (store.Reject, OSError) as exc:
                # nothing is in flight, so the item goes rather than sit unstarted
                store.STATE["items"].remove(it)
                return {"error": f"could not start the worker: {exc}"}
            seeded_names = [name for name, _ in pairs]
    store.bump()
    if seeded_names is None:
        return {"ok": True, "id": item_id, "advanced": True}
    return {"ok": True, "id": item_id, "seeded": seeded_names}
