"""The checks over the whole tree: the test suite, the handbook render, and
the corpus run.

Each check runs to completion, whatever an earlier one reported, and each
one reports its summary line and its failures.
"""

import json
import re
import subprocess

from dl.paths import REPO_ROOT, all_stems

# How many solvers one corpus run takes. A run holds every pair of its stems
# in one pool, so the corpus goes in parts.
CHUNK = 100

PYTEST_CMD = ["uv", "run", "pytest", "-q"]
CONTEXT_CMD = ["uv", "run", "python", "scripts/context.py"]
RUN_CMD = ["uv", "run", "python", "scripts/run_dl.py", "run"]

CORPUS_COMMAND = (f"uv run python scripts/run_dl.py run "
                  f"<the corpus, in chunks of {CHUNK}>")

# The runner opens each of its sections with this line, and closes the report
# with the summary.
SECTION = re.compile(r"^--- (.*) ---$")
SUMMARY = re.compile(r"^summary: (\d+)/(\d+) solvers$")
# A section the runner names `findings` holds style calls for a session to
# rule on, not failures.
FINDINGS = "findings"
# The per-solver verdict line of a corpus run.
FAIL_LINE = re.compile(r"^\S+: \d+/\d+ FAIL$")

# The line pytest closes with, and the banner over its failure detail.
PYTEST_STATS = re.compile(r"\b\d+ (passed|failed|error|errors)\b")
PYTEST_BANNER = re.compile(r"^=+ (FAILURES|ERRORS) =+$")

type Section = tuple[str, list[str]]
type Check = dict[str, object]


def sections(out: str) -> list[Section]:
    """The runner's sections as (header, body lines). The summary line closes
    the last one."""
    found: list[Section] = []
    for raw in out.splitlines():
        line = raw.strip()
        if SUMMARY.match(line):
            break
        if m := SECTION.match(line):
            found.append((m.group(1), []))
        elif found:
            found[-1][1].append(raw)
    return found


def run_counts(out: str) -> tuple[int, int] | None:
    """The passing and total solver counts of one corpus run, or None when
    the run printed no summary."""
    for raw in out.splitlines():
        if m := SUMMARY.match(raw.strip()):
            return int(m.group(1)), int(m.group(2))
    return None


def run_failures(out: str) -> str:
    """What one corpus run reports as failing: its FAIL verdict lines, and
    every section the runner does not name a findings section."""
    parts: list[str] = [raw for raw in out.splitlines()
                        if FAIL_LINE.match(raw.strip())]
    for header, body in sections(out):
        if FINDINGS in header or not any(line.strip() for line in body):
            continue
        parts.append(f"--- {header} ---")
        parts.extend(body)
    return "\n".join(parts).strip()


def corpus_summary(outs: list[str]) -> str:
    """The chunks' counts as one summary line."""
    counts = [c for out in outs if (c := run_counts(out)) is not None]
    return (f"summary: {sum(p for p, _ in counts)}/"
            f"{sum(t for _, t in counts)} solvers")


def pytest_summary(out: str) -> str:
    """The stats line pytest closes with."""
    for raw in reversed(out.splitlines()):
        if PYTEST_STATS.search(raw):
            return raw.strip()
    return ""


def pytest_failures(out: str) -> str:
    """Pytest's report on the tests that failed. Without its failure banner
    the whole output stands, so nothing is dropped."""
    lines = out.splitlines()
    for n, raw in enumerate(lines):
        if PYTEST_BANNER.match(raw.strip()):
            return "\n".join(lines[n:]).strip()
    return out.strip()


def _run(cmd: list[str], keep_stdout: bool = True) -> tuple[int, str]:
    """One command from the repo root, with its output as one text."""
    proc = subprocess.run(
        cmd, cwd=REPO_ROOT, text=True,
        stdout=subprocess.PIPE if keep_stdout else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def check_pytest() -> Check:
    code, out = _run(PYTEST_CMD)
    return {"command": " ".join(PYTEST_CMD),
            "passed": code == 0,
            "summary": pytest_summary(out),
            "failures": "" if code == 0 else pytest_failures(out)}


def check_context() -> Check:
    """The handbook render. Its output is what the check discards; what it
    reports is whether the render came through."""
    code, out = _run(CONTEXT_CMD, keep_stdout=False)
    return {"command": " ".join(CONTEXT_CMD) + " > /dev/null",
            "passed": code == 0,
            "summary": f"exit {code}",
            "failures": "" if code == 0 else out.strip()}


def chunks(stems: list[str], size: int = CHUNK) -> list[list[str]]:
    """The stems in parts of at most `size`. The runner reads one stem as a
    single-solver run and reports it in another form, so a part left holding
    one stem takes a second one from the part before it."""
    parts = [stems[n:n + size] for n in range(0, len(stems), size)]
    if len(parts) > 1 and len(parts[-1]) == 1:
        parts[-2].extend(parts.pop())
    return parts


def check_corpus() -> Check:
    """Every solver, run a chunk at a time, reported as one check."""
    codes: list[int] = []
    outs: list[str] = []
    failures: list[str] = []
    for part in chunks(all_stems(), CHUNK):
        code, out = _run([*RUN_CMD, *part])
        codes.append(code)
        outs.append(out)
        text = run_failures(out) if run_counts(out) else out.strip()
        if text:
            failures.append(text)
    return {"command": CORPUS_COMMAND,
            "passed": all(code == 0 for code in codes) and not failures,
            "summary": corpus_summary(outs),
            "failures": "\n\n".join(failures)}


def main() -> int:
    checks = [check_pytest(), check_context(), check_corpus()]
    print(json.dumps({"checks": checks}, ensure_ascii=False, indent=1))
    return 0
