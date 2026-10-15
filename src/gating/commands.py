"""The gate commands, the stems each runs on, and the fixed inputs under
`tests/gate/` they read."""

import textwrap
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from engine import checkout
from handbook.readers import CONTEXT_READERS, ArgumentForm

GATE = checkout.ROOT / "tests" / "gate"
SOLVERS = GATE / "solvers"
WITNESSES = GATE / "witnesses"
FROZEN = GATE / "frozen"
INPUTS = GATE / "inputs"
ACCEPTED = GATE / "accepted"
DOCUMENTS = GATE / "documents"
"""The documents a context command renders, laid out as the checkout is."""

STEMS = ("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602", "a096bf4d",
         "9b4c17c4", "a5f85a15")
"""The stems `run` runs on, of which each other command that reads no grid
input runs on those with the least accepted time whose runs together cover
every line of `src/` and `scripts/` that its runs on all of them cover, but
the lines of the run cache's pruning, which a run reaches by a random draw.
`sweep` also runs on 9b30e358, whose swept parameters' values are symbols."""
SWEEP_STEM = "a934301b"
"""The stem `sweep` runs on besides those of `STEMS`, whose sweep marks the
gaps of a parameter under a case marker."""
BRANCH_STEM = "abbfd121"
"""The stem `audit` and `derive` run on besides those of `STEMS`, whose branches
render with their recorded witnesses."""
RECORD_STEM = "a61ba2ce"
"""The stem the commands that read a grid input run on, whose witness file
the inputs fit."""
LIB_STEMS = ("6e453dd6", "33067df9", "97a05b5b", "6d1d5c90", "99306f82", "6165ea8f",
             "ca8de6ea", "f8b3ba0a", "ff28f65a", "409aa875", "aa62e3f4", "50846271",
             "89565ca0", "696d4842", "0dfd9992", "4c7dc4dd", "84551f4c")
"""The stems `run` runs on besides `STEMS`. A component is a `.comp` that a
module under `programs/lib/` declares. A solver uses a component where its
program instantiates it, directly, inside an instance of another component,
or as the base of a component it so instantiates, so that the component runs
when the solver runs. Every component that some solver under
`programs/solvers/` uses is used by a solver of a stem `run` runs on."""

type Sub = Literal["run", "lint", "witness", "derive", "store", "audit",
                   "record", "sweep", "determination-plan", "deletions", "grid",
                   "relation", "drop-one", "derived-constant", "expand", "size",
                   "keywords"]
"""The `run_dl.py` subcommands the gate runs."""

WITNESS_FILE_SUBS: frozenset[Sub] = frozenset({"derive", "audit", "store", "witness", "record"})
"""The subcommands given a witness file, which is then one of the
command's outputs."""

type Ext = Literal["txt", "wit.json", "rc"]
"""The extension of an output file: the normalized output, the witness file,
and the exit code."""
EXTS: tuple[Ext, ...] = ("txt", "wit.json", "rc")
"""Every output file's extension, in the order a command's are compared."""


def frozen_witness(stem: str) -> Path:
    """The frozen witness file of `stem`, which a command that takes a
    witness file is given a copy of."""
    return FROZEN / f"{stem}.wit.json"


@dataclass(frozen=True)
class Named:
    """A gate command's name in output file names."""
    name: str

    def key(self, stem: str) -> str:
        """The name of the command's output files and accepted time on
        `stem`, less the extension."""
        return f"{self.name}-{stem}"


@dataclass(frozen=True)
class Command(Named):
    """A gate command: its name in output file names, the `run_dl.py`
    subcommand, the arguments between the stem and the witness file, the
    arguments after the witness file, and the stems it runs on."""
    sub: Sub
    args: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()
    stems: tuple[str, ...] = STEMS

    @property
    def takes_witness_file(self) -> bool:
        return self.sub in WITNESS_FILE_SUBS

    def argv(self, stem: str, witness_file: Path) -> list[str]:
        """The `run_dl.py` arguments of the command on `stem`."""
        wf = ["--witness-file", str(witness_file)] if self.takes_witness_file else []
        return [self.sub, stem, *self.args, *wf, *self.extra]

    @property
    def exts(self) -> tuple[Ext, ...]:
        return tuple(e for e in EXTS if e != "wit.json" or self.takes_witness_file)

    @property
    def reads_input(self) -> bool:
        """Whether one of the command's arguments is a grid input under
        `INPUTS`."""
        return any(Path(a).is_relative_to(INPUTS) for a in self.args)

    script = "run_dl.py"
    """The script under `scripts/` the command runs."""

    def copied(self, stem: str) -> tuple[Path, ...]:
        """The files and directories the gate copies for the command on
        `stem` before it runs: the frozen witness file it is given."""
        return (frozen_witness(stem),) if self.takes_witness_file else ()


@dataclass(frozen=True)
class ContextCommand(Named):
    """A gate command that prints readers' contexts through
    `scripts/context.py context`, rendered from a copy of `DOCUMENTS`: its
    name in output file names, and each reader with its arguments. Its
    stems are its readers, each its arguments joined by `-`."""
    readers: tuple[tuple[str, ...], ...]

    takes_witness_file = False
    exts: ClassVar[tuple[Ext, ...]] = ("txt", "rc")
    script = "context.py"
    """The script under `scripts/` the command runs."""

    @property
    def stems(self) -> tuple[str, ...]:
        return tuple("-".join(r) for r in self.readers)

    def argv(self, stem: str, witness_file: Path) -> list[str]:
        """The `context.py` arguments of the command on the reader `stem`."""
        return ["context", *dict(zip(self.stems, self.readers, strict=True))[stem]]

    def copied(self, stem: str) -> tuple[Path, ...]:
        """The files and directories the gate copies for the command
        before it runs: `DOCUMENTS`."""
        return (DOCUMENTS,)


type GateCommand = Command | ContextCommand


def _record(name: str, label: str, input_file: str, *extra: str) -> Command:
    """A `record` command adding the entry `label` to the witness file, with
    the inputs of a replay call read from `input_file` under `inputs/`."""
    return Command(name, "record", (label, str(INPUTS / input_file), *extra),
                   stems=(RECORD_STEM,))


def named_readers() -> list[tuple[str, str]]:
    """Each reader the `context` command takes by name, with each name
    `DOCUMENTS` defines for it."""
    return [(reader, name) for reader, known in CONTEXT_READERS.items()
            if known.form is ArgumentForm.NAME for name in known.values(DOCUMENTS)]


COMMANDS: dict[str, GateCommand] = {c.name: c for c in (
    Command("run", "run", stems=(*STEMS, SWEEP_STEM, BRANCH_STEM, *LIB_STEMS)),
    Command("lint", "lint", stems=("9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602", "9b4c17c4",
                                   "a5f85a15")),
    Command("witness", "witness", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce",
                                         "a04b2602", "a5f85a15")),
    Command("witnesseverycase", "witness", extra=("--every-case",),
            stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602", "a5f85a15")),
    Command("derive", "derive", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                       "a096bf4d", "a5f85a15", BRANCH_STEM)),
    Command("store", "store", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                     "a096bf4d", "a5f85a15")),
    Command("audit", "audit", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                     "a096bf4d", "a5f85a15", BRANCH_STEM)),
    _record("recordnew", "touching-pieces", "a61ba2ce_edge-touch.txt", "--separates",
            "The edge-touch input under a new id."),
    _record("recordreplace", "two-color-l", "a61ba2ce_edge-touch.txt", "--separates", "test"),
    _record("recordassign", "gap-outward", "a61ba2ce_gap-outward.txt", "--assign",
            '{"corner_quadrant": [["DIAG_TL", "DIAG_BR"], ["DIAG_TR", "DIAG_BL"], '
            '["DIAG_BL", "DIAG_TR"], ["DIAG_BR", "DIAG_TL"]]}', "--separates",
            "The gap-outward input with the stored map sending each missing corner to the opposite quadrant, as the concept does."),
    Command("sweep", "sweep", stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                     "a5f85a15", SWEEP_STEM)),
    Command("determination-plan", "determination-plan",
            stems=("9c1e755f", "9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602", "9b4c17c4",
                   "a5f85a15")),
    Command("deletions", "deletions", stems=("9b30e358", "9b2a60aa", "a61ba2ce", "a04b2602",
                                             "a096bf4d", "9b4c17c4", "a5f85a15")),
    Command("grid", "grid", (str(INPUTS / "a61ba2ce_two-color-l.txt"),), stems=(RECORD_STEM,)),
    Command("relation", "relation", ("out", str(INPUTS / "a61ba2ce_two-color-l.txt")),
            stems=(RECORD_STEM,)),
    Command("drop-one", "drop-one", stems=("9c1e755f", "9b2a60aa", "a61ba2ce", "a04b2602",
                                           "9b4c17c4", "a5f85a15")),
    Command("derived-constant", "derived-constant",
            stems=("9b2a60aa", "a61ba2ce", "a04b2602", "9b4c17c4", "a5f85a15")),
    Command("expand", "expand", stems=("9b2a60aa", "a61ba2ce", "a04b2602", "9b4c17c4", "a5f85a15")),
    Command("size", "size", stems=("9c1e755f", "9b2a60aa", "a61ba2ce", "a04b2602", "a5f85a15")),
    Command("keywords", "keywords", stems=("9c1e755f", "9b2a60aa", "a61ba2ce", "a04b2602",
                                           "a5f85a15")),
    ContextCommand("context", (("session",), ("codex",), *named_readers())),
)}
"""Every gate command, in the order a pass runs them."""


def command_of(output: str) -> GateCommand | None:
    """The gate command whose accepted output `output` is, a path whose
    file name is a key of that command followed by an extension, or None
    where it is no command's."""
    key = Path(output).name.split(".", 1)[0]
    return next((c for c in COMMANDS.values() if key in keys_of([c])), None)


def keys_of(cmds: Iterable[GateCommand]) -> set[str]:
    return {c.key(s) for c in cmds for s in c.stems}


def dropped_stems(cmd: GateCommand) -> tuple[str, ...]:
    """The stems of `STEMS` that `cmd` does not run on, where it is a
    command that reads no grid input and so runs on a stem list chosen
    from `STEMS`; none for any other command."""
    if not isinstance(cmd, Command) or cmd.reads_input:
        return ()
    return tuple(s for s in STEMS if s not in cmd.stems)


def stems_listing() -> str:
    """Each gate command, in the order a pass runs them, with the stems it
    runs on, for the end of `--help`."""
    return "The stems each command runs on:\n\n" + "\n".join(
        textwrap.fill(" ".join(c.stems), width=78, initial_indent=f"  {c.name}: ",
                      subsequent_indent=" " * 4, break_on_hyphens=False)
        for c in COMMANDS.values())
