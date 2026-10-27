"""Refuse project agents' Bash deletes outside their permitted directories.

Executable shell input is visited (`shell_visitor`, over the tokens of
`shell_lexer`) before words are projected for operand checks. Unreadable
executable syntax produces a refusal.
"""

import os
import re
import shlex
import tempfile
from pathlib import Path

from command_labels import segment_program
from controlled_markdown import mctx
from hook_entry import Hook
from operations.roles import Role
from shell_lexer import UNKNOWN, Unreadable
from shell_visitor import Command, PythonFile, Refusal, executable_inputs, resolved

SCRATCH_ONLY = frozenset({Role.TICKET_REVIEWER, Role.CODE_REVIEWER,
                         Role.DESIGN_REVIEWER, Role.DOC_REVIEWER,
                         Role.ITEM_CHECKER, Role.LIB_REVIEWER})
PYTHON_DELETE = re.compile(r"\b(?:shutil\.rmtree|os\.(?:remove|unlink|rmdir))\s*\(|\.(?:unlink|rmdir)\s*\(")


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
