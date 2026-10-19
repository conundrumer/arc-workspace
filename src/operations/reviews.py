"""The code review and the lib review, the reviews of `state.Review`.

Each launches at any step where a commit of `master` that changes the
paths it reviews is one the tag of its last baseline does not reach, and
no reviewer of its role of the session runs. Its occasion is the newest
such commit, so a review that ended with no tag launches again only once
newer code of its paths merges. Where the read gives no baseline
(`NoBaseline`), the unreviewed commits are unknown, and the step is
undecided: on the newest commit of `master` that changes its paths, so
that an operator hands it on once for each such commit, or, where no
commit of `master` that the state reads changes them, on the baseline
alone, so that one analyst takes it until the baseline reads or such a
commit merges."""

from collections.abc import Callable

from controlled_markdown import mctx
from operations import briefs
from operations.filing import scratch_dir
from operations.main_session import main_only
from operations.state import NoBaseline, Review, State
from operations.steps import Launch, Step, Undecided


def procedure(of: Review) -> Callable[[State], Step | None]:
    """The procedure of the review `of`. It gives the step of `review`,
    and only an operator of the main session gives that step."""
    return main_only(lambda state: review(state, of))


PROCEDURES = tuple(procedure(r) for r in Review)
"""The procedure of each review, in the order of `Review`."""


def review(state: State, of: Review) -> Step | None:
    """The launch of the review `of`, where one is due."""
    if any(a.pending for a in state.agents_of(of.role)):
        return None
    baseline = state.git.reviews[of]
    if isinstance(baseline, NoBaseline):
        newest = next((c.hash for c in state.git.commits if of in c.reviews), None)
        commits = (mctx("and no commit of `master` that the command reads changes the paths it "
                        "reviews") if newest is None else
                   mctx("with `{commit}` the newest commit of `master` that changes the paths "
                        "it reviews").format(commit=newest))
        return Undecided(mctx("the last {name}'s baseline, its `{prefix}<n>` tag of the highest "
                              "`<n>`, is unknown, {commits}: {why}").format(
            name=of.facts.noun, prefix=of.value, commits=commits, why=baseline.value))
    if not baseline.unreviewed:
        return None
    number = baseline.number + 1
    return Launch(of.role, of.tag(number),
                  briefs.review(of, baseline.number, number, scratch_dir(of.stem, state.scratch)),
                  occasion=baseline.unreviewed[0])
