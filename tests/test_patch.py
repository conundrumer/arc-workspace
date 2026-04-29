import pytest

from arc.patch import (
    BranchSection,
    DeleteSection,
    DiffSection,
    PatchParseError,
    ReplaceSection,
    parse,
)


def test_empty():
    p = parse("")
    assert p.metadata == {}
    assert p.sections == []


def test_metadata_only():
    p = parse("comment: hello\nissue: https://example.com/foo\n")
    assert p.metadata == {"comment": "hello", "issue": "https://example.com/foo"}
    assert p.sections == []


def test_url_value_keeps_colon():
    # first-': ' split must not break on the colon in 'https:'
    p = parse("issue: https://github.com/foo/bar/issues/1\n")
    assert p.metadata["issue"] == "https://github.com/foo/bar/issues/1"


def test_diff_plain():
    text = """\
@diff train 0 input
0 0 0
0 1 0
0 0 0
"""
    s = parse(text).sections[0]
    assert isinstance(s, DiffSection)
    assert (s.set, s.idx, s.grid) == ("train", 0, "input")
    assert s.rows == [[0, 0, 0], [0, 1, 0], [0, 0, 0]]


def test_diff_with_change_cells():
    text = """\
@diff train 0 output
0 1 0
0 1~2 0~7
"""
    s = parse(text).sections[0]
    assert isinstance(s, DiffSection)
    assert s.rows == [[0, 1, 0], [0, (1, 2), (0, 7)]]


def test_replace():
    text = """\
@replace train 2 output
1 2 3
4 5 6
---
9 8 7
6 5 4
"""
    s = parse(text).sections[0]
    assert isinstance(s, ReplaceSection)
    assert s.old == [[1, 2, 3], [4, 5, 6]]
    assert s.new == [[9, 8, 7], [6, 5, 4]]


def test_replace_dim_change_allowed():
    text = """\
@replace train 0 output
1 2
3 4
---
9
"""
    s = parse(text).sections[0]
    assert isinstance(s, ReplaceSection)
    assert s.old == [[1, 2], [3, 4]]
    assert s.new == [[9]]


def test_replace_missing_separator():
    with pytest.raises(PatchParseError, match="separator"):
        parse("@replace train 2 output\n1 2 3\n4 5 6\n9 8 7\n")


def test_replace_rejects_change_cell():
    text = """\
@replace train 2 output
1 2~3 4
---
5 6 7
"""
    with pytest.raises(PatchParseError, match="not allowed"):
        parse(text)


def test_delete():
    text = """\
@delete train 5
0 0 0
0 0 0
---
1 1 1
1 1 1
"""
    s = parse(text).sections[0]
    assert isinstance(s, DeleteSection)
    assert (s.set, s.idx) == ("train", 5)
    assert s.input == [[0, 0, 0], [0, 0, 0]]
    assert s.output == [[1, 1, 1], [1, 1, 1]]


def test_delete_missing_separator():
    text = "@delete train 5\n0 0 0\n0 0 0\n1 1 1\n"
    with pytest.raises(PatchParseError, match="separator"):
        parse(text)


def test_delete_too_many_separators():
    text = "@delete train 5\n0 0\n---\n1 1\n---\n2 2\n"
    with pytest.raises(PatchParseError, match="separator"):
        parse(text)


def test_branch_rule():
    text = """\
@branch test 0 rule
0 1 0
0 1~2 0
"""
    s = parse(text).sections[0]
    assert isinstance(s, BranchSection)
    assert s.kind == "rule"
    assert s.rows == [[0, 1, 0], [0, (1, 2), 0]]


def test_branch_tiebreak():
    s = parse("@branch test 0 tiebreak\n0 1 0\n").sections[0]
    assert isinstance(s, BranchSection)
    assert s.kind == "tiebreak"


def test_branch_rejects_invalid_kind():
    with pytest.raises(PatchParseError, match="rule.*tiebreak|tiebreak.*rule"):
        parse("@branch test 0 multi\n0 1 0\n")


def test_multi_section():
    text = """\
comment: two unrelated edits

@diff train 0 output
0 1~2 0

@delete train 3
0 0
---
1 1
"""
    p = parse(text)
    assert p.metadata["comment"] == "two unrelated edits"
    assert len(p.sections) == 2
    assert isinstance(p.sections[0], DiffSection)
    assert isinstance(p.sections[1], DeleteSection)


def test_separator_outside_delete_fails():
    text = "@diff train 0 input\n0 0\n---\n0 0\n"
    with pytest.raises(PatchParseError, match="---.*delete"):
        parse(text)


def test_unknown_verb():
    with pytest.raises(PatchParseError, match="unknown verb"):
        parse("@frobnicate train 0 input\n0\n")


def test_bad_set():
    with pytest.raises(PatchParseError, match="train.*test|test.*train"):
        parse("@diff middle 0 input\n0\n")


def test_bad_grid():
    with pytest.raises(PatchParseError, match="input.*output|output.*input"):
        parse("@diff train 0 sideways\n0\n")


def test_negative_index():
    with pytest.raises(PatchParseError, match="non-negative"):
        parse("@diff train -1 input\n0\n")


def test_arg_count_mismatch():
    with pytest.raises(PatchParseError, match="expects 3 args"):
        parse("@diff train 0\n0\n")


def test_invalid_cell_token():
    with pytest.raises(PatchParseError, match="invalid cell"):
        parse("@diff train 0 input\n0 abc 0\n")


def test_blank_lines_decorate():
    text = """\
comment: c


@diff train 0 input

0 0 0

0 1 0


@diff train 1 input
0 0
"""
    p = parse(text)
    assert len(p.sections) == 2
    s0, s1 = p.sections
    assert isinstance(s0, DiffSection)
    assert isinstance(s1, DiffSection)
    assert s0.rows == [[0, 0, 0], [0, 1, 0]]
    assert s1.rows == [[0, 0]]
