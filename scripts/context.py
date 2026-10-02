"""Print the handbook and the other contexts the repo's readers get.
handbook.context renders them, and `--help` prints HELP."""

import json
import signal
import sys

from controlled_markdown import mctx
from handbook.context import (
    context_text,
    contexts_text,
    agent_paths,
    role_text,
    section_text,
    session_text,
    workflow_bundle,
    write_agent,
    write_analyze_next,
    write_codex,
    write_interfaces,
)
from handbook.libcheck import check
from handbook.paths import REPO_ROOT

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/context.py                  # print the handbook
        uv run python scripts/context.py --help | -h      # print this text
        uv run python scripts/context.py --write          # write the generated files
        uv run python scripts/context.py role <name>      # print one role's prompt
        uv run python scripts/context.py section <where>  # print one section
        uv run python scripts/context.py workflow <name>  # print every role, as JSON
        uv run python scripts/context.py contexts         # list the readers
        uv run python scripts/context.py context <reader> [args]  # one reader's context
        ```
    - With no argument, the command prints the handbook, the passes a session runs, and the lib. That form and `--write` also write the lib's interface files: the `.md` beside each lib source, which the handbook's lib index points to.
    - `--write` first checks the lib's sources, prints what the checks find and exits 1 when they find anything. Otherwise it writes the files below, which git does not track. A session reads them only when they were written before it started.
        - One agent under `.claude/agents/` per document under `prompts/agents/`, with the context its document composes as its system prompt.
        - `.claude/analyze-next.md`, the steps the `analyze` agent reads after it writes the concept.
        - The files a codex session on the repo reads: `AGENTS.md`, [Codex on arc-workspace](prompts/codex.md) rendered, and `.codex/config.toml`, with `docs/codex-style.md` as its developer instructions.
    - `role <name>` prints a role's prompt.
    - `section <where>` prints one section in full, for a reader whose handbook shows that section as a heading alone. `<where>` takes three forms:
        ```
        section 'Solver file#Header'                 # chapter title, section heading
        section docs/handbook/procedure.md#develop   # a link as a document carries it
        section 'programs/lib/cells.dl#Tile2D'       # a lib source, one declaration in it
        ```
    - `workflow <name>` prints, as JSON, the text of every role under `prompts/roles/`, from which a run of that workflow takes the ones it uses. A name with no script under `.claude/workflows/` is an error.
    - `contexts` lists each reader the `context` command knows, with the argument it takes and that argument's values.
    - `context <reader> [args]` prints that reader's context, each part under a `==== <what follows> ====` line.
    """)

# A print form run under `head` ends when the reader closes the pipe.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] in ("--help", "-h"):
        print(HELP)
    elif args == ["--write"]:
        if findings := check():
            print("\n".join(findings))
            sys.exit(1)
        interfaces = write_interfaces()
        write_agent()
        agents = [out for _name, out in agent_paths()]
        for out in (*interfaces, *agents, write_analyze_next(),
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
