"""Paces a Create pass by wall time: a create agent calls it at the start of
each step of its pass, and it prints the time used and the budget of the
step that starts. `HELP`, which `--help` prints, gives the usage and what
each call prints.

The budgets, the run's target and its limit are `Step`, `TARGET_MINUTES`
and `LIMIT_MINUTES`. Each call appends a record to `work/task/<task
id>/pace.jsonl`, and a run is the records since the last `Read` call, or
all of them where none is a `Read` call."""

import argparse
import json
import re
import textwrap
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from arc import task
from controlled_markdown import mctx

TARGET_MINUTES = 15
LIMIT_MINUTES = 25
RECORDS = "pace.jsonl"
LAST_PASS = "last-pass.dl"
LAST_PASS_WITNESSES = "last-pass.wit.json"
TASK_ID = re.compile(task.TASK_ID)


@dataclass(frozen=True)
class Cap:
    """A step's name, its wall-time budget, and what the agent does when the
    step goes past that budget."""
    name: str
    minutes: float
    action: str


class Step(Enum):
    READ = Cap("Read", 1.5, mctx(
        "Go to Precedent and design."))
    PRECEDENT = Cap("Precedent and design", 7, mctx(
        "Write the solver now."))
    WRITE = Cap("Write", 1.5, mctx(
        "Write the solver file now, and go to Develop."))
    DEVELOP = Cap("Develop", 4, mctx(
        "Stop adding branches. If no run has passed every pair, cut the solver to the concept "
        "case with no second choice point, run it, and keep it. Write each branch you drop "
        "under Unsettled. Follow Rules for one long command. Go to Determine."))
    DETERMINE = Cap("Determine", 5, mctx(
        "Stop the plan runs, write each entry that the last plan run lists under Unsettled, and "
        "go to Witness."))
    WITNESS = Cap("Witness", 5, mctx(
        "Make two attempts for each difference; then list it under Departures. Go to Simplify "
        "and Prune."))
    SIMPLIFY = Cap("Simplify and Prune", 2.5, mctx(
        "Stop simplifying, apply Rules for one long command to `deletions`, and go to Report."))
    REPORT = Cap("Report", 2.5, mctx(
        "Write the report now."))

    @property
    def cap(self) -> Cap:
        return self.value

    @property
    def slug(self) -> str:
        return slugged(self.cap.name)


def slugged(text: str) -> str:
    """`text` in lower case, with each run of spaces and hyphens a single
    hyphen."""
    return re.sub(r"[\s-]+", "-", text.strip().lower())


BY_SLUG = {s.slug: s for s in Step}


def step_named(text: str) -> Step | None:
    """The step whose name or slug `text` gives, ignoring case, spaces and
    hyphens; None where `text` gives none."""
    return BY_SLUG.get(slugged(text))


HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/create_pace.py <task id> <step> [--status <exit code>]
        ```
    - Run it at the start of each step of a Create pass. `<step>` is one of {steps}, each with its wall-time budget in minutes.
    - It records the time of the call under `work/task/<task id>/`. The first call for a task, and each call with `read`, starts the run's clock.
    - It prints the wall time used in the run and in the step that ended, the budget of the step that starts, and what to do when that step reaches its budget.
    - Where the step that ended went past its budget, it says so.
    - A call with the step in progress, the step of the run's last call, records no new start, and checks the step's time: it prints the run time, the time the step has used against its budget, and that step's at-budget action where the step is past its budget.
    - `--status` gives the exit code of the command that ran before the call. Where it is 124 (timeout) or 137 (`-9` kill), the call says which, and where to read what to do. Any other code adds nothing.
    - Where the run went past its target of {target} minutes, it says to take the at-budget action of the step that starts now.
    - Where the run went past its limit of {limit} minutes, at any step, it prints to go to the Report step, and on the first call past it, to restore `work/task/<task id>/{last_pass}` and `work/task/<task id>/{witnesses}` where they exist.
    """)

RUN_TIME = mctx("Run time used: {used:.1f} min. Target: {target} min. Limit: {limit} min.")
STEP_ENDED = mctx("{step} took {used:.1f} min. Its budget: {budget:g} min.")
STEP_STARTS = mctx("{step} starts. Its budget: {budget:g} min.")
STEP_OVER = mctx("{step} went past its budget.")
RUN_OVER_TARGET = mctx("The run is past its target. Do the at-budget action of {step} now.")
AT_BUDGET = mctx("At its budget, {step}: {action}")
RUN_OVER_LIMIT = mctx("The run is past its limit of {limit} min.")
RESTORE = mctx(
    "Restore the solver from `{path}` and the witness file from `{witnesses}` where it exists, "
    "and do not start another step. Write each step that you skipped or cut under "
    "`## Unsettled`, with the step name and its budget.")
NO_LAST_PASS = mctx(
    "`{path}` does not exist, so keep the current solver, and do not start another step. Write "
    "each step that you skipped or cut under `## Unsettled`, with the step name and its budget.")
TO_REPORT = mctx("Go to the Report step.")
WRITE_REPORT = mctx("Write the report.")
STEP_PAST = mctx("{step} is past its budget.")
STEP_USED = mctx("{step} has used {used:.1f} min. Its budget: {budget:g} min.")
STATUS_TIMEOUT = mctx("The last command stopped at its timeout (exit status 124).")
STATUS_KILLED = mctx("The last command was killed (exit status 137).")
LONG_COMMAND = mctx("For what to do, read the section `Rules for one long command` of `prompts/agents/create.md`.")
UNKNOWN_STEP = mctx("`{step}` is not a step; the steps are {steps}")
BAD_TASK = mctx("`{task}` is not a task id")


@dataclass(frozen=True)
class Call:
    """A call of the script: the step it gave and the time it came."""
    step: Step
    time: float


def read_run(records: Path) -> tuple[list[Call], bool]:
    """The calls of the run that `records` ends in, and whether a call of
    that run gave the restore text; none and False where `records` does not
    exist. A `Read` call starts a run; a record `{"restore": time}` marks
    the restore text."""
    calls: list[Call] = []
    restored = False
    if not records.exists():
        return calls, restored
    for line in records.read_text().splitlines():
        row = json.loads(line)
        if "restore" in row:
            restored = True
            continue
        call = Call(BY_SLUG[row["step"]], row["time"])
        if call.step is Step.READ:
            calls, restored = [], False
        calls.append(call)
    return calls, restored


def append(records: Path, row: dict[str, object]) -> None:
    records.parent.mkdir(parents=True, exist_ok=True)
    with records.open("a") as f:
        f.write(json.dumps(row) + "\n")


STATUS_TEXTS = {124: STATUS_TIMEOUT, 137: STATUS_KILLED}
"""The exit statuses of a command that a timeout or a `-9` kill stopped, each
with the line that says which."""


def pace(task_dir: Path, step: Step, now: float, status: int | None = None) -> str:
    """Record a call of `step` at `now` under `task_dir`, unless `step` is the
    step of the run's last call, and give the text it prints, with the lines
    for the exit `status` of the command before it where that is a stop."""
    records = task_dir / RECORDS
    run, restored = ([], False) if step is Step.READ else read_run(records)
    in_progress = bool(run) and run[-1].step is step
    if not in_progress:
        append(records, {"step": step.slug, "time": now})
    used = (now - run[0].time) / 60 if run else 0.0
    past_limit = used > LIMIT_MINUTES
    lines = [RUN_TIME.format(used=used, target=TARGET_MINUTES, limit=LIMIT_MINUTES)]
    if in_progress:
        lines += check_lines(task_dir, step, (now - run[-1].time) / 60, past_limit, restored)
    else:
        lines += start_lines(task_dir, step, run, now, used, restored)
    if past_limit and not restored:
        append(records, {"restore": now})
    if status in STATUS_TEXTS:
        lines += [STATUS_TEXTS[status], LONG_COMMAND]
    return "\n".join(lines)


def limit_lines(task_dir: Path, step: Step, restored: bool) -> list[str]:
    """The lines of a call past the run's limit: where no earlier call gave
    them, the restore of the last passing solver, and the pointer to the
    report, or, for a call at the Report step, the order to write it."""
    path = task_dir / LAST_PASS
    restore = [] if restored else [(RESTORE if path.exists() else NO_LAST_PASS).format(
        path=path, witnesses=task_dir / LAST_PASS_WITNESSES)]
    return [RUN_OVER_LIMIT.format(limit=LIMIT_MINUTES), *restore,
            WRITE_REPORT if step is Step.REPORT else TO_REPORT]


def check_lines(task_dir: Path, step: Step, took: float, past_limit: bool, restored: bool) -> list[str]:
    """What a call with the step in progress prints after the run time:
    the time `step` has used, and the limit lines or the step's action
    where the run or the step is past its limit or budget."""
    lines = [STEP_USED.format(step=step.cap.name, used=took, budget=step.cap.minutes)]
    if past_limit:
        return lines + limit_lines(task_dir, step, restored)
    if took > step.cap.minutes:
        lines += [STEP_PAST.format(step=step.cap.name),
                  AT_BUDGET.format(step=step.cap.name, action=step.cap.action)]
    return lines


def start_lines(task_dir: Path, step: Step, run: list[Call], now: float, used: float,
                restored: bool) -> list[str]:
    """What a call at `now` that starts `step` prints after the run time,
    where `run` holds the calls before it. Past the run's limit, only a call
    that starts the Report step gets its budget and action."""
    past_limit = used > LIMIT_MINUTES
    lines: list[str] = []
    over_step = False
    if run:
        ended = run[-1].step
        took = (now - run[-1].time) / 60
        over_step = took > ended.cap.minutes
        lines.append(STEP_ENDED.format(step=ended.cap.name, used=took, budget=ended.cap.minutes))
    if past_limit:
        lines += limit_lines(task_dir, step, restored)
        if step is not Step.REPORT:
            return lines
    lines.append(STEP_STARTS.format(step=step.cap.name, budget=step.cap.minutes))
    if over_step and not past_limit:
        lines.append(STEP_OVER.format(step=run[-1].step.cap.name))
    lines.append(AT_BUDGET.format(step=step.cap.name, action=step.cap.action))
    if used > TARGET_MINUTES and not past_limit:
        lines.append(RUN_OVER_TARGET.format(step=step.cap.name))
    return lines


def main() -> None:
    steps = ", ".join(f"`{s.slug}` {s.cap.minutes:g}" for s in Step)
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(HELP).format(
            steps=steps, target=TARGET_MINUTES, limit=LIMIT_MINUTES, last_pass=LAST_PASS, witnesses=LAST_PASS_WITNESSES),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task_id")
    parser.add_argument("step")
    parser.add_argument("--status", type=int)
    args = parser.parse_args()
    task_id: str = args.task_id
    if not TASK_ID.fullmatch(task_id):
        parser.error(BAD_TASK.format(task=task_id))
    step = step_named(args.step)
    if step is None:
        parser.error(UNKNOWN_STEP.format(step=args.step, steps=", ".join(f"`{slug}`" for slug in BY_SLUG)))
    print(pace(Path("work/task") / task_id, step, time.time(), args.status))


if __name__ == "__main__":
    main()
