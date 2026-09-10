"""Print the handbook: the solver docs and lib.dl as a solver session reads them.
dl.context renders it.

    uv run python scripts/context.py            # print the handbook
    uv run python scripts/context.py --write    # write the handbook agent

`--write` writes `.claude/agents/handbook.md`: the agent that runs a role
under `.claude/roles/` with the handbook as its system prompt. The file is
not tracked; write it before a session that spawns the agent starts.
"""

import sys

from dl.context import AGENT_PATH, render, write_agent

if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        write_agent()
        print(AGENT_PATH.relative_to(AGENT_PATH.parents[2]))
    elif sys.argv[1:]:
        sys.exit(f"usage: {sys.argv[0]} [--write]")
    else:
        print(render(), end="")
