"""Makes a code review's `code-review/<n>` tag once the reviewer's run
shows the step call that completes its line-level step. `HELP`, which
`--help` prints, gives the usage form and the rules."""

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
from operations.state import code_review_tag as tag_name

scripts_importable()

from run_reads import tool_results  # noqa: E402
from transcripts import transcripts_of  # noqa: E402
from transcript_entries import Entry, Refused, blocks, print_refused, read_entries  # noqa: E402
from tree_reads import main_tree  # noqa: E402

LINE_LEVEL = "Find the line-level places"
"""The item of the code reviewer's checklist whose completion the tag
needs."""

HELP = mctx("""
    - The usage form:
        ```
        uv run python scripts/code_review_tag.py <n> <commit> <agent id>
        ```
    - The command reads the transcripts of the code reviewer `<agent id>`, and looks for a Bash call whose command runs `scripts/step.py code-reviewer` with the item `{item}`, and whose tool result holds the text of the item that follows it in the checklist of the main tree as it stands at the command's call, with trailing whitespace stripped from both.
        - Where that checklist holds no such item, the command fails and names the item it wants.
    - Where it finds such a call, it runs `git tag code-review/<m> <commit>` for the least `<m>` from `<n>` up that git accepts, and prints the tag.
    - Where it finds none, it makes no tag, exits non-zero, and prints the step call that completes the line-level step, to be run once the line-level places are found, before the command is run again.
        - Where it finds no transcript of `<agent id>`, it prints that, and that `<agent id>` is the code reviewer's own agent id.
    """).format(item=LINE_LEVEL)

NO_TRANSCRIPT = mctx("no transcript of the agent `{agent}` is found: give your own agent "
                     "id as `<agent id>`")

NO_STEP = mctx("the transcripts of `{agent}` show no step call that completes the item "
               "`{item}` of the checklist as it stands now: once you have found the "
               "line-level places, run `uv run python scripts/step.py {reviewer} {id}`, "
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


def tag(n: int, commit: str) -> str:
    """The tag `HELP` gives; a failure other than a taken name is
    `GitFailed`."""
    root = checkout.ROOT
    m = n
    while True:
        name = tag_name(m)
        done = checkout.git(root, "tag", name, commit)
        if done.returncode == 0:
            return name
        if checkout.git_answer(root, "rev-parse", "-q", "--verify",
                               f"refs/tags/{name}").returncode != 0:
            raise checkout.GitFailed(root, ("tag", name, commit), done.stderr)
        m += 1


def code_review_tag(n: int, commit: str, agent: str) -> str:
    paths = transcripts_of(agent)
    if not paths:
        raise Refused(NO_TRANSCRIPT.format(agent=agent))
    reviewer = Role.CODE_REVIEWER
    following = Checklist(reviewer.value, main_tree()).after(LINE_LEVEL)
    if not step_done((e for p in paths for e in read_entries(p)), reviewer, LINE_LEVEL,
                     following):
        raise Refused(NO_STEP.format(agent=agent, item=LINE_LEVEL, reviewer=reviewer.value,
                                     id=slug(LINE_LEVEL)))
    return tag(n, commit)


def main() -> int:
    parser = argparse.ArgumentParser(description=textwrap.dedent(HELP),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("n", type=int)
    parser.add_argument("commit")
    parser.add_argument("agent_id")
    args = parser.parse_args()
    if not re.fullmatch(AGENT_ID, args.agent_id):
        parser.error(mctx("`{agent}` is not an agent id").format(agent=args.agent_id))
    try:
        print(code_review_tag(args.n, args.commit, args.agent_id))
    except Refused as e:
        print_refused(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
