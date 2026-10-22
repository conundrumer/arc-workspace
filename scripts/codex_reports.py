"""Fail-closed acceptance of a filed native assignment's report.

A receipt binds report bytes, assignment bytes and input bytes. Runtime
completion alone supplies no receipt, and a repeated attempt runs every check
again except the checklist walk, which belongs to the turn that made the receipt.
"""

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from checklist_walk_hook import _calls, stop_bound, walk_gap
from codex_ticket import Assignment, Refused
from filed_texts import report_file
from handbook.checklist import checklist_agents
from report_file_hook import written_since


class Outcome(StrEnum):
    FINISHED = "finished"
    NEEDS_OPERATOR = "needs-operator"


@dataclass(frozen=True)
class Validated:
    manifest: Path
    agent: str
    revision: int
    assignment_digest: str
    inputs_digest: str
    report_digest: str
    outcome: Outcome


@dataclass(frozen=True)
class Evidence:
    agent: str
    revision: int
    inputs_digest: str
    entries: list[dict[str, Any]]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate(manifest: Path, reply: str, evidence: Evidence, outcome: Outcome,
             previous: Validated | None = None) -> Validated:
    """Validate current evidence, then compare any receipt being accepted."""
    assignment = Assignment.read(manifest)
    if (evidence.agent, evidence.revision, evidence.inputs_digest) != (
            assignment.agent, assignment.revision, assignment.inputs_digest):
        raise Refused("execution evidence belongs to another assignment or input revision")
    entries = evidence.entries
    if report_file(reply) != assignment.report:
        raise Refused("final text must be the assigned report path alone")
    if digest(assignment.brief.read_bytes()) != assignment.inputs_digest:
        raise Refused("assignment input changed; a new revision is required")
    if not assignment.report.is_file():
        raise Refused("assigned report is missing")
    if assignment.report.stat().st_mtime_ns <= manifest.stat().st_mtime_ns:
        raise Refused("report predates this assignment revision")
    if not entries:
        raise Refused("assignment has no readable execution evidence")
    if not written_since(assignment.report, reversed(entries)):
        raise Refused("report predates substantive input")
    kind = assignment.actual_type
    if previous is None and kind in checklist_agents():
        calls = _calls(entries, kind)
        stop = stop_bound(entries, calls, kind)
        if stop is not None and outcome is not Outcome.NEEDS_OPERATOR:
            raise Refused("a stopped checklist cannot finish the assignment")
        gap = walk_gap(kind, calls, stop)
        if gap is not None:
            raise Refused(f"assignment checklist is incomplete: the walk lacks "
                          f"`{gap.item.heading.text}`; run `{gap.call}` and walk on from there")
    receipt = Validated(manifest.resolve(), assignment.agent, assignment.revision,
                        digest(manifest.read_bytes()), assignment.inputs_digest,
                        digest(assignment.report.read_bytes()), outcome)
    if previous is not None and previous != receipt:
        raise Refused("report receipt no longer matches the assignment and its inputs")
    return receipt
