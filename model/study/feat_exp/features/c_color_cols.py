"""C: the Color columns of X. C1 counts them; the paint features of r3f read no table with two or more."""
from featlib import feature


def _color_columns(p):
    return [c for c in p.x.columns() if c.type == 'Color']


@feature
def c1_color_cols(p):
    """C1: the number of X's columns of type Color (0 when none)."""
    return len(_color_columns(p))
