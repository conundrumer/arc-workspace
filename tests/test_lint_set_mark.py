"""The arclog lint refuses a `(SET)` mark where its conditions fail."""
from pathlib import Path

from arclog_convert.lint import Linter, arcdata_errs


def codes(tmp_path: Path, arclog: str, arcdata: str | None = None) -> set[str]:
    path = tmp_path / "x.arclog"
    path.write_text(arclog)
    lint = Linter(path)
    lint.run()
    found = {code for _, code, _ in lint.errs}
    if arcdata is not None:
        data = tmp_path / "x.arcdata"
        data.write_text(arcdata)
        found |= {code for _, code, _ in arcdata_errs(data, lint)}
    return found


def test_a_set_mark_after_a_one_column_proposer_with_several_rows_passes(tmp_path):
    assert "set" not in codes(tmp_path, "(DET &c UnchangedColor (SET))\n", "(param &c Color (1) (2))\n")


def test_a_set_mark_after_a_type_domain_proposer_is_refused(tmp_path):
    assert "set" in codes(tmp_path, "(DET &c ColorDomain (SET))\n")


def test_a_set_mark_after_a_two_column_proposer_is_refused(tmp_path):
    assert "set" in codes(tmp_path, "(DET &p ChangedPairs (SET))\n")


def test_a_set_mark_on_a_param_of_one_row_is_refused(tmp_path):
    assert "set" in codes(tmp_path, "(DET &c UnchangedColor (SET))\n", "(param &c Color (1))\n")


def test_a_set_mark_on_a_det_or_rule_line_follows_the_same_rules(tmp_path):
    assert "set" not in codes(tmp_path, "(DET_OR_RULE &c UnchangedColor (SET))\n")
    assert "set" in codes(tmp_path, "(DET_OR_RULE &c ColorDomain (SET))\n")
