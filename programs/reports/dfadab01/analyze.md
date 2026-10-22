# dfadab01

## Concept
- Fits every pair (`work/task/dfadab01/probe.py`). Each claim has a relational form, and no witness has the verdict `other`.

## Choice points
- `sample-picture`: what gives the picture that the sample's key draws
    - `concept`: the stored `stamp` table, for every key
    - `$SampleStamp`: replaces `stamp-at-marker` for the sample's key. That key's stamp is the sample's picture, read relative to the top-left of the sample's box, and every other key reads `stamp`. Parameters: `stamp`, `anchor`, `key-corner`, `background`. Undefined where the concept is undefined. Fits every pair. Witness `sample-picture`: it breaks `legend` and stands at the stored assignment. Plausibility `borderline`, verdict `$SampleStamp`. It breaks the invariant that in every input with a sample, the sample shows the table's picture of its key.
    - `$SampleOnly`: replaces `stamp-at-marker`. The sample's picture is the only stamp, and no table is stored. Undefined on an input with a marker whose color is not the sample's key, and on an input with no sample. Fails train0.
- `key-marker`: which markers are the sample's key markers
    - `concept`: the marker one step past the `key-corner` corner of the sample's box on both axes
    - `$KeyByContact`: replaces the key marker of `legend` and of `stamp-at-marker`. Every marker outside the sample's box that touches the box at a side or a corner is a key marker and is wiped. It reads no `key-corner`. Undefined where the concept is undefined. Fits every pair. Witness `marker-beside-sample` breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `$KeyAnyCorner`: replaces the key marker of `legend` and of `stamp-at-marker`. Every marker one step past any corner of the sample's box on both axes is a key marker. It reads no `key-corner`. Undefined where the concept is undefined. Fits every pair. Witness `marker-past-other-corner` breaks no scene claim. Plausibility `ordinary`, verdict `concept`.
    - `$StampKeyMarker`: replaces `stamp-at-marker`. The key marker draws its stamp like any other marker. Fails train0.
- `overhang`: a stamp whose box runs past the grid edge
    - `concept`: the cells past the edge are dropped, and the rest are drawn
    - `$DropOverhang`: replaces `stamp-at-marker`. That marker draws nothing. Fails test0.
    - `$OverhangUndefined`: replaces `stamp-at-marker`. Undefined on an input where a stamp's box runs past the grid edge. Fails test0.
- `sample-wipe`: how the sample leaves the output
    - `concept`: the sample is wiped, and a stamp drawn into its box stays
    - `$WipeAfterStamp`: replaces `wipe-rest`. The sample's box is wiped after the stamps are drawn. Fails train1.
    - `$KeepSample`: replaces `wipe-rest`. The sample stays in the output. Fails train0.
- `marker-identity`: what makes a cell a marker
    - `concept`: its color is a key of `stamp`
    - `$MarkerBySingleton`: replaces `markers`. A marker is a cell that touches no cell of its own color at a side or a corner, whatever its color. Undefined on an input with such a cell of a color that `stamp` has no key for. Fits every pair. Witness `touching-markers` breaks `stamps-apart`. Plausibility `foreign`, verdict `concept`. It breaks the invariant that, with the key marker left out, no two markers' stamp boxes overlap.
    - `$MarkerBySingleton4`: replaces `markers`. It is `$MarkerBySingleton` with contact at a side only. On test0 the corner cells of the `7` cross sample are markers with no stamp, so it fails test0.
- `background`: the field color
    - `concept`: stored, `0`
    - `background=DominantColor`: the commonest color of the input. Undefined where two colors tie for commonest. Fits every pair. Witness `background=DominantColor`: it breaks `markers` and stands at the stored assignment. Plausibility `variant`, verdict `background=DominantColor`. It breaks the invariant that the field is `0` in every input.
- `sample-picture` & `marker-identity`, `sample-picture` & `background`, `key-marker` & `marker-identity`, `key-marker` & `background`, `marker-identity` & `background`: the two branches' changes applied together
- `sample-picture` & `key-marker`: the sample's picture is the stamp of the color its key markers share, and the model is undefined where those markers differ in color
- `overhang` and `sample-wipe` with another point: no case takes a branch other than the concept's at either of them

## Open parameters
- none

## Not formed
- An order of drawing for stamps whose boxes overlap: at such an input the concept is undefined where two stamps put different colors on one cell. Every input keeps the stamps apart (`stamps-apart`), and no pair, solver header or proposer gives an order among the markers.
- The stamp color stored apart from the picture, keyed by marker color: each assignment of it agrees with an assignment of `stamp`, and the reverse also holds, so it is equivalent to the concept.
- Another `anchor` or `key-corner` value: these are values of the concept's parameters, and every other value fails train0.

## Tickets filed
- none
