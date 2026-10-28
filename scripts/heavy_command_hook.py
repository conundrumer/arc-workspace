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
shell variable, is not read.

A command is also heavy where the Python code its interpreter runs calls a
module of `HEAVY` with entry `ANY`. That code is the `-c` argument of a
`python`, the text of the `.py` script file a `python` runs, or the bodies of
the heredocs of the call where a `python` runs neither `-c` code nor a
script. A call counts where its function is a name, or a chain of attribute
names, that starts at a name an `import` or a `from ... import` binds to the
module or to a name of it, or where the code gives `from <module> import *`.
A name that the code only reads, and a module it only imports, are not
calls. Code that does not parse, and a script file that cannot be read as
text, call nothing."""

import ast
import re
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
    "codex": frozenset({"app-server"}),
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


def bindings(tree: ast.AST) -> tuple[dict[str, str], list[str]]:
    """The dotted name each name that an import of `tree` binds stands for,
    and the modules it gives `from <module> import *`."""
    names: dict[str, str] = {}
    stars: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    names[alias.asname] = alias.name
                else:
                    first = alias.name.partition(".")[0]
                    names[first] = first
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                if alias.name == "*":
                    stars.append(node.module)
                else:
                    names[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return names, stars


def dotted(function: ast.expr) -> list[str] | None:
    """The names of the chain `a.b.c` that `function` is, or None."""
    if isinstance(function, ast.Name):
        return [function.id]
    if isinstance(function, ast.Attribute) and (head := dotted(function.value)) is not None:
        return [*head, function.attr]
    return None


def heavy_calls(code: str) -> str | None:
    """The first module of `HEAVY` with entry `ANY` whose callable the
    Python `code` calls, or None."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return None
    names, stars = bindings(tree)
    called: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (chain := dotted(node.func)) is not None and chain[0] in names:
            called.append(".".join([names[chain[0]], *chain[1:]]))
    return next((module for module, subcommands in HEAVY.items()
                 if subcommands is None
                 and (module in stars or any(name.startswith(module + ".") for name in called))), None)


def script_text(path: Path) -> str | None:
    """The text of the file `path`, or None where it does not exist or is no text."""
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError):
        return None


def heredoc_bodies(command: str) -> str:
    """The bodies of the heredocs of the Bash command `command`, joined."""
    from operations.command_words import HEREDOC

    return "\n".join(m[0].partition("\n")[2].rpartition("\n")[0] for m in HEREDOC.finditer(command))


def python_code(program: str, args: list[str], prefix: list[str], command: str, cwd: Path) -> str | None:
    """The Python code the simple command `program` with `args` and the
    words `prefix` before them runs, as the Bash command `command` gives
    it, in the directory `cwd`, or None."""
    if re.fullmatch(r"python[\d.]*", program):
        if prefix[-1:] == ["-c"]:
            return args[0] if args else None
        return heredoc_bodies(command)
    if program.endswith(".py"):
        return script_text(cwd / prefix[-1])
    return None


def refusal(program: str, args: list[str], prefix: list[str], gate: Gate | None,
            command: str, cwd: Path) -> str | None:
    """The reason to refuse the command `program` with `args` and the words
    `prefix` before them, which the Bash command `command` gives and which
    runs in `cwd` under `gate`, or None."""
    from controlled_markdown import mctx

    module = None
    if not heavy(program, args):
        code = python_code(program, args, prefix, command, cwd)
        module = heavy_calls(code) if code else None
        if module is None:
            return None
    if gate is None:
        what = (mctx("`{program}` runs code that calls `{module}`, a heavy module, outside the gate.")
                if module else mctx("`{program}` is a heavy command and runs outside the gate."))
        return "Blocked: " + what.format(program=program, module=module) + " " + mctx(
            "Run it as `{form}`, with `--cpus` the processes or threads it runs at once.").format(form=FORM)
    count = workers(program, args)
    if count is not None and gate.cpus is not None and count > gate.cpus:
        return mctx("Blocked: `{program}` runs {count} workers, over the {cpus} CPUs its gate call declares. "
                    "Run it as `<checkout>/scripts/run_heavy.py --cpus {count} <command>`.").format(
            program=program, count=count, cpus=gate.cpus)
    return None


def refusals(command: str, outer: Gate | None, cwd: Path) -> Iterator[str]:
    """The reason to refuse each heavy command of the Bash command
    `command`, which runs in `cwd` under the gate `outer`."""
    from command_labels import segment_program, simple_commands

    for words in simple_commands(command):
        program, args = segment_program(words)
        if program is None:
            continue
        prefix = words[:len(words) - len(args)]
        gate = narrowed(outer, gate_of(prefix))
        if program in SHELLS and prefix[-1:] == ["-c"] and args:
            yield from refusals(args[0], gate, cwd)
        elif (reason := refusal(program, args, prefix, gate, command, cwd)) is not None:
            yield reason


def check(hook: dict[str, Any]) -> str | None:
    """The reasons to deny a Bash or Monitor call that runs a heavy command
    outside its gate, or None."""
    if hook["tool_name"] not in ("Bash", "Monitor"):
        raise not_registered("Bash and Monitor", "tool", hook["tool_name"])
    from engine import checkout

    cwd = Path(hook.get("cwd") or checkout.ROOT)
    reasons = list(refusals(hook["tool_input"]["command"], None, cwd))
    return "\n".join(reasons) if reasons else None

