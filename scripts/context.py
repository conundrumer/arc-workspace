"""Print the handbook: the solver docs and the lib as a solver session reads them.
dl.context renders it.

    uv run python scripts/context.py            # print the handbook
    uv run python scripts/context.py --write    # write the handbook agents

Both forms write the lib's interface files, the `.md` beside each of its
sources, which the handbook's lib index points at. `--write` also writes the
agents that run a role under `.claude/roles/` with the handbook as their
system prompt: `.claude/agents/handbook.md`, over the handbook with the lib
as an index, and `.claude/agents/handbook-expanded.md`, over the handbook
with the lib's full interface. The files are not tracked; write them before
a session that spawns an agent starts.
"""

import sys

from dl.context import expanded_agent_path, render, write_agent, write_interfaces

if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        path = write_agent()
        for out in (path, expanded_agent_path(path)):
            print(out.relative_to(out.parents[2]))
    elif sys.argv[1:]:
        sys.exit(f"usage: {sys.argv[0]} [--write]")
    else:
        write_interfaces()
        print(render(), end="")
