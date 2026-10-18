"""The reads of an operator's calls of `scripts/merge_change.py`: the
commit messages its merge calls give, and the outcome of each call."""

import math
from collections.abc import Mapping
from pathlib import Path

from run_reads import blocks
from state_reads import DERIVED, Kept, state_cache
from transcript_entries import fold
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
    `merge_change.py` runs did, or None for any other call, one that
    merges no change, as a call of its `--help`, and one still pending. A
    call the harness refused, an error with no line of the script's own,
    never ran. A call that `pending_wait_hook` denied for its timeout has
    no outcome either, so the merge call is given again, unless the
    operator's last merge call of `command` was denied so too: `denied`
    holds each command whose last merge call was, read in the order of
    the calls, and that second denial never ran. A call whose output gives that `master` is fast-forwarded
    and the worktree stays for changes made after the commit left edits.
    Otherwise it merged where `master` holds, by `subjects`, the
    time of the latest commit of `master` with each subject, a commit made
    at or after the call with the message of each change it merges,
    whatever its exit status, as through a pipe. Otherwise the forms of
    its output give what it did, as `Merge` gives, and a stopped call has
    no outcome, so the merge call is given again. A call whose quoting cannot be
    read has no outcome, and an `undecided` line names it."""
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
