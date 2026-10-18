"""The final reply of an agent, as its transcript gives it. The read is
kept on disk (`state_reads.Kept.DISK`) in this module, which imports
none of the modules that call it, so that a commit to those leaves its
records standing (`kept_reads.code_of`)."""

from pathlib import Path

from agent_turns import has_ended, run_back, turn_marks
from run_reads import blocks
from state_reads import DERIVED, Kept, state_cache
from transcript_entries import epoch

from operations.state import Report


@state_cache(DERIVED, kept=Kept.DISK)
def final_reply(path: Path) -> Report | None:
    """The final reply in the transcript at `path`: the text of the entry
    that ends its last turn, or the message of the call that ends it, where
    its turn has ended."""
    if not has_ended(path):
        return None
    marks = turn_marks(run_back(path))
    e = next((e for e, _, end in marks if end), None)
    if e is None:
        return None
    stamp = e.get("timestamp")
    if not stamp:
        return None
    if e.get("type") == "assistant":
        text = "\n".join(str(b.get("text", "")) for b in blocks(e, "text"))
    else:
        ended = {b.get("tool_use_id") for b in blocks(e, "tool_result")}
        text = next((str((b.get("input") or {}).get("message", ""))
                     for x, _, _ in marks if x.get("type") == "assistant"
                     for b in blocks(x, "tool_use") if b.get("id") in ended), "")
    return Report(epoch(stamp), text) if text.strip() else None
