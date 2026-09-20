"""Print the handbook: the solver docs and the lib as a solver session reads them.
dl.context renders it.

    uv run python scripts/context.py            # print the handbook
    uv run python scripts/context.py --write    # write the handbook agents
    uv run python scripts/context.py role <name>  # print one role's prompt
    uv run python scripts/context.py section <doc>#<slug>  # print one section

The first two forms write the lib's interface files, the `.md` beside each of
its sources, which the handbook's lib index points at. `--write` also writes
the agents that run a role under `prompts/roles/` with the handbook as their
system prompt: `.claude/agents/handbook.md`, over the handbook with the lib
and some docs as an index, and `.claude/agents/handbook-expanded.md`, over
the handbook with the lib's full interface and every doc in full. It also
writes the files a codex session on the repo reads: `AGENTS.md`, the handbook
with the project CLAUDE.md, and `.codex/config.toml`, with
`docs/codex-style.md` as the developer instructions. The files are not
tracked; write them before a session that spawns an agent starts, and before a
codex session starts.

`role <name>` prints `prompts/roles/<name>.md` as a session spawning that role
reads it: the agent's name on the first line, then the prompt's opening text.

`section <doc>#<slug>` prints one section of `docs/handbook/<doc>.md` in full,
for a reader whose handbook shows that section as a heading alone.

`workflow <name>` prints what a workflow run needs, as JSON: the text of each
role it reaches. The script holds its own briefs and its own return schemas,
each wrapped in `mctx`, so the check reads their words where they stand.
"""

import json
import sys

from dl.context import (
    expanded_agent_path,
    role_text,
    section_text,
    session_text,
    workflow_bundle,
    write_agent,
    write_codex,
    write_interfaces,
)
from dl.paths import REPO_ROOT

if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--write"]:
        path = write_agent()
        for out in (path, expanded_agent_path(path), *write_codex()):
            print(out.relative_to(REPO_ROOT))
    elif len(args) == 2 and args[0] == "role":
        print(role_text(args[1]), end="")
    elif len(args) == 2 and args[0] == "section":
        print(section_text(args[1]), end="")
    elif len(args) == 2 and args[0] == "workflow":
        print(json.dumps(workflow_bundle(args[1])))
    elif args:
        sys.exit(f"usage: {sys.argv[0]} "
                 f"[--write | role <name> | section <doc>#<section> "
                 f"| workflow <name>]")
    else:
        write_interfaces()
        print(session_text(), end="")
