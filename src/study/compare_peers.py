"""Whether the dropped peers look like the shipped cases they stand beside.

A past session sometimes wrote one file that holds the shipped solver's
cases and one more case beside them. That extra case was dropped, and the
session's report says on what ground. Both sides sit in one file, so the
per-case features of the kept cases and of the dropped case are measured
under the same program.

The report this module writes holds three sections: the inventory counted
by drop ground, the per-case features of the files that hold a dropped case
beside the kept ones, and a verdict on whether a dropped case sits inside
the range the kept cases span on every feature. A dropped case inside that
range on every feature, dropped on a ground that speaks of the model rather
than of the fit, is a calibration candidate.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from dl.dlparse import ParseError, parse
from dl.features import _components, features_report
from dl.features_run import case_members
from dl.paths import REPO_ROOT, SOLVERS_DIR

OUT_DIR = REPO_ROOT / ".scratch" / "peers"
INVENTORY = OUT_DIR / "inventory.tsv"
REPORT = OUT_DIR / "compare.md"

NONE_STRATUM = "(none)"
"""How an empty stratum is written in the report."""

MODEL_STRATA = {"subsumed", "peer-priors", "exercised"}
"""Drop grounds that speak of the model, not of the fit to the pairs."""

MIN_STRATUM_CASES = 5
"""Dropped cases with a stratum below which the verdict is undecidable."""

FEATURES = [
    "atoms", "shared_atoms", "reach_atoms", "facts", "reach_facts",
    "negations", "disjunctions", "lib_instances", "atoms_ratio_min",
    "reach_atoms_ratio_min", "is_smallest_reach_atoms",
]
"""The per-case columns the comparison tabulates."""

CASE_COLUMNS = ["task_id", "path", "case", "role", "stratum", *FEATURES]

type Row = dict[str, str]
"""One row of the inventory, by column name."""


@dataclass
class Peer:
    """One peer file that holds a case the shipped solver lacks."""
    task_id: str
    path: Path
    stratum: str
    kept: set[str]
    dropped: set[str]


@dataclass
class Skipped:
    """One peer file left out, with why it was."""
    path: str
    reason: str


# --- the inventory ---

def read_inventory(path: Path = INVENTORY) -> list[Row]:
    """Every row of the inventory TSV. Columns the report does not know are
    carried along and ignored."""
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _number(row: Row, column: str) -> int:
    value = row.get(column, "").strip()
    return int(value) if value.isdigit() else 0


def _passes_all(row: Row) -> bool:
    total = _number(row, "pairs_total")
    return total > 0 and _number(row, "pairs_passed") == total


def stratum_frame(rows: list[Row]) -> pd.DataFrame:
    """The inventory counted by stratum, one row per stratum."""
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        name = row.get("stratum", "").strip() or NONE_STRATUM
        cell = counts.setdefault(name, {
            "count": 0, "with_file": 0, "runs": 0,
            "passes_all": 0, "undefined": 0, "diverging": 0,
        })
        cell["count"] += 1
        cell["with_file"] += row.get("source", "") == "scratch"
        cell["runs"] += row.get("runs", "") == "yes"
        cell["passes_all"] += _passes_all(row)
        cell["undefined"] += _number(row, "pairs_undefined") > 0
        cell["diverging"] += _number(row, "pairs_diverging") > 0
    frame = pd.DataFrame(
        [{"stratum": name, **cell} for name, cell in counts.items()])
    return frame.sort_values("stratum", ignore_index=True)


def copy_count(rows: list[Row]) -> int:
    """How many rows hold a copy of the shipped solver rather than a peer."""
    return sum(row.get("is_copy", "") == "yes" for row in rows)


# --- the files that hold a dropped case ---

def choice_ctors(path: Path) -> set[str]:
    """Every constructor the file's `Choice` ranges over. A record `Choice`
    gives the constructors of each of its field types."""
    program = parse(path.read_text())
    return {name for component in _components(program) for name in component}


def case_ctors(case: str) -> set[str]:
    """The constructors one case name stands for. A case named as a record
    (`[Table, Or]`) stands for each of its members."""
    return set(case_members(case))


def in_file_peers(rows: list[Row]) -> tuple[list[Peer], list[Skipped]]:
    """The peer files that hold both a shipped case and a case the shipped
    solver lacks, and the files left out with why."""
    peers: list[Peer] = []
    skipped: list[Skipped] = []
    for row in rows:
        if row.get("source") != "scratch" or row.get("is_copy") == "yes":
            continue
        path = REPO_ROOT / row["path"]
        shipped = SOLVERS_DIR / f"{row['task_id']}.dl"
        if not path.exists() or not shipped.exists():
            continue
        try:
            held = choice_ctors(shipped)
            mine = choice_ctors(path)
        except (OSError, ParseError) as error:
            skipped.append(Skipped(row["path"], str(error)))
            continue
        kept, dropped = mine & held, mine - held
        if kept and dropped:
            peers.append(Peer(row["task_id"], path,
                              row.get("stratum", "").strip(), kept, dropped))
    return peers, skipped


def case_frame(peers: list[Peer]) -> tuple[pd.DataFrame, list[Skipped]]:
    """One row per case of every in-file peer, each case marked `kept` when
    the shipped solver holds its constructors and `dropped` otherwise."""
    records: list[dict] = []
    skipped: list[Skipped] = []
    for peer in peers:
        try:
            report = features_report(str(peer.path))
        except (OSError, ParseError) as error:
            skipped.append(Skipped(str(peer.path), str(error)))
            continue
        for case in report.cases:
            ctors = case_ctors(case.case)
            role = "kept" if ctors <= peer.kept else "dropped"
            records.append({
                "task_id": peer.task_id,
                "path": str(peer.path.relative_to(REPO_ROOT)),
                "case": case.case,
                "role": role,
                "stratum": peer.stratum or NONE_STRATUM,
                **{name: getattr(case, name) for name in FEATURES},
            })
    return pd.DataFrame(records, columns=CASE_COLUMNS), skipped


# --- the comparison ---

def kept_range(cases: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """The span the kept cases of every file cover on each feature."""
    kept = cases[cases["role"] == "kept"]
    spans: dict[str, tuple[float, float]] = {}
    for name in FEATURES:
        values = pd.to_numeric(kept[name], errors="coerce").dropna()
        if len(values):
            spans[name] = (float(values.min()), float(values.max()))
    return spans


def _inside(value, span: tuple[float, float]) -> bool:
    """Whether one value sits inside a span. A case with no value on a
    feature is not told apart by it, and counts as inside."""
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return True
    return span[0] <= float(number) <= span[1]


def overlap_flags(cases: pd.DataFrame) -> pd.DataFrame:
    """The dropped cases, each with one column per feature saying whether it
    sits inside the kept range there, and `inside_all` for every feature."""
    spans = kept_range(cases)
    dropped = cases[cases["role"] == "dropped"].copy()
    for name in FEATURES:
        span = spans.get(name)
        dropped[name + "_inside"] = [
            _inside(value, span) if span else False
            for value in dropped[name]
        ]
    columns = [name + "_inside" for name in FEATURES]
    dropped["inside_all"] = (dropped[columns].all(axis=1) if columns
                             else False)
    return dropped


def summary_frame(cases: pd.DataFrame) -> pd.DataFrame:
    """Per feature: the median over the kept cases, the median over the
    dropped cases, the kept range, and how many dropped cases sit inside
    that range."""
    spans = kept_range(cases)
    flags = overlap_flags(cases)
    kept = cases[cases["role"] == "kept"]
    dropped = cases[cases["role"] == "dropped"]
    records = []
    for name in FEATURES:
        span = spans.get(name)
        records.append({
            "feature": name,
            "kept_median": pd.to_numeric(kept[name], errors="coerce").median(),
            "dropped_median": pd.to_numeric(
                dropped[name], errors="coerce").median(),
            "kept_min": span[0] if span else None,
            "kept_max": span[1] if span else None,
            "overlap": int(flags[name + "_inside"].sum()) if len(flags) else 0,
        })
    return pd.DataFrame(records)


def candidates(cases: pd.DataFrame) -> pd.DataFrame:
    """The dropped cases inside the kept range on every feature that carry a
    drop ground speaking of the model."""
    flags = overlap_flags(cases)
    if not len(flags):
        return flags
    picked = flags[flags["inside_all"] & flags["stratum"].isin(MODEL_STRATA)]
    return picked[["task_id", "path", "case", "stratum"]]


def verdict(cases: pd.DataFrame) -> str:
    """The verdict line: whether the comparison asks for calibration."""
    dropped = cases[cases["role"] == "dropped"]
    with_stratum = dropped[dropped["stratum"] != NONE_STRATUM]
    if len(with_stratum) < MIN_STRATUM_CASES:
        files = cases["path"].nunique()
        return (f"calibration needed: undecidable ({files} in-file peers, "
                f"{len(with_stratum)} with a stratum)")
    found = len(candidates(cases))
    return (f"calibration needed: yes ({found})" if found
            else "calibration needed: no")


# --- the report ---

def _table(frame: pd.DataFrame) -> str:
    if not len(frame):
        return "(no rows)\n"
    return frame.to_markdown(index=False, floatfmt=".2f") + "\n"


def render(rows: list[Row], peers: list[Peer], cases: pd.DataFrame,
           skipped: list[Skipped]) -> str:
    """The whole report as Markdown."""
    parts = [
        "# Dropped peers against the cases they stand beside\n",
        "## A. The inventory by stratum\n",
        _table(stratum_frame(rows)),
        f"\nRows: {len(rows)}, of which {copy_count(rows)} hold a copy of the "
        "shipped solver rather than a peer; a copy runs no pairs, so it "
        "counts under `count` alone.\n",
        "\nA peer that passes every train pair cannot diverge from a passing "
        "shipped case on a train pair, so divergence under `diverging` comes "
        "from the test pairs and from the peers that fail.\n",
        "\n## B. The cases inside one file\n",
        f"\nFiles considered: {len(peers)}.\n",
    ]
    parts.append("\n")
    for peer in peers:
        parts.append(f"- `{peer.path.relative_to(REPO_ROOT)}` "
                     f"({peer.task_id}, stratum {peer.stratum or NONE_STRATUM})"
                     f": drops {', '.join(sorted(peer.dropped))}\n")
    if skipped:
        parts.append("\nFiles left out:\n\n")
        for item in skipped:
            parts.append(f"- `{item.path}`: {item.reason}\n")
    parts.extend([
        "\n### Per case\n",
        _table(cases),
        "\n### Per feature\n",
        _table(summary_frame(cases)),
    ])
    inside_all = overlap_flags(cases)
    total = int(inside_all["inside_all"].sum()) if len(inside_all) else 0
    parts.append(f"\nDropped cases inside the kept range on every feature: "
                 f"{total}.\n")
    parts.extend([
        "\n## C. The verdict\n",
        "\n### Calibration candidates\n",
        _table(candidates(cases)),
        f"\n{verdict(cases)}\n",
    ])
    return "".join(parts)


def build(inventory: Path = INVENTORY,
          out: Path = REPORT) -> tuple[Path, pd.DataFrame]:
    """Read the inventory, compare the in-file peers, write the report, and
    give back where it went with the per-case frame behind it."""
    rows = read_inventory(inventory)
    peers, skipped = in_file_peers(rows)
    cases, more = case_frame(peers)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rows, peers, cases, skipped + more))
    return out, cases
