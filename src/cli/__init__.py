"""The commands, each a few lines over the packages below: load the
solver, call the checks, surveys or solve functions it needs, render
through `checker`, and exit by the pass rule."""

import sys
from collections.abc import Collection

HELP_FLAGS = ("-h", "--help")


def command_args(argv: list[str], names: Collection[str]) -> list[str]:
    if not argv or argv[0] not in (*names, *HELP_FLAGS):
        return ["run", *argv]
    return argv


def main(argv: list[str]) -> int:
    """Run the command `argv` names, as `command_args` reads it, under the
    shared hold of the heavy commands' lock. The stamp of the code the
    process loaded goes to stderr after the command, so that what a command
    writes for a program stays as it is."""
    from checker.render import commands
    from cli.common import stamp
    from cli.parser import parser
    from engine import rwlock

    taken = stamp()
    top, names = parser()
    args = top.parse_args(command_args(argv, names))
    with rwlock.held(rwlock.Hold.SHARED):
        code = args.handler(args)
    sys.stdout.flush()
    print(commands.STAMP.format(stamp=taken), file=sys.stderr)
    return code
