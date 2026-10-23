"""Refuse project agents' Bash deletes outside their permitted directories.

Executable shell input is visited before words are projected for operand
checks. Unreadable executable syntax produces a refusal.
"""

import os
import re
import shlex
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from command_labels import ASSIGNMENT, VARIABLE, WRAPPERS, WRAPPER_OPTIONS, segment_program
from controlled_markdown import mctx
from hook_entry import Hook
from operations.roles import Role

SCRATCH_ONLY = frozenset({Role.TICKET_REVIEWER, Role.CODE_REVIEWER,
                         Role.DESIGN_REVIEWER, Role.DOC_REVIEWER,
                         Role.ITEM_CHECKER, Role.LIB_REVIEWER})
PYTHON_DELETE = re.compile(r"\b(?:shutil\.rmtree|os\.(?:remove|unlink|rmdir))\s*\(|\.(?:unlink|rmdir)\s*\(")
UNKNOWN = "\x01"
DOLLAR = "\x02"
GLOB = re.compile(r"[*?[]")
SHELLS = {"bash", "sh", "zsh"}
PYTHON = re.compile(r"python[\d.]*$")


class Unreadable(ValueError):
    """Executable input whose boundaries or context cannot be read."""


@dataclass
class Word:
    text: str
    children: list[list['Token']] = field(default_factory=list)
    quoted: bool = False
    splits: bool = False
    span: tuple[int, int] | None = None


@dataclass
class Redirect:
    fd: int
    operator: str
    target: Word
    body: Word | None = None


type Token = Word | Redirect | str


class Lexer:
    """Retain executable children, quoting and input redirections.

    Offsets in failures refer to this reader's source, including a nested
    interpreter's source when that interpreter is read separately.
    """

    def __init__(self, source: str):
        self.source = source
        self.at = 0

    def fail(self, start: int, reason: str) -> Unreadable:
        return Unreadable(f"source[{start}:{self.at + 1}] {self.source[start:self.at + 1]!r}: {reason}")

    def tokens(self, closing: bool = False) -> list[Token]:
        tokens: list[Token] = []
        pending: list[Redirect] = []
        while self.at < len(self.source):
            start = self.at
            c = self.source[self.at]
            if c in ' \t\r':
                self.at += 1
                continue
            if c == '#':
                end = self.source.find('\n', self.at)
                self.at = len(self.source) if end < 0 else end
                continue
            if c == '\n':
                self.at += 1
                tokens.append('\n')
                for redir in pending:
                    lines: list[str] = []
                    while self.at < len(self.source):
                        end = self.source.find('\n', self.at)
                        end = len(self.source) if end < 0 else end + 1
                        line = self.source[self.at:end]
                        self.at = end
                        if redir.operator == '<<-':
                            line = line.lstrip('\t')
                        if line.rstrip('\n') == redir.target.text.replace(DOLLAR, '$'):
                            break
                        lines.append(line)
                    else:
                        raise self.fail(start, 'unterminated heredoc')
                    body = ''.join(lines)
                    redir.body = (Word(body.replace("$", DOLLAR)) if redir.target.quoted
                                  else Lexer(body).word(data=True))
                pending.clear()
                continue
            if self.source.startswith(('<(', '>('), self.at):
                tokens.append(self.word())
                continue
            redirection = re.match(r'(\d*)(<<-|<<<|<<|>>|<>|>&|<&|>|<)', self.source[self.at:])
            if redirection:
                self.at += redirection.end()
                fd, op = redirection.groups()
                while self.at < len(self.source) and self.source[self.at] in ' \t':
                    self.at += 1
                target = self.word(delimiter=op in {'<<', '<<-'})
                if not target.text:
                    raise self.fail(start, 'missing redirection operand')
                redir = Redirect(int(fd) if fd else (0 if op.startswith('<') else 1), op, target)
                tokens.append(redir)
                if op in {'<<', '<<-'}:
                    pending.append(redir)
                continue
            if c in ';&|()':
                self.at += 1
                if c == ')' and closing:
                    if pending:
                        raise self.fail(start, 'heredoc before substitution boundary')
                    return tokens
                op = c
                if c in ';&|' and self.at < len(self.source) and self.source[self.at] == c:
                    op += c
                    self.at += 1
                elif c == '|' and self.at < len(self.source) and self.source[self.at] == '&':
                    op += '&'
                    self.at += 1
                if op == '(':
                    tokens.extend(['(', *self.tokens(closing=True), ')'])
                else:
                    tokens.append(op)
                continue
            tokens.append(self.word())
        if pending or closing:
            raise self.fail(self.at, 'missing executable input boundary')
        return tokens

    def word(self, *, data: bool = False, delimiter: bool = False) -> Word:
        start = self.at
        out = Word('')
        quote = ''
        while self.at < len(self.source):
            c = self.source[self.at]
            if not data and not quote and (c in ' \t\r\n;&|()<>'):
                if not self.source.startswith(('<(', '>('), self.at):
                    break
            self.at += 1
            if c == '\\' and quote != "'":
                if self.at >= len(self.source):
                    raise self.fail(start, 'trailing escape')
                following = self.source[self.at]
                if (quote == '"' or data) and following not in '$`\\\n"':
                    out.text += '\\'
                    continue
                self.at += 1
                out.quoted = True
                if following != '\n':
                    out.text += DOLLAR if following == '$' else following
                continue
            if not data and c in "'\"":
                if not quote:
                    quote = c
                    out.quoted = True
                    continue
                if quote == c:
                    quote = ''
                    continue
            if quote == "'" or delimiter:
                out.text += DOLLAR if c == '$' else c
                continue
            if c == '`':
                out.children.append(self.backticks(start))
                out.text += UNKNOWN
                continue
            if not quote and not data and c in '<>' and self.at < len(self.source) and self.source[self.at] == '(':
                self.at += 1
                out.children.append(self.tokens(closing=True))
                out.text += UNKNOWN
                continue
            if c == '$' and self.at < len(self.source):
                out.splits |= not quote and not data
                if self.source.startswith('(', self.at) and not self.source.startswith('((', self.at):
                    self.at += 1
                    out.children.append(self.tokens(closing=True))
                    out.text += UNKNOWN
                    continue
                if self.source[self.at] in '{(':
                    self.expansion(out, start)
                    continue
                if self.source[self.at] in "'\"":
                    raise self.fail(start, 'unsupported shell quote expansion')
            out.text += c
        if quote:
            raise self.fail(start, 'unterminated quote')
        if not data and self.at == start:
            raise self.fail(start, 'unsupported word boundary')
        out.span = (start, self.at)
        return out

    def backticks(self, start: int) -> list[Token]:
        nested = ''
        while self.at < len(self.source):
            c = self.source[self.at]
            self.at += 1
            if c == '`':
                return Lexer(nested).tokens()
            if c == '\\' and self.at < len(self.source) and self.source[self.at] in '$`\\':
                c = self.source[self.at]
                self.at += 1
            nested += c
        raise self.fail(start, 'unterminated backticks')

    def expansion(self, out: Word, start: int) -> None:
        opening = self.source[self.at]
        closing = '}' if opening == '{' else ')'
        self.at += 1
        inner_start = self.at
        depth = 1
        while self.at < len(self.source):
            c = self.source[self.at]
            if c == '\\':
                self.at += 2
                continue
            if c == '`':
                self.at += 1
                out.children.append(self.backticks(start))
                continue
            if c in "'\"":
                raise self.fail(start, 'unsupported quote inside extended expansion')
            if self.source.startswith(('<(', '>('), self.at):
                self.at += 2
                out.children.append(self.tokens(closing=True))
                continue
            if self.source.startswith('$(', self.at) and not self.source.startswith('$((', self.at):
                self.at += 2
                out.children.append(self.tokens(closing=True))
                continue
            if self.source.startswith(('${', '$(('), self.at):
                self.at += 1
                self.expansion(out, start)
                continue
            if c == opening:
                depth += 1
            elif c == closing:
                depth -= 1
                if depth == 0:
                    inner = self.source[inner_start:self.at]
                    self.at += 1
                    out.text += ('${' + inner + '}' if opening == '{' and re.fullmatch(r'\w+', inner)
                                 else UNKNOWN)
                    return
            self.at += 1
        raise self.fail(start, 'unterminated parameter or arithmetic expansion')


@dataclass
class Context:
    cwd: Path | None
    values: dict[str, str]
    exported: set[str]
    stack: list[Path | None] = field(default_factory=list)
    opaque_variables: bool = False

    def copy(self) -> 'Context':
        return Context(self.cwd, self.values.copy(), self.exported.copy(), self.stack.copy(), self.opaque_variables)

    def invocation(self) -> 'Context':
        return Context(self.cwd, {name: self.values.get(name, UNKNOWN) for name in self.exported},
                       self.exported.copy(), opaque_variables=self.opaque_variables)

    def invalidate(self, names: set[str] | None) -> None:
        for name in self.values.keys() if names is None else names:
            self.values[name] = UNKNOWN



@dataclass(frozen=True)
class Command:
    """A simple command after its executable children have been visited."""
    words: tuple[str, ...]
    cwd: Path | None
    values: dict[str, str]


@dataclass(frozen=True)
class PythonInput:
    text: str


@dataclass(frozen=True)
class PythonFile:
    path: Path


type Input = Command | PythonInput | PythonFile


def invocation(words: list[str]) -> tuple[str | None, list[str], list[str]]:
    """Identify a program while retaining its interpreter and wrapper context."""
    normalized = ['command' if word == 'builtin' else word for word in words]
    for at, word in enumerate(normalized):
        if (word.startswith('-') or ASSIGNMENT.fullmatch(word)
                or Path(word).name in WRAPPERS or re.fullmatch(r'\d+[smh]?', word)):
            continue
        name, _ = segment_program([*normalized[:at], '__input__'])
        if name == '__input__':
            return Path(words[at]).name, words[at + 1:], words[:at]
    return None, [], words


def mutated_names(name: str, args: list[str]) -> set[str] | None:
    """Names a variable builtin can change, or unknown for unreadable arguments."""
    names: set[str] = set()
    if name == 'printf':
        if not args or not args[0].startswith('-v'):
            return names
        args = [args[0][2:]] if args[0] != '-v' else args[1:2]
    elif name == 'getopts':
        return {'OPTARG', 'OPTIND', args[1]} if len(args) > 1 and re.fullmatch(r'[a-zA-Z_]\w*', args[1]) else None
    elif name == 'let':
        return None
    elif name in {'read', 'mapfile', 'readarray'}:
        valued = ({'-d', '-i', '-n', '-N', '-p', '-t', '-u'} if name == 'read'
                  else {'-d', '-n', '-O', '-s', '-u', '-C', '-c'})
        flags = {'-r', '-s', '-e', '-E'} if name == 'read' else {'-t'}
        remaining: list[str] = []
        at = 0
        while at < len(args):
            arg = args[at]
            at += 1
            if arg == '-a' and name == 'read':
                if at >= len(args):
                    return None
                remaining.append(args[at])
                at += 1
            elif arg in valued:
                if at >= len(args) or arg == '-C':
                    return None
                at += 1
            elif arg in flags or arg == '--':
                continue
            elif arg.startswith('-'):
                return None
            else:
                remaining.append(arg)
        args = remaining or ['REPLY' if name == 'read' else 'MAPFILE']
    for arg in args:
        if arg.startswith('-') and name in {'unset', 'declare', 'typeset', 'local', 'readonly'}:
            continue
        variable = arg.partition('=')[0]
        match = re.fullmatch(r'([a-zA-Z_]\w*)(?:\[[^\]]*\])?', variable)
        if match is None:
            return None
        names.add(match[1])
    return names


def change_directory(name: str, args: list[str], context: Context) -> None:
    if args[:1] == ['--']:
        args = args[1:]
    previous = context.cwd
    if name == 'popd':
        context.cwd = context.stack.pop() if not args and context.stack else None
        if args:
            context.stack.clear()
    elif name == 'pushd' and not args and context.stack:
        context.cwd, context.stack[-1] = context.stack[-1], previous
    else:
        operand = (args[0] if len(args) == 1 else context.values.get('HOME', UNKNOWN)
                   if name == 'cd' and not args else UNKNOWN)
        if operand == '-':
            operand = context.values.get('OLDPWD', UNKNOWN)
        if operand.startswith('-') or name == 'pushd' and operand.startswith('+'):
            operand = UNKNOWN
        directory = resolved(operand, context.cwd)
        context.cwd = directory.resolve() if directory is not None else None
        if name == 'pushd':
            if UNKNOWN in operand:
                context.stack = [None]
            else:
                context.stack.append(previous)
    context.values['OLDPWD'] = str(previous) if previous is not None else UNKNOWN
    context.values['PWD'] = str(context.cwd) if context.cwd is not None else UNKNOWN


class Visitor:
    """Visit shell-local execution contexts without running commands."""

    def __init__(self):
        self.inputs: list[Input] = []

    def word(self, word: Word, context: Context) -> str:
        for child in word.children:
            self.visit(child, context.copy())
        def value(match: re.Match[str]) -> str:
            found = UNKNOWN if context.opaque_variables else context.values.get(match[1] or match[2], UNKNOWN)
            if word.splits and any(c.isspace() for c in found):
                raise Unreadable(f'source{word.span}: unquoted variable requires field splitting')
            return found
        return VARIABLE.sub(value, word.text).replace(DOLLAR, '$')

    def visit(self, tokens: list[Token], context: Context, stdin: str | None = None) -> None:
        outcomes = [(context, True)]
        connector = ';'
        words: list[Word] = []
        redirects: list[Redirect] = []
        at = 0
        while at <= len(tokens):
            token = tokens[at] if at < len(tokens) else ';'
            at += 1
            if isinstance(token, Word):
                words.append(token)
                continue
            if isinstance(token, Redirect):
                redirects.append(token)
                continue
            if token == '(':
                if words or redirects:
                    raise Unreadable('source: unsupported function or array syntax')
                start, depth = at, 1
                while at < len(tokens) and depth:
                    part = tokens[at]
                    if isinstance(part, str):
                        depth += (part == '(') - (part == ')')
                    at += 1
                if depth:
                    raise Unreadable('source: unclosed subshell')
                grouped: list[tuple[Context, bool]] = []
                for state, success in outcomes:
                    if connector == '&&' and not success or connector == '||' and success:
                        grouped.append((state, success))
                        continue
                    self.visit(tokens[start:at - 1], state.copy(), stdin)
                    grouped.extend([(state, True), (state.copy(), False)])
                outcomes = grouped
                continue
            if token not in {';', '\n', '&&', '||', '|', '|&', '&'}:
                raise Unreadable(f'source: unsupported shell operator {token!r}')
            if words or redirects:
                following: list[tuple[Context, bool]] = []
                for state, success in outcomes:
                    if connector == '&&' and not success or connector == '||' and success:
                        following.append((state, success))
                        continue
                    old = state.copy()
                    certain = self.command(words, redirects, state, UNKNOWN if connector in {'|', '|&'} else stdin)
                    following.append((state, True))
                    if not certain:
                        following.append((old, False))
                outcomes = following
            words, redirects = [], []
            # A pipeline can keep the parent's state; include that context
            # when reading its right side and the commands after it.
            if token in {'|', '|&', '&'}:
                outcomes.append((context.copy(), True))
            if token not in {'&&', '||'}:
                unique: list[tuple[Context, bool]] = []
                for state, _ in outcomes:
                    if not any(state == previous for previous, _ in unique):
                        unique.append((state, True))
                outcomes = unique
            connector = token
            if len(outcomes) > 64:
                raise Unreadable('source: too many possible shell contexts')

    def command(self, words: list[Word], redirects: list[Redirect], context: Context,
                stdin: str | None) -> bool:
        assigned = context.copy()
        expanded: list[str] = []
        assigning = True
        prefixed: set[str] = set()
        for word in words:
            value = self.word(word, assigned if assigning else context)
            expanded.append(value)
            if assigning and (match := ASSIGNMENT.fullmatch(value)):
                assigned.values[match[1]] = match[2]
                prefixed.add(match[1])
            else:
                assigning = False
        descriptors = {0: stdin}
        for redir in redirects:
            target = self.word(redir.target, context)
            body = self.word(redir.body, context) if redir.body is not None else None
            if redir.operator in {'<<', '<<-'}:
                descriptors[redir.fd] = body
            elif redir.operator == '<<<':
                descriptors[redir.fd] = target + '\n'
            elif redir.operator == '<&' and target.isdigit():
                descriptors[redir.fd] = descriptors.get(int(target), UNKNOWN)
            elif redir.operator.startswith('<'):
                descriptors[redir.fd] = UNKNOWN
        stdin = descriptors.get(0)
        if not expanded:
            return False
        if all(ASSIGNMENT.fullmatch(word) for word in expanded):
            context.values = assigned.values
            return True
        assigned.exported.update(prefixed)
        while expanded[:1] == ['!']:
            expanded.pop(0)
        name, args, prefix = invocation(expanded)
        if name is None:
            raise Unreadable(f'source{words[0].span}: command has no readable program')
        if name in {'if', 'then', 'else', 'elif', 'fi', 'for', 'while', 'until',
                    'do', 'done', 'case', 'esac', '{', '}', 'function', 'eval', 'source', '.',
                    'coproc', 'select', 'repeat', 'foreach', 'end', 'noglob', 'nocorrect'}:
            raise Unreadable(f'source{words[0].span}: unsupported executable construct {name!r}')
        for at, word in enumerate(prefix):
            wrapper = Path(word).name
            if wrapper in WRAPPERS:
                following = prefix[at + 1:]
                if following and following[0].startswith('-') and following[0] != '--' and following[0] not in WRAPPER_OPTIONS.get(wrapper, ()):
                    raise Unreadable(f'source{words[0].span}: unsupported wrapper option {following[0]!r}')
            if match := ASSIGNMENT.fullmatch(word):
                assigned.values[match[1]] = match[2]
                assigned.exported.add(match[1])
            if wrapper == 'env':
                rest = prefix[at + 1:]
                if any(a in {'-C', '--chdir', '-S', '--split-string'} or a.startswith(('--chdir=', '--split-string=')) for a in rest):
                    raise Unreadable(f'source{words[0].span}: unsupported env execution context')
                for index, option in enumerate(rest):
                    if option in {'-u', '--unset'}:
                        if index + 1 >= len(rest):
                            raise Unreadable('source: env unset has no name')
                        assigned.values[rest[index + 1]] = UNKNOWN
                        assigned.exported.discard(rest[index + 1])
                    elif option.startswith('--unset='):
                        variable = option.partition('=')[2]
                        assigned.values[variable] = UNKNOWN
                        assigned.exported.discard(variable)
            if wrapper == 'uv' and any(a in {'--directory', '--project'} or a.startswith(('--directory=', '--project=')) for a in prefix[at + 1:]):
                raise Unreadable(f'source{words[0].span}: unsupported uv execution context')
        if name == 'export':
            if any(arg.startswith('-') and arg not in {'--', '-n'} for arg in args):
                context.invalidate(None)
                return False
            unexport = '-n' in args
            names: set[str] = set()
            for arg in args:
                if arg in {'--', '-n'}:
                    continue
                match = ASSIGNMENT.fullmatch(arg)
                variable = match[1] if match else arg
                if not re.fullmatch(r'[a-zA-Z_]\w*', variable):
                    context.invalidate(None)
                    return False
                names.add(variable)
                if match and not unexport:
                    context.values[variable] = match[2]
                if unexport:
                    context.exported.discard(variable)
                else:
                    context.exported.add(variable)
            if unexport:
                context.invalidate(names)
            return True
        if name in {'unset', 'declare', 'typeset', 'local', 'readonly', 'read', 'printf',
                    'mapfile', 'readarray', 'getopts', 'let'}:
            context.invalidate(mutated_names(name, args))
            if name in {'declare', 'typeset', 'local', 'readonly'}:
                context.opaque_variables = True
            return False
        if name in {'cd', 'pushd', 'popd'}:
            change_directory(name, args, context)
            return False
        self.inputs.append(Command(tuple([name, *args]), assigned.cwd, assigned.values))
        if name not in SHELLS and not PYTHON.fullmatch(name):
            return False
        assigned = assigned.invocation()
        source = stdin
        script: str | None = None
        while args:
            arg = args.pop(0)
            if arg == '-c':
                if not args:
                    raise Unreadable('source: interpreter -c has no input')
                source = args[0]
                break
            if arg == '-m':
                return False
            if arg == '-' or arg == '-s':
                break
            if arg.startswith('-'):
                if arg in {'-u', '-B', '-E', '-I', '-S', '-O', '-OO', '--', '-e', '-x', '-f', '-l'}:
                    continue
                raise Unreadable(f'source: unsupported interpreter option {arg!r}')
            script = arg
            break
        if script is not None:
            if PYTHON.fullmatch(name) and (path := resolved(script, assigned.cwd)) is not None:
                self.inputs.append(PythonFile(path))
            return False
        if source is None:
            return False
        if UNKNOWN in source:
            raise Unreadable('source: interpreter input has an unresolved expansion or redirection')
        if name in SHELLS:
            self.visit(Lexer(source).tokens(), assigned, stdin)
        else:
            self.inputs.append(PythonInput(source))
        return False


@dataclass(frozen=True)
class Read:
    inputs: tuple[Input, ...]


@dataclass(frozen=True)
class Refusal:
    reason: str


def executable_inputs(command: str, cwd: Path) -> Read | Refusal:
    """Fully visited commands and Python inputs, or an executable-source refusal."""
    try:
        visitor = Visitor()
        visitor.visit(Lexer(command).tokens(), Context(cwd, dict(os.environ) | {'PWD': str(cwd)}, set(os.environ) | {'PWD'}))
        return Read(tuple(visitor.inputs))
    except (ValueError, RecursionError, OSError) as exc:
        return Refusal(str(exc) or 'source: executable nesting exceeds the reader bound')


def resolved(word: str, cwd: Path | None) -> Path | None:
    """Resolve a delete's parent, keeping a final symbolic link at its own path."""
    if UNKNOWN in word or not word:
        return None
    glob = GLOB.search(word)
    if glob:
        prefix = word[:glob.start()]
        word = prefix.rsplit('/', 1)[0] if '/' in prefix else '.'
        word = word or '/'
    try:
        path = Path(word).expanduser()
        if not path.is_absolute():
            if cwd is None:
                return None
            path = cwd / path
        return path.resolve() if word.rstrip('/').rsplit('/', 1)[-1] in {'.', '..', ''} else path.parent.resolve() / path.name
    except (RuntimeError, OSError, ValueError) as exc:
        raise Unreadable(f'source operand {word!r}: {exc}') from exc


def operands(args: list[str], valued: frozenset[str] = frozenset()) -> list[str]:
    out: list[str] = []
    at = 0
    while at < len(args):
        arg = args[at]
        at += 1
        if arg == '--':
            return out + args[at:]
        if arg in valued:
            at += 1
        elif not arg.startswith('-'):
            out.append(arg)
    return out


def deleted(command: Command, scratch_only: bool) -> list[Path | None]:
    """Delete operands of a fully visited simple command, in command order."""
    name, args = segment_program(list(command.words))
    cwd = command.cwd
    paths: list[str] = []
    if name in {'rm', 'rmdir', 'unlink'}:
        paths = operands(args)
    elif name == 'mv' and scratch_only:
        paths = operands(args, frozenset({'-t', '--target-directory', '-S', '--suffix'}))
        if not any(a in {'-t', '--target-directory'} or a.startswith('--target-directory=') for a in args):
            paths = paths[:-1]
    elif name == 'find' and '-delete' in args:
        paths = []
        for arg in args:
            if arg in {'-H', '-L', '-P', '--'}:
                continue
            if arg.startswith('-') or arg in {'(', '!', ')'}:
                break
            paths.append(arg)
        paths = paths or ['.']
    elif name == 'xargs':
        program, _ = segment_program(operands(args, frozenset({'-I', '-i', '-n', '-P', '-s', '-d', '-E', '-L', '-a'})))
        if program in {'rm', 'rmdir', 'unlink'}:
            return [None]
    elif name == 'git':
        while args and args[0].startswith('-'):
            arg = args.pop(0)
            if arg == '-C' and args:
                cwd = resolved(args.pop(0), cwd)
            elif arg.startswith('-C'):
                cwd = resolved(arg[2:], cwd)
            elif arg in {'-c', '--git-dir', '--work-tree', '--namespace'} and args:
                args.pop(0)
        if args[:1] == ['clean']:
            return [cwd]
        if args[:1] == ['rm']:
            paths = operands(args[1:])
        elif args[:2] == ['worktree', 'remove']:
            paths = operands(args[2:])
    return [resolved(path, cwd) for path in paths]


def unreadable_reason(source: str) -> str:
    return mctx('Blocked: executable input cannot be read: {source}. Leave the paths in place.').format(source=source)


def check(hook: Hook) -> str | None:
    from engine import checkout
    from run_reads import agent_type, caller_transcript, hook_session
    from tree_reads import scratch

    if hook['tool_name'] != 'Bash':
        return None
    try:
        kind = agent_type(caller_transcript(hook))
    except ValueError:
        return None
    if kind is None or kind == 'main' or not (checkout.agents() / f'{kind}.md').is_file():
        return None
    session = hook_session(hook)
    own = scratch(session.name, session.parent.name).resolve()
    only = kind in SCRATCH_ONLY
    roots = [own]
    if not only:
        roots += [checkout.main_worktree(checkout.ROOT).resolve(), Path('/private/tmp'), Path(tempfile.gettempdir()).resolve()]
    result = executable_inputs(hook['tool_input']['command'], Path(hook.get('cwd') or checkout.ROOT))
    if isinstance(result, Refusal):
        return unreadable_reason(result.reason)
    shared = Path(f'/private/tmp/claude-{os.getuid()}')
    for item in result.inputs:
        target: str | Path | None = None
        if isinstance(item, Command):
            try:
                paths = deleted(item, only)
            except Unreadable as exc:
                return unreadable_reason(str(exc))
            for path in paths:
                if path is None:
                    if only or segment_program(list(item.words))[0] == 'xargs':
                        target = shlex.join(word.replace(UNKNOWN, '<unknown>') for word in item.words)
                        break
                elif not path.is_relative_to(own) and (path.is_relative_to(shared) or not any(path.is_relative_to(root) for root in roots)):
                    target = path
                    break
        elif only:
            if isinstance(item, PythonFile):
                if not item.path.is_relative_to(own) or item.path.suffix != '.py':
                    continue
                try:
                    text = item.path.read_text()
                except (OSError, UnicodeError) as exc:
                    return unreadable_reason(f'{item.path}: {exc}')
            else:
                text = item.text
            if match := PYTHON_DELETE.search(text):
                target = match[0]
        if target is not None:
            return mctx('Blocked: this call deletes {target}. Your permitted roots are {roots}, excluding paths under {shared} outside your session scratch directory. Leave the path in place.').format(target=target, roots=', '.join(map(str, roots)), shared=shared)
    return None
