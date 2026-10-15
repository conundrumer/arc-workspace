"""The reads of the files the operator's command writes for the calls it
prints (`operations.filing.filed`): a brief or a message whose text gives a
file by the line `operations.filing.FILED` or `operations.filing.COMMANDED`,
and a report that is the path of a report file alone. A file that is gone
leaves its text unknown, and an `undecided` line names it."""

import re
from pathlib import Path

from controlled_markdown import mctx

from noted_reads import note_read
from operations.filing import FILED_LINE, REPORT_NAME, filed_path
from state_reads import file_text, is_file


def unfiled(text: str, where: str, undecided: list[str]) -> str:
    """`text` with each `FILED_LINE` line in it replaced by the text of the file
    it gives. `where` names the text in an `undecided` line."""
    def read(m: re.Match[str]) -> str:
        path = filed_path(m)
        note_read(path)
        if not is_file(path):
            undecided.append(mctx("{where}: the file {path} its text gives is gone, so that "
                                  "text is unknown").format(where=where, path=path))
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
        undecided.append(mctx("{where}: its report file {path} is gone, so its report is "
                              "unknown").format(where=where, path=path))
        return None
    return file_text(path).strip()
