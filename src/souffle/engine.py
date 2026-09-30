"""`SouffleEngine`, the `engine.Engine` over the Souffle binary."""

from collections.abc import Mapping, Sequence
from pathlib import Path

from engine.engine import (
    Index,
    InputValue,
    Limits,
    ParseFailure,
    RelationValue,
    RemovalTarget,
    Rendered,
    RunResult,
)
from engine import checkout
from engine.program import Program, RelationName
from souffle import expand, ops, parser, render
from souffle.index import index_of
from souffle.run import Runner

FUNCTOR_DIR = checkout.programs()
"""Where `libfunctors.dylib`, the lib's functors, stands, in the checkout
at import."""
CACHE_DIR = checkout.scratch() / "cache" / "engine-souffle"
"""Where each run is stored under the hash of all it reads, in the
checkout at import."""


class SouffleEngine:
    """Parses, rewrites, renders and runs Souffle programs. `functor_dir`
    holds the functor library every run links; `cache_dir` stores runs, and
    None stores none."""

    def __init__(self, functor_dir: Path | None = FUNCTOR_DIR,
                 cache_dir: Path | None = CACHE_DIR):
        self.runner = Runner(functor_dir, cache_dir)

    def parse(self, text: str, base_dir: Path) -> Program | ParseFailure:
        return parser.parse(text, base_dir)

    def index(self, program: Program) -> Index:
        return index_of(program)

    def fix_relation(self, program: Program, relation: RelationName,
                     value: RelationValue) -> Program:
        """Raises `ValueError` where no declaration answers `relation`, and
        for a grid on a stamp or sparse GRID form (`souffle.ops`)."""
        return ops.fix_relation(program, relation, value)

    def remove(self, program: Program, target: RemovalTarget) -> Program:
        """Raises `ValueError` where `program` lacks `target`."""
        return ops.remove(program, target)

    def instantiate(self, program: Program, component: str, name: str) -> Program:
        """Raises `ValueError` where no top-level component is `component`."""
        return ops.instantiate(program, component, name)

    def run(self, program: Program, inputs: Mapping[RelationName, InputValue],
            outputs: Sequence[RelationName], limits: Limits,
            caps: Mapping[RelationName, int] | None = None) -> RunResult:
        return self.runner.run(program, inputs, outputs, limits, caps)

    def expand(self, program: Program) -> Program:
        return expand.expand(program)

    def render(self, program: Program) -> Rendered:
        return render.render(program)

    def format(self, program: Program) -> str:
        return render.format_program(program)
