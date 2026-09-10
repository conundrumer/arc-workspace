# `apply_between` — a D4 transform read in one frame and seated in another

The image of a cell under a D4 element, read in the frame one Position places and seated at the frame another places: the cell is viewed from the source frame, transformed there, and composed onto the target frame. `apply_about` is this with one frame for both, and it cannot state the two-frame form: a reflection that exchanges two lines turns about their midline, which for an odd separation is no cell, and a copy that turns as it moves has a source and a landing with no shared origin. The two frames need no relation to the cell or to each other; each is any Position the flip or turn fixes as its origin.

```
.decl apply_between(d: D4, p_src: Position, p_dst: Position, p: Position, p_out: Position) inline
apply_between(D, F_src, F_dst, P, P_out) :-
    displacement(F_src, P, V), apply(D, V, V2), compose(F_dst, V2, P_out).
```

Not: `apply_about` (one frame — a rule whose view and seat bind the same Position); `apply` (the grid's own frame); a seat with no transform (`displacement` and `compose` around a stored or searched offset, as a stamp placement or a copy reads); a transform inside a decomposition's inner frame reseated by `concat` or a frame comp's `inner` read backward, where no Position places the frames; a landing by a Shift searched over and keyed, which many origin pairs produce.

Match: a rule, or a chain of rules through a stored Shift, that binds two distinct Positions F_src and F_dst and holds all three of `displacement(F_src, P, V)` — or a `Reframe.inner` or `BoxFrame.inner` whose `outer` is F_src — `apply(D, V, V2)`, and `compose(F_dst, V2, P_out)` — or a `BoxFrame.inner` whose `outer` is F_dst, read backward — in either compose argument order; and the same shape reached through two `apply_dir`-free steps, a grid-frame `apply` followed by a `jump` or a `compose` with a displacement of the two frames. Grep signature: files holding both `displacement` (or `.inner`) and `apply(` and `compose(`; `grep -n 'displacement\|\.inner\|apply(\|compose(' programs/solvers/*.dl` then read the rules that hold all three with two frame Positions.

Survey: 2026-09-09 22:10

That pass read the whole corpus, 610 solvers, by the grep signature and by a parser pass over every rule holding a bare `apply` atom, tagged by whether the same rule holds a view (`displacement`, `.inner`), a seat (`compose`), or a `jump`. 158 rules in 105 files name a D4 element; 49 of them hold `apply` beside a view, a seat, or a jump. Nine callers, listed below. Its near-misses: the one-frame sites, which are `apply_about`'s callers; a landing by a Shift no origin produces, searched (`0e206a2e`, `412b6263`, `1acc24af`, `50f325b5`, `b7cb93ac`, `0dfd9992`, `08573cc6`, and the RIGID files `142ca369`, `150deff5`, `269e22fb`, `3aa6fb7a`, `3d588dc9`, `409aa875`, `4c177718`) or a grid-frame flip then a `jump` by a stored or scalar amount (`3631a71a` with its sibling `af22c60d`, `496994bd`); `1b60fb0c`, whose translation is the displacement of one ink cell's turned image from another, collected over every ink pair into a placement set — the Shift is the model's object, not one pair of frames; a decomposition frame no Position places (`833966f4`, `e3497940`, `47c1f68c`, `5a719d11`, `8e5a5113`, `eb281b96`, `e9afcf9a`, `4e7e0eb9`, `103eff5b`, and the tile-arrangement solvers); `apply` in the grid's own frame with nothing seated.

## Callers

- `66ac4c3b` — `painted`: every ink cell read from one marker line's frame, flipped across the marker axis, and seated at the other marker line: the reflection that exchanges the two lines. The frames are the lines' own axis-only Positions, and the rule states its own domain test.
- `4938f0c2` — `img`, the `$Seat` case: each object cell viewed from the box cell at the corner facing the block, transformed by a group element, seated one step out of the block corner its image faces; the entry's exact form. Its `$Mirror` case and its determination are one-frame.
- `3e980e27` — `parse.footprint` with `paint`, and the determination: a shape cell viewed from the marker inside its shape, stored as a Shift catalog keyed by marker color, transformed by the color's D4 element, seated at a bare marker of that color. View and seat in different rules.
- `36d67576` — `anchored` with `carried`: a mark viewed from the model part's anchor, turned by the part's pose, seated at that part's anchor. Different rules.
- `4c416de3` — `shape` with `stamp`: a stamp cell viewed from the site the whole stamp surrounds, stored as a Shift catalog keyed by corner, carried onto another corner by the D4 element mapping the corners, seated at the target site. Different rules.
- `11dc524f` — `paint`, the mirror branch: a shape cell viewed through `BoxFrame.inner` from the shape's box, flipped across the slide axis, seated by `compose` at the mirror box, a Position `jump` derives from the docked box.
- `2546ccf6` — `reflect` with `mirror`: a block-tile cell viewed through `BoxFrame.inner` from its tile's box, flipped across the cut (two flips chained for the diagonal), seated by reading the missing tile's `BoxFrame.inner` backward. Both frames are `tile_frame.margin` Positions.
- `64efde09` — `emit`: a beam source viewed through `BoxFrame.inner` from its bar's box, carried by the `D4Map` element mapping the bar onto another, seated by reading the other bar's `BoxFrame.inner` backward.
- `2c181942` — `dock_cell`: a piece cell turned in its box frame, then composed with the displacement of the turned notch cell from the seat cell, `P_seat + G(P - P_notch)`: the two-step form with the notch cell as source frame and the seat cell as target, both bound in the rule.

## Spec

No interface change: every caller binds its two frames as plain Positions already in its rules, so the inline five-argument form serves all of them, and no key or comp form is needed.

- **Seat through a frame view read backward.** `2546ccf6` and `64efde09` seat by reading the target's `BoxFrame.inner` backward, which is `compose(F_dst, V2, P_out)` restricted to the target's viewed cells; `BoxFrame.margin` places both frames, so the `Not:` clause on decomposition frames does not reach them. The Match line names that seat form beside the `Reframe.inner` view form, and a caller states the domain test itself.
- **Split view and seat.** `3e980e27`, `36d67576`, and `4c416de3` store the viewed Shift in a catalog and seat it in a later rule. A call joins the view into the seating rule, or the catalog carries the source frame as a column.
- **The Shift exclusion.** What keeps `1b60fb0c` out beside `2c181942` is that its Shift is searched over and keyed, with many origin pairs collapsing onto it, where `2c181942` binds one notch cell and one seat cell.
