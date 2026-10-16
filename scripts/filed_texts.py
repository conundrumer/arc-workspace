"""The reads of the files the operator's command writes for the calls it
prints (`operations.filing.filed`): a brief or a message whose text gives a
file by the line `operations.filing.FILED` or `operations.filing.COMMANDED`,
and a report that is the path of a report file alone. A file that is gone
leaves its text unknown, and an `undecided` line of `GONE_FILE` or
`GONE_REPORT` names it."""

import re
from pathlib import Path

from controlled_markdown import form, mctx

from noted_reads import note_read
from operations.filing import FILED_LINE, REPORT_NAME, filed_path
from file_reads import file_text, is_file

GONE_FILE = mctx("{where}: the file {path} its text gives is gone, so that text is unknown")
GONE_REPORT = mctx("{where}: its report file {path} is gone, so its report is unknown")
GONE = tuple(re.compile(form(template, {"where": ".*", "path": ".*"}))
             for template in (GONE_FILE, GONE_REPORT))


def gone_line(line: str) -> bool:
    """Whether `line` is an `undecided` line that names a file that is gone."""
    return any(p.fullmatch(line) for p in GONE)


def unfiled(text: str, where: str, undecided: list[str]) -> str:
    """`text` with each `FILED_LINE` line in it replaced by the text of the file
    it gives. `where` names the text in an `undecided` line."""
    def read(m: re.Match[str]) -> str:
        path = filed_path(m)
        note_read(path)
        if not is_file(path):
            undecided.append(GONE_FILE.format(where=where, path=path))
            return m.group(0)
        return file_text(path).rstrip("\n")
    return FILED_LINE.sub(read, text)


def report_file(text: str) -> Path | None:
    """The report file a report whose text is its path alone gives, or
    None where the text is no such path."""
    line = text.strip()
    if "\n" in line or not line.startswith("/"):
        return None
    path = Path(line)
    return path if REPORT_NAME.fullmatch(path.name) else None


def report_text(path: Path, where: str, undecided: list[str]) -> str | None:
    """The text of the report file `path`, or None where it is gone, which
    an `undecided` line names."""
    note_read(path)
    if not is_file(path):
        undecided.append(GONE_REPORT.format(where=where, path=path))
        return None
    return file_text(path).strip()
