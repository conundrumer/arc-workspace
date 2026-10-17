"""Makes the tag of a review's baseline once the reviewer's run shows the
step call that completes the item of its checklist that the tag needs.
`HELP`, which `--help` prints, gives the usage form and the rules."""

import argparse
import re
import sys
import textwrap
from collections.abc import Iterable

from controlled_markdown import mctx, slug
from engine import checkout
from handbook.checklist import Checklist
from handbook.paths import scripts_importable
from operations.roles import AGENT_ID, Role
from operations.state import Review

scripts_importable()

from run_reads import tool_results  # noqa: E402
from transcripts import transcripts_of  # noqa: E402
from transcript_entries import Entry, Refused, blocks, print_refused, read_entries  # noqa: E402
from tree_reads import main_tree  # noqa: E402

ITEMS = {Review.CODE: "Find the line-level places", Review.LIB: "Find the places"}
"""The item of each reviewer's checklist whose completion the tag needs."""

REVIEWS = {r.role.value: r for r in Review}

HELP = mctx("""
    - The usage form:
        ```
        uv run python scripts/review_tag.py <reviewer> <n> <commit> <agent id>
        ```
    - `<reviewer>` is one of the reviewers this list gives, each with the item of its checklist the tag needs and the prefix of its tag:
        {table}
    - The command reads the transcripts of the reviewer `<agent id>`, and looks for a Bash call whose command runs `scripts/step.py <reviewer>` with that item, and whose tool result holds the text of the item that follows it in the checklist of the main tree as it stands at the command's call, with trailing whitespace stripped from both.
        - Where that checklist holds no such item, the command fails and names the item it wants.
    - Where it finds such a call, it runs `git tag <prefix><m> <commit>` for the least `<m>` from `<n>` up that git accepts, and prints the tag.
    - Where it finds none, it makes no tag, exits non-zero, and prints the step call that completes that item, to be run once that item is done, before the command is run again.
        - Where it finds no transcript of `<agent id>`, it prints that, and that `<agent id>` is the reviewer's own agent id.
    """)

ROW = mctx("- `{reviewer}`: the item `{item}`, the prefix `{prefix}`.")

NO_TRANSCRIPT = mctx("no transcript of the agent `{agent}` is found: give your own agent "
                     "id as `<agent id>`")

NO_STEP = mctx("the transcripts of `{agent}` show no step call that completes the item "
               "`{item}` of the checklist as it stands now: once you have done that "
               "item, run `uv run python scripts/step.py {reviewer} {id}`, "
               "do each item from the one it prints up to this command, then run this "
               "command again")

STEP_CALL = re.compile(r"""scripts/step\.py\s+(\S+)\s+("[^"]*"|'[^']*'|[^\s;|&)]+)""")
"""A call of the step command in a Bash command: its agent and its first
argument."""


def runs_step(command: str, agent: Role, item: str) -> bool:
    return any(m[1] == agent.value and slug(m[2].strip("'\"")) == slug(item)
               for m in STEP_CALL.finditer(command))


def step_done(entries: Iterable[Entry], agent: Role, item: str, following: str) -> bool:
    """The step call `HELP` gives, of `item` of the checklist of `agent`,
    whose result holds `following`, the text the step command prints for
    the item after it."""
    entries = list(entries)
    calls = {str(b.get("id")) for e in entries if e.get("type") == "assistant"
             for b in blocks(e, "tool_use") if b.get("name") == "Bash"
             and runs_step(str((b.get("input") or {}).get("command", "")), agent, item)}
    want = following.rstrip()
    return any(call in calls and want in result.rstrip()
               for e in entries for call, _, result in tool_results(e))


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


def review_tag(review: Review, n: int, commit: str, agent: str) -> str:
    paths = transcripts_of(agent)
    if not paths:
        raise Refused(NO_TRANSCRIPT.format(agent=agent))
    reviewer, item = review.role, ITEMS[review]
    following = Checklist(reviewer.value, main_tree()).after(item)
    if not step_done((e for p in paths for e in read_entries(p)), reviewer, item, following):
        raise Refused(NO_STEP.format(agent=agent, item=item, reviewer=reviewer.value, id=slug(item)))
    return tag(review, n, commit)


def help_text() -> str:
    rows = "\n".join(ROW.format(reviewer=r.role.value, item=ITEMS[r], prefix=r.value) for r in Review)
    return textwrap.dedent(HELP).format(table=textwrap.indent(rows, " " * 4).lstrip())


def main() -> int:
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
