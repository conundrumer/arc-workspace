"""The provenance of the files the converter writes under `gen/`: the header of each file, the record of each solver, and
the hash of the converter that both hold.

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

A file matches the record where its bytes have the recorded sha256 and its header holds the recorded hashes
(`file_faults`). The code hash is the hash of the import closure of `arclog_convert.convert`, of the Souffle sources
that its runs depend on, of the lib's files and of the native streams digest (`code_digest`); the readers of `gen/`
are in `arclog_convert.readback`, which `arclog_convert.convert` does not import.
"""

import ast
import hashlib
import json
import re
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
    """The hash of the code that can change what the converter writes: the modules that `arclog_convert.convert`
    imports, followed through their imports under `src/`, the sources that the Souffle runs of `Rows` depend on
    (`cli.common.SOURCES`), and the lib's files. The native streams digest also binds the static-valid normalization
    implementation and registry types."""
    from arclog import streams_digest
    from arclog_convert.lib import LIB_DL, REGISTRY, SIGNATURE
    from cli.common import SOURCES
    files = {*module_files([CODE_ROOT]), *checkout.matched(checkout.ROOT, SOURCES), LIB_DL, SIGNATURE, REGISTRY}
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


def read_bytes_or_none(path: Path) -> bytes | None:
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
        found += [f"{CASES}/{name}: {kind}" for kind in file_faults(path, read_bytes_or_none(path), record.cases.get(name), record)]
    return found
