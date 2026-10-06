"""The labels of the calls of an agent's transcript: the command of a
call, and the programs a Bash command runs, with the label of the known
command or of the program it runs."""

import re
import shlex
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

from cli import command_args
from cli.parser import parser as run_dl_parser
from controlled_markdown import mctx
from file_ticket import TICKET_HEAD

WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")
AGENT_TOOLS = ("Agent", "Task")
KNOWN = {"gate.py": "gate", "merge_change.py": "merge_change.py",
         "materialize.py": "materialize.py", "pytest": "pytest",
         "pyright": "pyright"}
RUN_DL = "run_dl.py"
SETUP = {"cd", "echo", "export", "set", "true", ":", "printf", "date",
         "source", ".", "uptime", "[", "[[", "test"}
WRAPPERS = {"timeout", "time", "nice", "env", "exec", "command", "sudo", "uv",
            "run"}
# Options that take the next word as their value, by the wrapper they follow.
# A wrapper not listed takes no such option.
UV_OPTIONS = frozenset({"--env-file", "--with", "--python", "-p", "--project",
                        "--directory", "--package", "--extra", "--group",
                        "--from"})
WRAPPER_OPTIONS = {"timeout": frozenset({"-s", "-k"}),
                   "env": frozenset({"-u", "--unset", "-C", "--chdir", "-S",
                                     "--split-string"}),
                   "uv": UV_OPTIONS, "run": UV_OPTIONS}
OPENERS = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "("}
CLOSERS = {"for", "case", "done", "fi", "esac", "}"}
POLL = "poll"
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2[ \t]*(?=\n|$)",
                     re.S)
REDIRECT = re.compile(r"\d*>&\d+|&>")
ASSIGNMENT = re.compile(r"^(\w+)=(.*)$", re.S)
VARIABLE = re.compile(r"\$\{(\w+)\}|\$(\w+)")


def segment_program(words: list[str]) -> tuple[str | None, list[str]]:
    """The program a simple command runs, and its arguments, past
    environment assignments, wrappers such as timeout and uv run, and an
    interpreter given a script or module."""
    toks = [t for t in (t.strip("(){}") for t in words) if t]
    i, interp, wrapper = 0, None, None
    while i < len(toks):
        t = toks[i]
        base = Path(t).name
        if interp is None and base in WRAPPERS:
            wrapper, i = base, i + 1
        elif interp is None and (ASSIGNMENT.match(t)
                                 or re.fullmatch(r"\d+[smh]?", t)):
            i += 1
        elif interp is None and re.fullmatch(r"python[\d.]*|bash|sh|zsh", base):
            interp, i = base, i + 1
        elif interp and t == "-c":
            return interp, toks[i + 1:]
        elif interp and t == "-m" and i + 1 < len(toks):
            return toks[i + 1], toks[i + 2:]
        elif interp and t.startswith("-") and t != "-":
            i += 1
        elif interp and t != "-" and not t.startswith("<"):
            return base, toks[i + 1:]
        elif interp:
            return interp, toks[i + 1:]
        elif wrapper and t in WRAPPER_OPTIONS.get(wrapper, frozenset()):
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            return base, toks[i + 1:]
    return interp, []


def shell_segments(cmd: str) -> list[str]:
    """The simple commands of a shell command line: split at ;, &, |, newlines,
    and the openings of $( and backquotes, outside quotes."""
    segs: list[str] = []
    cur: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if quote:
            if c == quote:
                quote = None
            elif c == "\\" and quote == '"':
                cur.append(c)
                i += 1
                c = cmd[i] if i < len(cmd) else ""
            cur.append(c)
        elif c in "'\"":
            quote = c
            cur.append(c)
        elif c == "\\":
            cur.append(cmd[i:i + 2])
            i += 1
        elif c in ";&|\n`" or cmd.startswith("$(", i):
            segs.append("".join(cur))
            cur = []
            i += 1 if c == "$" else 0
        else:
            cur.append(c)
        i += 1
    segs.append("".join(cur))
    return segs


def split_words(seg: str) -> list[str]:
    """The words of a simple command, with quotes removed and comments
    dropped, or its blank-separated words where its quotes do not pair."""
    try:
        return shlex.split(seg, comments=True)
    except ValueError:
        return [w.strip("'\"") for w in seg.split()]


def simple_commands(cmd: str) -> Iterator[list[str]]:
    """The words of each simple command of a Bash command line, past the
    keywords that open it, with the values of the shell variables set
    before it put in place of their names."""
    cmd = REDIRECT.sub(" ", HEREDOC.sub(" ", cmd)).replace("\\\n", " ")
    values: dict[str, str] = {}

    def expand(word: str) -> str:
        return VARIABLE.sub(lambda m: values.get(m.group(1) or m.group(2), m.group(0)),
                            word)

    for seg in shell_segments(cmd):
        words = split_words(seg)
        while words and words[0] in OPENERS:
            words.pop(0)
        if words and words[0] == "export":
            words.pop(0)
        sets = [ASSIGNMENT.match(w) for w in words]
        if words and all(sets):
            for m in sets:
                if m:
                    values[m.group(1)] = expand(m.group(2))
            continue
        yield [expand(w) for w in words]


@cache
def run_dl_commands() -> frozenset[str]:
    return frozenset(run_dl_parser()[1])


def run_dl_command(args: list[str]) -> str:
    """The command a run of `run_dl.py` with the arguments `args` runs, or
    the help flag it gives."""
    return command_args(args, run_dl_commands())[0]


def command_label(cmd: str) -> str:
    """The known commands a Bash command runs, joined by " + ", or else
    `poll` for one that runs sleep, or else the first program it runs
    past setup, or else the first program it runs."""
    known: list[str] = []
    first: str | None = None
    setup: str | None = None
    for prog, rest in programs(cmd):
        label = f"{RUN_DL} {run_dl_command(rest)}" if prog == RUN_DL else KNOWN.get(prog)
        if label and label not in known:
            known.append(label)
        if prog in SETUP:
            setup = setup or prog
        else:
            first = first or prog
    if known:
        return " + ".join(known)
    if runs_sleep(cmd):
        return POLL
    return first or setup or "shell"


def programs(cmd: str) -> Iterator[tuple[str, list[str]]]:
    """The program each simple command of a Bash command runs, with its
    arguments, as `segment_program` gives them."""
    for words in simple_commands(cmd):
        if not words or words[0] in CLOSERS:
            continue
        prog, rest = segment_program(words)
        if prog:
            yield prog, rest


def runs_sleep(cmd: str) -> bool:
    """Whether a simple command of a Bash command runs `sleep`: the call
    waits by timer."""
    return any(prog == "sleep" for prog, _ in programs(cmd))


def call_command(block: dict[str, Any], undecided: list[str], run: str) -> str:
    """The command of a call, as the HELP of `profile_runs` gives it. A
    transcript records a call whose input fails the tool's schema, so a
    field the command reads that the input lacks is left out, and an
    `undecided` line names it."""
    name, inp = block["name"], block["input"]

    def read(key: str) -> str:
        if key not in inp:
            undecided.append(mctx("{run}: {tool} call {call} gives no `{key}`").format(
                run=run, tool=name, call=block["id"], key=key))
            return ""
        return str(inp[key])

    if name == "Bash":
        command = read("command")
        kinds = "".join(f"kind {m.group('kind')}: "
                        for m in TICKET_HEAD.finditer(command))
        return kinds + command
    if name in AGENT_TOOLS:
        return read("description")
    if name in WRITE_TOOLS:
        return read("notebook_path" if name == "NotebookEdit" else "file_path")
    if name == "SendMessage":
        to = read("to")
        message = str(inp.get("message", ""))
        return f"to {to}: {message}" if to else message
    if name == "SubagentHandback":
        return read("message")
    return ""
