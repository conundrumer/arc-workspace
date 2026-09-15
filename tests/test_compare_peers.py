"""The inventory counts by stratum, the dropped cases inside the kept range,
and the verdict each outcome gives."""

import pandas as pd

from study.compare_peers import (
    CASE_COLUMNS,
    FEATURES,
    NONE_STRATUM,
    candidates,
    case_ctors,
    kept_range,
    overlap_flags,
    read_inventory,
    stratum_frame,
    summary_frame,
    verdict,
)

COLUMNS = [
    "task_id", "source", "path", "peer_name", "report_name", "stratum",
    "is_copy", "runs", "pairs_passed", "pairs_total", "pairs_illformed",
    "pairs_diverging", "nearest_case", "pairs_matching_case", "matched_by",
]

ROWS = [
    # a copy of the shipped solver: no stratum, no run
    ["aaaaaaaa", "scratch", ".scratch/aaaaaaaa/orig.dl", "orig", "", "",
     "yes", "", "", "", "", "", "", "", ""],
    # a peer that passes every pair
    ["aaaaaaaa", "scratch", ".scratch/aaaaaaaa/peer.dl", "peer", "peer",
     "subsumed", "no", "yes", "4", "4", "0", "0", "Paint", "4", "name"],
    # a peer that fails, ill-formed on two pairs
    ["bbbbbbbb", "scratch", ".scratch/bbbbbbbb/probe.dl", "probe", "",
     "subsumed", "no", "yes", "0", "5", "2", "5", "Rows", "0", ""],
    # a peer that runs and diverges without being ill-formed
    ["bbbbbbbb", "scratch", ".scratch/bbbbbbbb/alt.dl", "alt", "",
     "peer-priors", "no", "yes", "3", "4", "0", "1", "Rows", "3", "close"],
    # a peer with a file that never ran
    ["cccccccc", "scratch", ".scratch/cccccccc/wide.dl", "wide", "", "",
     "no", "", "", "", "", "", "", "", ""],
    # a report mention with no file
    ["cccccccc", "report", "unnamed", "", "", "unnamed",
     "no", "", "", "", "", "", "", "", ""],
]


def write_inventory(path):
    lines = ["\t".join(COLUMNS)] + ["\t".join(row) for row in ROWS]
    path.write_text("\n".join(lines) + "\n")
    return path


def case_row(role, stratum, values, task_id="aaaaaaaa", case="Paint"):
    """One per-case row, its features given in `FEATURES` order."""
    row = {"task_id": task_id, "path": f".scratch/{task_id}/peer.dl",
           "case": case, "role": role, "stratum": stratum}
    row.update(dict(zip(FEATURES, values)))
    return row


KEPT_LOW = [10, 5, 40, 2, 8, 0, 0, 1, 1.0, 1.0, True]
KEPT_HIGH = [20, 5, 50, 4, 12, 2, 1, 3, 2.0, 1.25, False]
INSIDE = [15, 5, 45, 3, 10, 1, 0, 2, 1.5, 1.1, False]
OUTSIDE = [99, 5, 45, 3, 10, 1, 0, 2, 1.5, 1.1, False]


def frame(rows):
    return pd.DataFrame(rows, columns=CASE_COLUMNS)


def test_stratum_frame_counts_files_runs_and_divergence(tmp_path):
    rows = read_inventory(write_inventory(tmp_path / "inventory.tsv"))
    table = stratum_frame(rows).set_index("stratum")

    assert list(table.index) == [NONE_STRATUM, "peer-priors", "subsumed",
                                 "unnamed"]
    assert table.loc[NONE_STRATUM, "count"] == 2
    assert table.loc[NONE_STRATUM, "with_file"] == 2
    assert table.loc[NONE_STRATUM, "runs"] == 0
    assert table.loc["subsumed", "count"] == 2
    assert table.loc["subsumed", "passes_all"] == 1
    assert table.loc["subsumed", "illformed"] == 1
    assert table.loc["subsumed", "diverging"] == 1
    assert table.loc["peer-priors", "diverging"] == 1
    assert table.loc["unnamed", "with_file"] == 0


def test_case_ctors_reads_a_record_case():
    assert case_ctors("Paint") == {"Paint"}
    assert case_ctors("[Table, Or]") == {"Table", "Or"}


def test_overlap_marks_a_dropped_case_inside_the_kept_range():
    cases = frame([
        case_row("kept", "subsumed", KEPT_LOW, case="Paint"),
        case_row("kept", "subsumed", KEPT_HIGH, case="Skip"),
        case_row("dropped", "subsumed", INSIDE, case="Survive"),
        case_row("dropped", "subsumed", OUTSIDE, case="Ink"),
    ])

    assert kept_range(cases)["atoms"] == (10.0, 20.0)
    flags = overlap_flags(cases).set_index("case")
    assert bool(flags.loc["Survive", "inside_all"])
    assert not bool(flags.loc["Ink", "inside_all"])
    assert not bool(flags.loc["Ink", "atoms_inside"])

    summary = summary_frame(cases).set_index("feature")
    assert summary.loc["atoms", "kept_median"] == 15.0
    assert summary.loc["atoms", "overlap"] == 1
    assert summary.loc["reach_atoms", "overlap"] == 2


def five_dropped(stratum, values):
    return [case_row("dropped", stratum, values, case=f"D{i}")
            for i in range(5)]


def test_verdict_is_undecidable_below_five_dropped_cases_with_a_stratum():
    cases = frame([
        case_row("kept", "subsumed", KEPT_LOW, case="Paint"),
        case_row("kept", "subsumed", KEPT_HIGH, case="Skip"),
        case_row("dropped", "subsumed", INSIDE, case="Survive"),
        case_row("dropped", NONE_STRATUM, INSIDE, case="Ink"),
    ])

    assert verdict(cases) == ("calibration needed: undecidable "
                             "(1 in-file peers, 1 with a stratum)")


def test_verdict_is_yes_when_dropped_cases_sit_inside_on_a_model_stratum():
    cases = frame([case_row("kept", "subsumed", KEPT_LOW, case="Paint"),
                   case_row("kept", "subsumed", KEPT_HIGH, case="Skip")]
                  + five_dropped("subsumed", INSIDE))

    assert verdict(cases) == "calibration needed: yes (5)"
    assert len(candidates(cases)) == 5


def test_verdict_is_no_when_every_dropped_case_stands_outside():
    cases = frame([case_row("kept", "subsumed", KEPT_LOW, case="Paint"),
                   case_row("kept", "subsumed", KEPT_HIGH, case="Skip")]
                  + five_dropped("subsumed", OUTSIDE))

    assert verdict(cases) == "calibration needed: no"
    assert len(candidates(cases)) == 0
