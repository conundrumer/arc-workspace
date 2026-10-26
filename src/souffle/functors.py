"""The functor library Souffle links: its source, the constants it is built
with, and its build, which gives the same bytes in every checkout."""

import subprocess
import tempfile
import threading
from pathlib import Path

from engine.engine import ParseFailure
from engine.memo import write_whole
from engine.program import NumberTerm
from souffle.install import souffle_include
from souffle.parser import parse

FUNCTOR_LIB_NAME = "functors"
"""The name Souffle links the functor library by, after `-l`."""
FUNCTOR_LIB = f"lib{FUNCTOR_LIB_NAME}.dylib"
"""The functor library's file in the functor directory."""
FUNCTOR_SOURCE = "lib_functors.cpp"
"""The functor library's source in the functor directory."""
FUNCTOR_CONSTANTS = Path("lib") / "orientation.dl"
"""The lib module, under the functor directory, whose `#define` constants
the functor library's source reads."""

_BUILDING = threading.Lock()


def functor_constants(path: Path) -> tuple[str, ...]:
    """The compiler flags that define each `#define` constant of the
    Souffle file at `path` with its number. A `#define` whose value is no
    number is an error."""
    program = parse(path.read_text(), path.parent)
    if isinstance(program, ParseFailure):
        raise RuntimeError(f"{path}:{program.line}: {program.message}")
    flags: list[str] = []
    for d in program.defines:
        if d.params is not None or not isinstance(d.value, NumberTerm):
            raise RuntimeError(f"{path}:{d.line}: #define {d.name} is no number constant")
        flags.append(f"-D{d.name}={d.value.value}")
    return tuple(flags)


def build_functors(functor_dir: Path) -> None:
    """Compile the functor library from its source, with the clang++ of the
    SDK xcrun selects and the constants of `FUNCTOR_CONSTANTS`
    (`functor_constants`), where the library is absent or older than the
    source or that module. The library's install name is `@rpath/` and its
    file name, whatever the directory it is built in, so that two
    checkouts with the same source, constants and compiler build the same
    bytes. The library is written whole, so a run in another process reads
    the old library or the new one."""
    source = functor_dir / FUNCTOR_SOURCE
    constants = functor_dir / FUNCTOR_CONSTANTS
    lib = functor_dir / FUNCTOR_LIB
    with _BUILDING:
        newest = max(source.stat().st_mtime_ns, constants.stat().st_mtime_ns)
        if lib.exists() and lib.stat().st_mtime_ns >= newest:
            return
        with tempfile.TemporaryDirectory(prefix="functors-") as tmp:
            out = Path(tmp) / FUNCTOR_LIB
            done = subprocess.run(
                ["xcrun", "clang++", "-std=c++17", "-shared", "-fPIC",
                 f"-I{souffle_include()}", *functor_constants(constants),
                 f"-Wl,-install_name,@rpath/{FUNCTOR_LIB}",
                 "-o", str(out), str(source)],
                capture_output=True, text=True)
            if done.returncode != 0:
                raise RuntimeError(f"building {lib} from {source} failed:\n{done.stderr}")
            write_whole(lib, out.read_bytes())
