"""The files the command writes for a printed call.

A brief, and a message to an agent other than the coordinator, goes to a
file the command writes before it prints the call (`filed`), and the
printed prompt or message is the line `printed_forms.FILED` with that file's path, or,
for an agent whose own command reads that file, an operator or an
operator launcher, the line `printed_forms.COMMANDED`, which asks for no read. A
message to the coordinator that opens with `steps.DECISION` keeps its
first line, which names what it gives, and files the rest. Each brief
gives the report file the agent writes its final reply to
(`with_report`), other than a brief of `roles.BARE_BRIEFS`. The readers of a launched agent's brief, of a
message to it and of its report read the file in place of the line.
The scratch directory a brief gives is named here too (`scratch_dir`),
by the same search for the first free name as the report file."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from operations import briefs
from operations.constants import COORDINATOR
from operations.roles import BARE_BRIEFS, GENERAL_ROLES, Role
from operations.printed_forms import COMMANDED, FILED, REPORT_SUFFIX
from operations.steps import DECISION, Launch, Send, Step, digest


FILES = "operator-files"
"""The directory under the session's scratchpad that holds the files the
command writes."""


def files_of(scratch: Path) -> Path:
    return scratch / FILES


def file_path(step: Step, scratch: Path) -> Path:
    """The file the brief of the launch `step`, or the filed part of the
    message `step`, is written to, named by the step's digest
    (`steps.digest`), so each brief and each message has its own."""
    return files_of(scratch) / f"{digest(step)}.md"


def report_path(step: Launch, scratch: Path) -> Path:
    """The report file of the launch `step`: the first name of
    `<digest>-reply.txt`, `<digest>-2-reply.txt`, `<digest>-3-reply.txt`, ... whose
    file does not exist. The path stays the same at each print of the step
    until the launched agent writes the file, and a later launch of the same
    step gets the next free name, so no run writes over an earlier run's
    report."""
    k = digest(step)
    return first_free(lambda suffix: files_of(scratch) / f"{k}{suffix}{REPORT_SUFFIX}")


def scratch_dir(name: str, scratch: Path) -> Path:
    """The scratch directory a brief gives: the first free name
    (`first_free`) under the session's scratchpad `scratch`. The path stays the same at each print of the step
    until the launched agent creates the directory, so no brief gives a
    directory an earlier run used."""
    return first_free(lambda suffix: scratch / f"{name}{suffix}")


def editor_scratch(number: str, role: Role, scratch: Path) -> Path:
    """The scratch directory of the brief of an editor of role `role` on
    the change `number`."""
    return scratch_dir(f"{number}-{role}", scratch)


def first_free(path: Callable[[str], Path]) -> Path:
    """The first of `path("")`, `path("-2")`, `path("-3")`, ... that does
    not exist."""
    n = 1
    while (p := path("" if n == 1 else f"-{n}")).exists():
        n += 1
    return p


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
