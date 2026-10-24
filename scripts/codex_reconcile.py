"""Accepted rollout evidence for ticket execution and descendant recovery."""

from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from codex_ticket import Assignment, Phase, Refused, Store, Terminal, bound


def reconcile(scratch: Path, agent: str, native: str, home: Path) -> dict[str, Any]:
    """Settle the agent's unresolved descendants, deepest first, then the agent.

    Each turn is settled from its own accepted rollout evidence, so a turn or
    reservation left unresolved by an earlier failed read is settled here. A
    descendant that cannot be settled raises its refusal under its operations id."""
    _, store = bound(scratch)
    agents = store.snapshot()["agents"]

    def depth(aid: str) -> int | None:
        """Parent links from `aid` up to `agent`, or None where `agent` is no ancestor."""
        steps, parent = 0, agents[aid]["parent"]
        while parent is not None:
            steps += 1
            if parent == agent:
                return steps
            parent = agents[parent]["parent"]
        return None

    below = {aid: steps for aid, item in agents.items()
             if item["phase"] != Phase.ENDED and (steps := depth(aid)) is not None}
    for aid in sorted(below, key=lambda aid: -below[aid]):
        try:
            settle(store, aid, agents[aid]["native"], home)
        except (OSError, ValueError, KeyError) as exc:
            raise Refused(mctx("child {agent}: {reason}").format(agent=aid, reason=exc)) from exc
    try:
        return settle(store, agent, native, home)
    except (OSError, ValueError, KeyError) as exc:
        raise Refused(mctx("agent {agent}: {reason}").format(agent=agent, reason=exc)) from exc


def settle(store: Store, agent: str, native: str | None, home: Path) -> dict[str, Any]:
    """Use the agent's own accepted rollout to settle its entry.

    A native of None or a runtime path (starting with `/`) is resolved by the
    child-rollout search. A reserved child no rollout and no parent activity shows
    is released, once its parent's turn has ended."""
    import codex_rollout

    item = store.snapshot()["agents"][agent]
    assignment = Assignment.read(store.manifest(agent, item["revision"]))
    runtime = native
    if native is None or "/" in native:
        if item["parent"] is None or (native is not None and native.rsplit("/", 1)[-1] != agent):
            raise Refused("runtime child identity does not match its reserved task name")
        if native is not None and item["native"] is not None and item.get("runtime") == native:
            native = item["native"]
        else:
            found = child_rollout(store, agent, item, home)
            if found is None:
                release_unaccepted(store, agent, item, home)
                return store.snapshot()["agents"][agent]
            native = found
    assert native is not None
    path = codex_rollout.rollout_path(native, home)
    if item["parent"] is not None:
        metadata = [row["payload"] for row in codex_rollout.rows(path) if row.get("type") == "session_meta"]
        parent = store.snapshot()["agents"][item["parent"]]
        if len(metadata) != 1 or native_parent(metadata[0]) != parent["native"]:
            raise Refused("native child rollout does not belong to the reserved parent")
    turns = [turn for turn in codex_rollout.turns(native, home)
             if turn.started >= item["reserved"]]
    if len(turns) != 1:
        raise Refused("submission has no unique accepted rollout turn")
    turn = turns[0]
    matching_input(assignment, store.manifest(agent, item["revision"]), turn)
    if item["phase"] in (Phase.RESERVED, Phase.INTERRUPTING):
        store.accepted(agent, item["token"], native, turn.turn, runtime)
    elif (item["native"], item["turn"]) != (native, turn.turn):
        raise Refused("rollout belongs to another accepted turn")
    if turn.ended is not None:
        status = Terminal.COMPLETED if turn.end_state is codex_rollout.TurnEnd.COMPLETE else Terminal.INTERRUPTED
        store.ended(agent, turn.turn, status)
    from codex_delivery import reconcile_messages
    reconcile_messages(store, agent, home)
    from codex_attempts import publish
    from attempt_record import observe
    observe(lambda: publish(store, store.snapshot()))
    return store.snapshot()["agents"][agent]


def child_rollout(store: Store, agent: str, item: dict[str, Any], home: Path) -> str | None:
    """The one rollout of the child's identity with a turn from its reservation, or None.

    The identity is the parent's native thread and an agent path ending in the
    child's operations id; its input is checked afterward by `matching_input`."""
    import codex_rollout

    parent = store.snapshot()["agents"][item["parent"]]
    if parent["native"] is None:
        raise Refused("native parent has no accepted identity")
    candidates = []
    for candidate in codex_rollout.rollout_files(home):
        if candidate.stat().st_mtime < item["reserved"]:
            continue
        metadata = [row["payload"] for row in codex_rollout.rows(candidate)
                    if row.get("type") == "session_meta"]
        if (len(metadata) != 1 or native_parent(metadata[0]) != parent["native"]
                or not str(metadata[0].get("agent_path")).endswith("/" + agent)):
            continue
        if any(turn.started >= item["reserved"] for turn in codex_rollout.read_turns(candidate)):
            candidates.append(metadata[0]["id"])
    if len(candidates) > 1:
        raise Refused("runtime child has no unique accepted assignment rollout")
    return candidates[0] if candidates else None


def release_unaccepted(store: Store, agent: str, item: dict[str, Any], home: Path):
    """Release a reserved child that neither its rollouts nor its parent's turn show.

    While the parent's turn runs, or where the parent's turn shows the child
    started, the absence of a child rollout is a refusal."""
    import codex_rollout
    from datetime import datetime

    if item["phase"] != Phase.RESERVED or item["native"] is not None:
        raise Refused("runtime child has no unique accepted assignment rollout")
    parent = store.snapshot()["agents"][item["parent"]]
    try:
        turns = [turn for turn in codex_rollout.turns(parent["native"], home)
                 if turn.turn == parent["turn"]]
    except ValueError as exc:
        raise Refused(f"native parent rollout is unreadable: {exc}") from exc
    if len(turns) != 1 or turns[0].ended is None:
        raise Refused("runtime child has no rollout, and its parent's turn has not ended")
    for row in turns[0].activity:
        payload = row.get("payload", {})
        activity = payload.get("item", {}) if payload.get("type") == "item_completed" else {}
        if (activity.get("type") == "SubAgentActivity"
                and str(activity.get("agent_path")).endswith("/" + agent)
                and datetime.fromisoformat(row["timestamp"]).timestamp() >= item["reserved"]):
            raise Refused("inconsistent evidence: its parent's turn started the child, "
                          "and no rollout of the child is found")
    store.refused(agent, item["token"])


def native_parent(metadata: dict[str, Any]) -> str | None:
    source = metadata.get("source")
    subagent = source.get("subagent") if isinstance(source, dict) else None
    spawn = subagent.get("thread_spawn") if isinstance(subagent, dict) else None
    return spawn.get("parent_thread_id") if isinstance(spawn, dict) else None


def matching_input(assignment: Assignment, manifest: Path, turn: Any):
    """Require the filed input and execution parameters in accepted rollout evidence.

    A native child's task arrives as an `agent_message` addressed to its task path,
    whose payload is encrypted; the message's presence and recipient are proved, and
    its encrypted content is not compared. Any other turn must hold the filed brief
    and manifest in a plaintext user prompt."""
    if assignment.model is not None:
        contexts = [row["payload"] for row in turn.activity if row.get("type") == "turn_context"]
        if not contexts or any((context.get("model"), context.get("effort")) != (
                assignment.model, assignment.effort) for context in contexts):
            raise Refused("accepted turn does not use its assigned model and effort")
    from codex_reads import rollout_message

    encrypted = any(
        row.get("type") == "response_item" and row["payload"].get("type") == "agent_message"
        and str(row["payload"].get("recipient")).endswith("/" + assignment.agent)
        and any(part.get("type") == "encrypted_content" for part in row["payload"]["content"])
        for row in turn.activity)
    if encrypted:
        return
    prompts = [message[1] for row in turn.activity
               if (message := rollout_message(row)) is not None and message[0] == "user"]
    if not any(assignment.brief.read_text() in prompt and str(manifest) in prompt for prompt in prompts):
        raise Refused("accepted turn does not contain its filed assignment input")

