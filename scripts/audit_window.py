"""The window of the next cost audit, under the project's transcript
directory: its start, the launch of the latest run whose `.meta.json`
`description` reads as `Role.COST_AUDIT`, of any session, and its spend,
the token cost of the requests whose entries have a timestamp at or after
that start, in the own lines of each transcript, as `audit_records`
computes them."""

from pathlib import Path

from audit_records import start_and_spend

from operations.state import AuditWindow


def window(root: Path, started: float, undecided: list[str]) -> AuditWindow:
    """The window of the next cost audit under `root`, as `start_and_spend`
    gives it."""
    return AuditWindow(*start_and_spend(root, started, undecided))
