"""What the converter's commands share: the output directory a run writes under
and the timing line of a phase."""

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from arclog_convert import OUT_ENV, paths, writable_out


def use_out(out: Path | None) -> None:
    """Point this run, and the workers it starts, at the directory `out`, or at
    `arclog_convert.out` where `out` is None."""
    if out is None:
        writable_out()
        return
    # set before the pools start, so that their workers read it
    os.environ[OUT_ENV] = str(out.resolve())
    (paths.OUT_ROOT, paths.OUT_DIR, paths.PLANS, paths.NAMES_DIR, paths.COLUMNS_DIR,
     paths.CASE_RECORDS) = paths.out_dirs()


@contextmanager
def phase(name: str) -> Iterator[None]:
    """Print `<name>: <seconds> s`, the wall time of the block, as it ends."""
    start = time.monotonic()
    try:
        yield
    finally:
        print(f"{name}: {time.monotonic() - start:.1f} s", flush=True)
