"""The read check of the PreToolUse hook: the whole-file reads of a Bash
command that another command is joined to, where the files' text is long
enough that a failure of the other command cuts its middle from the call's
output. The docstring of `pending_wait_hook` states the cases it denies and
the ones it allows."""

import re
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from shell_parse import Command, Operator, Unparsed, parse

FAILED_OUTPUT_CAP = 10000 + 1024
"""The characters of a failed command's output the Bash tool keeps whole:
its cap and the slack past it, as of Claude Code 2.1.290."""

UTF8_MAX_BYTES = 4
"""The most bytes a UTF-8 decode turns into one character."""

CAT_OPTIONS = frozenset("nbveEtTAu")
"""The options of `cat` that never shorten its output."""

PIPES = frozenset({Operator.PIPE, Operator.PIPE_ALL})

ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")

DIRECTORY_CHANGERS = frozenset({"cd", "pushd", "popd"})

SHELL_CHANGERS = frozenset({
    "exec", "eval", "source", ".", "alias", "unalias", "builtin", "command",
    "enable", "disable", "hash", "unhash", "rehash", "functions", "autoload",
    "unfunction", "export", "typeset", "declare", "readonly", "local",
    "integer", "float", "unset", "set", "setopt", "unsetopt", "emulate",
    "trap"})
"""Commands that can change what a later `cat` resolves to, where the
shell's output goes, or the working directory. A command with an assignment
or a name that is not literal before it can too."""


def check(hook: dict[str, Any], notes: list[str]) -> str | None:
    """The reason to deny the Bash call `hook` gives, where it joins another
    command to a long read. A command line the parse refuses goes to
    `notes`."""
    if hook["tool_name"] != "Bash":
        return None
    try:
        files = long_reads(hook["tool_input"]["command"], Path(hook["cwd"]))
    except Unparsed as e:
        notes.append(f"allowed: the command line holds {e}, which the read "
                     "check does not split")
        return None
    if not files:
        return None
    return mctx(
        "Blocked: this command reads {files} whole and joins another command "
        "to that read, and where the other command fails, the Bash tool cuts "
        "the middle of the text from the output, so run the read as a command "
        "of its own."
    ).format(files=", ".join(f"`{f}`" for f in files))


def long_reads(line: str, cwd: Path) -> list[Path]:
    """The files of each long read in `line` joined to another command,
    with relative operands taken against `cwd`. Raises `Unparsed` where
    `line` does not parse."""
    commands = parse(line)
    pipelines = sum(1 for c in commands if c.words and c.operator not in PIPES)
    if pipelines < 2:
        return []
    out: list[Path] = []
    moved = False
    for c in commands:
        if not c.words:
            continue
        first = c.words[0]
        name = first.text
        if (not first.literal or name in SHELL_CHANGERS
                or ASSIGNMENT.match(name)):
            break
        if name in DIRECTORY_CHANGERS:
            moved = True
        elif name == "cat":
            files = read_files(c, cwd, moved)
            if files and text_length(files) > FAILED_OUTPUT_CAP:
                out += files
    return out


def read_files(c: Command, cwd: Path, moved: bool) -> list[Path] | None:
    """The files a `cat` command `c` writes whole to the call's output, or
    None where any of its arguments or redirections leaves that unknown."""
    if 1 in c.redirected or c.operator in PIPES:
        return None
    files: list[Path] = []
    options = True
    for w in c.words[1:]:
        if not w.literal:
            return None
        if options and w.text == "--":
            options = False
        elif options and w.text.startswith("-") and w.text != "-":
            if not set(w.text[1:]) <= CAT_OPTIONS:
                return None
        else:
            path = Path(w.text)
            if not path.is_absolute():
                if moved:
                    return None
                path = cwd / path
            if not path.is_file():
                return None
            files.append(path)
    return files or None


def text_length(files: list[Path]) -> int:
    """The characters of the text of `files` together, counted no further
    than the cap needs."""
    total = 0
    for f in files:
        size = f.stat().st_size
        if size <= FAILED_OUTPUT_CAP * UTF8_MAX_BYTES:
            total += len(f.read_bytes().decode("utf-8", errors="replace"))
        else:
            total += size // UTF8_MAX_BYTES
    return total
