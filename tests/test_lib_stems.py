"""The components of the lib the gate's `run` reaches. A solver added,
dropped or redone can leave a component that some solver uses outside the
stems `run` runs on, and the gate then passes a change to that component
in silence."""

from pathlib import Path

from engine import checkout
from engine.program import Program
from solver.model import Graph, component_chain, parse_with_lib
from souffle.engine import SouffleEngine
from tests.conftest import script


def used(engine: SouffleEngine, solver: Path) -> set[str]:
    """The components the program of `solver` instantiates anywhere in the
    instance tree `Graph` walks, with the bases of each."""
    program = parse_with_lib(engine, solver.read_text())
    assert isinstance(program, Program), f"{solver} does not parse: {program}"
    components = {c.name: c for c in program.components}
    return {name for comp in Graph(program, engine)._tree().values()
            for name in component_chain(components, comp) if name is not None}


def test_run_stems_use_every_used_lib_component():
    gate = script("gate")
    engine = SouffleEngine(cache_dir=None)
    lib = parse_with_lib(engine, "")
    assert isinstance(lib, Program)
    modules = checkout.programs() / "lib"
    components = {c.name for c in lib.components
                  if c.span is not None and c.span.file is not None
                  and Path(c.span.file).parent == modules}
    covered = set[str]().union(*(used(engine, gate.SOLVERS / f"{stem}.dl")
                                 for stem in gate.COMMANDS["run"].stems))
    outside: dict[str, list[str]] = {}
    for solver in sorted(checkout.solvers().glob("*.dl")):
        for name in sorted(used(engine, solver) & components - covered):
            outside.setdefault(name, []).append(solver.stem)
    assert outside == {}
