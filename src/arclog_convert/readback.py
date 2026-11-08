"""The provenance of the files the converter writes under `gen/`, and the readback that refuses a file that does
not match it.

Each file the converter writes under `gen/` (`<stem>.arclog`, `<stem>.arcdata` and each file of
`gen/cases/<stem>/`) is read-only and begins with two comment lines:

    ;; inputs <inputs hash> programs/solvers/<stem>.dl
    ;; converter <code hash>

`<inputs hash>` is the inputs hash of the solver (`arclog_convert.plans.inputs_hash`: its solver file, task file and
witness file), and `<code hash>` is `code_digest()`. The record of the solver, `case_records/<stem>.sha256`, holds
these two hashes, the sha256 of each file the converter wrote for the solver, and, where they apply, the number of
cases skipped for a fault and the error that stopped the case files. Its lines are:

    inputs <inputs hash>
    code <code hash>
    arclog <sha256 of <stem>.arclog>
    arcdata <sha256 of <stem>.arcdata>
    case <sha256> <file name under gen/cases/<stem>/>      (a line per case file)
    skipped <n>                                              (where n is not 0)
    error <JSON string>                                      (where the case files stopped with a REPEATABLE error)

A record is current where its inputs hash is that of the solver's files now and its code hash is `code_digest()`.
A file matches the record where its bytes have the recorded sha256 and its header holds the recorded hashes.
A program that reads a file under `gen/` reads it through `read_checked`, which raises `Stale` where the header's
inputs hash is not the solver's now or the file does not match its record.

    uv run python -m arclog_convert.readback [--out <dir>] [<stem> ...]

prints, for each solver whose files do not match a current record, the solver and the kinds of fault, and the count of
such solvers; it exits with status 1 where there is one. It reads no file but the ones it checks, the solver, task
and witness files, and the code that `code_digest()` hashes.
"""

import ast
import hashlib
import json
import re
import sys
from collections import Counter
from functools import cache
from pathlib import Path
from typing import NamedTuple

from arclog_convert import paths
from engine import checkout
from engine.memo import hash_files, write_whole


CASES = "cases"
"""The directory of `gen/` that holds, in a directory per solver, the files of the cases."""

CODE_ROOT = "arclog_convert.convert"
"""The module that the code hash follows the imports of."""


def module_files(roots: list[str]) -> set[Path]:
    """The file of each module under `src/` that the modules `roots` name or import, with the files of the packages
    they stand in, followed through the imports in those files at any depth. A module that has no file under `src/`
    has none in the set."""
    src = checkout.ROOT / "src"
    files: dict[str, Path] = {}
    todo = list(roots)
    while todo:
        name = todo.pop()
        if name in files:
            continue
        base = src.joinpath(*name.split("."))
        file = base.with_suffix(".py")
        if not file.is_file():
            file = base / "__init__.py"
        if not file.is_file():
            continue
        files[name] = file
        parent = name.rpartition(".")[0]
        if parent:
            todo.append(parent)
        package = name if file.name == "__init__.py" else parent
        for node in ast.walk(ast.parse(file.read_bytes())):
            match node:
                case ast.Import(names=aliases):
                    todo += [alias.name for alias in aliases]
                case ast.ImportFrom(level=level, module=module, names=aliases):
                    held = package.split(".")[:len(package.split(".")) - level + 1] if level else []
                    imported = ".".join([*held, *([module] if module else [])])
                    todo += [imported, *(f"{imported}.{alias.name}" for alias in aliases)]
    return set(files.values())


@cache
def code_digest() -> str:
    """The hash of the converter: the modules that `arclog_convert.convert` imports, followed through their imports
    under `src/`, every file of `src/arclog_convert/` other than Markdown and bytecode, the sources that the Souffle
    runs of `Rows` depend on (`cli.common.SOURCES`), and the lib's files. The native streams digest also binds the
    static-valid normalization implementation and registry types."""
    from arclog import streams_digest
    from arclog_convert.lib import LIB_DL, REGISTRY, SIGNATURE
    from cli.common import SOURCES
    package = Path(__file__).resolve().parent
    own = {p for p in package.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".md", ".pyc")}
    files = {*module_files([CODE_ROOT]), *own, *checkout.matched(checkout.ROOT, SOURCES), LIB_DL, SIGNATURE, REGISTRY}
    digest = hashlib.sha256(streams_digest().encode())
    hash_files(digest, ((str(path.relative_to(checkout.ROOT)), path) for path in sorted(files)))
    return digest.hexdigest()


HEADER_LINE = re.compile(r";; (?:inputs|converter) [^\n]*\n")


def header(stem: str, inputs: str, code: str) -> str:
    """The two comment lines that begin a file the converter writes for the solver `stem` whose inputs hash is
    `inputs`, under the code hash `code`."""
    return f";; inputs {inputs} programs/solvers/{stem}.dl\n;; converter {code}\n"


def strip_header(text: str) -> str:
    """`text` without the comment lines of `header` at its start."""
    while match := HEADER_LINE.match(text):
        text = text[match.end():]
    return text


def with_header(text: str, head: str) -> str:
    """`text` with the comment lines `head` at its start, in place of any it has."""
    return head + strip_header(text)


def read_header(text: str) -> tuple[str, str] | None:
    """The inputs hash and the code hash that the first two lines of `text` give; none where they are not the lines
    of `header`."""
    lines = text.split("\n", 2)[:2]
    if len(lines) < 2 or not lines[0].startswith(";; inputs ") or not lines[1].startswith(";; converter "):
        return None
    inputs = lines[0].split(" ")[2:3]
    code = lines[1].split(" ")[2:3]
    return (inputs[0], code[0]) if inputs and code else None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_gen(path: Path, text: str) -> str:
    """Write `text` to `path` whole and read-only, and give the sha256 of the bytes written."""
    data = text.encode()
    write_whole(path, data)
    path.chmod(0o444)
    return sha256(data)


class Record(NamedTuple):
    """The content of `case_records/<stem>.sha256`."""

    inputs: str
    """The inputs hash of the solver (`plans.inputs_hash`) that the files were made from."""
    code: str
    """The hash of the converter that made them (`code_digest`)."""
    arclog: str
    """The sha256 of `gen/<stem>.arclog`."""
    arcdata: str
    """The sha256 of `gen/<stem>.arcdata`."""
    cases: dict[str, str]
    """The sha256 of each file of `gen/cases/<stem>/`, by file name."""
    error: str | None = None
    """The error that stopped the case files of the solver, where one did and `arclog_convert.convert.REPEATABLE`
    holds it."""
    skipped: int = 0
    """The number of cases that `arclog.case_files` gave a fault, and that got no files."""


def current_inputs(stem: str) -> str:
    """The inputs hash of the solver `stem` now (`plans.inputs_hash` over `paths.SOLVERS`). `plans` is imported here,
    so that a module that `plans` imports can import this one."""
    from arclog_convert.plans import inputs_hash
    return inputs_hash(stem, paths.SOLVERS)


def read_record(stem: str, records: Path | None = None) -> Record | None:
    """The record of `stem` in the directory `records`, `paths.CASE_RECORDS` where none is given; none where there is
    no file, or it is not in the form of `write_record`."""
    try:
        fields: dict[str, str] = {}
        cases: dict[str, str] = {}
        for line in ((records or paths.CASE_RECORDS) / f"{stem}.sha256").read_text().splitlines():
            key, _, rest = line.partition(" ")
            if key == "case":
                digest, _, name = rest.partition(" ")
                if not digest or not name:
                    return None
                cases[name] = digest
            else:
                fields[key] = rest
        error = json.loads(fields["error"]) if "error" in fields else None
        return Record(fields["inputs"], fields["code"], fields["arclog"], fields["arcdata"], cases, error,
                      int(fields.get("skipped", 0)))
    except (OSError, ValueError, KeyError):
        return None


def write_record(stem: str, record: Record) -> None:
    """Write the record of `stem` whole."""
    lines = [f"inputs {record.inputs}", f"code {record.code}", f"arclog {record.arclog}", f"arcdata {record.arcdata}",
             *(f"case {digest} {name}" for name, digest in sorted(record.cases.items())),
             *([f"skipped {record.skipped}"] if record.skipped else []),
             *([f"error {json.dumps(record.error)}"] if record.error else [])]
    paths.CASE_RECORDS.mkdir(parents=True, exist_ok=True)
    write_whole(paths.CASE_RECORDS / f"{stem}.sha256", ("\n".join(lines) + "\n").encode())


def record_faults(stem: str, record: Record) -> list[str]:
    """The kinds of fault of `record` itself: its inputs hash is not that of the solver's files now, or its code hash
    is not `code_digest()`."""
    return [*(["inputs hash not current"] if record.inputs != current_inputs(stem) else []),
            *(["code hash not current"] if record.code != code_digest() else [])]


def file_faults(path: Path, data: bytes | None, want: str | None, record: Record) -> list[str]:
    """The kinds of fault of the file `path`, of which `data` is the bytes (none where it cannot be read), against
    the sha256 `want` that `record` holds for it (none where it holds none): the file is missing or not in the record,
    its bytes differ from the record, its header is not the record's, or it can be written."""
    if data is None:
        return ["missing"]
    if want is None:
        return ["not in the record"]
    faults = ["bytes differ from the record"] if sha256(data) != want else []
    if read_header(data.decode(errors="replace")) != (record.inputs, record.code):
        faults.append("header differs from the record")
    if path.stat().st_mode & 0o222:
        faults.append("writable")
    return faults


def _bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def case_faults(stem: str, record: Record) -> list[str]:
    """The kinds of fault of the files under `gen/cases/<stem>/` against `record`, each led by `cases/` and the
    file's name: a file of the directory that the record lacks, or a file of the record that fails `file_faults`."""
    directory = paths.OUT_DIR / CASES / stem
    held = {p.name for p in directory.iterdir()} if directory.is_dir() else set()
    found = []
    for name in sorted(held | record.cases.keys()):
        path = directory / name
        found += [f"{CASES}/{name}: {kind}" for kind in file_faults(path, _bytes(path), record.cases.get(name), record)]
    return found


def faults(stem: str) -> list[str]:
    """The kinds of fault of the files of `stem` under `gen/` against its record, each led by the file's name; empty
    where the record is current and every file matches it."""
    record = read_record(stem)
    if record is None:
        return ["no record"]
    found = [f"record: {kind}" for kind in record_faults(stem, record)]
    for suffix, want in (("arclog", record.arclog), ("arcdata", record.arcdata)):
        path = paths.OUT_DIR / f"{stem}.{suffix}"
        found += [f"{path.name}: {kind}" for kind in file_faults(path, _bytes(path), want, record)]
    return found + case_faults(stem, record)


class Stale(Exception):
    """A file under `gen/` is not current: its header's inputs hash is not that of the solver's files now, or it does
    not match its record."""


def locate(path: Path) -> tuple[Path, str, str | None]:
    """The directory `gen/` that holds the file `path`, the solver's stem, and, for a file of `cases/<stem>/`, the
    file's name there; none for the name where the file is `<stem>.arclog` or `<stem>.arcdata`."""
    path = path.resolve()
    if path.parent.parent.name == CASES:
        return path.parent.parent.parent, path.parent.name, path.name
    return path.parent, path.name.partition(".")[0], None


def read_checked(path: Path) -> str:
    """The text of the file `path`, a `<stem>.arclog`, a `<stem>.arcdata` or a file of `cases/<stem>/` of a `gen/`
    directory, where it is current; raises `Stale` otherwise. It is current where:
      - its header's inputs hash is the inputs hash of the solver's files now, so that a solver file edited and not
        converted again makes it stale;
      - the record of its solver, in `case_records/` beside `gen/`, holds that inputs hash and the sha256 of the
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
    record = read_record(stem, gen.parent / "case_records")
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
    parser.add_argument("stems", nargs="*", help="the solvers to check; every solver of `gen/` where none is given")
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
