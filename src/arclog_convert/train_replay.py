"""The replay of each converted case on the train pairs of its task, and the
report of the cases that do not end `Consistent`.

    uv run python -m arclog_convert.train_replay [--out <dir>] [<stem> ...]

The command replays the files under `gen/` of `arclog_convert.out`, or of
`--out`, with no conversion; in a linked worktree it writes no record without `--out` or `ARCLOG_OUT`; `arclog_convert.convert` runs the same replay on
the solvers it converted. the `verdicts` binary of `arclog-cli` replays every case closed-world
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

A task's verdicts stand in `train_replay/<stem>.json` beside `gen/`, as a
record with these fields: `files`, the sha256 of the task's `.arclog` and
`.arcdata`, of the files of each solver that a `(representative <id>)` line
names, followed to its end, and of the task file; `sources`, the digest of the
engine's sources; `binary`, the sha256 of the built `verdicts` binary; and
`cases`. A task is fresh, and replays nothing, where its record's `files`
equal the current ones and either its `sources` equal the current digest or its
`binary` equals the current binary's digest; the binary is built and hashed
only where a task fails the source test, and a task fresh by its binary gets
its `sources` rewritten. A record in the old form, with a `key`, is stale.

`unreproduced.tsv` is the baseline: a line `<task> <verdict> <count>
<ticket or ->` (tab-separated) for each task and verdict other than
`Consistent` with a count above 0, sorted. The report covers the tasks the run
covers. It prints a line for each task and verdict whose count exceeds the
baseline's, with the first such case; a line for each case that the task's
previous record gives as `Consistent` and that is not now; a line for each
task and verdict whose count fell below the baseline's; and a final line
with the counts. The exit status is 1 where a count exceeds the baseline or
a case that was `Consistent` is not now, and 0 otherwise. Only
`arclog_convert.convert --accept` rewrites the baseline."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from arc.task import TASKS_DIR
from engine import checkout

BASELINE = Path(__file__).with_name("unreproduced.tsv")

ENGINE_PATTERNS = (
    "engine/Cargo.toml", "engine/Cargo.lock",
    *(f"engine/{crate}/{pattern}"
      for crate in ("arclog", "arclog-constructions", "arclog-tables", "arclog-cli")
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


def tool_binary(name: str) -> Path:
    """The built `name` binary of `arclog-cli` (`verdicts`, `arclog-cli`)."""
    return checkout.ROOT / "engine" / "target" / "tool" / name


def hash_binary(name: str = "verdicts") -> str:
    """The sha256 of the `name` binary as it stands."""
    return hashlib.sha256(tool_binary(name).read_bytes()).hexdigest()


def binary_digest(name: str = "verdicts") -> str:
    """The sha256 of the `name` binary, built first."""
    command = ["cargo", "build", "--profile", "tool", "-q", "-p", "arclog-cli", "--bin", name]
    subprocess.run(command, cwd=checkout.ROOT / "engine", check=True)
    return hash_binary(name)


def files_digest(stem: str, gen: Path, tasks: Path) -> str:
    """The digest of the files of `stem` and its representatives, and its task file."""
    digest = hashlib.sha256()
    for path in [*solver_files(gen, stem), tasks / f"{stem}.json"]:
        digest.update(path.name.encode() + b"\0")
        digest.update((path.read_bytes() if path.exists() else b"") + b"\0")
    return digest.hexdigest()


def read_record(records: Path, stem: str) -> dict | None:
    path = records / f"{stem}.json"
    return json.loads(path.read_text()) if path.exists() else None


def stale_tasks(stems: list[str], files: Callable[[str], str], records: Path, sources: str,
                binary: Callable[[], str] = binary_digest) -> list[str]:
    """The stems whose record is missing, in the old form, or has other files
    than `files(stem)` gives,
    and neither `sources` nor the digest `binary()` gives. `binary` runs at
    most once, and only where a task with equal files has other sources. A
    task fresh by its binary gets its record's `sources` rewritten."""
    stale, built = [], None
    for stem in stems:
        record = read_record(records, stem)
        if record is None or record.get("files") != files(stem):
            stale.append(stem)
        elif record["sources"] != sources:
            built = binary() if built is None else built
            if record["binary"] != built:
                stale.append(stem)
            else:
                record["sources"] = sources
                (records / f"{stem}.json").write_text(json.dumps(record, indent=1) + "\n")
    return stale


def run_verdicts(stems: list[str], gen: Path, tasks: Path) -> dict[str, list[Case]]:
    """The cases of each of `stems`, from one run of the `verdicts` binary."""
    command = [str(tool_binary("verdicts")), str(gen), str(tasks), *stems]
    done = subprocess.run(command, cwd=checkout.ROOT / "engine", stdout=subprocess.PIPE, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} exited with {done.returncode}")
    cases: dict[str, list[Case]] = {stem: [] for stem in stems}
    for line in done.stdout.splitlines():
        task, case, concept, verdict, token, detail = line.split("\t", 5)
        cases[task].append(Case(case, concept == "1", verdict, token, detail))
    return cases


def write_record(records: Path, stem: str, files: str, sources: str, binary: str, cases: list[Case]) -> None:
    """Write the record of `stem`."""
    records.mkdir(parents=True, exist_ok=True)
    data = {"files": files, "sources": sources, "binary": binary, "cases": [vars(c) for c in cases]}
    (records / f"{stem}.json").write_text(json.dumps(data, indent=1) + "\n")


def replay(stems: list[str], out: Path, accept: bool = False) -> int:
    """Replay the stale tasks of `stems` under `out`, print the report, and
    give the exit status."""
    gen, records, tasks = out / "gen", out / "train_replay", TASKS_DIR
    sources = engine_digest()
    digests: list[str] = []

    def binary() -> str:
        digests.append(binary_digest())
        return digests[-1]

    stale = stale_tasks(stems, lambda stem: files_digest(stem, gen, tasks), records, sources, binary)
    previous = {stem: read_record(records, stem) for stem in stale}
    cases: dict[str, list[Case]] = {}
    if stale:
        built = digests[0] if digests else binary_digest()
        cases = run_verdicts(stale, gen, tasks)
        if hash_binary() != built:
            raise RuntimeError("the verdicts binary was replaced during the run")
        for stem in stale:
            write_record(records, stem, files_digest(stem, gen, tasks), sources, built, cases[stem])
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
    parser.add_argument("--out", type=Path, help="the directory that holds gen/, in place of `arclog_convert.out`; required in a linked worktree unless `ARCLOG_OUT` is set")
    parser.add_argument("stems", nargs="*", help="the solvers to replay; every solver of gen/ where none is given")
    args = parser.parse_args(argv)
    from arclog_convert import writable_out
    root = args.out.resolve() if args.out else writable_out()
    stems = args.stems or sorted(p.stem for p in (root / "gen").glob("*.arclog"))
    return replay(stems, root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
