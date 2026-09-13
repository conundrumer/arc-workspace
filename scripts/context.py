"""Print the handbook: the solver docs and the lib as a solver session reads them.
dl.context renders it.

    uv run python scripts/context.py            # print the handbook
    uv run python scripts/context.py --write    # write the handbook agent

`--write` writes `.claude/agents/handbook.md`: the agent that runs a role
under `.claude/roles/` with the handbook as its system prompt. It also writes
`.claude/agents/handbook-principles.md`, the same agent over a handbook that
carries principles.md unabridged. The files are not tracked; write them before
a session that spawns an agent starts.
"""

import sys

from dl.context import principles_agent_path, render, write_agent

if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        path = write_agent()
        for out in (path, principles_agent_path(path)):
            print(out.relative_to(out.parents[2]))
    elif sys.argv[1:]:
        sys.exit(f"usage: {sys.argv[0]} [--write]")
    else:
        print(render(), end="")
