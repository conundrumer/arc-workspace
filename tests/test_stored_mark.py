"""A `@store` relation that Souffle keys by columns outside its value gets a
`(STORED ...)` mark on its `RULE_OR_DET` line, and the lint takes the mark as a mark."""
from pathlib import Path

from arclog_convert.forms import fold_or_lines
from arclog_convert.lint import Linter
from arclog_convert.stored_columns import key_labels, keyed_value_columns, stored_mark

LINE = '(RULE_OR_DET &diagonal.ray "Each diagonal." (STORED (:key D) D))\n'


def test_a_relation_keyed_by_columns_outside_its_value_has_those_value_columns(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ARCLOG_OUT", str(tmp_path))
    assert keyed_value_columns("a5f85a15") == {"diagonal.ray": ((0, 2), 5)}
    assert (tmp_path / "stored_columns" / "a5f85a15.json").exists()
    assert keyed_value_columns("a5f85a15") == {"diagonal.ray": ((0, 2), 5)}


def test_the_mark_names_a_bare_column_and_each_field_of_the_key_record():
    names = ["key", "P", "D", "K", "Origin"]
    assert stored_mark((0, 2), names, ["D"]) == " (STORED (:key D) D)"
    assert stored_mark((0,), names, ["A", "B"]) == " (STORED (:key A) (:key B))"


def test_the_key_record_fields_are_the_caret_labels_of_the_key_body():
    assert key_labels(["(INIT &d Ray", "(key ((diag_opposite ^D (:Opp *O)) (m ^A)))"]) == ["A", "D"]


def test_the_lint_takes_the_mark_as_a_mark_and_the_fold_keeps_the_line(tmp_path: Path):
    path = tmp_path / "x.arclog"
    path.write_text(LINE)
    lint = Linter(path)
    lint.run()
    assert not [e for e in lint.errs if e[1] == "det-or-rule"]
    assert fold_or_lines(LINE) == LINE
