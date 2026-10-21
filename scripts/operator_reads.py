"""The reads of the transcripts of a session's operators: the operators
that ran `operate.py`, the text of a message an operator
received from its parent, the agents operators launched, merged across
operators, and the reports of solver passes (`operator_transcript` reads
one operator's transcript, and `agent_ends` the final replies of
agents)."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_turns import first_time
from controlled_markdown import mctx
from filed_texts import unfiled
from run_reads import (MAIN, agent_messages, agent_type, blocks,
                       message_text,
                       session_agents)
from file_reads import file_text, is_dir, is_file, listed, mtime
from state_reads import DERIVED, Kept, state_cache
from ticket_numbers import TICKET_NUMBER
from transcripts import find, session_directory
from entry_reads import read_entries

from operations.reports import CONCEPT_FAULTS, TICKETS_FILED, section, section_items
from operations.roles import Role
from operations.state import (
    Agent, PassReport, Tool,
)
from operations.task_dirs import refine_report, tasks_work
from operations.command_words import COMMAND
from operations.printing import unfenced


def pass_report(task: str, role: Role, launched: float, main: Path) -> Path | None:
    """The report file the pass of `role` on `task` wrote since its launch
    at `launched`, as `docs/handbook/procedure.md` names it: for Refine,
    the `refine-<n>.md` first written after the launch."""
    work = tasks_work(main) / task
    if not is_dir(work):
        return None
    files = (sorted(work / e.name for e in listed(work) if refine_report(e.name))
             if role is Role.REFINE else [work / f"{role.value}.md"])
    written = [(mtime(p), p) for p in files if is_file(p)]
    return min(((t, p) for t, p in written if t > launched), default=(0.0, None))[1]


def pass_read(task: str, role: Role, launched: float, main: Path) -> PassReport:
    """The read of the report file of the pass (`PassReport`)."""
    path = pass_report(task, role, launched, main)
    if path is None:
        return PassReport(None, ())
    text = file_text(path)
    filed = section(text, TICKETS_FILED)
    tickets = None if filed is None else tuple(m.group(0).rstrip("_") for m in re.finditer(
        rf"(?<![\w-]){TICKET_NUMBER.pattern}_", filed))
    return PassReport(tickets, section_items(text, CONCEPT_FAULTS))


@state_cache(DERIVED, kept=Kept.DISK)
def ran_command(path: Path) -> bool:
    """Whether the transcript at `path` holds a Bash call of the command."""
    return any(b.get("name") == Tool.BASH and COMMAND in str((b.get("input") or {}).get("command"))
               for e in read_entries(path, naming={COMMAND}) if e.get("type") == "assistant"
               for b in blocks(e, "tool_use"))


def operator_runs(session: str, me: str) -> list[tuple[str, Path]]:
    """The operator `me` and each other operator of the session that ran
    the command, by agent id, in the order of their first entry. An
    operator that never ran the command left no work under its procedures.
    An operator whose transcript holds no timestamped entry has made no
    call yet, and is left out."""
    return list(session_operators(session, me))


@state_cache(DERIVED)
def session_operators(session: str, me: str) -> tuple[tuple[str, Path], ...]:
    """`operator_runs`, held."""
    directory = session_directory(find(session))
    runs = [(aid, p, t) for aid, p in session_agents(directory).items()
            if agent_type(p) == Role.OPERATOR.agent_type and (aid == me or ran_command(p))
            and (t := first_time(p)) is not None]
    return tuple((aid, p) for aid, p, _ in sorted(runs, key=lambda r: r[2]))


WRAP = ("The coordinator sent a message while you were working:",
        "Address this before completing your current task.")
"""The lines the harness puts around a message from the coordinator that
arrives while the operator works."""


MESSAGE_FROM = mctx("{run}: a message from")


def unwrapped(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.strip() not in WRAP).strip()


def from_parent(aid: str, e: dict[str, Any], parent: str, undecided: list[str]) -> str:
    """The text of the brief, or of the message from `parent`, that the
    entry `e` of the operator `aid` gives, where `parent` is the operator's
    parent, or `main` for a message of the coordinator's. An operator
    launcher's brief and messages are files the command wrote, read in
    place of the line that gives each, and a message of its arrives in the
    form of any agent's."""
    text = unwrapped(message_text(e))
    if parent == MAIN:
        return text
    given = [t for s, t in agent_messages(e) if s == parent]
    where = MESSAGE_FROM.format(run=aid)
    return unfiled(unfenced("\n".join(given) if given else text), f"{where} {parent}",
                   undecided)


@dataclass(frozen=True)
class AgentsRead:
    """Agents read from transcripts, with the parts of
    `TranscriptsRead.messaged` and `TranscriptsRead.limited` for them."""
    agents: tuple[Agent, ...]
    messaged: Mapping[str, frozenset[str]]
    limited: Mapping[str, float]


def joined(reads: Sequence[AgentsRead]) -> AgentsRead:
    """The agents of `reads`, in their order, with their mappings merged."""
    return AgentsRead(tuple(a for r in reads for a in r.agents),
                      {k: v for r in reads for k, v in r.messaged.items()},
                      {k: v for r in reads for k, v in r.limited.items()})


def kept(agents: Sequence[Agent], reads: Sequence[AgentsRead]) -> AgentsRead:
    """`agents`, with the parts of the mappings of `reads` for them."""
    ids = {a.agent_id for a in agents}
    whole = joined(reads)
    return AgentsRead(tuple(agents),
                      {k: v for k, v in whole.messaged.items() if k in ids},
                      {k: v for k, v in whole.limited.items() if k in ids})
