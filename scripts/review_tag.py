"""Records a review's commit, and makes the tag of a review's baseline once
the reviewer's step calls have printed its checklist's walk up to the
item after the one the tag needs. `HELP`, which `--help` prints, gives the
usage forms and the rules."""

import argparse
import os
import re
import sys
import tempfile
import textwrap
from collections.abc import Iterable
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.checklist import Checklist, Gap
from handbook.paths import scripts_importable
from operations.roles import AGENT_ID
from operations.state import Review

scripts_importable()

from checklist_walk_hook import step_calls  # noqa: E402
from entry_reads import read_entries  # noqa: E402
from transcript_snapshots import Entry, Refused, print_refused  # noqa: E402
from transcripts import transcripts_of  # noqa: E402
from tree_reads import main_tree  # noqa: E402

REVIEWS = {r.role.value: r for r in Review}

HELP = mctx("""
    - The usage forms:
        ```
        uv run python scripts/review_tag.py commit <reviewer> <n>
        uv run python scripts/review_tag.py <reviewer> <n> <commit> <agent id>
        ```
    - `<reviewer>` is one of the reviewers this list gives, each with the item of its checklist the tag needs and the prefix of its tag:
        {table}
    - `commit` records the review's commit, with `<n>`, the review's number, in its message: the tree of `HEAD` with the paths `<reviewer>` reviews as the working tree it runs from holds them, untracked files included, as a commit whose parent is `HEAD`.
        - It prints the commit's hash on one line, then the git pathspecs that select those paths, one on a line.
    - The form with `<commit>` makes the tag of the review's baseline.
        - It reads the transcripts of the reviewer `<agent id>`, and checks that the tool results of its Bash calls whose command runs `scripts/step.py <reviewer>` hold, whole, each item the step command gives from the first item of the checklist of the main tree, as it stands at the command's call, up to the item after that item, each in a result after the last result that holds an earlier item.
            - Where that checklist holds no such item, the command fails and names the item it wants.
        - Where the results hold each of those items, it runs `git tag <prefix><m> <commit>` for the least `<m>` from `<n>` up that git accepts, and prints the tag.
        - Where they do not, it makes no tag, exits non-zero, and prints the step call that prints the first item they do not hold, to be run, with each item from the one it prints up to this command done, before the command is run again.
            - Where it finds no transcript of `<agent id>`, it prints that, and that `<agent id>` is the reviewer's own agent id.
    """)

ROW = mctx("- `{reviewer}`: the item `{item}`, the prefix `{prefix}`.")

NO_TRANSCRIPT = mctx("no transcript of the agent `{agent}` is found: give your own agent "
                     "id as `<agent id>`")

NO_STEP = mctx("the step-call results in the transcripts of `{agent}` do not hold, whole, "
               "the item `{missing}` of the checklist as it stands now in a result after "
               "the last result that holds an earlier item, and the tag needs "
               "each item the step command gives up to the item after `{item}`: run `{call}`, "
               "do each item from the one it prints up to this command, then run this "
               "command again")


def step_gap(entries: Iterable[Entry], checklist: Checklist, item: str) -> Gap | None:
    """The first item of the walk of `checklist` up to the item after
    `item` that the step-call results among `entries` do not hold, as
    `HELP` gives it, or None."""
    _, after = checklist.named(item)
    if after is None:
        raise ValueError(f"`{item}` is the last item of the checklist of {checklist.agent}")
    results = (r for _, r in step_calls(entries, checklist.agent))
    return checklist.gap(results, after.heading.text)


def tag(review: Review, n: int, commit: str) -> str:
    """The tag `HELP` gives; a failure other than a taken name is
    `GitFailed`."""
    root = checkout.ROOT
    m = n
    while True:
        name = review.tag(m)
        done = checkout.git(root, "tag", name, commit)
        if done.returncode == 0:
            return name
        if checkout.git_answer(root, "rev-parse", "-q", "--verify",
                               f"refs/tags/{name}").returncode != 0:
            raise checkout.GitFailed(root, ("tag", name, commit), done.stderr)
        m += 1


def review_commit(review: Review, n: int) -> str:
    """The hash of the commit `HELP` gives for `commit`. Its index is a
    file of its own, so the repo's index stays as it was."""
    root = checkout.ROOT
    paths = review.facts.paths
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(scratch) / "index")}
        checkout.git_out(root, "read-tree", "HEAD", env=env)
        checkout.git_out(root, "add", "-A", "--", *paths, env=env)
        tree = checkout.git_out(root, "write-tree", env=env).strip()
        return checkout.git_out(root, "commit-tree", tree, "-p", "HEAD",
                                "-m", review.tag(n), env=env).strip()


def review_tag(review: Review, n: int, commit: str, agent: str) -> str:
    paths = transcripts_of(agent)
    if not paths:
        raise Refused(NO_TRANSCRIPT.format(agent=agent))
    item = review.facts.item
    checklist = Checklist(review.role.value, main_tree())
    gap = step_gap((e for p in paths for e in read_entries(p)), checklist, item)
    if gap is not None:
        raise Refused(NO_STEP.format(agent=agent, missing=gap.item.heading.text, item=item,
                                     call=gap.call))
    return tag(review, n, commit)


def help_text() -> str:
    rows = "\n".join(ROW.format(reviewer=r.role.value, item=r.facts.item, prefix=r.value) for r in Review)
    return textwrap.dedent(HELP).format(table=textwrap.indent(rows, " " * 4).lstrip())


def commit_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="review_tag.py commit", description=help_text(),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reviewer", choices=sorted(REVIEWS))
    parser.add_argument("n", type=int)
    args = parser.parse_args(argv)
    review = REVIEWS[args.reviewer]
    print("\n".join([review_commit(review, args.n), *review.facts.paths]))
    return 0


def main() -> int:
    if sys.argv[1:2] == ["commit"]:
        return commit_main(sys.argv[2:])
    parser = argparse.ArgumentParser(description=help_text(),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reviewer", choices=sorted(REVIEWS))
    parser.add_argument("n", type=int)
    parser.add_argument("commit")
    parser.add_argument("agent_id")
    args = parser.parse_args()
    if not re.fullmatch(AGENT_ID, args.agent_id):
        parser.error(mctx("`{agent}` is not an agent id").format(agent=args.agent_id))
    try:
        print(review_tag(REVIEWS[args.reviewer], args.n, args.commit, args.agent_id))
    except Refused as e:
        print_refused(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
