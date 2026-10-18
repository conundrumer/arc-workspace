"""The functor library is built again when the module its constants come
from changes."""

import os
import shutil
from pathlib import Path

from souffle.engine import FUNCTOR_DIR
from souffle.run import FUNCTOR_CONSTANTS, FUNCTOR_LIB, FUNCTOR_SOURCE, build_functors


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
