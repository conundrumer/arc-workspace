"""Dispatch ticket-log recovery before a merged change closes.

A recovery is complete only when current ticket evidence removes the need
or ordinary role readers consume an accepted result. Pending work and an
unproved consumption keep closure pending. Missing or conflicting source
evidence requires the existing held-step judgment.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from controlled_markdown import mctx
from operations import briefs
from operations.completion import finished
from operations.filing import scratch_dir
from operations.handled import repeated
from operations.roles import EDITORS, Role
from operations.state import Agent, State, Ticket
from operations.steps import Launch, Send, Step, Undecided
from ticketing.vocabulary import Status


class Mode(StrEnum):
    DELIVER = "deliver"
    REPLACE = "replace"


@dataclass(frozen=True)
class Request:
    agent: str
    mode: Mode
    time: float


@dataclass(frozen=True)
class Pending:
    """Unresolved recovery, with a ready dispatch or held-step judgment, or,
    where `step` is None, the agent whose work is awaited (`waits_on`) and
    the time of the request it answers (`since`)."""
    step: Step | None
    waits_on: str | None = None
    since: float | None = None


def requests(ticket: Ticket) -> tuple[Request, ...] | str:
    found: dict[str, Request] = {}
    for line in ticket.log:
        if not line.note.startswith("recover "):
            continue
        match = re.fullmatch(r"recover ([a-zA-Z0-9-]+) (deliver|replace): .+", line.note)
        if match is None:
            return mctx("unreadable recovery note at {time}").format(time=line.time)
        request = Request(match[1], Mode(match[2]), line.time)
        previous = found.get(request.agent)
        if previous is not None and previous.mode is not request.mode:
            return mctx("conflicting recovery modes for {agent}").format(agent=request.agent)
        found.setdefault(request.agent, request)
    return tuple(found.values())


DELIVER = mctx(
    "Deliver the completed report of launch {agent} using the current execution "
    "readers, then reply to operator {operator}. Preserve its required report "
    "path and all execution evidence. If delivery fails, "
    "give the reason.")
HOLD = mctx("recovery of {agent}: {reason}")


def held(ticket: Ticket, agent: str, reason: str) -> Pending:
    return Pending(Undecided(HOLD.format(agent=agent, reason=reason), change=ticket.number))


def consumed(state: State, agent: Agent) -> bool:
    """Require a later consumer launch on an editor's reported result."""
    if agent.role not in EDITORS or not finished(agent) or (report := agent.last_report) is None:
        return False
    from operations.change_agents import of_change

    ticket = state.ticket(agent.subject)
    return ticket is not None and any(
        a.role in (Role.ITEM_CHECKER, Role.TICKET_ANALYST) and a.launched > report.time
        for a in of_change(state, ticket))


def step(state: State, ticket: Ticket) -> Pending | None:
    """None means resolved; Pending(None) means work must still be awaited."""
    queued = requests(ticket)
    if isinstance(queued, str):
        return held(ticket, ticket.number, queued)
    agents = (*state.transcripts.agents, *state.transcripts.elsewhere)
    for request in queued:
        original = next((a for a in agents if a.agent_id == request.agent), None)
        if original is None:
            return held(ticket, request.agent, mctx("source launch is missing"))
        target = state.ticket(original.subject)
        if target is not None and target.status is Status.CLOSED:
            continue
        attempts = [a for a in agents
                    if a.role is original.role and a.subject == original.subject
                    and (original.role not in EDITORS or briefs.part_of(a) == briefs.part_of(original))]
        evidence = state.recovery.value
        accepted = [a for a in attempts if a.launched >= original.launched
                    and (identity := a.agent_id) is not None
                    and identity in evidence and evidence[identity].accepted]
        if any(consumed(state, a) for a in accepted):
            continue
        if running := [a for a in attempts if a.pending]:
            return Pending(None, running[0].agent_id or request.agent, request.time)
        if any(a.role in EDITORS and finished(a) for a in accepted):
            return Pending(None, request.agent, request.time)
        if accepted and any(finished(a) for a in accepted):
            return held(ticket, request.agent, mctx("accepted result consumption cannot be established for this role"))
        retry = Send(request.agent, DELIVER.format(agent=request.agent, operator=state.me),
                     f"recover {ticket.number} {request.agent} {request.time}", request.time)
        if request.mode is Mode.DELIVER and not repeated(retry, state):
            return Pending(retry)
        source = evidence.get(request.agent)
        if source is None or not source.available:
            return held(ticket, request.agent, mctx("source brief or worktree is unavailable"))
        if not original.brief.strip():
            return held(ticket, request.agent, mctx("source brief is empty"))
        recovery_name = f"recovery {ticket.number} {request.agent} {request.time}"
        prior = [a for a in attempts if a.launched > request.time and recovery_name in a.brief]
        if prior:
            return held(ticket, request.agent, mctx("replacement ended without proof that its result was accepted and consumed"))
        brief = original.brief
        if original.report_file is not None:
            brief = "\n".join(line for line in brief.splitlines()
                              if str(original.report_file) not in line)
        # Rebind only the per-run scratch field; preserve work and worktree paths.
        old_scratch = briefs.scratch_of(brief)
        if old_scratch is not None:
            fresh = scratch_dir(f"recover-{request.agent}", state.scratch)
            brief = brief.replace(str(old_scratch), str(fresh))
        elif original.role in EDITORS:
            return held(ticket, request.agent, mctx("source scratch field cannot be rebound"))
        brief += "\n" + mctx("Recovery occasion: {occasion}.").format(occasion=recovery_name)
        return Pending(Launch(original.role, original.subject, brief, occasion=recovery_name))
    return None
