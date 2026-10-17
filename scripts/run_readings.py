"""The lines `profile_runs.py --help one` gives after a run's token cost, as it gives them."""

import time
from collections import Counter

from controlled_markdown import mctx
from open_agents import CallTimes, hung_time
from operations.alerts import AlertKind, opening
from run_profile import COMMAND_WIDTH
from run_records import Run
from transcripts import agent_id

NONE = mctx("none")


def print_readings(r: Run, own: CallTimes, among: CallTimes) -> None:
    """Those lines of `r`, with `own` and `among` as
    `open_agents.usual` takes them."""
    counts = Counter(r.bash_commands)
    hung = sum(1 for s in r.spans
               if hung_time(own, among, s) <= (s.end if s.end is not None else time.time()))
    me = agent_id(r.path)
    given = {opening(k, me): k for k in AlertKind}
    alerted = Counter(given[line.strip()] for m in (*r.messages, *r.others)
                      for line in m.text.splitlines() if line.strip() in given)
    print("  " + mctx("repeated: {repeated}").format(repeated="; ".join(
        f"{n}x {c[:COMMAND_WIDTH]}" for c, n in sorted(counts.items()) if n > 1) or NONE))
    print("  " + mctx("refused: {refused}  hung: {hung}  alerts: {alerts}").format(
        refused=len(r.refused), hung=hung,
        alerts=", ".join(f"{k.value} {n}" for k, n in sorted(alerted.items(),
                                                             key=lambda e: e[0].value))
        or NONE))
