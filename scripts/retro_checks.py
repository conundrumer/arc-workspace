"""Run the tree's checks and print what each one reports, as JSON. Deprecated.

    uv run python scripts/retro_checks.py [stem ...]

The handbook render, and a run of every solver, or of the
stems given. Each one runs to completion, whatever an earlier one reported.
The checks take minutes, and nothing but stdout is written.

Each check is an object with its `command`, whether it `passed`, its
`summary` line and its `failures`. The corpus run goes in chunks of
`CHUNK` solvers through `run --json`. A solver fails when a pair of it
fails or its determination check finds a problem.
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from checker.render import commands
from cli.common import all_stems
from controlled_markdown import mctx

ROOT = Path(__file__).resolve().parents[1]

# How many solvers one corpus run takes. A run holds every pair of its stems
# in one pool, so the corpus goes in parts.
CHUNK = 100

CONTEXT_CMD = ["uv", "run", "python", "scripts/context.py"]
RUN_CMD = ["uv", "run", "python", "scripts/run_dl.py", "run", "--json"]

CORPUS_COMMAND = (f"uv run python scripts/run_dl.py run --json "
                  f"<the corpus, in chunks of {CHUNK}>")

# The kind of a `run --json` section whose lines show why a solver fails.
FAILURES = "failures"

type Check = dict[str, object]


@dataclass(frozen=True)
class Ran:
    """One command's exit code, and what it wrote to stdout and stderr."""

    code: int
    stdout: str
    stderr: str


def _run(cmd: list[str]) -> Ran:
    """One command from the repo root."""
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return Ran(proc.returncode, proc.stdout, proc.stderr)


def check_context() -> Check:
    """The handbook render. Its output is what the check discards; what it
    reports is whether the render came through."""
    ran = _run(CONTEXT_CMD)
    return {"command": " ".join(CONTEXT_CMD) + " > /dev/null",
            "passed": ran.code == 0,
            "summary": f"exit {ran.code}",
            "failures": "" if ran.code == 0 else ran.stderr.strip()}


def chunks(stems: list[str], size: int = CHUNK) -> list[list[str]]:
    """The stems in parts of at most `size`."""
    return [stems[n:n + size] for n in range(0, len(stems), size)]


def _streams(*texts: str) -> list[str]:
    return [text.strip() for text in texts if text.strip()]


@dataclass(frozen=True)
class Report:
    """What `run --json` printed: per solver its stem, pair counts and
    whether its pairs all pass, the solvers whose determination check
    finds a problem, and the sections."""

    verdicts: tuple[tuple[str, int, int, bool], ...]
    problems: frozenset[str]
    sections: tuple[tuple[str, str, tuple[str, ...]], ...]

    @staticmethod
    def of(data: dict[str, Any]) -> "Report":
        return Report(
            tuple((v["stem"], v["passes"], v["total"], v["pairs_pass"])
                  for v in data["verdicts"]),
            frozenset(d["stem"] for d in data["determination_checks"]
                      if d["problem"]),
            tuple((s["kind"], s["header"], tuple(s["lines"]))
                  for s in data["sections"]))

    def fails(self, stem: str, pairs_pass: bool) -> bool:
        return not pairs_pass or stem in self.problems

    @property
    def stems(self) -> list[str]:
        return [v[0] for v in self.verdicts]

    @property
    def passing(self) -> int:
        return sum(not self.fails(s, p) for s, _n, _t, p in self.verdicts)

    @property
    def exit_code(self) -> int:
        return 0 if self.passing == len(self.verdicts) else 1

    def failures(self) -> list[str]:
        """The verdict line of each solver that fails, then each failure
        section that holds an entry."""
        lines = [commands.verdict_line(s, n, t, True)
                 for s, n, t, p in self.verdicts if self.fails(s, p)]
        for kind, header, entries in self.sections:
            if kind == FAILURES and entries:
                lines += [*commands.section_header(header), *entries]
        return lines


@dataclass(frozen=True)
class NoReport:
    """The run's stdout holds no report: no JSON, or JSON of another
    shape."""

    def entry(self, ran: Ran, stems: list[str]) -> list[str]:
        return [mctx("no report from the run (exit {code}) over "
                     "{stems}").format(code=ran.code, stems=" ".join(stems)),
                *_streams(ran.stdout, ran.stderr)]


@dataclass(frozen=True)
class ExitDisagrees:
    """The run exited on another code than its report gives."""

    reported: int

    def entry(self, ran: Ran, stems: list[str]) -> list[str]:
        return [mctx("the run over {stems} exited {code}, and its report "
                     "gives exit {reported}").format(
                         stems=" ".join(stems), code=ran.code,
                         reported=self.reported),
                *_streams(ran.stderr)]


@dataclass(frozen=True)
class OtherSolvers:
    """The run's report covers other solvers than the run was given."""

    reported: tuple[str, ...]

    def entry(self, ran: Ran, stems: list[str]) -> list[str]:
        return [mctx("the report of the run (exit {code}) over {stems} "
                     "covers {reported}").format(
                         code=ran.code, stems=" ".join(stems),
                         reported=" ".join(self.reported)),
                *_streams(ran.stderr)]


# Why the check takes no verdicts from a run. Each one's `entry` is a
# heading and the streams of the run that show the cause.
type Unreported = NoReport | ExitDisagrees | OtherSolvers


def _report(ran: Ran, stems: list[str]) -> Report | Unreported:
    """The report a run over `stems` printed, or why the check takes none
    from it."""
    try:
        report = Report.of(json.loads(ran.stdout))
    except (ValueError, KeyError, TypeError):
        return NoReport()
    if ran.code != report.exit_code:
        return ExitDisagrees(report.exit_code)
    if report.stems != stems:
        return OtherSolvers(tuple(report.stems))
    return report


def check_corpus(stems: list[str]) -> Check:
    """The solvers, run a chunk at a time, reported as one check. A solver
    that fails in the report of its chunk fails the check, with the lines
    that show why. A chunk whose run gives no report the check takes fails
    the check with the reason (`Unreported`), and its solvers count toward
    the total and not toward the passing."""
    passing = total = 0
    failures: list[str] = []
    unreported: list[str] = []
    for part in chunks(stems, CHUNK):
        ran = _run([*RUN_CMD, *part])
        total += len(part)
        report = _report(ran, part)
        if not isinstance(report, Report):
            unreported += part
            heading, *shown = report.entry(ran, part)
            failures.append("\n".join(
                [heading + (":" if shown else ""), *shown]))
            continue
        passing += report.passing
        if lines := report.failures():
            failures.append("\n".join(lines).strip())
    summary = commands.SUMMARY.format(passing=passing, total=total)
    if unreported:
        summary += mctx(", {count} with no verdict").format(
            count=len(unreported))
    command = CORPUS_COMMAND if stems == all_stems() else " ".join(
        [*RUN_CMD, *stems])
    return {"command": command,
            "passed": not failures,
            "summary": summary,
            "failures": "\n\n".join(failures)}


def main(argv: list[str]) -> int:
    stems = argv or all_stems()
    checks = [check_context(), check_corpus(stems)]
    print(json.dumps({"checks": checks}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
