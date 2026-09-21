"""Print the handbook and the other contexts the repo's readers get.
dl.context renders them.

    uv run python scripts/context.py                  # print the handbook
    uv run python scripts/context.py --help | -h      # print this text
    uv run python scripts/context.py --write          # write the generated files
    uv run python scripts/context.py role <name>      # print one role's prompt
    uv run python scripts/context.py section <where>  # print one section
    uv run python scripts/context.py workflow <name>  # print every role, as JSON
    uv run python scripts/context.py contexts         # list the readers
    uv run python scripts/context.py context <reader> [args]  # one reader's context

With no argument the command prints the handbook, the passes a session runs,
and the lib. That form and `--write` also write the lib's interface files, the
`.md` beside each of its sources, which the handbook's lib index points at.

`--write` writes the agents that run a role under `prompts/roles/` with the
handbook as their system prompt: `.claude/agents/handbook.md`, over the
handbook with the lib and some docs as an index, and
`.claude/agents/handbook-expanded.md`, over the handbook with the lib's full
interface and every doc in full. It also writes the files a codex session on
the repo reads: `AGENTS.md`, [Codex on arc-workspace](prompts/codex.md)
rendered, and `.codex/config.toml`, with `docs/codex-style.md` as the
developer instructions. The files are not tracked; write them before a
session that spawns an agent starts, and before a codex session starts.

`role <name>` prints `prompts/roles/<name>.md` as a session spawning that role
reads it: the agent's name on the first line, then the prompt's opening text.

`section <where>` prints one section in full, for a reader whose handbook
shows that section as a heading alone. `<where>` takes three forms:

    section 'Solver file#Header'           # chapter heading, section heading
    section docs/handbook/procedure.md#develop   # the link a document carries
    section 'programs/lib/cells.dl#Tile2D'  # one lib declaration

The first form names the chapter by the title a render shows and the section
by the heading text, which the render slugifies. The second form is the link
form a document carries. The third form names a lib source and one component
declared in it.

`workflow <name>` prints what a workflow run needs, as JSON: the text of every
role under `prompts/roles/`. A run picks the ones it reaches. The script holds
its own briefs and its own return schemas, each wrapped in `mctx`, so the
check reads their words where they stand. A name with no script under
`.claude/workflows/` is an error, and the message names the workflows that
exist.

`contexts` lists every reader the `context` command knows, one per line, with
the argument that reader takes and the values the argument takes. `context
<reader> [args]` prints that reader's context, each part under a
`==== <what follows> ====` marker line that says what the part is and when it
arrives.
"""

import json
import signal
import sys

from dl.context import (
    context_text,
    contexts_text,
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

# A print form run under `head` ends when the reader closes the pipe.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] in ("--help", "-h"):
        print(__doc__, end="")
    elif args == ["--write"]:
        interfaces = write_interfaces()
        path = write_agent()
        for out in (*interfaces, path, expanded_agent_path(path),
                    *write_codex()):
            print(out.relative_to(REPO_ROOT))
    elif len(args) == 2 and args[0] == "role":
        print(role_text(args[1]), end="")
    elif len(args) == 2 and args[0] == "section":
        print(section_text(args[1]), end="")
    elif len(args) == 2 and args[0] == "workflow":
        print(json.dumps(workflow_bundle(args[1])))
    elif args == ["contexts"]:
        print(contexts_text(), end="")
    elif args and args[0] == "context":
        print(context_text(args[1] if args[1:] else "", args[2:]), end="")
    elif args:
        sys.exit(f"usage: {sys.argv[0]} "
                 f"[--help | --write | role <name> | section <where> "
                 f"| workflow <name> | contexts | context <reader> [args]]")
    else:
        write_interfaces()
        print(session_text(), end="")
