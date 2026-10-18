"""The reads of the files the operator's command writes for the calls it
prints (`operations.filing.filed`): a brief or a message whose text gives a
file by the line `operations.printed_forms.FILED` or `operations.printed_forms.COMMANDED`,
a report that is the path of a report file alone, and the report file a
brief gives, which its agent may not have written. A file that is gone
leaves its text unknown, and an `undecided` line of `GONE_FILE` or
`GONE_REPORT` names it."""

import re
from dataclasses import replace
from pathlib import Path

from controlled_markdown import form, mctx

from noted_reads import note_read
from operations.briefs import REPORT_FILE, REPORT_RULE
from operations.printed_forms import FILED_LINE, REPORT_NAME, filed_path
from operations.state import Agent
from file_reads import file_text, is_file

GONE_FILE = mctx("{where}: the file {path} its text gives is gone, so that text is unknown")
GONE_REPORT = mctx("{where}: its report file {path} is gone, so its report is unknown")
GONE = tuple(re.compile(form(template, {"where": ".*", "path": ".*"}))
             for template in (GONE_FILE, GONE_REPORT))

BRIEF_REPORT = re.compile("^(?:" + "|".join(form(line, {"path": f"(?P<{name}>/[^`\\n]+)"})
                                             for name, line in (("file", REPORT_FILE),
                                                                ("rule", REPORT_RULE)))
                          + ")$", re.MULTILINE)


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


def brief_report_file(brief: str) -> Path | None:
    """The report file the brief `brief` gives by its `REPORT_FILE` or
    `REPORT_RULE` line, or None where it gives none."""
    m = BRIEF_REPORT.search(brief)
    return None if m is None else Path(m["file"] or m["rule"])


def written_report(path: Path) -> str | None:
    """The text of the report file `path`, or None where no file is there.
    The read is noted either way, so a kept read sees the file once its
    agent writes it."""
    note_read(path)
    return file_text(path).strip() if is_file(path) else None


def report_text(path: Path, where: str, undecided: list[str]) -> str | None:
    """The text of the report file `path`, or None where it is gone, which
    an `undecided` line names."""
    text = written_report(path)
    if text is None:
        undecided.append(GONE_REPORT.format(where=where, path=path))
    return text


def filed_report(a: Agent) -> Agent:
    """`a` with its last report read from `Agent.report_file`, at that
    report's time, where that file is there and that report is not
    already read from it."""
    last = a.last_report
    if a.report_file is None or last is None or last.file == a.report_file:
        return a
    text = written_report(a.report_file)
    if text is None:
        return a
    return replace(a, reports=(*a.reports[:-1], replace(last, text=text, file=a.report_file)))
