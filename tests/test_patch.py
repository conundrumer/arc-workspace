
from arc.patch import (
    DeleteSection,
    DiffSection,
    ReplaceSection,
    parse,
)


def test_url_value_keeps_colon():
    # first-': ' split must not break on the colon in 'https:'
    p = parse("issue: https://github.com/foo/bar/issues/1\n")
    assert p.metadata["issue"] == "https://github.com/foo/bar/issues/1"


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
