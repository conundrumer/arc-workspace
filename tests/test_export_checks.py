"""`export_checks.check_case` gives no line on a consistent case and reports each of four changes to it."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("export_checks", Path(__file__).parent.parent / "engine/arclog-py/export_checks.py")
assert spec and spec.loader
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)

TASK = {"train": [{"input": [[1, 2]], "output": [[3, 4]]}], "test": [{"input": [[5, 6]]}]}
ORIENTATION = {"Dir": {0, 1, 2, 3}, "Dir8": set(range(8))}


def evidence(fact, depth=0):
    return dict(token=0, point=2, fact=fact, column_types=["Example", "Box", "Color"], width=6, det_relations=[], det_types=[], det_widths=[],
                projections=0, fault=None, depth=depth, keys=[[0, 1]], output_position=-1, output_color=-1)


def case():
    """ex_input, ex_output, a table `R` of columns Example and Color that copy ex_input's, and a table `S` of one
    Dir column that copies the Dir8 column of its `DET` `D`, one Color column that copies `R`'s and `D`'s, and one Dir8 column
    that copies the Dir column of `D`, with their values."""
    tables = pd.DataFrame([evidence("ex_input"), evidence("ex_output"),
                           dict(token=5, point=0, fact="R", column_types=["Example", "Color"], width=2, det_relations=[], det_types=[], det_widths=[],
                                projections=0, fault=None, depth=1, keys=[[0, 1]], output_position=-1, output_color=-1),
                           dict(token=6, point=0, fact="S", column_types=["Dir", "Color", "Dir8"], width=3, det_relations=["D"], det_types=[["Dir8", "Color", "Dir"]],
                                det_widths=[3], projections=0, fault=None, depth=2, keys=[[0, 1]], output_position=-1, output_color=-1)])
    entries = pd.DataFrame(dict(table=[0, 0, 1, 2, 3], example_kind=[1, 2, 1, 1, 1], example_index=[0, 0, 0, 0, 0], kind=[0] * 5,
                                rows=[2, 2, 2, 2, 2], offset=[0, 12, 24, 36, 40]))
    assigned = pd.DataFrame(dict(entry=[4], det=[0], rows=[1], offset=[46]))
    flows = pd.DataFrame(dict(table=[2, 2, 3, 3, 3, 3], column=[0, 1, 0, 1, 1, 2], kind=[0] * 6, source_table=[0, 0, 2, 2, 2, 2],
                              source_relation=["ex_input", "ex_input", "D", "R", "D", "D"], source_column=[-2, 2, 0, 1, 1, 2],
                              det=[-1, -1, 0, -1, 0, 0]))
    values = np.array([0, 0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 2,
                       1, 0, 0, 0, 1, 5, 1, 0, 0, 1, 0, 6,
                       0, 0, 0, 0, 1, 3, 0, 0, 0, 1, 0, 4,
                       0, 1, 0, 2,
                       1, 2, 2, 1, 7, 2,
                       1, 7, 2], np.int32)
    return dict(tables=tables, entries=entries, assigned=assigned, flows=flows), values


def lines(frames, values):
    return checks.check_case(frames, values, TASK, ORIENTATION)


def test_consistent_case_gives_no_line():
    frames, values = case()
    assert lines(frames, values) == []


def test_copy_between_two_types_is_reported():
    frames, values = case()
    frames["flows"].loc[1, "source_column"] = 1
    assert any(l.startswith("flows-copy-type") for l in lines(frames, values))


def test_color_column_with_copy_flows_of_two_other_types_is_reported_and_stops_nothing():
    frames, values = case()
    flows = frames["flows"]
    flows.loc[len(flows)] = [3, 1, 0, 1, "R", 0, -1]       # S's Color column also copies an Example column of R
    flows.loc[len(flows)] = [3, 1, 0, 1, "R", 1, -1]       # and a Color column of D through no det, of another width
    found = lines(frames, values)
    assert any(l.startswith("flows-copy-type") for l in found)


def test_count_entry_with_an_offset_is_reported():
    frames, values = case()
    frames["tables"].loc[2, "projections"] = 1
    frames["entries"].loc[3, ["kind", "offset"]] = [1, 36]
    assert any(l.startswith("entries-offset") for l in lines(frames, values))


def test_evidence_cell_that_differs_from_the_task_is_reported():
    frames, values = case()
    values = values.copy()
    values[5] = 9
    assert any(l.startswith("values-evidence") for l in lines(frames, values))


def test_column_with_a_value_in_neither_of_its_sources_is_reported():
    frames, values = case()
    values = values.copy()
    values[43] = 8
    assert any(l.startswith("values-copy") for l in lines(frames, values))


def test_column_with_rows_where_its_source_holds_none_is_reported():
    frames, values = case()
    frames["entries"].loc[3, "rows"] = 0
    frames["entries"].loc[4:, "offset"] -= 4
    frames["assigned"].loc[:, "offset"] -= 4
    frames["flows"] = frames["flows"].drop(4).reset_index(drop=True)
    found = [l for l in lines(frames, np.delete(values, range(36, 40))) if l.startswith("values-copy")]
    assert len(found) == 1
