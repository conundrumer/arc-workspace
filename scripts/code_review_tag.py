"""Makes a code review's `code-review/<n>` tag once the reviewer's run
shows a read of its second stage. `HELP`, which `--help` prints, gives the
usage form and the rules."""

import argparse
import re
import sys
import textwrap
from collections.abc import Iterable
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.agents import next_file
from handbook.paths import scripts_importable
from operations.roles import AGENT_ID, Role
from operations.state import code_review_tag as tag_name

scripts_importable()

from run_reads import tool_results  # noqa: E402
from transcripts import transcripts_of  # noqa: E402
from transcript_entries import Entry, Refused, blocks, read_entries  # noqa: E402
from tree_reads import main_tree  # noqa: E402

HELP = mctx("""
    - The usage form:
        ```
        uv run python scripts/code_review_tag.py <n> <commit> <agent id>
        ```
    - The command reads the transcripts of the code reviewer `<agent id>`, and looks for a Bash call whose command names `.claude/code-reviewer-next.md` and whose tool result holds the whole text of the rendered `.claude/code-reviewer-next.md` in the main tree as it stands at the command's call, with trailing whitespace stripped from both.
    - Where it finds one, it runs `git tag code-review/<m> <commit>` for the least `<m>` from `<n>` up that git accepts, and prints the tag.
    - Where it finds none, it makes no tag, exits non-zero, and prints that the second stage is to be read, and its places found and filed, before the command is run again.
        - Where it finds no transcript of `<agent id>`, it prints that, and that `<agent id>` is the code reviewer's own agent id.
    """)

REFUSED = mctx("refused: {reason}")

NO_TRANSCRIPT = mctx("no transcript of the agent `{agent}` is found: give your own agent "
                     "id as `<agent id>`")

NO_READ = mctx("the transcripts of `{agent}` show no read of the second stage as it "
               "stands now: read it by the `cat` line of your documents, find and file its "
               "places, then run this command again")


def second_stage() -> Path:
    return next_file(Role.CODE_REVIEWER, checkout.claude_of(main_tree()))


def read_whole(entries: Iterable[Entry], name: str, text: str) -> bool:
    """The read `HELP` gives, of the file `name` with the text `text`."""
    entries = list(entries)
    calls = {str(b.get("id")) for e in entries if e.get("type") == "assistant"
             for b in blocks(e, "tool_use") if b.get("name") == "Bash"
             and name in str((b.get("input") or {}).get("command", ""))}
    whole = text.rstrip()
    return any(call in calls and whole in result.rstrip()
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
    stage = second_stage()
    name = f"{checkout.claude_of(Path())}/{stage.name}"
    if not read_whole((e for p in paths for e in read_entries(p)), name, stage.read_text()):
        raise Refused(NO_READ.format(agent=agent))
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
        print(REFUSED.format(reason=e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
