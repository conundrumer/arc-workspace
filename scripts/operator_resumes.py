"""The resumes of operators and the messages from their callees."""

from pathlib import Path
from typing import Any

from agent_launches import launched_or_resumed
from controlled_markdown import mctx
from run_reads import agent_messages, notifications, run_entries, is_prompt
from state_reads import DERIVED, Kept, state_cache
from transcript_entries import epoch


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def resumed_at(aid: str, path: Path, undecided: list[str]) -> list[float]:
    """The time of each resume of the agent `aid` whose transcript is at
    `path`. A resume is as `ALERTS` in `src/operations/monitor.py` gives
    it."""
    out: list[float] = []
    ended = False
    for e in run_entries(path):
        if e.get("toolEndsTurn"):
            ended = True
        elif e.get("type") == "assistant":
            ended = False
        elif ended and is_prompt(e):
            ended = False
            if e.get("timestamp"):
                t = epoch(e["timestamp"])
                if not by_callees(path, e, t, undecided):
                    out.append(t)
            else:
                undecided.append(mctx("{run}: a prompt after the run ended has no timestamp, "
                                      "so it is not counted as a resume").format(run=aid))
    return out


def by_callees(path: Path, e: dict[str, Any], t: float, undecided: list[str]) -> bool:
    senders = [s for s, _ in agent_messages(e)]
    notes = notifications(e)
    if not senders and not notes:
        return False
    mine = launched_or_resumed(path, undecided, before=t)
    return (all(s in mine for s in senders)
            and all(any(i in mine for i in n.ids) for n in notes))

