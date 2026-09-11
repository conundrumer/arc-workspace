# `D4Placement<Key>` — a D4 element placed over a cell set, and the cells each placement carries onto the set

The shifts that place a keyed D4 element over a keyed cell set so that the element carries some cell onto a cell, the cells each such placement carries onto the set, and the placements that carry the most. A placement is the element taken about a center other than the frame's: `apply` about the frame and then a shift. `D4Map` is the placement at `ORIGIN`, and `ShiftInvariance` is the identity element's placements, so this is the element-and-center reading that both leave out. A shift places an element as an isometry of the element's own kind: any shift places a rotation, and a shift places a reflection only when it crosses the mirror line, so no glide reflection enters. A solver that finds a figure's own mirror line, or lays a turned copy of a figure where it overlaps the figure most, states that with one instance.

```
.comp D4Placement<Key> {
    .decl cell(key: Key, p: Position)  // input
    .decl elem(key: Key, d: D4)        // input

    // The shift carrying one cell's image under the element onto a cell.
    .decl _carry(key: Key, delta: Shift, p: Position)
    _carry(Ky, Delta, P) :-
        cell(Ky, P), elem(Ky, D), apply(D, P, P_img),
        cell(Ky, Q), displacement(P_img, Q, Delta).

    // A shift places the element as an isometry of its own kind: any shift
    // places a rotation, and a shift places a reflection when the reflection
    // negates it, so the shift crosses the mirror line.
    .decl placement(key: Key, delta: Shift)
    placement(Ky, Delta) :-
        _carry(Ky, Delta, _), elem(Ky, D),
        ( c4_elem(D)
        ; !c4_elem(D), apply(D, Delta, Delta_img), displacement(Delta, ORIGIN, Delta_img)
        ).

    // Cell p's image under the placed element is a cell.
    .decl landed(key: Key, delta: Shift, p: Position)
    landed(Ky, Delta, P) :- placement(Ky, Delta), _carry(Ky, Delta, P).

    .init _fit = Mode<Key, Shift, Position>
    _fit.item(Ky, Delta, P) :- landed(Ky, Delta, P).

    // The placements landing the most cells.
    .decl best(key: Key, delta: Shift)
    best(Ky, Delta) :- _fit.mode(Ky, Delta).
}
```

Call site (8e5c0c38): `mirrored` states `landed` for the flip of `params.mirror_axis` over each shape, with the mirror-line crossing written as `same_line` on that axis between the cell and its partner, and `fit`, a `Mode` over it, is `best`; the tie-break resolutions and the output read both.

Not: `D4Map` (the element about the frame's own center, with no shift); `ShiftInvariance` (translations alone, the identity element); `apply_about` (the element about a center a Position names, where the center is given and not searched); `D4Map.onto` and `Congruent` (whether one set is another's image, with no scoring of partial overlap); a stored shift or pivot read from Params; `Occurrences` (a stored shape found in the grid, with no transform); the orbit under a placed element (1b60fb0c `orbit`, which walks `landed`'s step to closure and lies beyond the operation).

Match: a rule that binds a Shift from `displacement` between the `apply` image of one cell of a set and another cell of the same set, in any order of atoms and across rules — including forms where the image is taken about a frame `Position` by two `apply` steps — together with a count or `Mode` over the cells of that set carried by that shift, or a readout of the shift set itself. Grep `apply(` beside `displacement(` in `programs/solvers/*.dl`, and `Mode<` whose member is a `Shift`; confirm with the parser (`tests/test_ast_match.py`) that the two positions of `displacement` are an image and a member of one set.

Survey: 2026-09-11 02:11 — the whole corpus.

Callers:
8e5c0c38 `mirrored` — the shifts that carry a shape cell's flip (`flip_of` of `params.mirror_axis`) onto a shape cell of the same line, with the landed cell beside each; `fit`, a `Mode` over it, is the placement landing the most cells, and the tiebreak resolutions and `kept` read both. This is the entry's call site.
1b60fb0c `placement` — the shifts that carry an ink cell's image under `params.sym` (a quarter turn, so no mirror-crossing test) onto an ink cell; `copy_cell` joined with `ink_cell` is the landed set, and `fittest`, a `Mode` over it, is the placement that overlaps the figure most for the $Copy case. The $Complete case walks `orbit` from the same `placement`, which lies past the operation.

Near-misses:
3345333e `cand`, `mirror`, `upheld`, `contradicted` — the $Fitted case searches the mirror line: candidates are the boxes of two figure cells on one line (the frame whose flip swaps them), `mirror` is the flip taken about each candidate through a `Reframe` view, and the fitted frame is one no figure cell contradicts. Ruled out by the target set and the readout: a cell is upheld when its image is a figure cell or an occluder cell, so the set landed on is not the set placed, and the readout is that every cell lands, not that the most land.
2c181942 `dock_cell` — the shift carrying a turned notch cell of a piece onto a seat cell, then the whole piece carried by it; `mate` tests the fit exactly. Ruled out because the two positions of `displacement` are cells of two sets (the piece's notch and the hub's seat), and the readout is exact set equality on the seat's line, not overlap.
20a9e565 `cand`, `share`, `best` — the shift between a layer cell and each cell of the layer a period earlier, and per cell the shift shared by the most cells of its layer. Ruled out because the element is the identity and the two sets differ (one layer and the layer before it); it is the translation reading of placement-by-overlap that `ShiftInvariance` also leaves out, since that comp has dst = src and no partial score.
0e206a2e `seat`, `placed` and 6e4f6532 `seat`, `seated` — an anchor pattern transformed by every D4 element and seated where `Occurrences` finds it among marker cells, then the whole object carried to that seat. Ruled out by `Occurrences`: the fit is exact over a valued pattern against another set, with no scoring of partial overlap.
0dfd9992 `Wallpaper.cand`, `pair`, `mismatch`, `witnessed`, `sym` — candidates are an isometry kind composed with a shift from the lattice's fundamental domain, `pair` binds valued cell pairs under each candidate, and `sym` keeps the candidates some pair witnesses and no pair contradicts. Ruled out because candidates come from a lattice quotient and cells are compared by value; its restriction on self-inverse kinds (the candidate's square lands in the lattice) is the lattice form of the entry's condition that a reflection negates its shift.
47996f11 `Determine.cand`, `mirrored`, `mirror_mismatch`, `axis_center` and 981571dc the same relations — the grid-center flip of an axis composed with twice a candidate offset, over every sub-extent, kept where some cell lands and no cell lands on a different color; the program itself reads the center from `params.center`. Ruled out because the candidates are enumerated from the extents rather than derived from cell pairs, cells are compared by color, and the readout is unbroken, not most.
0934a4d8 `Determine.ext_cand`, `ext_map`, `ext_mismatch`, `ext_pair`, `axis_ext` — one-sided frame extensions per axis, each tested as the flip about the extended frame with a color mismatch and a distinct-pair witness. Ruled out on the same grounds as 47996f11's Determine.
11852cab `Parse.sym4`, 3a25b0d8 `fig_sym`, 44d8ac46 `sym`, 72ca375d `inv`, 73ccf9c2 `inv`, 18419cfa `paint`, 64efde09 `emit` — the element about a bounding box or a wall interior, through `BoxFrame.inner` and `D4Map`. Ruled out by `D4Map`: the center is the box's, given, not searched.
47996f11 `counterpart`, 981571dc `counterpart`, e729b7be `image` ($Marker), 90347967 `moved`, 7ed72f31 `image_along`, 2b01abd0 `mirror`, 2bcee788 `mirror`, 538b439f `image`, 5545f144 `sym_cell`, 5b692c0f `mirror`, 60d73be6 `image`, 66ac4c3b `painted`, 6855a6e4 `image`, 84551f4c `landed`, 88207623 `image`, 4938f0c2 `img`, 4c5c2cf0 `copy` — a cell read from a given center (a stored offset, a marker, a line, a box), transformed, and seated back. Ruled out by `apply_about`: the center is given and not searched.
67b4a34d `sym`, b8825c91 `sym`, af22c60d, 5751f35e, 73251a56 `mirror`, ce039d91, a8610ef7 — the element about the frame's own center. Ruled out by `D4Map`.
291dc1e1 `placed` — a turned block's shift into its slab is fixed by `centered`, not by landing on a set; the `apply` and the `displacement` sit in different rules. Ruled out because no shift is chosen by what it carries onto.
045e512c `fits` — a seating from `Occurrences` read as a shift, with no transform. Ruled out by `Occurrences`.

Spec:
The surfacing solver and 1b60fb0c both place one set over itself and read `best`, so the entry's definition holds at its callers. The near-misses argue two changes to the interface, each from several sites that are not the surfacing solver.
A src/dst split, as `D4Map` has it, with dst = src as the self-placement reading. 3345333e lands figure cells on figure or occluder cells, 2c181942 lands notch cells on seat cells, and 20a9e565 lands one layer on the layer before it (identity element); each derives its shift from a cell of one set and the image of a cell of another, which the single `cell` input cannot state. With the split, 20a9e565 becomes a caller of `placement` and `best` at `elem` = `D4_ID`, and 2c181942 a caller of `placement` alone.
A universal readout beside `best`: the placements under which every src cell lands, the `map` reading of `D4Map`. 3345333e's `contradicted` is its negation, and the Determine comps of 47996f11, 981571dc, and 0934a4d8 read the same thing over colors. The value comparison at those three, and at 0dfd9992, is a `Val` type param with a `mismatch` readout; a membership caller instantiates `Unit`. The candidate enumeration at those sites (sub-extents, a lattice domain) is the part the operation would replace, since a placement derived from cell pairs is witnessed by construction, which is what their `ext_pair` and `witnessed` add back. 0dfd9992's lattice quotient stays outside the operation.

Reimplementations: none.
The parser matcher under the scratch path scored 34 rule hits for `apply` feeding `displacement` or `compose` (3 with both positions bound by one relation: 8e5c0c38 `mirrored`, 1b60fb0c `placement`, 0dfd9992 `Wallpaper.cand`) and 14 for a two-sided read through one relation around `apply`; every hit and every grep hit for `apply(` beside `displacement(` (20 solvers), `Mode<` over a `Shift` (3), and `Tally`/`ArgExtremes` over a `Shift` (3) was read in its rule.
