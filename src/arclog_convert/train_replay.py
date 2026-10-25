"""The replay of each converted case on the train pairs of its task, and the
report of the cases that do not end `Consistent`.

    uv run python -m arclog_convert.train_replay [--out <dir>] [--accept] [<stem> ...]

The command replays the files under `gen/` of `arclog_convert.out`, or of
`--out`, with no conversion; `arclog_convert.convert` runs the same replay on
the solvers it converted. `arclog-cli verdicts` replays every case closed-world
and gives each case a verdict: the consistency of the last `RULE` the stream
ends (`Consistent`, `NotConsistent`, `SeveralValues`, `Fault`, `Stopped`),
`NoRule` where it ends none, `Refused` where the decoder refuses the stream,
`NoStream` where the writer gives the case no stream, and `Unread` for a
solver whose files or task do not read. The cases are the solver's cases,
without the combinations that its `exclude` forms leave out. A task whose
every case holds a `DEMONSTRATED` form gets no line, so its record holds no
case. A `SeveralValues` detail is the relation (`&x`) whose several values keep
every train pair consistent. The command needs a Rust toolchain
and no Python environment with the `arclog` package: cargo finds or builds
the engine's tool build in the tree the command runs in.

A task's verdicts stand in `train_replay/<stem>.json` beside `gen/`, under a
key: the sha256 of the task's `.arclog` and `.arcdata`, of the files of each
solver that a `(representative <id>)` line names, followed to its end, of the
task file, and of the engine's sources. A task whose record has its key
replays nothing. A task with a case `Stopped` at the deadline gets no
record, since that verdict depends on the machine's load.

`unreproduced.tsv` is the baseline: a line `<task> <verdict> <count>
<ticket or ->` (tab-separated) for each task and verdict other than
`Consistent` with a count above 0, sorted. The report covers the tasks the run
covers. It prints a line for each task and verdict whose count exceeds the
baseline's, with the first such case; a line for each case that the task's
previous record gives as `Consistent` and that is not now; a line for each
task and verdict whose count fell below the baseline's; and a final line
with the counts. The exit status is 1 where a count exceeds the baseline or
a case that was `Consistent` is not now, and 0 otherwise. `--accept`
rewrites the baseline lines of the covered tasks to the run's counts, keeping
the ticket field of each line whose task and verdict stay."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from arc.task import TASKS_DIR
from engine import checkout

BASELINE = Path(__file__).with_name("unreproduced.tsv")

ENGINE_PATTERNS = (
    "engine/Cargo.toml", "engine/Cargo.lock",
    *(f"engine/{crate}/{pattern}"
      for crate in ("arclog", "arclog-constructions", "arclog-cli")
      for pattern in ("Cargo.toml", "src/**/*.rs")),
    "engine/lib/*",
)
"""The engine's files the verdicts rest on."""

REPRESENTATIVE = re.compile(r"\(representative\s+([^\s()]+)\)")


@dataclass(frozen=True)
class Case:
    case: str
    concept: bool
    verdict: str
    token: str
    detail: str


def read_baseline(path: Path = BASELINE) -> dict[tuple[str, str], tuple[int, str]]:
    """The count and the ticket of each task and verdict of the baseline."""
    baseline = {}
    for line in path.read_text().splitlines() if path.exists() else []:
        task, verdict, count, ticket = line.split("\t")
        baseline[task, verdict] = (int(count), ticket)
    return baseline


def write_baseline(baseline: dict[tuple[str, str], tuple[int, str]], path: Path = BASELINE) -> None:
    path.write_text("".join(f"{task}\t{verdict}\t{count}\t{ticket}\n"
                            for (task, verdict), (count, ticket) in sorted(baseline.items())))


def solver_files(gen: Path, stem: str) -> list[Path]:
    """The `.arclog` and `.arcdata` files of the solver `stem`, then those of
    each representative its `.arcdata` names, followed to its end."""
    files, queue, seen = [], [stem], set()
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        files += [gen / f"{name}.arclog", gen / f"{name}.arcdata"]
        data = gen / f"{name}.arcdata"
        if data.exists():
            queue += REPRESENTATIVE.findall(data.read_text())
    return files


def engine_digest() -> str:
    """The digest of the engine's sources."""
    return checkout.sources_digest(ENGINE_PATTERNS)


def record_key(stem: str, gen: Path, tasks: Path, engine: str) -> str:
    """The key of the record of `stem`: the digest of its files, its task file and `engine`."""
    digest = hashlib.sha256(engine.encode())
    for path in [*solver_files(gen, stem), tasks / f"{stem}.json"]:
        digest.update(path.name.encode() + b"\0")
        digest.update((path.read_bytes() if path.exists() else b"") + b"\0")
    return digest.hexdigest()


def read_record(records: Path, stem: str) -> dict | None:
    path = records / f"{stem}.json"
    return json.loads(path.read_text()) if path.exists() else None


def stale_tasks(stems: list[str], gen: Path, tasks: Path, records: Path, engine: str) -> list[str]:
    """The stems with no record under `records`, or a record with another key."""
    stale = []
    for stem in stems:
        record = read_record(records, stem)
        if record is None or record["key"] != record_key(stem, gen, tasks, engine):
            stale.append(stem)
    return stale


def run_verdicts(stems: list[str], gen: Path, tasks: Path) -> dict[str, list[Case]]:
    """The cases of each of `stems`, from one `arclog-cli verdicts` run."""
    command = ["cargo", "run", "--profile", "tool", "-q", "-p", "arclog-cli", "--",
               "verdicts", str(gen), str(tasks), *stems]
    done = subprocess.run(command, cwd=checkout.ROOT / "engine", stdout=subprocess.PIPE, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} exited with {done.returncode}")
    cases: dict[str, list[Case]] = {stem: [] for stem in stems}
    for line in done.stdout.splitlines():
        task, case, concept, verdict, token, detail = line.split("\t", 5)
        cases[task].append(Case(case, concept == "1", verdict, token, detail))
    return cases


def write_record(records: Path, stem: str, key: str, cases: list[Case]) -> None:
    """Write the record of `stem`, unless a case stopped at the deadline."""
    if any(c.verdict == "Stopped" and c.detail == "Deadline" for c in cases):
        (records / f"{stem}.json").unlink(missing_ok=True)
        return
    records.mkdir(parents=True, exist_ok=True)
    data = {"key": key, "cases": [vars(c) for c in cases]}
    (records / f"{stem}.json").write_text(json.dumps(data, indent=1) + "\n")


def replay(stems: list[str], out: Path, accept: bool = False) -> int:
    """Replay the stale tasks of `stems` under `out`, print the report, and
    give the exit status."""
    gen, records, tasks = out / "gen", out / "train_replay", TASKS_DIR
    engine = engine_digest()
    stale = stale_tasks(stems, gen, tasks, records, engine)
    previous = {stem: read_record(records, stem) for stem in stale}
    cases: dict[str, list[Case]] = {}
    if stale:
        cases = run_verdicts(stale, gen, tasks)
        for stem in stale:
            write_record(records, stem, record_key(stem, gen, tasks, engine), cases[stem])
    for stem in stems:
        if stem not in cases:
            cases[stem] = [Case(**c) for c in read_record(records, stem)["cases"]]
    baseline = read_baseline()
    counts = {(stem, v): n for stem in stems for v, n in Counter(c.verdict for c in cases[stem]).items() if v != "Consistent"}
    beyond = below = regressed = 0
    for (stem, verdict), n in sorted(counts.items()):
        if n > baseline.get((stem, verdict), (0, "-"))[0]:
            beyond += n - baseline.get((stem, verdict), (0, "-"))[0]
            first = next(c for c in cases[stem] if c.verdict == verdict)
            print(f"{stem}: {n} cases {verdict} where the baseline gives {baseline.get((stem, verdict), (0, '-'))[0]}; "
                  f"first {first.case} (token {first.token}) {first.detail}")
    for stem in stale:
        old = previous[stem]
        if old is None:
            continue
        was = {c["case"] for c in old["cases"] if c["verdict"] == "Consistent"}
        for c in cases[stem]:
            if c.case in was and c.verdict != "Consistent":
                regressed += 1
                print(f"{stem}: case {c.case} was Consistent and is {c.verdict} (token {c.token}) {c.detail}")
    for (stem, verdict), (n, _) in sorted(baseline.items()):
        if stem in cases and counts.get((stem, verdict), 0) < n:
            below += n - counts.get((stem, verdict), 0)
            print(f"{stem}: {counts.get((stem, verdict), 0)} cases {verdict} where the baseline gives {n}")
    total = sum(counts.values())
    print(f"train replay: {len(stale)} tasks replayed, {len(stems) - len(stale)} taken from their record; "
          f"{total} cases not Consistent, {beyond} beyond the baseline, {below} below it")
    if accept:
        kept = {k: v for k, v in baseline.items() if k[0] not in cases}
        kept |= {k: (n, baseline.get(k, (0, "-"))[1]) for k, n in counts.items()}
        write_baseline(kept)
    return 1 if beyond or regressed else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m arclog_convert.train_replay")
    parser.add_argument("--out", type=Path, help="the directory that holds gen/, in place of `arclog_convert.out`")
    parser.add_argument("--accept", action="store_true", help="rewrite the baseline lines of the tasks the run covers")
    parser.add_argument("stems", nargs="*", help="the solvers to replay; every solver of gen/ where none is given")
    args = parser.parse_args(argv)
    from arclog_convert import out
    root = args.out.resolve() if args.out else out()
    stems = args.stems or sorted(p.stem for p in (root / "gen").glob("*.arclog"))
    return replay(stems, root, args.accept)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
