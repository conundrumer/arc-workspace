"""The abstract execution of shell source for `delete_bash_hook`: `Visitor`
walks the tokens that `shell_lexer.Lexer` gives, tracking the working
directory and the variables of each possible shell context without running
a command, and collects the commands and Python inputs the source would run
(`executable_inputs`). A wrapper option it cannot read, or an execution
context it cannot model, raises `Unreadable`."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from command_labels import ASSIGNMENT, VARIABLE, WRAPPER_FLAGS, WRAPPER_OPTIONS, WRAPPERS, segment_program
from shell_lexer import DOLLAR, UNKNOWN, Lexer, Redirect, Token, Unreadable, Word

GLOB = re.compile(r"[*?[]")
SHELLS = {"bash", "sh", "zsh"}
PYTHON = re.compile(r"python[\d.]*$")


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
                admitted = WRAPPER_OPTIONS.get(wrapper, frozenset()) | WRAPPER_FLAGS.get(wrapper, frozenset())
                if following and following[0].startswith('-') and following[0] != '--' and following[0] not in admitted:
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
