"""Native operations identities, execution evidence and validated reports."""

import json
import re
import shlex
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import codex_agent
from codex_commands import (command_entries, command_output, live_commands, native_shell_call,
                            output_blocks, rollout_message)
from codex_agent import BUSY_REFUSAL, FRESH_REFUSAL
from command_labels import segment_program, simple_commands
from run_reads import blocks, is_prompt

from operations.roles import GENERAL, Role
from codex_ticket import Assignment
from state_reads import DERIVED, state_cache


@dataclass(frozen=True)
class Native:
    store: Path
    manifest: Path
    assignment: Assignment
    state: dict[str, Any]


_native_sessions: dict[str, Path] = {}


def native_assignments(session_scratch: Path | None = None, *, include_history: bool = False) -> list[Native]:
    """One projection of enrolled operations identities and their current turns."""
    from ticket_numbers import session_id
    from tree_reads import scratch

    directory = (session_scratch or scratch(session_id())) / "codex-stores"
    return list(native_projection(directory, include_history))


@state_cache(DERIVED)
def native_projection(directory: Path, include_history: bool) -> tuple[Native, ...]:
    """The projection of the stores in `directory`, read once per state."""
    import codex_ticket
    from file_reads import stat_read

    stat_read(directory)
    result = []
    for pointer in sorted(directory.glob("*.json")):
        stat_read(pointer)
        store = Path(json.loads(pointer.read_text())["store"])
        stat_read(store / "state.json")
        state = json.loads((store / "state.json").read_text())
        records = list(state["agents"].items())
        if include_history:
            records += [(item["agent"], item) for item in state.get("history", [])]
        for agent, item in records:
            manifest = store / "assignments" / f"{agent}-{item['revision']}.json"
            stat_read(manifest)
            assignment = codex_ticket.Assignment.read(manifest)
            stat_read(assignment.brief)
            stat_read(assignment.report)
            if (assignment.agent != agent or assignment.operator != state["operator"]
                    or assignment.ticket != state["ticket"]):
                raise ValueError("native assignment differs from its store")
            result.append(Native(store, manifest, assignment, item))
            _native_sessions[agent] = directory.parent
    unique = {(item.assignment.agent, item.assignment.revision): item for item in result}
    if len(unique) != len(result):
        raise ValueError("native operations identity occurs in more than one store")
    return tuple(sorted(result, key=lambda item: (item.state["reserved"],
        item.assignment.subject or item.assignment.ticket, item.assignment.role.value, item.assignment.revision)))


def native_find(agent: str, session_scratch: Path | None = None) -> Native | None:
    if session_scratch is None and agent in _native_sessions:
        session_scratch = _native_sessions[agent]
    return next((item for item in native_assignments(session_scratch)
                 if item.assignment.agent == agent), None)


def native_turn(item: Native, home: Path | None = None):
    import codex_rollout
    from file_reads import stat_read

    thread, turn = item.state["native"], item.state["turn"]
    if thread is None or turn is None:
        raise ValueError("native submission has no accepted turn")
    path = codex_rollout.rollout_path(thread, home or Path.home())
    stat_read(path)
    found = [value for value in codex_rollout.read_turns(path) if value.turn == turn]
    if len(found) != 1:
        raise ValueError("native assignment has no unique rollout turn")
    return found[0]


def native_execution(assignment: Assignment, state: dict[str, Any], home: Path) -> tuple[list[dict[str, Any]], str]:
    """Read commands, inputs and the final reply from this assignment's own turn."""
    from codex_ticket import Binding
    import codex_rollout

    turn = native_turn(Native(Path(), Path(), assignment, state), home)
    entries: list[dict[str, Any]] = [{"type": "user", "uuid": str(assignment.revision),
        "timestamp": datetime.fromtimestamp(turn.started).astimezone().isoformat(),
        "message": {"content": assignment.brief.read_text()}}]
    binding = Binding.read(assignment.scratch)
    history = []
    if binding is not None:
        store_state = json.loads((binding.store / "state.json").read_text())
        accepted = {item["turn"] for item in store_state.get("history", [])
                    if item["agent"] == assignment.agent and item["native"] == state["native"]}
        history = [old for old in codex_rollout.turns(state["native"], home) if old.turn in accepted]
    entries = [entry for old in history for entry in live_commands(old.activity, include_prompts=True)] + entries
    entries.extend(live_commands(turn.activity, include_prompts=True))
    reply = ""
    for row in turn.activity:
        payload = row["payload"]
        message = rollout_message(row)
        if message is not None and message[0] == "assistant":
            reply = message[1]
        if payload.get("type") == "task_complete" and isinstance(payload.get("last_agent_message"), str):
            reply = payload["last_agent_message"]
        elif (row.get("type") == "response_item" and payload.get("type") == "message"
              and payload.get("role") == "assistant" and payload.get("phase") == "final"):
            reply = "\n".join(part["text"] for part in payload["content"] if "text" in part)
        elif row.get("type") == "event_msg" and payload.get("type") == "agent_message":
            reply = payload["message"]
    return entries, reply


def native_receipt(item: Native, home: Path | None = None):
    """Revalidate the current report bytes and terminal execution on every read."""
    from codex_reports import Evidence, Outcome, Validated, validate
    from codex_ticket import Phase, Terminal
    from codex_reconcile import matching_input
    from codex_rollout import TurnEnd

    if (not item.state["validated"] or item.state["phase"] != Phase.ENDED
            or item.state.get("status") != Terminal.COMPLETED):
        return None
    turn = native_turn(item, home)
    if turn.ended is None or turn.end_state is not TurnEnd.COMPLETE:
        raise ValueError("receipt has no terminal rollout evidence")
    matching_input(item.assignment, item.manifest, turn)
    value = dict(item.state["receipt"])
    value["manifest"] = Path(value["manifest"])
    value["outcome"] = Outcome(value["outcome"])
    previous = Validated(**value)
    entries, reply = native_execution(item.assignment, item.state, home or Path.home())
    return validate(item.manifest, reply, Evidence(item.assignment.agent, item.assignment.revision,
                    item.assignment.inputs_digest, entries), previous.outcome, previous)


def native_agents(owner: str, session_scratch: Path | None = None,
                  home: Path | None = None):
    """Assemble launches and validated reports for the existing operations joins.

    Each agent's launch time, last resume, reports and messages sent come
    from the record of its attempt (`operations.attempt_view`), as a Claude
    agent's do; its state is decided from that record
    (`operator_state.attempt_reads`). A current report counts where its
    recorded digest is that of the report file, and the file's write time
    gives its time. A report whose dispatch file or report file cannot be
    read is no current report."""
    from operator_reads import AgentsRead
    from operator_state import projection
    from operations import attempt_view
    from operations.state import Agent, Report, Running, Waits
    from codex_reports import Outcome, digest
    from review_anchor import read_anchor

    agents = []
    messaged: dict[str, frozenset[str]] = {}
    items = native_assignments(session_scratch)
    launched: dict[str, float] = {}
    for item in native_assignments(session_scratch, include_history=True):
        launched[item.assignment.agent] = min(item.state["reserved"],
                                              launched.get(item.assignment.agent, item.state["reserved"]))
    ours = [item for item in items if (item.state["parent"] or item.assignment.operator) == owner]
    attempts = projection([item.assignment.agent for item in ours])
    for item in ours:
        assignment, state = item.assignment, item.state
        attempt = attempts.get(assignment.agent)
        reports = []
        showing = False
        for reported, current in (attempt_view.recorded_reports(attempt) if attempt is not None else ()):
            if reported.text is None:
                continue
            if not current:
                reports.append(Report(reported.at, reported.text))
                continue
            dispatch = assignment.scratch / "codex-dispatch.json"
            try:
                pending = (state.get("receipt", {}).get("outcome") != Outcome.FINISHED
                           and dispatch.exists() and json.loads(dispatch.read_text()).get("call"))
                if (not pending and assignment.report.exists()
                        and digest(assignment.report.read_bytes()) == reported.digest
                        and reported.revision == assignment.revision):
                    reports.append(Report(assignment.report.stat().st_mtime, reported.text,
                                          assignment.report))
                    showing = True
            except (OSError, ValueError):
                continue
        reviewing = (read_anchor(session_scratch, assignment.agent)
                     if assignment.role in (Role.CODE_EDITOR, Role.DOC_EDITOR) else None)
        since = attempt_view.since(attempt) if attempt is not None else None
        agents.append(Agent(assignment.agent, owner, assignment.role,
            assignment.subject or assignment.ticket, assignment.brief.read_text(),
            launched[assignment.agent], state["reserved"] if since is None else since,
            Running(Waits.AT_WORK), tuple(reports), True,
            report_file=(assignment.report if showing
                or assignment.role in (Role.CODE_EDITOR, Role.DOC_EDITOR) else None),
            reviewing=reviewing, reachable=False, awaited=not showing))
        if attempt is not None:
            messaged[assignment.agent] = attempt_view.sent_to(attempt)
    return AgentsRead(tuple(agents), messaged, {})


@dataclass(frozen=True)
class NativeSend:
    call: str
    arguments: dict[str, Any]
    at: float | None
    accepted: bool


def native_sends(rows):
    """Completed native message calls, with the tool's delivery outcome."""
    from transcript_entries import epoch
    pending: dict[str, tuple[dict[str, Any], float | None]] = {}
    for row in rows:
        payload = row['payload']
        if row.get('type') != 'response_item':
            continue
        if (payload.get('type') == 'function_call'
                and payload.get('name', '').removeprefix('collaboration.') in ('send_message', 'followup_task')):
            try:
                at = epoch(row['timestamp'])
            except (KeyError, TypeError, ValueError):
                at = None
            pending[payload['call_id']] = (json.loads(payload['arguments']), at)
        elif payload.get('type') == 'function_call_output' and payload['call_id'] in pending:
            args, at = pending[payload['call_id']]
            output = payload['output']
            result = (json.loads(output) if output.strip() else None) if isinstance(output, str) else output
            accepted = result is None or (isinstance(result, dict) and not result.get('error')
                and not result.get('isError') and (result.get('status') in (
                    'sent', 'delivered', 'queued', 'accepted', 'running') or isinstance(result.get('message_id'), str)))
            yield NativeSend(payload['call_id'], args, at, accepted)
