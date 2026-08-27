"""The finalize backlog: the solvers no fable pass has been over yet."""

import time

from . import config, ledger, prompts, solvers, store, workers

# What the finalize lens lists under the items in flight: every solver on disk
# that no fable session has passed over yet. The scan reads every solver file
# and the whole ledger, so it is its own endpoint and never runs inside
# /api/state; the rows it produces are reused for a few seconds, while the
# flags and the live items are read fresh on every request.

BACKLOG_TTL = 3
BACKLOG_CACHE: dict = {"at": 0.0, "rows": []}


def backlog_row(item_id: str, proposals: str, no_solver: bool = False) -> dict:
    comps = solvers.comps_of(item_id)
    calls = solvers.task_callouts(item_id)
    return {"id": item_id, "title": solvers.title_of(item_id), "comps": comps,
            "comps_unproposed": solvers.unproposed(comps, proposals),
            "callouts": calls, "callout_n": len(calls),
            "callout_rank": solvers.callout_rank(calls),
            "callout_act": solvers.callout_act(calls),
            "reports": solvers.report_stages(item_id), "no_solver": no_solver}


def backlog_scan() -> list[dict]:
    done = ledger.fabled(ledger.ledger_rows())
    proposals = solvers.prop_text()
    rows = []
    for path in sorted(config.SOLVERS.glob("*.dl")):
        # a running souffle drops `.tmp*.dl` scratch files into the directory
        if path.name.startswith("."):
            continue
        item_id = path.stem
        if item_id in done:
            continue
        rows.append(backlog_row(item_id, proposals))
    # A pass that wrote no solver leaves the glob nothing to find, so the task
    # needing a ruling most is the one the scan cannot reach. The reports carry
    # it: the stage landed, and its account of why stands in for the file.
    rows += [backlog_row(it["id"], proposals, no_solver=True)
             for it in store.STATE["items"]
             if it.get("landed") and it["id"] not in done
             and not solvers.solver_path(it["id"]).exists()]
    return rows


def finalize_ready(it: dict) -> bool:
    """The wave chain has landed everything before finalize, so the task ranks
    in the backlog while the item still sits in the console — no approval or
    commit required."""
    nxt = store.next_stage(it, it["phase"])
    return (it["state"] in (store.NEEDS_REVIEW, store.APPROVED) and not store.active(it)
            and nxt is not None and nxt["name"] == "finalize"
            and bool(solvers.report_of(it, it["phase"])))


def backlog_view() -> list[dict]:
    with store.LOCK:
        at = time.monotonic()
        if at - BACKLOG_CACHE["at"] > BACKLOG_TTL:
            BACKLOG_CACHE.update(at=at, rows=backlog_scan())
        table = ledger.flags()
        held = {it["id"] for it in store.STATE["items"]
                if it["state"] != store.COMMITTED and not finalize_ready(it)}
        rows = [dict(row) for row in BACKLOG_CACHE["rows"]
                if row["id"] not in held]
        for row in rows:
            row["flag"] = (table.get(row["id"]) or {}).get("level", 0)
    # A missing solver leads: it outranks a flag because it is not a reading of
    # the task but the absence of one. A P0 — broken tooling — follows it,
    # ahead of the flags, since the breakage may hold up other passes too.
    # -callout_n runs last, so a report carrying only P3s still edges out one
    # that raised nothing once everything ahead of it ties.
    rows.sort(key=lambda row: (0 if row["no_solver"] else 1,
                               0 if row["callout_rank"] == 0 else 1,
                               row["flag"] or 9,
                               solvers.callout_weight(row["callout_rank"]),
                               0 if row["comps"] else 1,
                               -row["callout_act"], -row["callout_n"],
                               row["id"]))
    return rows


def act_dismiss(body: dict) -> dict:
    """Drop a task from the finalize backlog: a ledger line records the ruling
    that it needs no fable pass. Deleting that line by hand restores it."""
    item_id = str(body.get("id") or "").strip()
    if not item_id or not solvers.solver_path(item_id).exists():
        return {"error": f"no solver for {item_id}"}
    ledger.ledger_append({"task": item_id, "stage": "dismissed", "backend": None,
                          "model": None, "session": None, "ts": int(time.time()),
                          "source": "user"})
    with store.LOCK:
        BACKLOG_CACHE["at"] = 0.0
    store.bump()
    return {"ok": True}


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
                return {"error": "already in the console — use the item itself"}
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
                  "feed": [], "append": prompts.wave_append(store.STATE["wave"]), "ver": 0,
                  "reports": {}}
            store.STATE["items"].append(it)
            seeded = ", ".join(name for name, _ in pairs)
            store.say(it, store.event(f"{stage['name']} started · "
                                      + (f"seeded from {seeded}" if seeded
                                         else "no earlier reports")))
            try:
                workers.launch(it, prompts.finalize_message(item_id, pairs), stage["name"])
            except (store.Reject, OSError) as exc:
                # nothing is in flight, so the item goes rather than sit unstarted
                store.STATE["items"].remove(it)
                return {"error": f"could not start the worker: {exc}"}
            seeded_names = [name for name, _ in pairs]
        BACKLOG_CACHE["at"] = 0.0
    store.bump()
    if seeded_names is None:
        return {"ok": True, "id": item_id, "advanced": True}
    return {"ok": True, "id": item_id, "seeded": seeded_names}
