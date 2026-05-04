"""Solver for ARC task be03b35f — three rotated quadrant-witnesses collapse to one.

Rule (Souffle form):
    out(apply(D, P), col) :- template(Diag, D),
                             corner_view(Diag, c.h, c.w)(in)(P, col).

Each entry in `template` pairs a data quadrant's `DiagDir` with the d4
that takes that quadrant's cells to canonical (output) orientation. The
marker quadrant (BR here) is simply absent from the template. Set-dedup
collapses the three rotated witnesses into one canonical answer.

== Notes ==

- Sibling of 2dee498d (symmetric N-fold collapse): there all template
  D4s are IDENTITY and the dedup is pure modulo. Here the template
  carries non-identity rotations; the canonicalize step is a per-cell
  apply(D, P) before the dedup. Same shape, different per-tile D4s.
  Conceptually `tile_d4` run backwards (`untile_d4(template, tiled) →
  inner`); no primitive lifted yet.

- Three witnesses validate each other: if any quadrant disagreed under
  its declared D4, the union would carry overlap or missing cells, and
  set-dedup would not produce a clean (h, w) grid. Cheap consistency
  check that the BL+ROT_CW one-shot version doesn't get.

- Cross-separator at row 2, col 2 is handled implicitly: corner_view
  filters cells by anchor distance < (h, w), and separator cells sit at
  distance ≥ 2 from every corner. No separator concept needed in the
  body.

- Marker quadrant is encoded as absence from `template`. A richer marker
  scheme (multiple markers, marker color matters) would need explicit
  modeling — defer until a task forces it.

- Per-cell d4 transform lives inline as `apply(d4, p)`; a `transform(
  cells, d) -> Cells` primitive could lift it on a second occurrence.
  Object Principle 1; defer.

- `template` declares the per-quadrant D4 that maps quadrant → canonical.
  No notion of "inverse" — choose the forward direction at declaration
  time. (Inverses exist relationally but aren't primitive vocabulary.)

- D4 entries here: TL → ROT_CCW (the quadrant is canonical rotated 90°
  CW; rotating 90° CCW returns it). TR → ROT_180 (self-inverse). BL →
  ROT_CW.
"""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    h: int
    w: int
    template: set[tuple[DiagDir, D4]]


CONSTS = Consts(
    h=2,
    w=2,
    template={
        (DiagDir.TL, D4.ROT_CCW),
        (DiagDir.TR, D4.ROT_180),
        (DiagDir.BL, D4.ROT_CW),
    },
)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(apply(D, P), col) :- template(Diag, D), corner_view(Diag, c.h, c.w)(in)(P, col).
    return {
        (apply(d4, p), col)
        for (diag, d4) in c.template
        for (p, col) in corner_view(grid, diag, c.h, c.w)
    }
