"""The files the command writes for a printed call.

A brief, and a message to an agent other than the coordinator, goes to a
file the command writes before it prints the call (`filed`), and the
printed prompt or message is the line `FILED` with that file's path, or,
for an agent whose own command reads that file, an operator or an
operator launcher, the line `COMMANDED`, which asks for no read. A
message to the coordinator that opens with `steps.DECISION` keeps its
first line, which names what it gives, and files the rest. Each brief
gives the report file the agent writes its final reply to
(`with_report`), other than a brief of `roles.BARE_BRIEFS`. The readers of a launched agent's brief, of a
message to it and of its report read the file in place of the line."""

import re
from dataclasses import replace
from pathlib import Path

from controlled_markdown import form, mctx
from operations import briefs
from operations.constants import COORDINATOR
from operations.roles import BARE_BRIEFS, GENERAL_ROLES, Role
from operations.steps import DECISION, STEP_KEY, Launch, Send, Step, key


FILED = mctx("Read the file {path} first: it holds the text of this message.")
"""The line that gives the file a brief or a message is in."""


COMMANDED = mctx("The text of this message is in the file {path}, which your command reads.")
"""The line that gives the file a brief or a message is in, to an agent
whose command reads it."""


FILED_LINE = re.compile(
    "^(?:" + "|".join(form(line, {"path": f"(?P<{name}>/[^\\n]*?)"})
                      for name, line in (("path", FILED), ("commanded", COMMANDED)))
    + ")$", re.MULTILINE)


def filed_path(m: re.Match[str]) -> Path:
    """The path of the file the match `m` of `FILED_LINE` gives."""
    return Path(m["path"] or m["commanded"])


REPORT_SUFFIX = "-report.md"


REPORT_NAME = re.compile(rf"(?:{STEP_KEY.pattern})(?:-[0-9]+)?{re.escape(REPORT_SUFFIX)}")
"""The name of the report file a brief gives."""


FILES = "operator-files"
"""The directory under the session's scratchpad that holds the files the
command writes."""


def files_of(scratch: Path) -> Path:
    return scratch / FILES


def file_path(step: Step, scratch: Path) -> Path:
    """The file the brief of the launch `step`, or the filed part of the
    message `step`, is written to."""
    return files_of(scratch) / f"{key(step)}.md"


def report_path(step: Launch, scratch: Path) -> Path:
    """The report file of the launch `step`: the first name of
    `<key>-report.md`, `<key>-2-report.md`, `<key>-3-report.md`, ... whose
    file does not exist. The path stays the same at each print of the step
    until the launched agent writes the file, and a later launch of the same
    step gets the next free name, so no run writes over an earlier run's
    report."""
    k = key(step)
    n = 1
    while (path := files_of(scratch) / f"{k}{'' if n == 1 else f'-{n}'}{REPORT_SUFFIX}").exists():
        n += 1
    return path


def with_report(step: Launch, scratch: Path) -> Launch:
    """`step` with the line of its brief that gives its report file, other
    than one of `BARE_BRIEFS`."""
    if step.role in BARE_BRIEFS:
        return step
    form = briefs.REPORT_RULE if step.role in GENERAL_ROLES else briefs.REPORT_FILE
    report = report_path(step, scratch)
    return replace(step, brief="\n".join([step.brief, form.format(path=report)]))


def split_message(step: Send) -> tuple[str, str]:
    """The part of the message `step` printed in the call, and the part
    filed, as the module docstring gives them."""
    if step.to == COORDINATOR:
        if not step.message.startswith(DECISION):
            return step.message, ""
        head, _, rest = step.message.partition("\n")
        return head, rest
    return "", step.message


def filed(step: Step, scratch: Path) -> dict[Path, str]:
    """The files the command writes before it prints `step`, by path."""
    match step:
        case Launch(brief=brief):
            return {file_path(step, scratch): brief}
        case Send():
            rest = split_message(step)[1]
            return {file_path(step, scratch): rest} if rest else {}
        case _:
            return {}


def filed_line(step: Step, scratch: Path) -> str:
    match step:
        case Launch(role=Role.OPERATOR) | Send(commanded=True):
            line = COMMANDED
        case _:
            line = FILED
    return line.format(path=file_path(step, scratch))
