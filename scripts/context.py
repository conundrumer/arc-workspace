"""Print the handbook and the other contexts the repo's readers get.
The `handbook` package renders them, and `--help` prints HELP."""

import json
import os
import signal
import sys

from controlled_markdown import mctx
from handbook.agents import (agent_renderings, analyze_next_rendering,
                             unlisted_agents)
from handbook.context import (codex_renderings, role_text, section_text,
                              session_text, workflow_bundle, write_lib_output)
from handbook.coordinator_document import (coordinator_rendering,
                                           session_start_text)
from handbook.generated import MANIFEST
from handbook.libcheck import check
from handbook.paths import REPO_ROOT
from handbook.reader_diffs import (context_at, context_diff, contexts_diff,
                                   held_update_diff, update_diff)
from handbook.readers import context_text, contexts_text, reader_named

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/context.py                  # print the handbook
        uv run python scripts/context.py --help | -h      # print this text
        uv run python scripts/context.py --write          # write the generated files
        uv run python scripts/context.py session-start    # the session-start hook's text
        uv run python scripts/context.py role <name>      # print one role's prompt
        uv run python scripts/context.py section <where>  # print one section
        uv run python scripts/context.py workflow <name>  # print every role, as JSON
        uv run python scripts/context.py contexts         # list the readers
        uv run python scripts/context.py contexts --diff <commit>  # the readers whose context or linked sections changed since a commit
        uv run python scripts/context.py context <reader> [args]  # one reader's context
        uv run python scripts/context.py context --at <commit> <reader> [args]    # that context at a commit
        uv run python scripts/context.py context --diff <commit> <reader> [args]  # its diff since a commit
        uv run python scripts/context.py context --update <commit> <commit> <reader> [args]  # what a running reader gets
        uv run python scripts/context.py context --update --held <file> <file> <commit> <reader> [args]  # what a subagent gets at its first update
        ```
    - The items below say what each form does.
    - With no argument, the command prints the handbook, the passes a session runs, and the lib. That form and `--write` also write the lib's interface files: the `.md` beside each lib source, which the handbook's lib index points to.
    - `--write` first checks the lib's sources, prints what the checks find and exits 1 when they find anything. Otherwise it writes the files below, which git ignores. A session reads them only when they were written before it started.
        - One agent under `.claude/agents/` per document that stands directly in `prompts/agents/`, in no subdirectory, and whose text opens with front matter, with the context its document composes as its system prompt, and `.claude/agents/.manifest`, which lists each generated file written in the checkout.
        - `.claude/analyze-next.md`, the steps the `analyze` agent reads after it writes the concept.
        - `.claude/coordinator.md`, the document of the coordinator, the session the user talks with, rendered from `prompts/agents/notes/coordinator.md`.
        - The files a codex session on the repo reads: `AGENTS.md`, [Codex on arc-workspace](prompts/codex.md) rendered, and `.codex/config.toml`, with the main tree's `docs/codex-style.md` as its developer instructions.
    - Each form that writes a generated file in the checkout, other than `session-start`, first checks that git ignores each one it writes there. Where git does not ignore one, the form writes none, names each such file and `.gitignore`, and exits 1.
    - `--write` then removes each file that manifest lists and no source renders any more, where git ignores it and it has not changed since it was written, and prints it after `removed`. It names on stderr each listed file it leaves in place, with the reason, and each agent file that has no document and that the manifest does not list.
    - `session-start` is the command the session-start hook in `.claude/settings.json` runs. Where Claude Code started the session for the user to talk with, it writes `.claude/coordinator.md` and prints it, and in a `claude -p` session it prints nothing. Where that write fails, as where git does not ignore that file, it prints the failure and then the document, and exits 0. Where it printed the document, it then records the checkout's `HEAD` for the coordinator of the session the hook input on stdin names at a `startup` or a `clear` source, and at a `compact` or a `resume` source only where the coordinator has no record yet, as `scripts/reader_commits.py` gives.
    - `role <name>` prints a role's prompt.
    - `section <where>` prints one section in full, for a reader whose handbook shows that section as a heading alone. `<where>` takes three forms:
        ```
        section 'Solver file#Header'                 # chapter title, section heading
        section docs/handbook/procedure.md#develop   # a link as a document carries it
        section 'programs/lib/cells.dl#Tile2D'       # a lib source, one declaration in it
        ```
    - `workflow <name>` prints, as JSON, the text of every role under `prompts/roles/`, from which a run of that workflow takes the ones it uses. A name with no script under `.claude/workflows/` is an error.
    - `contexts` lists each reader the `context` command knows, with the argument it takes and that argument's values.
    - `contexts --diff <commit>` prints, one per line as a `context` command line, each reader with its argument whose context the change since the commit alters, or whose context leads by links to a section whose text the change alters, and nothing for any other reader. The commit's tree is written once, and its readers render there.
        - A reader both sides define is altered where its context at the commit, rendered as `context --at` renders it, differs from its context in the worktree. A render at the commit that fails is an error.
        - A reader only one side defines is altered, and its line ends in `(added)` where the worktree defines it and in `(removed)` where the commit does. The commit's readers are the ones its own `contexts` lists.
        - A walk of links starts at a link in the context to a document of the set `[tool.controlled_markdown]` in `pyproject.toml` names, and each later link stands in the target of the one before, on either side. A walk may pass a target twice. A link that names no heading targets the whole document, and a link to another file ends no walk.
        - Under a reader's line, an indented line names each section a walk from its context, on either side, reaches, whose text the change alters, as the checkout's code renders that section on each side, a section a side lacks as empty. A section is left out where the reader's context diff already removes and adds each of its changed lines. A section that lies, by heading depth in its document on each side that has it, within another section or the whole document listed for that reader is left out too.
        - After those lines, one indented line `<target> via <source>` stands for each link on a walk from the context, on either side, to such a section, a section left out within another included, once for that reader, sorted: a line of `<source>` links to `<target>`, and `<source>` is `context` where the link stands in the context.
        - The line of a reader whose context is the same on both sides and leads by links to such a section ends in `(linked)`.
    - `context <reader> [args]` prints that reader's context, each part under a `==== <what follows> ====` line and one blank line, then the part's text, where a definition printed above stands as its `==== <path>, the definition printed above ====` line alone.
    - `context --at <commit> <reader> [args]` prints that context as the commit's tree renders it, with the commit's own code, and `context --diff <commit> <reader> [args]` prints the unified diff from that render to the one of the worktree, then the unified diff of each section that `contexts --diff` lists under that reader, under a line that names that section alone, then the link lines it lists there. Where only one side defines the reader, as `contexts --diff` marks it, `--diff` takes the other side's context as empty, so an added reader's diff gains every line and a removed one's loses every line. Any other failed render is an error. Neither form changes the worktree: git writes the commit's tree into a temporary directory, and the render runs there.
    - `context --update <commit> <commit> <reader> [args]` prints what `context --diff` prints for that reader since the first commit, then the unified diff of `CLAUDE.md`, the project instructions Claude Code gives each session and subagent beside its context, since the second commit, a side that has no `CLAUDE.md` as an empty text, then the diff of each section links from either lead to, each under a line that names it alone, then the link lines, as `contexts --diff` gives them, of the walks from the context and of those from `CLAUDE.md`, each once, sorted, with `<source>` `CLAUDE.md` where the link stands in `CLAUDE.md`. A section links from the context lead to runs from the first commit. A section links from `CLAUDE.md` lead to runs from the first commit where it descends from the second, and from the second otherwise. A section whose diff both give with the same text on each side stands once, and `CLAUDE.md` stands only as itself, whole, with each section of it whose diff runs from the second commit, and the walks to those give no link lines. Of the other sections whose diffs run from the same commit, one that lies within another or within a whole document, as `contexts --diff` gives it, has no diff of its own, so each changed line stands in one diff.
    - `context --update --held <file> <file> <commit> <reader> [args]` prints what `context --update` prints for that reader, with the context's and `CLAUDE.md`'s diffs run from the texts the two files hold, those the harness gave the reader at its launch, in place of a commit, under a line that names each as at `launch`. The context's before side is that reader's context at the commit, with its first marked section, the reader's own definition, holding the first file's text, so each later marked section runs from the commit. The second file's text gets a final newline where it has none, as `CLAUDE.md` has. Each section links from either lead to runs from the commit.
    - Each hunk header line of the diffs `context --diff` and `context --update` print ends in the heading lines whose sections hold the hunk's first line, outermost first and joined by ` > `, as the text that line stands in renders them. A heading line in the hunk starts a section that holds each line after it up to the next heading line with as many `#` or fewer.
    """)

# The lines of the usage block of HELP, which the command exits with on
# arguments of no known form, and on a form given too few arguments.
USAGE = "\n".join(line.strip() for line in HELP.split("```")[1].splitlines()
                  if line.strip())

# The forms of the `context` command that render at a commit.
AT_COMMIT = {"--at": context_at, "--diff": context_diff}

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
        rest = [*agent_renderings(), analyze_next_rendering(),
                coordinator_rendering(), *codex_renderings()]
        unlisted = unlisted_agents()
        written, done = write_lib_output(rest, stale=True)
        for out in written:
            print(out.relative_to(REPO_ROOT))
        for out in done.removed:
            print(f"removed {out.relative_to(REPO_ROOT)}")
        for left in done.left:
            print(f"{left.path.relative_to(REPO_ROOT)}: in {MANIFEST} and "
                  f"rendered by no source, left in place: {left.why.value}",
                  file=sys.stderr)
        for out in unlisted:
            print(f"{out.relative_to(REPO_ROOT)}: no document under "
                  f"prompts/agents/ and not in {MANIFEST}; left in place",
                  file=sys.stderr)
    elif args == ["session-start"]:
        text = session_start_text(os.environ)
        print(text, end="", flush=True)
        from hook_entry import run_hook
        from reader_commits import RECORD_FAILED, start_session

        run_hook("session-start", RECORD_FAILED,
                 lambda hook: start_session(hook, coordinator=bool(text)))
    elif len(args) == 2 and args[0] == "role":
        print(role_text(args[1]), end="")
    elif len(args) == 2 and args[0] == "section":
        print(section_text(args[1]), end="")
    elif len(args) == 2 and args[0] == "workflow":
        print(json.dumps(workflow_bundle(args[1])))
    elif args == ["contexts"]:
        print(contexts_text(), end="")
    elif len(args) == 3 and args[:2] == ["contexts", "--diff"]:
        print(contexts_diff(args[2]), end="")
    elif (len(args) >= 4 and args[0] == "context"
          and args[1] in AT_COMMIT):
        print(AT_COMMIT[args[1]](args[2], args[3], args[4:]), end="")
    elif len(args) >= 7 and args[:3] == ["context", "--update", "--held"]:
        from pathlib import Path

        print(held_update_diff(Path(args[3]).read_text(), Path(args[4]).read_text(),
                               args[5], args[6], args[7:]), end="")
    elif len(args) >= 5 and args[:2] == ["context", "--update"]:
        print(update_diff(args[2], args[3], args[4], args[5:]), end="")
    elif (len(args) >= 2 and args[0] == "context"
          and not args[1].startswith("--")):
        print(context_text(reader_named(args[1]), args[2:]), end="")
    elif args:
        sys.exit(f"usage:\n{USAGE}")
    else:
        write_lib_output()
        print(session_text(), end="")
