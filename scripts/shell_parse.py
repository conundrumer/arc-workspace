"""A strict parse of a shell command line into its simple commands, each
with its words, its redirections and the control operator that ends it.

The parse covers the grammar bash and zsh share for lists of pipelines of
simple commands. It raises `Unparsed` on a command line it cannot split
with certainty. A word that expansion could change is marked as not literal, and
its text is left as written."""

from dataclasses import dataclass, field
from enum import Enum


class Unparsed(Exception):
    """A command line the parse cannot split with certainty, with the
    construct that stops it."""


class Operator(Enum):
    """The control operator that ends a simple command."""
    PIPE = "|"
    PIPE_ALL = "|&"
    AND = "&&"
    OR = "||"
    BACKGROUND = "&"
    SEQUENCE = ";"
    NEWLINE = "\n"
    END = ""


RESERVED = frozenset({"if", "then", "else", "elif", "fi", "do", "done",
                      "while", "until", "for", "case", "esac", "select",
                      "function", "coproc", "repeat", "foreach", "end", "{",
                      "}", "[[", "]]"})
"""The words that open, continue or close a compound command in bash or
zsh, where one stands first in a simple command."""

EXPANDING = frozenset("*?[{}")
"""The characters that make an unquoted word subject to globbing or brace
expansion."""


@dataclass
class Word:
    text: str
    literal: bool


@dataclass
class Command:
    """A simple command."""
    words: list[Word] = field(default_factory=list[Word])
    redirected: list[int] = field(default_factory=list[int])
    operator: Operator = Operator.END


def parse(line: str) -> list[Command]:
    """The simple commands of `line`, in order, each with the operator that
    ends it. A command line that ends in an operator ends in a command
    with no words."""
    return _Parser(line).commands()


class _Parser:
    def __init__(self, line: str) -> None:
        self.s = line
        self.i = 0

    def peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.s[j] if j < len(self.s) else ""

    def commands(self) -> list[Command]:
        out: list[Command] = []
        cur = Command()
        while True:
            self.skip_blanks()
            c = self.peek()
            if c == "":
                out.append(cur)
                break
            if c == "#":
                while self.peek() not in ("", "\n"):
                    self.i += 1
                continue
            op = self.operator()
            if op is not None:
                if (not cur.words and not cur.redirected
                        and op is not Operator.NEWLINE):
                    raise Unparsed(f"the operator `{op.value}` with no "
                                   "command before it")
                cur.operator = op
                out.append(cur)
                cur = Command()
                continue
            if c in "()":
                raise Unparsed("a subshell or a function definition")
            redirect = self.redirection(cur)
            if redirect:
                continue
            word = self.word()
            if not cur.words and word.text in RESERVED:
                raise Unparsed(f"the compound command keyword `{word.text}`")
            cur.words.append(word)
        return out

    def skip_blanks(self) -> None:
        while True:
            if self.peek() in (" ", "\t"):
                self.i += 1
            elif self.peek() == "\\" and self.peek(1) == "\n":
                self.i += 2
            else:
                return

    def operator(self) -> Operator | None:
        two = self.s[self.i:self.i + 2]
        if two in (";;", ";&", ";|"):
            raise Unparsed("a case clause")
        if two in ("&&", "||", "|&"):
            self.i += 2
            return Operator(two)
        if two == "&>":
            return None
        c = self.peek()
        if c in ("|", "&", ";", "\n"):
            self.i += 1
            return Operator(c)
        return None

    def redirection(self, cur: Command) -> bool:
        j = self.i
        while j < len(self.s) and self.s[j].isdigit():
            j += 1
        digits = self.s[self.i:j]
        rest = self.s[j:]
        if rest.startswith("&>") and not digits:
            fd, j = 1, j + 2
            if self.s[j:j + 1] == ">":
                j += 1
        elif rest[:1] in ("<", ">"):
            if rest.startswith("<<"):
                raise Unparsed("a heredoc or a herestring")
            if rest[1:2] == "(":
                raise Unparsed("a process substitution")
            fd = int(digits) if digits else (0 if rest[0] == "<" else 1)
            j += 1
            if self.s[j:j + 1] in (">", "|", "&"):
                j += 1
        else:
            return False
        self.i = j
        self.skip_blanks()
        if self.peek() in ("", "\n", ";", "&", "|", "<", ">", "(", ")"):
            raise Unparsed("a redirection with no target")
        self.word()
        cur.redirected.append(fd)
        return True

    def word(self) -> Word:
        text: list[str] = []
        literal = True
        start = self.i
        while True:
            c = self.peek()
            if c in ("", " ", "\t", "\n", ";", "&", "|", "<", ">", "(", ")"):
                break
            if c == "\\":
                if self.peek(1) == "\n":
                    self.i += 2
                    continue
                if self.peek(1) == "":
                    raise Unparsed("a backslash at the end of the line")
                text.append(self.peek(1))
                self.i += 2
            elif c == "'":
                end = self.s.find("'", self.i + 1)
                if end < 0:
                    raise Unparsed("a single quote left open")
                text.append(self.s[self.i + 1:end])
                self.i = end + 1
            elif c == '"':
                literal = self.double_quoted(text) and literal
            elif c == "`":
                raise Unparsed("a command substitution")
            elif c == "$":
                nxt = self.peek(1)
                if nxt == "(":
                    raise Unparsed("a command substitution")
                if nxt == "{":
                    raise Unparsed("a parameter expansion in braces")
                literal = False
                text.append(c)
                self.i += 1
            else:
                if c in EXPANDING or (c in "~=" and self.i == start):
                    literal = False
                text.append(c)
                self.i += 1
        return Word("".join(text), literal)

    def double_quoted(self, text: list[str]) -> bool:
        literal = True
        self.i += 1
        while True:
            c = self.peek()
            if c == "":
                raise Unparsed("a double quote left open")
            if c == '"':
                self.i += 1
                return literal
            if c == "\\" and self.peek(1) in ('"', "\\", "$", "`", "\n"):
                if self.peek(1) != "\n":
                    text.append(self.peek(1))
                self.i += 2
            elif c == "`":
                raise Unparsed("a command substitution")
            elif c == "$":
                nxt = self.peek(1)
                if nxt == "(":
                    raise Unparsed("a command substitution")
                if nxt == "{":
                    raise Unparsed("a parameter expansion in braces")
                literal = False
                text.append(c)
                self.i += 1
            else:
                text.append(c)
                self.i += 1
