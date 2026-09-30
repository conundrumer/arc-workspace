"""The commands, each a few lines over the packages below: load the
solver, call the checks, surveys or solve functions it needs, render
through `checker`, and exit by the pass rule."""

import sys


def main(argv: list[str]) -> int:
    """Run the command `argv` names; a first argument that names no
    command runs `run`. The stamp of the code the process loaded goes to
    stderr after the command, so that what a command writes for a program
    stays as it is."""
    from checker.render import commands
    from cli.common import stamp
    from cli.parser import parser

    taken = stamp()
    top, names = parser()
    if not argv or argv[0] not in (*names, "-h", "--help"):
        argv = ["run", *argv]
    args = top.parse_args(argv)
    code = args.handler(args)
    sys.stdout.flush()
    print(commands.STAMP.format(stamp=taken), file=sys.stderr)
    return code
