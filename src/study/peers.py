"""The alternate models past solver sessions wrote and did not ship.

A session that wrote a solver often wrote other whole programs beside it,
under `.scratch/<task id>/` and `.scratch/theory-test/<task id>/`. The
session's report says which of those it dropped and on what ground. This
module collects both sides: the programs on disk, the drop grounds the
reports state, and, for each program that is not a copy of the shipped
solver, what it does on the task's own pairs.

A peer's key on a pair is the set of grids it emits there, `UNDEF` when a
grid is not readable. The shipped solver's cases carry keys of the same
shape, so a pair either puts the peer on some shipped case or tells it
apart from every one of them.
"""

import difflib
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from arc.task import load as load_task
from dl.context import uncommented
from dl.dlparse import Comp, Decl, ParseError, TypeDecl, parse
from dl.features_run import ABSENT, UNDEF, Key, _pair_keys, report_of
from dl.paths import REPO_ROOT, SOLVERS_DIR
from dl.solve import PairResult, res_out_stem, run_pair
from dl.souffle import _pool_workers

SCRATCH_DIR = REPO_ROOT / ".scratch"
THEORY_DIR = SCRATCH_DIR / "theory-test"
REPORTS_DIR = REPO_ROOT / "tools" / "console" / "state" / "reports"
OUT_DIR = SCRATCH_DIR / "peers"

COPY_NAMES = {"orig", "before", "keep"}
"""File stems that hold a copy of the solver, not an alternate model."""

TASK_ID_RE = re.compile(r"^[0-9a-f]{8}")
SEPARATOR_RE = re.compile(r"^[-_.]")

STRATA: list[tuple[str, re.Pattern[str]]] = [
    ("fit", re.compile(r"does not fit|fails (train|test)|reproduces no", re.I)),
    ("restatement", re.compile(r"restatement", re.I)),
    ("subsumed", re.compile(r"subsum", re.I)),  # the reports write "subsumes"
    ("peer-priors", re.compile(r"Peer priors|same prior|parse alike", re.I)),
    ("exercised",
     re.compile(r"(peer|case|branch).{0,60}unexercised", re.I)),
]
"""Drop grounds, in the order a block is tested against."""

UNNAMED = "unnamed"
"""The stratum of a block that states no ground."""

DROP_RE = re.compile(
    r"gets no case|considered and dropped|dropped peer|subsum", re.I)
"""A block that says a model was dropped. `subsum` is the stem, because a
report states the ground as "the shipped case subsumes it"."""

FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)
HEADING_RE = re.compile(r"^#+ .*$", re.M)
BLOCK_SPLIT_RE = re.compile(r"\n\s*\n")
ITEM_SPLIT_RE = re.compile(r"\n(?=\s*(?:[-*+]|\d+\.)\s)")
TICKED_RE = re.compile(r"`([^`\n]+)`")
DOLLAR_RE = re.compile(r"\$[A-Za-z_]\w*")
IDENT_RE = re.compile(r"[A-Za-z_$][\w.$<>]*\Z")

TSV_COLUMNS = [
    "task_id", "source", "path", "peer_name", "report_name", "stratum",
    "is_copy", "runs", "pairs_passed", "pairs_total", "pairs_undefined",
    "pairs_diverging", "nearest_case", "pairs_matching_case", "matched_by",
    "shared_names",
]

type Mention = tuple[str, str]
"""A name a report block carries, with that block's stratum."""


@dataclass
class Block:
    """One mined report block: the names it carries, the ground it states,
    and whether it says a model was dropped."""

    names: list[str]
    stratum: str
    dropped: bool

    def keys(self) -> set[str]:
        return {norm_name(name) for name in self.names} - {""}


@dataclass
class Row:
    """One inventory line: a program on disk, or a report block that names
    no program."""

    task_id: str
    source: str            # "scratch" or "report"
    path: Path | None
    peer_name: str
    report_name: str = ""
    stratum: str = ""
    is_copy: bool = False
    runs: bool | None = None
    pairs_passed: int | None = None
    pairs_total: int | None = None
    pairs_undefined: int | None = None
    pairs_diverging: int | None = None
    nearest_case: str = ""
    pairs_matching_case: int | None = None
    matched_by: str = ""
    shared_names: str = ""

    def cells(self) -> list[str]:
        path = "" if self.path is None else str(self.path.relative_to(REPO_ROOT))
        return [
            self.task_id, self.source, path, self.peer_name, self.report_name,
            self.stratum, _flag(self.is_copy), _flag(self.runs),
            _num(self.pairs_passed), _num(self.pairs_total),
            _num(self.pairs_undefined), _num(self.pairs_diverging),
            self.nearest_case, _num(self.pairs_matching_case),
            self.matched_by, self.shared_names,
        ]


def _flag(value: bool | None) -> str:
    return "" if value is None else ("yes" if value else "no")


def _num(value: int | None) -> str:
    return "" if value is None else str(value)


# --- the programs on disk ---


def peer_name_of(file_name: str, task_id: str) -> str:
    """What a scratch file calls its model: the file stem without the task
    id it leads with and one separator after that id."""
    stem = Path(file_name).stem
    if stem.startswith(task_id):
        rest = stem[len(task_id):]
        rest = SEPARATOR_RE.sub("", rest, count=1)
        if rest:
            return rest
    return stem


def declares_out(text: str) -> bool:
    """True when the program declares `out`. A file Souffle's grammar
    rejects is read for the declaration line alone."""
    try:
        program = parse(text)
    except (ParseError, RecursionError):
        return bool(re.search(r"\.decl\s+out\b", text))
    return any(isinstance(it, Decl) and it.name == "out" for it in program.items)


def normalize_source(text: str) -> str:
    """A program's text with its comments gone and its spacing flattened,
    so two files that differ only in what they say about themselves
    normalize alike."""
    text = uncommented(text)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    return " ".join(text.split())


@cache
def declared_names(text: str) -> dict[str, str]:
    """The identifiers a program declares, keyed by their normalized form:
    the branch names of its `Choice` type and the name of every `.decl`,
    inside a comp as well as outside one."""
    try:
        program = parse(text)
    except (ParseError, RecursionError):
        return {}
    found: dict[str, str] = {}

    def walk(items) -> None:
        for it in items:
            if isinstance(it, Decl):
                found.setdefault(norm_name(it.name), it.name)
            elif isinstance(it, TypeDecl) and it.name == "Choice":
                for branch in it.branches:
                    found.setdefault(norm_name(branch), branch)
            elif isinstance(it, Comp):
                walk(it.items)

    walk(program.items)
    found.pop("", None)
    return found


def own_names(text: str, shipped: str) -> dict[str, str]:
    """The identifiers a program declares that the shipped solver does not.
    Those are what sets an alternate model apart, so those are what a report
    names when it describes one."""
    return {key: name for key, name in declared_names(text).items()
            if key not in declared_names(shipped)}


def _scratch_dirs(root: Path = SCRATCH_DIR) -> list[tuple[str, Path]]:
    """Every task directory under the scratch tree, as (task id, directory)."""
    found: list[tuple[str, Path]] = []
    for base in (root, root / "theory-test"):
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if path.is_dir() and TASK_ID_RE.fullmatch(path.name):
                found.append((path.name, path))
    return found


def scan_scratch(root: Path = SCRATCH_DIR,
                 solvers: Path = SOLVERS_DIR) -> list[Row]:
    """Every scratch program that declares `out`, one row each. A file whose
    stem is a copy name, or whose normalized text equals the shipped
    solver's, is marked a copy."""
    rows: list[Row] = []
    for task_id, directory in _scratch_dirs(root):
        shipped = solvers / f"{task_id}.dl"
        shipped_text = (normalize_source(shipped.read_text())
                        if shipped.is_file() else None)
        for path in sorted(directory.glob("*.dl")):
            text = path.read_text(errors="replace")
            if not declares_out(text):
                continue
            name = peer_name_of(path.name, task_id)
            is_copy = (path.stem in COPY_NAMES or name in COPY_NAMES
                       or normalize_source(text) == shipped_text)
            rows.append(Row(task_id=task_id, source="scratch", path=path,
                            peer_name=name, is_copy=is_copy))
    return rows


# --- the grounds the reports state ---


def blocks(text: str) -> list[str]:
    """A report's paragraphs and list items. Fenced code holds grids and a
    heading titles the prose under it, so neither is a block."""
    text = HEADING_RE.sub("", FENCE_RE.sub("\n", text))
    found: list[str] = []
    for para in BLOCK_SPLIT_RE.split(text):
        for item in ITEM_SPLIT_RE.split(para):
            if item.strip():
                found.append(item)
    return found


def block_names(block: str) -> list[str]:
    """The names a block carries: its backticked identifiers and its
    `$Name` terms, in the order they appear, each once."""
    names: list[str] = []
    for found in TICKED_RE.findall(block):
        token = found.strip()
        if IDENT_RE.match(token) and token not in names:
            names.append(token)
    for found in DOLLAR_RE.findall(block):
        if found not in names:
            names.append(found)
    return names


def block_stratum(block: str) -> str:
    """The ground a block states, or `unnamed` when it states none."""
    for name, pattern in STRATA:
        if pattern.search(block):
            return name
    return UNNAMED


def report_blocks(task_id: str, reports: Path = REPORTS_DIR) -> list[Block]:
    """The blocks of a task's reports that bear on a dropped model: those
    that state a ground, and those that say a model was dropped.
    `finalize.md` is read first, then `retro.md`, which amends it."""
    found: list[Block] = []
    for name in ("finalize.md", "retro.md"):
        path = reports / task_id / name
        if not path.is_file():
            continue
        for block in blocks(path.read_text()):
            dropped = bool(DROP_RE.search(block))
            stratum = block_stratum(block)
            if stratum == UNNAMED and not dropped:
                continue
            found.append(Block(block_names(block), stratum, dropped))
    return found


def mine_reports(task_id: str, reports: Path = REPORTS_DIR
                 ) -> tuple[list[Mention], list[Row]]:
    """What a task's reports say about dropped models: the names they carry
    with each name's ground, and a row for every block that says a model was
    dropped and names none."""
    mentions: list[Mention] = []
    rows: list[Row] = []
    seen: set[str] = set()
    for block in report_blocks(task_id, reports):
        if not block.names:
            if block.dropped:
                rows.append(Row(task_id=task_id, source="report", path=None,
                                peer_name="", stratum=block.stratum))
            continue
        for name in block.names:
            if name not in seen:
                seen.add(name)
                mentions.append((name, block.stratum))
    return mentions, rows


# --- matching one side to the other ---


def norm_name(name: str) -> str:
    """A name reduced to its letters and digits, for comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lstrip("$").lower())


def match_names(peer_names: list[str], report_names: list[str]
                ) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """Which report name each peer name stands for, and the report names
    left over. A name matches exactly, else as a suffix of the other, else
    as a close string."""
    peers = {name: norm_name(name) for name in peer_names}
    reports = {name: norm_name(name) for name in report_names}
    pairs: dict[str, tuple[str, str]] = {}
    taken: set[str] = set()

    def claim(peer: str, report: str, how: str) -> None:
        pairs[peer] = (report, how)
        taken.add(report)

    for peer, key in peers.items():
        for report, other in reports.items():
            if report not in taken and key and key == other:
                claim(peer, report, "exact")
                break
    for peer, key in peers.items():
        if peer in pairs or not key:
            continue
        for report, other in reports.items():
            if report in taken or not other:
                continue
            if key.endswith(other) or other.endswith(key):
                claim(peer, report, "suffix")
                break
    for peer, key in peers.items():
        if peer in pairs or not key:
            continue
        pool = {reports[r]: r for r in reports if r not in taken}
        close = difflib.get_close_matches(key, list(pool), n=1, cutoff=0.6)
        if close:
            claim(peer, pool[close[0]], "close")
    return pairs, [name for name in report_names if name not in taken]


def match_identifiers(text: str, shipped: str, found: list[Block]
                      ) -> tuple[Block | None, list[str]]:
    """The report block a program's own identifiers place it in, and the
    identifiers the two share. The block sharing the most identifiers wins,
    and the first such block wins a tie."""
    own = own_names(text, shipped)
    if not own:
        return None, []
    best: Block | None = None
    shared: set[str] = set()
    for block in found:
        here = own.keys() & block.keys()
        if len(here) > len(shared):
            best, shared = block, here
    if best is None:
        return None, []
    return best, sorted(own[key] for key in shared)


def inventory(only: str | None = None, limit: int | None = None,
              root: Path = SCRATCH_DIR, reports: Path = REPORTS_DIR,
              solvers: Path = SOLVERS_DIR
              ) -> tuple[list[Row], list[str]]:
    """Every scratch program with the ground its report states, and the
    names neither side could place. A program its file name does not place
    is placed by the identifiers it declares and the shipped solver does
    not."""
    rows = scan_scratch(root, solvers)
    by_task: dict[str, list[Row]] = {}
    for row in rows:
        by_task.setdefault(row.task_id, []).append(row)
    task_ids = [t for t in sorted(by_task) if only is None or t == only]
    if limit is not None:
        task_ids = task_ids[:limit]

    out: list[Row] = []
    unmatched: list[str] = []
    for task_id in task_ids:
        task_rows = by_task[task_id]
        found = report_blocks(task_id, reports)
        mentions, report_rows = mine_reports(task_id, reports)
        strata = dict(mentions)
        pairs, left = match_names([r.peer_name for r in task_rows],
                                  [name for name, _ in mentions])
        shipped_path = solvers / f"{task_id}.dl"
        shipped = shipped_path.read_text() if shipped_path.is_file() else ""
        placed: set[str] = set()
        for row in task_rows:
            if row.peer_name in pairs:
                row.report_name, row.matched_by = pairs[row.peer_name]
                row.stratum = strata[row.report_name]
                continue
            if row.is_copy or row.path is None:
                continue
            block, shared = match_identifiers(
                row.path.read_text(errors="replace"), shipped, found)
            if block is None:
                unmatched.append(f"{task_id}\tpeer\t{row.peer_name}")
                continue
            keys = {norm_name(name) for name in shared}
            named = [n for n in block.names if norm_name(n) in keys]
            row.report_name = named[0] if named else ""
            row.stratum = block.stratum
            row.matched_by = "identifiers"
            row.shared_names = ", ".join(shared)
            placed.update(named)
        unmatched += [f"{task_id}\treport\t{name}"
                      for name in left if name not in placed]
        out += task_rows + report_rows
    return out, unmatched


# --- what the programs do on the pairs ---


def _pairs_of(task_id: str) -> list[tuple[str, int, object]]:
    """Every pair of a task, train then test, as (kind, index, example)."""
    task = load_task(task_id)
    return [(kind, idx, ex)
            for kind, examples in (("train", task.train), ("test", task.test))
            for idx, ex in enumerate(examples)]


def peer_key(pair: PairResult, keys: dict[str, Key]) -> Key:
    """A program's key on one pair: the grids it emits there, `UNDEF` when the
    run failed, `ABSENT` when it emitted nothing."""
    if pair.error or not pair.variants:
        return UNDEF if pair.error else ABSENT
    grids: set = set()
    for key in keys.values():
        grids |= set(key)
    return frozenset(grids) if grids else ABSENT


@dataclass
class Divergence:
    pairs_undefined: int = 0
    pairs_diverging: int = 0
    nearest_case: str = ""
    pairs_matching_case: int = 0


def divergence(peer_pairs: list[PairResult], shipped_pairs: list[PairResult],
               peer_res: bool, shipped_res: bool) -> Divergence:
    """How a program's keys stand against the shipped solver's cases: the
    pairs where it is undefined, the pairs where it matches no case, and
    the case it matches on the most pairs."""
    _, peer_keys = _pair_keys(peer_pairs, None, peer_res)
    cases = report_of(shipped_pairs, None, shipped_res).cases
    _, shipped_keys = _pair_keys(shipped_pairs, None, shipped_res)

    found = Divergence()
    matches = {case: 0 for case in cases}
    for idx, pair in enumerate(peer_pairs):
        key = peer_key(pair, peer_keys[idx])
        if key == UNDEF or (not isinstance(key, str) and UNDEF in key):
            found.pairs_undefined += 1
        here = shipped_keys[idx] if idx < len(shipped_keys) else {}
        hit = False
        for case in cases:
            if here.get(case, ABSENT) == key:
                matches[case] += 1
                hit = True
        if not hit:
            found.pairs_diverging += 1
    if matches:
        best = max(matches, key=lambda c: matches[c])
        found.nearest_case, found.pairs_matching_case = best, matches[best]
    return found


@dataclass
class _Job:
    """One program's pair runs: where its results land."""

    stem: str
    task_id: str
    results: list[PairResult] = field(default_factory=list)


def run_rows(rows: list[Row], progress=None) -> None:
    """Run every non-copy program on its task's pairs, run each task's
    shipped solver once, and fill the run and divergence columns. All of the
    runs share one pool."""
    targets = [r for r in rows
               if r.source == "scratch" and not r.is_copy and r.path]
    task_ids = sorted({r.task_id for r in targets})
    pairs_of = {t: _pairs_of(t) for t in task_ids}

    shipped = {t: _Job(t, t) for t in task_ids}
    jobs: dict[int, _Job] = {}
    work: list[tuple[_Job, tuple]] = []
    for job in shipped.values():
        for kind, idx, ex in pairs_of[job.task_id]:
            work.append((job, (job.stem, job.task_id, kind, idx, ex)))
    for row in targets:
        job = _Job(str(row.path), row.task_id)
        jobs[id(row)] = job
        for kind, idx, ex in pairs_of[row.task_id]:
            work.append((job, (job.stem, job.task_id, kind, idx, ex)))

    slots: list[PairResult | None] = [None] * len(work)

    def one(i: int) -> None:
        slots[i] = run_pair(*work[i][1])

    with ThreadPoolExecutor(max_workers=_pool_workers()) as pool:
        list(pool.map(one, range(len(work))))
    for (job, _), result in zip(work, slots, strict=True):
        job.results.append(result)

    for task_id in task_ids:
        if progress:
            progress(task_id)
        shipped_job = shipped[task_id]
        shipped_res = res_out_stem(shipped_job.stem)
        for row in targets:
            if row.task_id != task_id:
                continue
            job = jobs[id(row)]
            row.pairs_total = len(job.results)
            row.pairs_passed = sum(1 for p in job.results if p.ok)
            row.runs = any(not p.error and p.variants for p in job.results)
            found = divergence(job.results, shipped_job.results,
                               res_out_stem(job.stem), shipped_res)
            row.pairs_undefined = found.pairs_undefined
            row.pairs_diverging = found.pairs_diverging
            row.nearest_case = found.nearest_case
            row.pairs_matching_case = found.pairs_matching_case


# --- the files ---


def write_outputs(rows: list[Row], unmatched: list[str],
                  out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    """Write the inventory and the unmatched names, and give both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = out_dir / "inventory.tsv"
    lines = ["\t".join(TSV_COLUMNS)]
    lines += ["\t".join(row.cells()) for row in rows]
    inventory_path.write_text("\n".join(lines) + "\n")
    unmatched_path = out_dir / "inventory-unmatched.txt"
    unmatched_path.write_text("\n".join(unmatched) + ("\n" if unmatched else ""))
    return inventory_path, unmatched_path


def stratum_counts(rows: list[Row]) -> dict[str, int]:
    """How many rows each ground holds. A row with no ground counts under
    an empty name."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.stratum] = counts.get(row.stratum, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def stratum_diverging(rows: list[Row]) -> dict[str, dict[str, int]]:
    """Per ground, how many run rows diverge from every shipped case on some
    pair and how many diverge on none."""
    table: dict[str, dict[str, int]] = {}
    for row in rows:
        if row.pairs_diverging is None:
            continue
        cell = table.setdefault(row.stratum, {"diverging": 0, "matching": 0})
        cell["diverging" if row.pairs_diverging else "matching"] += 1
    return dict(sorted(table.items()))
