"""What a call of `scripts/merge_change.py` printed, as the reads of an
operator's merge calls take it: the texts of the script that those reads
match, and whether the call ran, ended, refused a change, and whether
for a conflict, or left a worktree for changes made after its change's commit."""

import re

from controlled_markdown import form, mctx
from engine.duration import FOOTER_RE
from operations.merging import PREFIX, REFUSED, refusal_line, split_paths
from operations.state import Merge
from operations.worktrees import BASE

CONFLICT = mctx("rebasing {branch} onto {onto} conflicts in {paths}; {outcome}")
"""The refusal of a change whose rebase onto `master` conflicts, with what
the script did after it."""


def ran(output: str) -> bool:
    """Whether `output`, what a call of the script printed, holds a line of
    the script's own, which a call that never ran does not."""
    return any(line.startswith(PREFIX) for line in output.splitlines())


def ended(output: str) -> bool:
    """Whether `output`, what a call of the script printed, holds the
    script's footer, which a run that was stopped does not."""
    return any(m[0].startswith(PREFIX) for m in FOOTER_RE.finditer(output))


def refused(output: str) -> bool:
    """Whether `output`, what a call of the script printed, holds a
    refusal line (`merging.refusal_line`)."""
    return refusal_line(output) is not None


STAYS = mctx("{master} is fast-forwarded, and {why}, so {worktree} and {branch} stay")
"""The failure of a step after `master` is fast-forwarded that leaves a
change's worktree and branch."""

LEFT_AFTER = mctx("the worktree holds changes made after the commit, in {left}")
"""The reason a worktree stays where it holds changes made after its
change's commit."""


def conflict_paths(output: str) -> tuple[str, ...] | None:
    """The paths in which `output` gives that a change's rebase conflicts,
    or None where it refuses no change for a conflict."""
    m = re.search(form(REFUSED + CONFLICT, {"branch": r"\S+", "onto": r"\S+",
                                            "paths": r"(?P<paths>.*?)", "outcome": r""}),
                  output)
    return None if m is None else split_paths(m["paths"])


def call_conflicts(merge: Merge | None, output: str | None) -> tuple[str, ...]:
    """The paths that conflict in a merge call whose outcome is `merge` and
    that printed `output`: those `conflict_paths` gives where `merge` is
    `Merge.CONFLICT`, and none otherwise."""
    if merge is not Merge.CONFLICT:
        return ()
    return conflict_paths(output or "") or ()


def left_edits(output: str) -> bool:
    """Whether `output` gives that `master` is fast-forwarded and a
    worktree stays for changes made after its change's commit."""
    text = STAYS.format(master=BASE, why=LEFT_AFTER, worktree="{worktree}", branch="{branch}")
    return re.search(form(text, {"left": r".+?", "worktree": r"\S+", "branch": r"\S+"}),
                     output) is not None
