"""A RIGID block with a `Sense` column, placed at a rotation and at a
reflection. A rotation keeps the sense, and a reflection reverses it."""

import pytest

from engine import checkout
from engine.engine import Limits, ParseFailure, Tuples
from engine.program import RelationName
from souffle.engine import SouffleEngine

SENSE_CW, SENSE_CC = 60, 61
D4_CW, D4_LR, D4_AD = 51, 54, 57

PROGRAM = """
#include "lib.dl"
RIGID(blk,
    .decl spin(s: Sense, k: number)
    spin(SENSE_CW, 1).
    spin(SENSE_CC, 2).
)
.decl read_at(d: D4, s: Sense, k: number)
read_at(D, S, K) :- blk_spin(D, S, K).
"""


@pytest.fixture(scope="module")
def placed() -> list[tuple[int, int, int]]:
    engine = SouffleEngine(cache_dir=None)
    program = engine.parse(PROGRAM, checkout.programs())
    assert not isinstance(program, ParseFailure), program
    out = RelationName((), "read_at")
    result = engine.run(engine.expand(program), {}, [out], Limits(60, 120))
    assert isinstance(result, Tuples), result
    rows = [tuple(row) for row in result.relations[out]]
    assert all(isinstance(v, int) for row in rows for v in row)
    return [(int(row[0]), int(row[1]), int(row[2])) for row in rows]  # pyright: ignore[reportArgumentType]


def test_rotation_keeps_the_sense(placed):
    assert {(s, k) for d, s, k in placed if d == D4_CW} == {(SENSE_CW, 1), (SENSE_CC, 2)}


@pytest.mark.parametrize("pose", [D4_LR, D4_AD])
def test_reflection_reverses_the_sense(placed, pose):
    assert {(s, k) for d, s, k in placed if d == pose} == {(SENSE_CC, 1), (SENSE_CW, 2)}


def test_each_stored_value_has_one_image_per_pose(placed):
    poses_and_values = [(d, k) for d, _, k in placed]
    assert len(poses_and_values) == len(set(poses_and_values)) == 8 * 2
