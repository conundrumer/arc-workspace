"""The agent listing of a run: the agent types its transcript gives it as
launchable."""

from pathlib import Path

from run_reads import run_entries
from state_reads import DERIVED, Kept, state_cache

LISTING_DELTA = "agent_listing_delta"


@state_cache(DERIVED, kept=Kept.DISK)
def agent_listing(path: Path) -> frozenset[str] | None:
    """The agent types the agent listing of the run at `path` gives, or None
    where the run has no `LISTING_DELTA` attachment."""
    listing: set[str] | None = None
    for e in run_entries(path, naming={LISTING_DELTA}):
        a = e.get("attachment") if e.get("type") == "attachment" else None
        if not isinstance(a, dict) or a.get("type") != LISTING_DELTA:
            continue
        listing = (listing or set()) | set(a.get("addedTypes") or ())
        listing -= set(a.get("removedTypes") or ())
    return None if listing is None else frozenset(listing)
