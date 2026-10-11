"""The words of a Bash command an operator runs, and the call of the
command, `scripts/operate.py`, that a printed step runs."""

import shlex
from enum import StrEnum


COMMAND = "scripts/operate.py"


RUN_COMMAND = f"uv run python {COMMAND}"
"""How a printed step runs the command."""


OPERATORS = "();<>|&\n"
"""The characters of the shell's control and redirection operators."""


def simple_commands(command: str) -> list[list[str]]:
    """The words of each simple command of the Bash command `command`,
    without its redirections, or none where the shell's quoting in it is
    unbalanced. A redirection is an operator with `<` or `>`, the word
    after it, and a number before it."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=OPERATORS)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    out: list[list[str]] = [[]]
    redirect = False
    try:
        for word in lexer:
            if redirect:
                redirect = False
            elif set(word) <= set(OPERATORS) and set(word) & set("<>"):
                if out[-1] and out[-1][-1].isdigit():
                    out[-1].pop()
                redirect = True
            elif set(word) <= set(OPERATORS):
                out.append([])
            else:
                out[-1].append(word)
    except ValueError:
        return []
    return [words for words in out if words]


class Action(StrEnum):
    """An action of `operate.py` that prints an agent's next step."""
    NEXT = "next"
    """The action that prints an operator's next step."""
    RELAY = "relay"
    """The action that prints an operator launcher's next step."""


def next_command(agent: str, action: Action = Action.NEXT) -> str:
    return " ".join(run_words(action, agent))


def run_words(action: Action, agent: str) -> list[str]:
    """The words of the call of `operate.py` with `action` for the operator
    `agent`."""
    return [*RUN_COMMAND.split(), action, agent]


def runs(command: str, action: Action, agent: str) -> bool:
    """Whether the Bash command `command` runs `operate.py` with `action`
    for the operator `agent`, whatever else it runs."""
    return any(is_call(words, action, agent) for words in simple_commands(command))


def is_call(words: list[str], action: Action, agent: str) -> bool:
    """Whether the simple command `words` is the call of `operate.py` with
    `action` for the operator `agent`."""
    return words == run_words(action, agent)


def is_next(command: str, agent: str, action: Action = Action.NEXT) -> bool:
    return runs(command, action, agent)
