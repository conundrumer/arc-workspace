"""`export_checks.check_case` gives no line on a consistent case and reports each of three changes to it."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("export_checks", Path(__file__).parent.parent / "engine/arclog-py/export_checks.py")
assert spec and spec.loader
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)

TASK = {"train": [{"input": [[1, 2]], "output": [[3, 4]]}], "test": [{"input": [[5, 6]]}]}
ORIENTATION = {"Dir": {0, 1, 2, 3}}


def evidence(fact, depth=0):
    return dict(token=0, point=2, fact=fact, column_types=["Example", "Box", "Color"], width=6, det_relations=[], det_widths=[],
                projections=0, fault=None, depth=depth, keys=[[0, 1]], output_position=-1, output_color=-1)


def case():
    """ex_input, ex_output and a table `R` of columns Example and Color that copy ex_input's, with their values."""
    tables = pd.DataFrame([evidence("ex_input"), evidence("ex_output"),
                           dict(token=5, point=0, fact="R", column_types=["Example", "Color"], width=2, det_relations=[], det_widths=[],
                                projections=0, fault=None, depth=1, keys=[[0, 1]], output_position=-1, output_color=-1)])
    entries = pd.DataFrame(dict(table=[0, 0, 1, 2], example_kind=[1, 2, 1, 1], example_index=[0, 0, 0, 0], kind=[0, 0, 0, 0],
                                rows=[2, 2, 2, 2], offset=[0, 12, 24, 36]))
    flows = pd.DataFrame(dict(table=[2, 2], column=[0, 1], kind=[0, 0], source_table=[0, 0], source_relation=["ex_input"] * 2,
                              source_column=[-2, 2], det=[-1, -1]))
    values = np.array([0, 0, 0, 0, 1, 1, 0, 0, 0, 1, 0, 2,
                       1, 0, 0, 0, 1, 5, 1, 0, 0, 1, 0, 6,
                       0, 0, 0, 0, 1, 3, 0, 0, 0, 1, 0, 4,
                       0, 1, 0, 2], np.int32)
    return dict(tables=tables, entries=entries, flows=flows), values


def lines(frames, values):
    return checks.check_case(frames, values, TASK, ORIENTATION)


def test_consistent_case_gives_no_line():
    frames, values = case()
    assert lines(frames, values) == []


def test_copy_between_two_types_is_reported():
    frames, values = case()
    frames["flows"].loc[1, "source_column"] = 1
    assert any(l.startswith("flows-copy-type") for l in lines(frames, values))


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
