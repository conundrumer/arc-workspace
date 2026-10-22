"""The window of the next cost audit, under the project's transcript
directory: its start, the launch of the latest run whose `.meta.json`
`description` reads as `Role.COST_AUDIT`, of any session, and its spend,
the subscription dollars of priced Claude requests whose entries in the
own lines of those transcripts are at or after that start, and priced
Codex turns started at or after it from runs whose working directories
are under the main tree, as `audit_records` computes them."""

from pathlib import Path

from audit_records import start_and_spend

from operations.state import AuditWindow


def window(root: Path, main_tree: Path, started: float, undecided: list[str]) -> AuditWindow:
    """The window of the next cost audit, as `start_and_spend` gives it:
    Claude transcripts under `root` and Codex runs whose working
    directories are under `main_tree`, with spend in subscription dollars."""
    return AuditWindow(*start_and_spend(root, main_tree, started, undecided))
