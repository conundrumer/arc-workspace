"""Read execution and source-brief evidence for ticket-log recoveries.

Only tickets with recovery notes request this read. Each read uses current
transcripts and files; a report file alone does not establish execution.
"""

from pathlib import Path

from codex_reads import calls, commands, walk_entries
from entry_reads import entries_forward
from file_reads import is_dir, is_file
from noted_reads import note_read
from run_reads import agent_type, blocks, output_file, role_type
from transcripts import launched_find

from operations.roles import CODEX_LAUNCHER
from operations.state import Agent, RecoveryEvidence
from operations.worktrees import WORKTREE


def evidence(agent: Agent) -> RecoveryEvidence:
    """Validate the source brief and the accepted execution of this attempt."""
    if agent.agent_id is None or not agent.brief.strip():
        return RecoveryEvidence(False, "source launch or brief is missing", False)
    try:
        worktrees = [match.rstrip(".`") for match in WORKTREE.findall(agent.brief)]
        for tree in worktrees:
            target = Path(tree)
            note_read(target)
            if not (is_dir(target) or is_file(target)):
                return RecoveryEvidence(False, f"worktree is unavailable: {tree}", False)
        from codex_reads import native_find, native_receipt

        native = native_find(agent.agent_id)
        if native is not None:
            note_read(native.manifest)
            note_read(native.store / "state.json")
            if native_receipt(native) is None:
                return RecoveryEvidence(False, "native execution has no current validator receipt")
            return RecoveryEvidence(True, "validated native execution")
        path = launched_find(agent.agent_id)
        if path is None:
            return RecoveryEvidence(False, "source transcript is missing", False)
        entries = list(entries_forward(path))
        if agent_type(path) == CODEX_LAUNCHER:
            for entry in entries:
                for block in blocks(entry, "tool_result"):
                    output = output_file(block)
                    if output is not None:
                        note_read(output)
                for _, _, scratch in commands(entry):
                    for name in ("codex-session", "codex-events.jsonl", "codex-launch-failures.jsonl"):
                        note_read(scratch / name)
            kind = role_type(path)
            if kind is None:
                return RecoveryEvidence(False, "source role is unknown")
            walk_entries(entries, kind)
            if not calls(entries):
                return RecoveryEvidence(False, "no accepted work call")
        if agent.report_file is not None:
            note_read(agent.report_file)
            if not is_file(agent.report_file):
                return RecoveryEvidence(False, "required report file is missing")
        return RecoveryEvidence(True, "accepted execution")
    except (OSError, ValueError, KeyError, IndexError) as exc:
        return RecoveryEvidence(False, str(exc))


def read(agents: tuple[Agent, ...]) -> dict[str, RecoveryEvidence]:
    """Read each known attempt independently, preserving failures as evidence."""
    return {a.agent_id: evidence(a) for a in agents if a.agent_id is not None}
