"""The files the command writes for a printed call.

A brief, and a message to an agent other than the coordinator, goes to a
file the command writes before it prints the call (`filed`), and the
printed prompt or message is the line `FILED` with that file's path. A
message to the coordinator that opens with `steps.DECISION` keeps its
first line, which names what it gives, and files the rest. Each brief
gives the report file the agent writes its final reply to
(`with_report`), other than a solver pass's: the documents of a solver
pass give its report file. The readers of a launched agent's brief, of a
message to it and of its report read the file in place of the line."""

import re
from dataclasses import replace
from pathlib import Path

from controlled_markdown import form, mctx
from operations import briefs
from operations.constants import COORDINATOR
from operations.roles import GENERAL_ROLES, PASSES, Role
from operations.steps import DECISION, STEP_KEY, Launch, Send, Step, key


FILED = mctx("Read the file {path} first: it holds the text of this message.")
"""The line that gives the file a brief or a message is in."""


FILED_LINE = re.compile("^" + form(FILED, {"path": r"(?P<path>/[^\n]*?)"}) + "$", re.MULTILINE)


REPORT_SUFFIX = "-report.md"


ALERT_SUFFIX = "-alert.md"
"""The suffix of the alert file an auditor's brief gives, beside its
report file."""


REPORT_NAME = re.compile(rf"{STEP_KEY.pattern}{re.escape(REPORT_SUFFIX)}")
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
    return files_of(scratch) / f"{key(step)}{REPORT_SUFFIX}"


def alert_path(report: Path) -> Path:
    """The alert file of the auditor whose report file is `report`."""
    return report.with_name(report.name.removesuffix(REPORT_SUFFIX) + ALERT_SUFFIX)


def with_report(step: Launch, scratch: Path) -> Launch:
    """`step` with the line of its brief that gives its report file, other
    than a solver pass's, and for an auditor the line that gives its alert
    file."""
    if step.role in PASSES:
        return step
    form = briefs.REPORT_RULE if step.role in GENERAL_ROLES else briefs.REPORT_FILE
    report = report_path(step, scratch)
    lines = [step.brief, form.format(path=report)]
    if step.role is Role.OP_AUDITOR:
        lines.append(briefs.ALERT_FILE.format(path=alert_path(report)))
    return replace(step, brief="\n".join(lines))


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
    return FILED.format(path=file_path(step, scratch))
