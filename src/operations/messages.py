"""The messages the operator sends agents at work: each tells a running
agent of an event on its work, or asks it for an act or a reply."""

from controlled_markdown import mctx
from operations.briefs import OVER_BUDGET
from operations.reports import FOR_COORDINATOR, TICKETS_FILED
from ticketing.times import utc_stamp


REVIEW_AGAIN = mctx("""
    - Your reply at {time} came before the last report of an editor of the change.
    - Review the change again.
    """)


def review_again(time: float) -> str:
    """The message that asks a doc reviewer whose reply at `time` came
    before an editor's last report to review the change again."""
    return REVIEW_AGAIN.format(time=utc_stamp(time))


def decided_edits(number: str, analyst: str, text: str) -> str:
    """The message that gives an editor of the change `number` the text of
    the section of decision analyst `analyst`'s reply addressed to its
    role."""
    return mctx("Decision analyst {analyst} decided the edits below for your part of change "
                "{number}. Make each that the worktree does not hold yet, run the checks each "
                "gives, then give your final reply.").format(
        number=number, analyst=analyst) + f"\n{text}"


def merge_finding(number: str, output: str) -> str:
    return mctx("A finding of your checks on change {number}: the merge refused it, as "
                "below.").format(number=number) + f"\n{output}"


def later_line(number: str, time: float, note: str) -> str:
    """The message that gives a running ticket analyst a line the
    coordinator wrote on ticket `number` after its launch."""
    return "\n".join([
        mctx("The coordinator wrote on ticket {number}, in its log at {time:.0f}, after your "
             "launch: {note}").format(number=number, time=time, note=note),
        mctx("Take it into your work on that ticket.")])


def stop_work(number: str) -> str:
    """The message that tells an agent at work on a change or a draft whose
    ticket the operator no longer holds to end."""
    return mctx("Write nothing further on {number}, and end with your open work in your "
                "reply.").format(number=number)


def over_budget(number: str, reviewer: bool) -> str:
    """The message to an agent at work on the change `number` once the
    change passes its budget; `reviewer` gives the form of its doc
    reviewer."""
    lines = [OVER_BUDGET.format(number=number), mctx(
        "Launch nothing more on it, end the work at hand, and reply with what stands.")]
    if reviewer:
        lines.append(mctx("Before you reply, file each finding of yours that stands as a `bug` "
                          "ticket, with `change` as its domain and {number} as its "
                          "subject.").format(number=number))
    return "\n".join(lines)


RESTATE = mctx("""
    - What you sent {reader} at {time} is in no form its command reads, so the command cannot place it.
    - Send it again, in full, in this form: {form}
    """)

PASS_RESEND = mctx("""
    - When you replied at {time}, `programs/reports/<task_id>/` held no report that you wrote with a `{heading}` section.
    - Write your report to its file, with that section, and reply with that file's path alone.
    """)
DECISION_FORM = mctx("a reply that gives, on a line of its own, the ruling on the step, in a "
                     "form that `uv run python scripts/operate.py --help rulings` gives; or, where the "
                     "decision goes to the user, a `decision:` item under `{heading}`.").format(
                         heading=FOR_COORDINATOR)
SPLIT_FORM = mctx("your report, with each list item that opens with `split:` in the form that "
                  "[A split](prompts/agents/code-editor/split.md#a-split) gives.")
ALERT_FORM = mctx("where it is an alert, a message that opens with the line `alert: <kind> "
                  "<agent id>`; where it is no alert, a reply that says so.")


OPERATOR = mctx("the operator")
"""The reader `restate` names, in the operator's command and in the
monitor's steps."""


def pass_resend(time: float) -> str:
    """The message to a solver pass whose reply at `time` came with no
    report file of its own."""
    return PASS_RESEND.format(time=utc_stamp(time), heading=TICKETS_FILED)


def restate(time: float, form: str, reader: str) -> str:
    """The message that asks an agent to send again, in `form`, what it
    sent `reader` at `time` in no form the command of `reader` reads."""
    return RESTATE.format(reader=reader, time=utc_stamp(time), form=form)
