"""The functor library is built again when the module its constants come
from changes."""

import os
import shutil
from pathlib import Path

from engine import Limits, Program, RelationName, Tuples
from souffle import SouffleEngine
from souffle.engine import FUNCTOR_DIR
from souffle.functors import FUNCTOR_CONSTANTS, FUNCTOR_LIB, FUNCTOR_SOURCE, build_functors


def test_newer_constants_module_rebuilds_the_library(tmp_path: Path) -> None:
    shutil.copy(FUNCTOR_DIR / FUNCTOR_SOURCE, tmp_path / FUNCTOR_SOURCE)
    (tmp_path / FUNCTOR_CONSTANTS).parent.mkdir()
    shutil.copy(FUNCTOR_DIR / FUNCTOR_CONSTANTS, tmp_path / FUNCTOR_CONSTANTS)
    build_functors(tmp_path)
    lib = tmp_path / FUNCTOR_LIB
    built = lib.stat().st_mtime_ns
    newer = built + 10**9
    os.utime(tmp_path / FUNCTOR_CONSTANTS, ns=(newer, newer))
    build_functors(tmp_path)
    assert lib.stat().st_mtime_ns > built


def test_two_builds_in_two_directories_give_the_same_library(tmp_path: Path) -> None:
    built: list[bytes] = []
    for name in ("a", "b"):
        directory = tmp_path / name
        (directory / FUNCTOR_CONSTANTS).parent.mkdir(parents=True)
        shutil.copy(FUNCTOR_DIR / FUNCTOR_SOURCE, directory / FUNCTOR_SOURCE)
        shutil.copy(FUNCTOR_DIR / FUNCTOR_CONSTANTS, directory / FUNCTOR_CONSTANTS)
        build_functors(directory)
        built.append((directory / FUNCTOR_LIB).read_bytes())
    assert built[0] == built[1]


def test_a_run_calls_the_library_built_under_its_install_name(tmp_path: Path) -> None:
    (tmp_path / FUNCTOR_CONSTANTS).parent.mkdir()
    shutil.copy(FUNCTOR_DIR / FUNCTOR_SOURCE, tmp_path / FUNCTOR_SOURCE)
    shutil.copy(FUNCTOR_DIR / FUNCTOR_CONSTANTS, tmp_path / FUNCTOR_CONSTANTS)
    engine = SouffleEngine(functor_dir=tmp_path, cache_dir=None)
    program = engine.parse(
        ".type Box = [t: number, b: number, l: number, r: number]\n"
        ".functor box_centered(p: Box): number stateful\n"
        ".decl o(x: number)\no(@box_centered([1, 1, 2, 2])).\n", tmp_path)
    assert isinstance(program, Program), program
    out = RelationName((), "o")
    result = engine.run(program, {}, [out], Limits(20, 60))
    assert isinstance(result, Tuples), result
    assert result.relations[out] == ((1,),)
