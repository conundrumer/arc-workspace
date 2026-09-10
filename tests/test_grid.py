"""GRID and GRID_STAMP calls: which cell tokens each name takes, and the
facts a call expands to."""

import pytest

from dl.source import expand_grid_macros


def test_sparse_emits_a_zero_cell_as_a_value():
    out = expand_grid_macros("GRID_SPARSE_2x2(ink,\n    0, _,\n    _, 3)\n")
    assert out == "ink([0, 1, 0, 1], 0).\nink([1, 0, 1, 0], 3).\n"


def test_a_mask_cell_that_is_not_a_member_or_absent_raises():
    with pytest.raises(ValueError, match=r"GRID_MASK_1x2\(m\): cell '4'"):
        expand_grid_macros("GRID_MASK_1x2(m, 4, _)\n")


def test_a_color_cell_under_a_mask_name_raises():
    with pytest.raises(ValueError, match="not '1' or '_'"):
        expand_grid_macros("GRID_MASK_1x2(m, 1, 3)\n")


def test_a_sparse_cell_that_is_no_digit_raises():
    with pytest.raises(ValueError, match="not a color digit or '_'"):
        expand_grid_macros("GRID_SPARSE_1x2(s, 3, x)\n")


STAMP = """\
GRID_STAMP_3x3(footprint,
    1,  1, 1,
    1, @1, 1,
    1,  1, 1)
"""


def test_a_stamp_emits_each_member_cell_as_its_offset_from_the_anchor():
    out = expand_grid_macros(STAMP)
    assert out.count(").") == 9
    assert out.splitlines() == [
        "footprint([-1, 1, -1, 1]). footprint([-1, 1, 0, 0]). "
        "footprint([-1, 1, 1, -1]).",
        "footprint([0, 0, -1, 1]). footprint([0, 0, 0, 0]). "
        "footprint([0, 0, 1, -1]).",
        "footprint([1, -1, -1, 1]). footprint([1, -1, 0, 0]). "
        "footprint([1, -1, 1, -1]).",
    ]


def test_a_blank_anchor_emits_no_zero_offset():
    out = expand_grid_macros(STAMP.replace("@1", "@_"))
    assert out.count(").") == 8
    assert "footprint([0, 0, 0, 0])." not in out


def test_a_sparse_stamp_carries_the_cell_color():
    out = expand_grid_macros("GRID_STAMP_SPARSE_1x2(ink, @3, 5)\n")
    assert out == "ink([0, 0, 0, 0], 3). ink([0, 0, 1, -1], 5).\n"


def test_a_stamp_with_no_anchor_raises():
    with pytest.raises(ValueError, match=r"GRID_STAMP_1x2\(s\): 0 '@'"):
        expand_grid_macros("GRID_STAMP_1x2(s, 1, 1)\n")


def test_a_stamp_with_two_anchors_raises():
    with pytest.raises(ValueError, match="2 '@'"):
        expand_grid_macros("GRID_STAMP_1x2(s, @1, @1)\n")


def test_a_keyed_stamp_passes_its_key_through_and_the_error_names_it():
    assert expand_grid_macros("GRID_STAMP_1x2(s, 7, @1, 1)\n") == (
        "s(7, [0, 0, 0, 0]). s(7, [0, 0, 1, -1]).\n"
    )
    with pytest.raises(ValueError, match=r"GRID_STAMP_1x2\(s, 7\)"):
        expand_grid_macros("GRID_STAMP_1x2(s, 7, 1, 1)\n")


def test_a_call_inside_a_comment_stays_a_comment():
    """Expanding one would put the rows after the first outside the comment,
    and a call named in prose carries no cells to expand."""
    whole = "// GRID_MASK_2x2(shape, 1, _, _, 1)\n.decl shape(p: Position)\n"
    prose = "// a GRID_STAMP_3x3(footprint, ...) call\n"

    assert expand_grid_macros(whole) == whole
    assert expand_grid_macros(prose) == prose
