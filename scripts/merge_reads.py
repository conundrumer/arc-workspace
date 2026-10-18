"""The reads of an operator's calls of `scripts/merge_change.py`: the
commit messages its merge calls give, and the outcome of each call."""

import math
from collections.abc import Mapping
from pathlib import Path

from run_reads import blocks
from state_reads import DERIVED, Kept, state_cache
from transcript_folds import fold
from transcript_snapshots import Entry
from transcripts import chain
from wait_bound import bound_denied

from controlled_markdown import mctx
from operations.merge_outcomes import conflict_paths, ended, left_edits, ran, refused
from operations.merging import MERGE_SCRIPT, merge_messages
from operations.state import Merge, Tool


def merge_outcome(aid: str, command: str, time: float, result: str | None, error: bool,
                  subjects: Mapping[str, float], denied: set[str],
                  undecided: list[str]) -> Merge | None:
    """What a Bash call of the operator `aid` of `command` at `time` that
    `merge_change.py` runs did, as `Merge` gives it, by `subjects`, the
    time of the latest commit of `master` with each subject, and `denied`,
    each command whose last merge call `pending_wait_hook` denied for its
    timeout, read in the order of the calls. None for any other call, one
    that merges no change, as a call of its `--help`, one still pending,
    and one that has no outcome. A call whose quoting cannot be read has
    no outcome, and an `undecided` line names it."""
    if MERGE_SCRIPT not in command or result is None:
        return None
    messages = merge_messages(command)
    if messages is None:
        undecided.append(mctx("{run}: the quoting of the merge call `{command}` cannot be "
                              "read").format(run=aid, command=command))
        return None
    if not messages:
        return None
    if error and not ran(result):
        if bound_denied(result) and command not in denied:
            denied.add(command)
            return None
        denied.discard(command)
        return Merge.NOT_RUN
    denied.discard(command)
    if left_edits(result):
        return Merge.LEFT_EDITS
    if all(subjects.get(m, -math.inf) >= math.floor(time) for m in messages):
        return Merge.MERGED
    if not ran(result):
        return Merge.NOT_RUN
    if not ended(result):
        return None
    if conflict_paths(result) is not None:
        return Merge.CONFLICT
    return Merge.REFUSED if refused(result) else Merge.FAILED


def merge_step(subjects: set[str], _path: Path, _line: int, entry: Entry) -> None:
    """Add to `subjects` the commit messages the merge calls of `entry`
    give."""
    if entry.get("type") != "assistant":
        return
    for b in blocks(entry, "tool_use"):
        command = str((b.get("input") or {}).get("command", ""))
        if b.get("name") == Tool.BASH and MERGE_SCRIPT in command:
            subjects.update(merge_messages(command) or ())


@state_cache(DERIVED, kept=Kept.DISK)
def merge_subjects(path: Path) -> frozenset[str]:
    """The commit messages the merge calls of the run at `path` give
    (`operations.merging.merge_messages`), the subjects `merge_outcome`
    looks up."""
    return frozenset(fold(merge_step, set, path, chain(path), frozenset({MERGE_SCRIPT})))
