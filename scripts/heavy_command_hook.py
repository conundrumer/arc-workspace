"""PreToolUse check on Bash and Monitor: denies a call that runs a heavy
command outside `<checkout>/scripts/run_heavy.py`, or inside it with a
worker-count argument over its `--cpus`.

The check reads each simple command of the call, and of the `-c` script of a
`bash`, `sh` or `zsh` it runs, as `command_labels.segment_program` gives the
program and its arguments. A command is heavy where its program and
subcommand stand in `HEAVY`, or where it gives `--workers`, `--jobs` or
`--threads` over 1, or `cargo` gives `-j` over 1. A command with `--help` or
`--version` is not heavy. A heavy command is gated where `run_heavy.py` is
among its wrappers or among the wrappers of the shell command that holds it,
and the gate declares the `--cpus` that follows it (1 where none does), at
most the `--cpus` of the gates around it.

A worker count that the command line does not give as a number, such as a
shell variable, is not read."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hook_entry import not_registered

GATE = "run_heavy.py"
SHELLS = frozenset({"bash", "sh", "zsh"})
ANY = None
HEAVY: dict[str, frozenset[str] | None] = {
    "cargo": frozenset({"build", "test", "run", "bench", "clippy", "check", "doc", "install"}),
    "maturin": frozenset({"build", "develop"}),
    "arclog-cli": ANY,
    "arclog_convert.convert": ANY,
    "arclog_convert.row_parity": ANY,
    "arclog_convert.verify": ANY,
    "arclog_convert.lint": ANY,
    "tables_export.py": ANY,
    "export_checks.py": ANY,
    "change_checks.py": ANY,
    "encoder_check.py": ANY,
    "pretrain.py": ANY,
    "allpoints.py": ANY,
    "run_dl.py": ANY,
}
"""For each heavy program, the subcommands that make a call heavy, or `ANY`."""
WORKER_OPTIONS = frozenset({"--workers", "--jobs", "--threads"})
NOT_RUNS = frozenset({"--help", "--version"})
GATE_OPTIONS = frozenset({"--cpus", "--gib", "--need", "--minutes", "--wait"})
FORM = "<checkout>/scripts/run_heavy.py [--cpus <n>] [--need now|soon|idle] <command>"


@dataclass(frozen=True)
class Gate:
    """A gate call around a command: the CPUs it declares, or None where its
    `--cpus` is not a number."""

    cpus: int | None


def narrowed(outer: Gate | None, inner: Gate | None) -> Gate | None:
    """The gate a command runs under where `inner` runs under `outer`."""
    if outer is None or inner is None:
        return inner or outer
    known = [n for n in (outer.cpus, inner.cpus) if n is not None]
    return Gate(min(known) if known else None)


def gate_of(prefix: list[str]) -> Gate | None:
    """The gate among the wrappers `prefix`, the words before a program."""
    for at, word in enumerate(prefix):
        if Path(word).name != GATE:
            continue
        cpus: int | None = 1
        rest = prefix[at + 1:]
        while rest and rest[0].partition("=")[0] in GATE_OPTIONS:
            name, equals, value = rest.pop(0).partition("=")
            if not equals and rest:
                value = rest.pop(0)
            if name == "--cpus":
                cpus = int(value) if value.isdigit() else None
        return Gate(cpus)
    return None


def workers(program: str, args: list[str]) -> int | None:
    """The largest worker count the arguments `args` of `program` give, or
    None where they give none."""
    found: list[int] = []
    for at, arg in enumerate(args):
        name, equals, value = arg.partition("=")
        if name in WORKER_OPTIONS or (program == "cargo" and name == "-j"):
            if not equals:
                value = args[at + 1] if at + 1 < len(args) else ""
        elif program == "cargo" and arg.startswith("-j"):
            value = arg[2:]
        else:
            continue
        if value.isdigit():
            found.append(int(value))
    return max(found, default=None)


def subcommand(args: list[str]) -> str | None:
    """The first argument that is no option and no toolchain."""
    return next((a for a in args if not a.startswith(("-", "+"))), None)


def heavy(program: str, args: list[str]) -> bool:
    if NOT_RUNS & set(args):
        return False
    if program in HEAVY:
        subcommands = HEAVY[program]
        if subcommands is None or subcommand(args) in subcommands:
            return True
    return (workers(program, args) or 0) > 1


def refusal(program: str, args: list[str], gate: Gate | None) -> str | None:
    """The reason to refuse the command `program` with `args` run under
    `gate`, or None."""
    from controlled_markdown import mctx

    if not heavy(program, args):
        return None
    if gate is None:
        return mctx("Blocked: `{program}` is a heavy command and runs outside the gate. "
                    "Run it as `{form}`, with `--cpus` the processes or threads it runs at once.").format(
            program=program, form=FORM)
    count = workers(program, args)
    if count is not None and gate.cpus is not None and count > gate.cpus:
        return mctx("Blocked: `{program}` runs {count} workers, over the {cpus} CPUs its gate call declares. "
                    "Run it as `<checkout>/scripts/run_heavy.py --cpus {count} <command>`.").format(
            program=program, count=count, cpus=gate.cpus)
    return None


def refusals(command: str, outer: Gate | None) -> Iterator[str]:
    """The reason to refuse each heavy command of the Bash command
    `command`, which runs under the gate `outer`."""
    from command_labels import segment_program, simple_commands

    for words in simple_commands(command):
        program, args = segment_program(words)
        if program is None:
            continue
        prefix = words[:len(words) - len(args)]
        gate = narrowed(outer, gate_of(prefix))
        if program in SHELLS and prefix[-1:] == ["-c"] and args:
            yield from refusals(args[0], gate)
        elif (reason := refusal(program, args, gate)) is not None:
            yield reason


def check(hook: dict[str, Any]) -> str | None:
    """The reasons to deny a Bash or Monitor call that runs a heavy command
    outside its gate, or None."""
    if hook["tool_name"] not in ("Bash", "Monitor"):
        raise not_registered("Bash and Monitor", "tool", hook["tool_name"])
    reasons = list(refusals(hook["tool_input"]["command"], None))
    return "\n".join(reasons) if reasons else None

