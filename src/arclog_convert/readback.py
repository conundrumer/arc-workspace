"""The readers' check of the converted solvers' files (`programs/arclog/`): `read_checked` gives the text of a file that is current and raises
`Stale` for one that is not. The header and the record are those of `arclog_convert.provenance`.

A file is current where:
  - its header's inputs hash is the inputs hash of the solver's files now (`plans.inputs_hash`), so that a solver
    file edited and not converted again makes it stale;
  - the record of its solver, in `case_records/` of the converter's output directory, holds that inputs hash and the sha256 of the file's
    bytes.
A program that reads one of those files reads it through `read_checked`.

    uv run python -m arclog_convert.readback [--out <dir>] [<stem> ...]

prints, for each solver whose files do not match a current record (its inputs hash and its code hash both current),
the solver and the kinds of fault, and the count of such solvers; it exits with status 1 where there is one. It reads
no file but the ones it checks, the solver, task and witness files, and the code that `code_digest()` hashes.
This module is not imported by `arclog_convert.convert`, so a change to it leaves the code hash as it is.
"""

import sys
from collections import Counter
from pathlib import Path

from arclog_convert import paths
from arclog_convert.provenance import (
    CASES, case_faults, code_digest, file_faults, read_header, read_record, sha256, read_bytes_or_none, Record)


def current_inputs(stem: str) -> str:
    """The inputs hash of the solver `stem` now (`plans.inputs_hash` over `paths.SOLVERS`). `plans` is imported here,
    so that a module that `plans` imports can import this one."""
    from arclog_convert.plans import inputs_hash
    return inputs_hash(stem, paths.SOLVERS)


def record_faults(stem: str, record: Record) -> list[str]:
    """The kinds of fault of `record` itself: its inputs hash is not that of the solver's files now, or its code hash
    is not `code_digest()`."""
    return [*(["inputs hash not current"] if record.inputs != current_inputs(stem) else []),
            *(["code hash not current"] if record.code != code_digest() else [])]


def faults(stem: str) -> list[str]:
    """The kinds of fault of the files of `stem` among the converted solvers against its record, each led by the file's name; empty
    where the record is current and every file matches it."""
    record = read_record(stem)
    if record is None:
        return ["no record"]
    found = [f"record: {kind}" for kind in record_faults(stem, record)]
    for suffix, want in (("arclog", record.arclog), ("arcdata", record.arcdata)):
        path = paths.OUT_DIR / f"{stem}.{suffix}"
        found += [f"{path.name}: {kind}" for kind in file_faults(path, read_bytes_or_none(path), want, record)]
    return found + case_faults(stem, record)


class Stale(Exception):
    """A converted solver's file is not current: its header's inputs hash is not that of the solver's files now, or it does
    not match its record."""


def locate(path: Path) -> tuple[Path, str, str | None]:
    """The directory of converted solvers that holds the file `path`, the solver's stem, and, for a file of `cases/<stem>/`, the
    file's name there; none for the name where the file is `<stem>.arclog` or `<stem>.arcdata`."""
    path = path.resolve()
    if path.parent.parent.name == CASES:
        return path.parent.parent.parent, path.parent.name, path.name
    return path.parent, path.name.partition(".")[0], None


def read_checked(path: Path) -> str:
    """The text of the file `path`, a `<stem>.arclog`, a `<stem>.arcdata` or a file of `cases/<stem>/` of a converted
    solvers' directory, where it is current; raises `Stale` otherwise. It is current where:
      - its header's inputs hash is the inputs hash of the solver's files now, so that a solver file edited and not
        converted again makes it stale;
      - the record of its solver, in `case_records/` of the converter's output directory, holds that inputs hash and the sha256 of the
        file's bytes.
    One hash of the solver's files and one of the file are computed. The code hash is not compared: the reader may
    run in a checkout whose code differs from the converter's, and `faults` and the command of this module check it."""
    gen, stem, name = locate(path)
    try:
        data = path.read_bytes()
    except OSError as e:
        raise Stale(f"{path}: {e.strerror}") from e
    text = data.decode()
    head = read_header(text)
    if head is None:
        raise Stale(f"{path}: no header")
    try:
        current = current_inputs(stem)
    except OSError as e:
        raise Stale(f"{path}: the solver's files cannot be read, {e.strerror}") from e
    if head[0] != current:
        raise Stale(f"{path}: the solver's files changed since the conversion")
    record = read_record(stem, paths.records_of(gen))
    if record is None:
        raise Stale(f"{path}: no record")
    want = record.cases.get(name) if name is not None else record.arclog if path.suffix == ".arclog" else record.arcdata
    if record.inputs != current:
        raise Stale(f"{path}: the record is of other files of the solver")
    if want is None:
        raise Stale(f"{path}: not in the record")
    if sha256(data) != want:
        raise Stale(f"{path}: bytes differ from the record")
    return text


def main(argv: list[str]) -> int:
    import argparse
    from arclog_convert.phases import use_out
    parser = argparse.ArgumentParser(prog="python -m arclog_convert.readback")
    parser.add_argument("--out", type=Path, help="the directory to read under, in place of `arclog_convert.out`")
    parser.add_argument("stems", nargs="*", help="the solvers to check; every converted solver where none is given")
    args = parser.parse_args(argv)
    if args.out is not None:
        use_out(args.out)
    stems = args.stems or sorted(p.stem for p in paths.OUT_DIR.glob("*.arclog"))
    kinds: Counter[str] = Counter()
    bad = 0
    for stem in stems:
        found = faults(stem)
        if found:
            bad += 1
            these = [f.partition(": ")[2] or f for f in found]
            kinds.update(these)
            print(f"{stem}: {len(found)} faults ({', '.join(sorted(set(these)))})")
    print(f"{bad} of {len(stems)} solvers do not match a current record")
    for kind, count in kinds.most_common():
        print(f"  {kind:36} {count:6} files")
    return int(bad > 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
