"""Assess executable shell loops in Bash and Monitor command input.

Literal interpreter sources and substitutions use the same syntax reader.
Runtime expansion, script files and unknown operations remain opaque.
Unreadable syntax raises to the hook entry's independent failure handling.
"""

from dataclasses import dataclass, field
from enum import IntEnum, Enum, auto
from functools import lru_cache
import re
from typing import Any


class Assessment(IntEnum):
    CLEAR = 0
    WARN = 1
    DENY = 2


class Kind(Enum):
    COMMAND = auto()
    LIST = auto()
    AND = auto()
    OR = auto()
    PIPELINE = auto()
    NOT = auto()
    BACKGROUND = auto()
    LOOP = auto()
    BRANCH = auto()
    FUNCTION = auto()
    CASE = auto()


@dataclass
class Word:
    text: str
    literal: bool = True
    keyword: bool = True
    sources: list[str] = field(default_factory=list)
    heredoc: str | None = None


@dataclass
class Node:
    kind: Kind
    children: list['Node'] = field(default_factory=list)
    words: list[Word] = field(default_factory=list)
    loop: str = ''
    inputs: list[Word] = field(default_factory=list)
    stdin: Word | None = None


OPERATORS = ('<<<', '<<-', ';;&', ';;', ';&', '&&', '||', '>>', '<<', '<&', '>&', ';', '\n', '&', '|', '(', ')', '{', '}', '<', '>')
REDIRECTS = {'<<<', '<<', '<<-', '>>', '<', '>', '<&', '>&'}


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.i = 0

    def substitution(self, backtick: bool = False) -> str:
        start = self.i
        depth = 1
        quote = ''
        while self.i < len(self.source):
            c = self.source[self.i]
            if c == '\\':
                self.i += 2
                continue
            if backtick and c == '`':
                result = self.source[start:self.i]
                self.i += 1
                return result
            if c in "\"'":
                if quote == c:
                    quote = ''
                elif not quote:
                    quote = c
            if not backtick and quote != "'" and self.source.startswith('$(', self.i):
                self.i += 2
                self.substitution()
                continue
            if not quote and not backtick:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if not depth:
                        result = self.source[start:self.i]
                        self.i += 1
                        return result
            self.i += 1
        raise ValueError('unterminated substitution')

    def word(self) -> Word:
        w = Word('')
        quote = ''
        while self.i < len(self.source):
            c = self.source[self.i]
            if not quote and (c.isspace() or c in ';&|(){}<>'):
                if self.source[self.i:self.i + 2] not in ('<(', '>('):
                    break
            if c == '\\' and quote != "'":
                w.keyword = False
                self.i += 1
                if self.i == len(self.source):
                    raise ValueError('trailing escape')
                escaped = self.source[self.i]
                if escaped != '\n':
                    if quote == '"' and escaped not in '$`"\\':
                        w.text += '\\'
                    w.text += escaped
                self.i += 1
            elif c in "\"'" and (not quote or quote == c):
                w.keyword = False
                quote = '' if quote else c
                self.i += 1
            elif quote != "'" and (self.source.startswith('$(', self.i) or (not quote and self.source[self.i:self.i + 2] in ('<(', '>(')) or c == '`'):
                w.literal = False
                backtick = c == '`'
                self.i += 1 if backtick else 2
                w.sources.append(self.substitution(backtick))
                w.text += '$substitution'
            else:
                if quote != "'" and c == '$':
                    w.literal = False
                w.text += c
                self.i += 1
        if quote:
            raise ValueError('unterminated quote')
        return w

    def tokens(self) -> list[Word | str]:
        tokens: list[Word | str] = []
        pending: list[tuple[Word, bool]] = []
        document: str | None = None
        while self.i < len(self.source):
            c = self.source[self.i]
            if c in ' \t\r':
                self.i += 1
                continue
            if c == '#':
                end = self.source.find('\n', self.i)
                self.i = len(self.source) if end < 0 else end
                continue
            op = next((op for op in OPERATORS if self.source.startswith(op, self.i)), None)
            if self.source[self.i:self.i + 2] in ('<(', '>('):
                op = None
            if op is not None:
                tokens.append(op)
                self.i += len(op)
                if op in ('<<', '<<-'):
                    document = op
                if op == '\n':
                    for delimiter, tabs in pending:
                        lines: list[str] = []
                        while self.i < len(self.source):
                            end = self.source.find('\n', self.i)
                            end = len(self.source) if end < 0 else end
                            line = self.source[self.i:end]
                            self.i = min(end + 1, len(self.source))
                            if tabs:
                                line = line.lstrip('\t')
                            if line == delimiter.text:
                                break
                            lines.append(line)
                        else:
                            raise ValueError('unterminated heredoc')
                        delimiter.heredoc = '\n'.join(lines)
                        if delimiter.keyword:
                            expanded = Lexer('"' + delimiter.heredoc.replace('"', '\\"') + '"').word()
                            delimiter.sources.extend(expanded.sources)
                    pending.clear()
            else:
                w = self.word()
                tokens.append(w)
                if document:
                    pending.append((w, document == '<<-'))
                    document = None
        if pending:
            raise ValueError('missing heredoc')
        return tokens


class Parser:
    def __init__(self, source: str):
        self.tokens = Lexer(source).tokens()
        self.i = 0

    def at(self, *values: str) -> bool:
        if self.i == len(self.tokens):
            return False
        token = self.tokens[self.i]
        return (token if isinstance(token, str) else token.text if token.keyword else None) in values

    def take(self, value: str) -> None:
        if not self.at(value):
            raise ValueError(f'expected {value}')
        self.i += 1

    def sequence(self, stops: tuple[str, ...] = ()) -> Node:
        children: list[Node] = []
        while self.i < len(self.tokens) and not self.at(*stops):
            if self.at(';', '\n'):
                self.i += 1
                continue
            before = self.i
            node = self.logical()
            if self.at('&'):
                self.i += 1
                node = Node(Kind.BACKGROUND, [node])
            children.append(node)
            if self.i == before:
                raise ValueError('unexpected token')
        return Node(Kind.LIST, children)

    def logical(self) -> Node:
        node = self.pipeline()
        while self.at('&&', '||'):
            op = self.tokens[self.i]
            self.i += 1
            while self.at('\n'):
                self.i += 1
            right = self.pipeline()
            node = Node(Kind.AND if op == '&&' else Kind.OR, [node, right])
        return node

    def pipeline(self) -> Node:
        if self.at('!'):
            self.i += 1
            return Node(Kind.NOT, [self.pipeline()])
        if self.at('time'):
            self.i += 1
            if self.at('-p'):
                self.i += 1
            if self.at('--'):
                self.i += 1
            return self.pipeline()
        children = [self.atom()]
        while self.at('|'):
            self.i += 1
            while self.at('\n'):
                self.i += 1
            children.append(self.atom())
        return children[0] if len(children) == 1 else Node(Kind.PIPELINE, children)

    def atom(self) -> Node:
        if self.at('(') and self.i + 1 < len(self.tokens) and self.tokens[self.i + 1] == '(':
            self.i += 2
            depth = 2
            words = [Word('let')]
            while self.i < len(self.tokens):
                token = self.tokens[self.i]
                self.i += 1
                if isinstance(token, Word):
                    words.append(token)
                if token == '(':
                    depth += 1
                elif token == ')':
                    depth -= 1
                    if depth == 0:
                        return Node(Kind.COMMAND, words=words)
            raise ValueError('unterminated arithmetic')
        if (self.i + 2 < len(self.tokens) and isinstance(self.tokens[self.i], Word)
                and self.tokens[self.i + 1:self.i + 3] == ['(', ')']):
            self.i += 3
            return Node(Kind.FUNCTION, [self.atom()])
        if self.at('case'):
            self.i += 1
            node = Node(Kind.CASE)
            if self.i == len(self.tokens):
                raise ValueError('missing case subject')
            subject = self.tokens[self.i]
            if not isinstance(subject, Word):
                raise ValueError('invalid case subject')
            node.words.append(subject)
            self.i += 1
            while self.at('\n'):
                self.i += 1
            self.take('in')
            while True:
                while self.at('\n'):
                    self.i += 1
                if self.at('esac'):
                    self.i += 1
                    return node
                while self.i < len(self.tokens) and not self.at(')'):
                    token = self.tokens[self.i]
                    if isinstance(token, Word):
                        node.words.append(token)
                    self.i += 1
                self.take(')')
                node.children.append(self.sequence((';;', ';&', ';;&', 'esac')))
                if self.at(';;', ';&', ';;&'):
                    self.i += 1
        if self.at('while', 'until', 'for'):
            token = self.tokens[self.i]
            assert isinstance(token, Word)
            self.i += 1
            condition = self.sequence(('do',))
            self.take('do')
            body = self.sequence(('done',))
            self.take('done')
            return Node(Kind.LOOP, [condition, body], loop=token.text)
        if self.at('(', '{'):
            close = ')' if self.at('(') else '}'
            self.i += 1
            node = self.sequence((close,))
            self.take(close)
            self.redirects(node)
            return node
        if self.at('if'):
            self.i += 1
            condition = self.sequence(('then',))
            self.take('then')
            yes = self.sequence(('else', 'elif', 'fi'))
            no = Node(Kind.LIST)
            if self.at('else'):
                self.i += 1
                no = self.sequence(('fi',))
            elif self.at('elif'):
                self.tokens[self.i] = Word('if')
                return Node(Kind.BRANCH, [condition, yes, self.atom()])
            self.take('fi')
            return Node(Kind.BRANCH, [condition, yes, no])
        node = Node(Kind.COMMAND)
        while self.i < len(self.tokens):
            if self.at(*REDIRECTS):
                self.redirects(node)
            elif isinstance(self.tokens[self.i], Word):
                word = self.tokens[self.i]
                assert isinstance(word, Word)
                node.words.append(word)
                self.i += 1
            else:
                break
        return node

    def redirects(self, node: Node) -> None:
        while self.at(*REDIRECTS):
            op = self.tokens[self.i]
            descriptor = '0'
            if node.words and node.words[-1].text.isdecimal():
                descriptor = node.words.pop().text
            self.i += 1
            if self.i == len(self.tokens) or not isinstance(self.tokens[self.i], Word):
                raise ValueError('missing redirect target')
            word = self.tokens[self.i]
            assert isinstance(word, Word)
            node.inputs.append(word)
            if descriptor == '0' and op in {'<', '<<', '<<-', '<<<', '<&'}:
                node.stdin = word
            if op == '<<<' and word.literal:
                word.heredoc = word.text
            self.i += 1


@dataclass
class Invocation:
    words: list[Word]
    builtin_only: bool


def invocation(node: Node) -> Invocation | None:
    """The static invocation after assignments and command/builtin wrappers.

    Queries and unreadable wrapper options give no invoked operation.
    A builtin wrapper restricts its operand to shell builtins.
    """
    words = list(node.words)
    while words and re.match(r'^[A-Za-z_][A-Za-z_0-9]*=', words[0].text):
        words.pop(0)
    builtin_only = False
    while words and words[0].literal and words[0].text in ('builtin', 'command'):
        wrapper = words.pop(0).text
        builtin_only = wrapper == 'builtin'
        while words and words[0].literal and words[0].text.startswith('-'):
            option = words.pop(0).text
            if option == '--':
                break
            if wrapper != 'command' or not option[1:] or any(c not in 'pvV' for c in option[1:]):
                return None
            if 'v' in option or 'V' in option:
                return None
    return Invocation(words, builtin_only)


def operation(node: Node) -> str | None:
    invoked = invocation(node)
    if invoked is None:
        return None
    if not invoked.words:
        return ''
    word = invoked.words[0]
    return word.text if word.literal else None


READ_WAIT = {'read', 'mapfile', 'readarray', 'sleep', 'wait'}
BUILTINS = {''} | set(': true false printf echo test [ [[ let declare typeset local readonly export unset set shopt cd pwd pushd popd dirs alias unalias hash help history jobs kill getopts shift umask ulimit times trap return break continue enable bind complete compgen type'.split())
type States = set[tuple[bool, bool]]


def outcomes(node: Node) -> States:
    """Finite possible (success, explicit foreground read/wait) states."""
    match node.kind:
        case Kind.COMMAND:
            return {(True, operation(node) in READ_WAIT), (False, operation(node) in READ_WAIT)}
        case Kind.BACKGROUND | Kind.LOOP | Kind.FUNCTION | Kind.CASE:
            return {(True, False), (False, False)}
        case Kind.NOT:
            return {(not status, read) for status, read in outcomes(node.children[0])}
        case Kind.BRANCH:
            condition, yes, no = node.children
            return {(end, read or more) for status, read in outcomes(condition)
                    for end, more in outcomes(yes if status else no)}
        case _:
            states: States = {(True, False)}
            for i, child in enumerate(node.children):
                next_states: States = set()
                for status, read in states:
                    skip = i > 0 and ((node.kind == Kind.AND and not status) or
                                      (node.kind == Kind.OR and status))
                    if skip:
                        next_states.add((status, read))
                    else:
                        next_states.update((end, read or more) for end, more in outcomes(child))
                states = next_states
            return states


def shell_source(node: Node) -> str | None:
    invoked = invocation(node)
    if invoked is None or invoked.builtin_only:
        return None
    words = list(invoked.words)
    if words and words[0].literal and words[0].text.rsplit('/', 1)[-1] == 'env':
        words.pop(0)
        while words:
            value = words[0]
            if not value.literal:
                return None
            if value.text in ('-i', '--ignore-environment', '--') or re.match(r'^[A-Za-z_][A-Za-z_0-9]*=', value.text):
                words.pop(0)
            elif value.text in ('-u', '--unset', '-C', '--chdir'):
                del words[:2]
            elif value.text.startswith(('--unset=', '--chdir=')):
                words.pop(0)
            else:
                break
    if not words or not words[0].literal or words.pop(0).text.rsplit('/', 1)[-1] not in {'sh', 'bash', 'dash', 'ksh', 'zsh'}:
        return None
    script: Word | None = None
    stdin = True
    while words:
        option = words.pop(0)
        if not option.literal:
            return None
        if option.text == '--':
            if words:
                stdin = False
            break
        if not option.text.startswith(('-', '+')) or option.text == '-':
            stdin = False
            break
        if option.text in ('--help', '--version') or (option.text.startswith('-') and not option.text.startswith('--') and 'n' in option.text[1:]):
            return None
        if option.text in ('--rcfile', '--init-file'):
            if words:
                words.pop(0)
            continue
        if option.text.startswith('--'):
            continue
        if option.text in ('-o', '-O', '+o', '+O'):
            if words and words.pop(0).text == 'noexec':
                return None
            continue
        if 'c' in option.text[1:]:
            script = words[0] if words else None
            stdin = False
            break
        if 's' in option.text[1:]:
            continue
    if script is not None:
        return script.text if script.literal else None
    if stdin and node.stdin is not None:
        return node.stdin.heredoc
    return None


@lru_cache(maxsize=128)
def parsed(source: str) -> Node:
    return Parser(source).sequence()


def executable_nodes(node: Node):
    yield node
    for child in node.children:
        yield from executable_nodes(child)
    for word in node.words + node.inputs:
        for source in word.sources:
            yield from executable_nodes(parsed(source))
    source = shell_source(node) if node.kind == Kind.COMMAND else None
    if source is not None:
        yield from executable_nodes(parsed(source))


def commands(node: Node) -> list[str | None]:
    return [operation(child) if child.kind == Kind.COMMAND else None
            for child in executable_nodes(node)
            if child.kind in (Kind.COMMAND, Kind.FUNCTION)]


def loops(command: str) -> list[Node]:
    """Executable loops, including those in substitutions and literal scripts."""
    return [node for node in executable_nodes(parsed(command)) if node.kind == Kind.LOOP]


@lru_cache(maxsize=32)
def assess(command: str) -> Assessment:
    result = Assessment.CLEAR
    for loop in loops(command):
        if loop.loop == 'for':
            continue
        condition, body = loop.children
        continuing = {read for status, read in outcomes(condition) if status == (loop.loop == 'while')}
        if continuing and all(continuing):
            continue
        operations = commands(body)
        if operations and all(op in {':', 'true', 'read'} for op in operations):
            return Assessment.DENY
        if operations and all(op in BUILTINS for op in operations):
            result = Assessment.WARN
    return result


def assessment(hook: dict[str, Any]) -> Assessment:
    if hook.get('tool_name') not in ('Bash', 'Monitor'):
        return Assessment.CLEAR
    command = (hook.get('tool_input') or {}).get('command')
    return assess(command) if isinstance(command, str) else Assessment.CLEAR


def check(hook: dict[str, Any]) -> str | None:
    if assessment(hook) != Assessment.DENY:
        return None
    from controlled_markdown import mctx
    return mctx('Blocked: this loop can run without waiting and hold a CPU core during a wait. Run `sleep` in each pass to prevent that load.')


def context(hook: dict[str, Any]) -> str | None:
    if assessment(hook) != Assessment.WARN:
        return None
    from controlled_markdown import mctx
    return mctx("The commands in this loop's body do not wait; a busy loop holds a CPU core.")
