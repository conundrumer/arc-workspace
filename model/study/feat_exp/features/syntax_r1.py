"""Round 1 syntax features (ledger E1): the candidate's form and the library interfaces only."""
from featlib import feature, frame_zero


def _zero_box_sites(body, frame):
    """The sites of the body whose term is the literal 0 as a zero box in a relation, macro or fact: those that are
    the grid frame (`frame` true) or the others."""
    return sum(1 for a in body.arguments if a.is_zero and a.atom.operator is None
               and a.atom.kind in ('relation', 'macro', 'fact') and a.literal == 'zero box'
               and frame_zero(a) == frame)


@feature
def e1_zero_box_sites(p):
    """E1: number of sites in the form whose term is the literal 0 and whose library column (a relation, macro or fact of libraries.json) is a Box, Position or Offset: the literal is the zero box. A site where the zero box is the grid frame (`featlib.FRAME_ZERO_SITES`) is not counted; `e1_zero_frame_sites` counts it."""
    body = p.clause.body
    if body is None:
        return 0
    return _zero_box_sites(body, False)


@feature
def e1_zero_frame_sites(p):
    """E1: number of sites in the form where the literal 0 is the grid frame, as the zero box (`featlib.FRAME_ZERO_SITES`: the box of `inside` and `interior`, the second cell of `same_corner` and `same_dist`, the box `split` takes along an axis)."""
    body = p.clause.body
    if body is None:
        return 0
    return _zero_box_sites(body, True)
