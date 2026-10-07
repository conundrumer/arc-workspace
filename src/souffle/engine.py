"""`SouffleEngine`, the `engine.Engine` over the Souffle binary."""

from collections.abc import Mapping, Sequence
from pathlib import Path

from engine.engine import (
    Classed,
    GridMisfit,
    GridValue,
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
from engine.program import (DeclId, GridLayout, Instance, Program, RelationName,
                            Scope, TypeName)
from souffle import classify, expand, ops, parser, printer, render
from souffle.index import index_of
from souffle.run import Runner

FUNCTOR_DIR = checkout.programs()
"""Where the functor library (`run.FUNCTOR_LIB`) and its source stand, in
the checkout at import."""
CACHE_DIR = checkout.cache() / "engine-souffle"
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

    def parse_including(self, text: str, included: str,
                        base_dir: Path) -> Program | ParseFailure:
        return self.parse(f"{render.include(included)}\n#line 1\n{text}",
                          base_dir)

    def lib_instance(self, lib: Path, instance: str, component: str,
                     type_arguments: Sequence[TypeName]) -> Program | ParseFailure:
        """A program that includes the lib file `lib` and instantiates
        `component` at `type_arguments` as `instance`."""
        # The printer reads no id of the instance it prints.
        init = Instance(DeclId(0), instance, Scope(()), component,
                        tuple(type_arguments), None)
        text = f"{render.include(lib.name)}\n{printer.declaration(init)}\n"
        return self.parse(text, lib.parent)

    def index(self, program: Program) -> Index:
        return index_of(program)

    def fix_relation(self, program: Program, relation: RelationName,
                     value: RelationValue) -> Program:
        """Raises `ValueError` where no declaration answers `relation`, and
        for a grid it cannot place in the relation's GRID form
        (`souffle.ops`)."""
        return ops.fix_relation(program, relation, value)

    def place_grid(self, layout: GridLayout, mark: tuple[int, int] | None,
                   value: GridValue) -> GridValue | GridMisfit:
        """Raises `ValueError` for a stamp layout with no `mark`."""
        return ops.place_grid(layout, mark, value)

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

    def classify(self, program: Program, relation: RelationName,
                 column: int) -> Classed:
        return classify.classify(program, relation, column)

    def expand(self, program: Program) -> Program:
        return expand.expand(program)

    def render(self, program: Program) -> Rendered:
        return render.render(program)
