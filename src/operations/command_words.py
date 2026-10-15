"""The words of a Bash command an operator runs, and the call of the
command, `scripts/operate.py`, that a printed step runs."""

import re
import shlex
from enum import StrEnum
from functools import cache
from pathlib import PurePosixPath


COMMAND = "scripts/operate.py"


RUN_COMMAND = f"uv run python {COMMAND}"
"""How a printed step runs the command."""


OPERATORS = "();<>|&\n"
"""The characters of the shell's control and redirection operators."""


HEREDOC = re.compile(r"<<-?\s*(['\"]?)([^\s<>|&;()'\"]+)\1([^\n]*)\n.*?\n\s*\2[ \t]*(?=\n|$)", re.S)
"""A heredoc: its `<<WORD` or `<<-WORD` redirection, the rest of its
line, its body and the line that ends it."""


QUOTED_OR_ESCAPED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"|\\.", re.S)


def joined(command: str) -> str:
    """The Bash command `command` with each backslash before a newline
    outside quotes cut with that newline, as Bash reads a continued line."""
    return QUOTED_OR_ESCAPED.sub(lambda m: "" if m[0] == "\\\n" else m[0], command)


def without_heredocs(command: str) -> str:
    """The Bash command `command` with each heredoc's redirection, body and
    ending line in place of a space, and the rest of the redirection's line
    kept."""
    return HEREDOC.sub(lambda m: " " + m[3], command)


def simple_commands(command: str) -> list[list[str]]:
    """The words of each simple command of the Bash command `command`,
    without its redirections and its heredocs, or none where the shell's
    quoting outside its heredocs is unbalanced. A redirection is an
    operator with `<` or `>`, the word after it, and a number before it.
    A heredoc's redirection, body and ending line give no word, and the
    words after the redirection on its own line stay. A backslash before
    a newline outside quotes and heredocs gives no character, so a
    continued line stays in the simple command it continues."""
    return [list(words) for words in command_words(command)]


@cache
def command_words(command: str) -> tuple[tuple[str, ...], ...]:
    """`simple_commands`, parsed once for each command: the state gives
    each operator's commands at each read."""
    lexer = shlex.shlex(joined(without_heredocs(command)), posix=True, punctuation_chars=OPERATORS)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    out: list[list[str]] = [[]]
    redirect = False
    try:
        for word in lexer:
            if redirect:
                redirect = False
            elif word and set(word) <= set(OPERATORS) and set(word) & set("<>"):
                if out[-1] and out[-1][-1].isdigit():
                    out[-1].pop()
                redirect = True
            elif word and set(word) <= set(OPERATORS):
                out.append([])
            else:
                out[-1].append(word)
    except ValueError:
        return ()
    return tuple(tuple(words) for words in out if words)


class Action(StrEnum):
    """An action of `operate.py` that prints an agent's next step."""
    NEXT = "next"
    """The action that prints an operator's next step."""
    RELAY = "relay"
    """The action that prints an operator launcher's next step."""
    REVIEW = "review"
    """The action that prints a doc editor the launch of its doc reviewer."""


def next_command(agent: str, action: Action = Action.NEXT) -> str:
    return " ".join(run_words(action, agent))


def run_words(action: Action, agent: str) -> list[str]:
    """The words of the call of `operate.py` with `action` for the operator
    `agent`."""
    return [*RUN_COMMAND.split(), action, agent]


@cache
def runs(command: str, action: Action, agent: str) -> bool:
    """Whether the Bash command `command` runs `operate.py` with `action`
    for the operator `agent`, whatever else it runs."""
    return any(is_call(words, action, agent) for words in simple_commands(command))


def is_call(words: list[str], action: Action, agent: str) -> bool:
    """Whether the simple command `words` is the call of `operate.py` with
    `action` for the operator `agent`: the words of `run_words`, where the
    script word may be any path, absolute or relative, that ends in
    `scripts/operate.py`, as the path to the main tree's or a worktree's
    script does."""
    expected = run_words(action, agent)
    script = expected.index(COMMAND)
    return (len(words) == len(expected)
            and words[:script] + words[script + 1:] == expected[:script] + expected[script + 1:]
            and PurePosixPath(words[script]).parts[-2:] == PurePosixPath(COMMAND).parts)


def is_next(command: str, agent: str, action: Action = Action.NEXT) -> bool:
    return runs(command, action, agent)


def only_command(command: str, agent: str, action: Action = Action.NEXT) -> bool:
    """Whether the Bash command `command` runs `operate.py` with `action`
    for the operator `agent` and nothing else but `cd` and `:`, which run
    no step the command prints."""
    return is_next(command, agent, action) and all(
        words[0] in ("cd", ":") or is_call(words, action, agent)
        for words in simple_commands(command))
