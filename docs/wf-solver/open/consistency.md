# Consistency: mechanical splits across the corpus

Splits in file form where the solvers agree on the model and differ in naming, markers, or keying. Each entry gives the split, the form to agree on, and the files on the other side. No entry changes a model or a case.

## Case markers spell the case two ways

`// --- $Fixed ---` with the term sigil, against `// --- Bbox ---` with the bare constructor name. `style.md`'s skeleton shows the bare form. Files with the sigil: 1fad071e, 332efdb3, 3618c87e, 37ce87bb, 3b4c2228, 4522001f, 7447852a, d4469b4b, ded97339, ff28f65a, 1e81d6f9, 22eb0ac0, 69889d6e, bbc9ae5d, c48954c1, c7d4e6ad, c9f8e694, eb281b96, f25ffba3.

## Case markers carry a role word

`// --- Table, Size decompose data ---` against `// --- Table, Size ---`. The block under the marker holds that case's Params and rules, so the marker needs no word for the kind of content. Files with role words: 0520fde7, 94f9d214, e133d23d, ff28f65a (`$Fill (rule)`, `$Lookup (table)`), 1fad071e, 1e81d6f9, 69889d6e, c48954c1.

## A marker for a parameter read across two fields of a record `Choice`

4522001f names the reading branch values across fields, `// --- $Mark, $Block ---`; 6430c8c4 and 99b1bc43 leave `frame_dim` above the case markers because no marker holds all its readers. The form to agree on: a marker that lists the reading branch values, one from each field. Under `correspondence-frame.md` the parameter in 6430c8c4 and 99b1bc43 falls back to the `DecChoice` field alone and needs no cross-field marker.

## The leftover tile extent's name

Once the stored frame goes, the parameter that remains holds one tile's extent. 94f9d214, 0520fde7, e133d23d name it `tile_dim`; ce4f8723, dae9d2b5, e345f17b, fafffa47 keep `frame_dim`. One name per family: `tile_dim`, renamed in the representative and its siblings together.

## A stored value the pairs leave open

Four solvers record it in a comment above the parameter's `.decl`, two in the header, nineteen nowhere. The form to agree on: a comment above the `.decl` that says what fixes the stored value. Files with no note: 7ec998c9, 2697da3f, 30f42897, 36fdfd69, 3ac3eb23, 11852cab, 44d8ac46, 5961cc34, 23b5c85d, 2ba387bc, 845d6e51, 981571dc, 72ca375d, 67e490f4, 18419cfa, 1b60fb0c, e729b7be, 5289ad53, 80a900e0, 27a28665, 3631a71a, 1f85a75f; in 2697da3f and 11852cab the note sits in the header.

## The header and a property of the pairs

A property that collapses a dropped peer onto the current model, such as every line having a distinct nearest row, goes into the header beside the parse it licenses, as 13e47133 and 23b5c85d write it. 668eec9a left it in its report.

## Keying the stages downstream of a case split

50f325b5 keys the shared comp instance and the shared relations by `Choice`, with the case's own relation supplying the value the cases disagree over; 3a25b0d8 keys them by that value (`Axis`). The form to agree on is 50f325b5's. Files keyed by the value: 3a25b0d8, 13f06aa5 (the `ray` instance), 6d1d5c90 (the `rot` instance).
