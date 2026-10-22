"""The forms of what the command prints or writes that a script reads back
from a transcript: the key of a step (`STEP_KEY`), the line that gives the
file a brief or a message is in (`FILED_LINE`), the name of a report file
(`REPORT_NAME`), the report of an agent that sent its final reply by
SendMessage (`SENT_BY_MESSAGE`), the last line of a poll
(`POLL_AGAIN`), and the line of a call that a running state read outlasts
(`READ_RUNNING`). They stand apart from the modules that
print them so that the import closure of a script that reads them, which
`scripts/kept_reads.py` keys its records on, holds none of the code that
plans a step."""

import re
from pathlib import Path

from arc.task import TASK_ID
from controlled_markdown import form, mctx
from operations.constants import COORDINATOR
from operations.roles import AGENT_ID, PASSES
from ticketing.vocabulary import TICKET_NUMBER


KEY_LENGTH = 12


STEP_KEY = re.compile(rf"{TASK_ID}-(?:{'|'.join(PASSES)})"
                      rf"|(?:(?P<change>{TICKET_NUMBER.pattern})-)?[0-9a-f]{{{KEY_LENGTH}}}")


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


REPORT_SUFFIX = "-reply.txt"


REPORT_NAME = re.compile(rf"(?:{STEP_KEY.pattern})-.+")
"""The name of the report file a brief gives, with any suffix that opens
with `-`: a reply that gives the path of a report file named with an
earlier `REPORT_SUFFIX` reads as that file's report after the suffix
changes."""


SENT = mctx("My final reply went to {to} by SendMessage.")
"""The line an agent gives as its report after it sent its final reply by
SendMessage to the agent `to`."""


SENT_BY_MESSAGE = re.compile(
    r"\A" + form(SENT, {"to": rf"(?:{re.escape(COORDINATOR)}|{AGENT_ID})"}) + r"\Z")
"""The whole text of `SENT`, to the coordinator or to any agent."""


POLL_AGAIN = mctx("Run the command again: nothing is ready.")
"""The last line of what the command prints for a poll."""


READ_RUNNING = mctx("The state read runs in the resident ({phase}, {seconds} s so far).")
"""The line, printed before `POLL_AGAIN`, of a call whose bound came while the
state read it waited on was running, with the read's phase and its seconds so far."""


STATE_READ_TIMEOUT = mctx("State read/planning failed for agent {agent}: the foreground bound "
                          "of {seconds} seconds elapsed before a result was available. Work "
                          "readiness is unknown. Investigate why state read/planning "
                          "exceeded the foreground bound.")
"""The watchdog's failure report to the coordinator, including the caller
id (the editor's for `review`)."""


NEXT_FAILED = mctx("A call of `operate.py next` failed for agent {agent} and printed no call. "
                   "The output of the call is below.")
"""The report to the coordinator of a failed call of `next` that printed no
call, with the caller's id, printed after `AFTER_TIMEOUT`."""


AFTER_TIMEOUT = mctx("Send the failure below to the coordinator, then run the command again "
                     "to continue your procedure.")
