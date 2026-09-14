# Orientation: a model whose rules differ by axis

Open question in `principles.md`, Invariance — Orientation, read with Invariance scope.

## The question

The rule does not say whether a model that applies different rules to two axes violates it. Invariance scope holds that invariance does not extend to how the rules combine their inputs, and an orientation choice is a value a parameter carries.

## The text

> A task may single out a direction, axis, or transformation. Without that, no choice is singled out.
>
> - Position's four edge distances remove the corner origin.
> - Dir, Axis, DiagDir, and D4 make each orientation choice a value, so a mirrored sibling needs a parameter edit, not a program restructure.

## Candidate texts

1. **Orientation.** A third Orientation bullet:

    > - A model whose rules differ by axis singles out no orientation when a parameter names the axis they key on. Coverage judges such a model.

    A per-axis model stands or falls at Coverage, and a peer whose rules differ by axis can earn a case under Different parse.

2. **Evidence.** An Evidence bullet:

    > - **Refuted elsewhere.** A peer that gives an unwitnessed member of a class the rule the pairs refute on a witnessed member gets no case.

    9841fdad ships as written, and any such peer is removed whether or not the pairs bear on that member.

## Solvers

- 9841fdad (draft) — its refine pass refused the per-row-runs peer a case under Orientation, on a ground it called a stretch.

## Witness

The 7×21 two-panel grid: the per-row-runs peer copies each row's run on its own and keeps the L, while both shipped cases square the L off to its bounding box. The pairs refute per-cell anchoring on the split axis, and the peer applies it on the axis across the split, which the two panels share.
