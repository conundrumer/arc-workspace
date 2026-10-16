"""The entry point of `scripts/run_dl.py`."""

import sys

from checker.render import commands
from cli import command_args
from cli.common import stamp
from cli.parser import parser
from engine import rwlock
from engine.duration import footer


def main(argv: list[str]) -> int:
    """Run the command `argv` names, as `command_args` reads it, under the
    shared hold of the heavy commands' lock. The stamp of the code the
    process loaded goes to stderr after the command, so that what a command
    writes for a program stays as it is, and after it the duration footer
    (`engine.duration`)."""
    taken = stamp()
    args = parser().parse_args(command_args(argv))
    with footer(f"run_dl {args.cmd}"):
        with rwlock.held(rwlock.Hold.SHARED):
            code = args.handler(args)
        sys.stdout.flush()
        print(commands.STAMP.format(stamp=taken), file=sys.stderr)
    return code
