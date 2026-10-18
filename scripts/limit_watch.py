"""Watch the usage limit, and exit once it lifts after it stopped calls.
`HELP`, which `--help` prints, gives what the watcher reads and prints."""

import argparse
import sys
import time

from controlled_markdown import mctx
from ticketing.times import utc_stamp
from usage_limit import Limit, read

SAMPLE_SECONDS = 60

HELP = mctx("""
    - The usage form:
        ```
        uv run python scripts/limit_watch.py
        ```
    - The command reads the usage limit every {sample} s, as `uv run python scripts/operate.py --help next` gives it.
    - It exits 0 once a reading gives the limit as lifted after an earlier reading of its run gave it in force.
    - On that exit it prints the time of the reading that gave the limit in force and of the one that gave it lifted, then the line that asks its reader to resume each agent of its own that the usage limit stopped and that has not run since, by a message that asks the agent to continue its work.
    """).format(sample=SAMPLE_SECONDS)

RESUME = mctx("Resume each agent of yours that the usage limit stopped and that has not run "
              "since, by a message that asks it to continue its work.")


def watch() -> tuple[float, float]:
    """Reads until the limit lifts after a reading in force, and returns
    the time of each of those two readings."""
    in_force: float | None = None
    while True:
        now = time.time()
        limit = read(now, []).limit
        if limit is Limit.IN_FORCE and in_force is None:
            in_force = now
        elif limit is Limit.LIFTED and in_force is not None:
            return in_force, now
        time.sleep(SAMPLE_SECONDS)


def main(argv: list[str]) -> int:
    argparse.ArgumentParser(description=HELP, formatter_class=argparse.RawDescriptionHelpFormatter,
                            usage=argparse.SUPPRESS).parse_args(argv)
    in_force, lifted = watch()
    print("\n".join([mctx("The usage limit was in force at {time}.").format(time=utc_stamp(in_force)),
                     mctx("The usage limit was lifted at {time}.").format(time=utc_stamp(lifted)),
                     RESUME]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
