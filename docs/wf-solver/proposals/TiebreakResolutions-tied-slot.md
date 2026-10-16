# TiebreakResolutions-tied-slot — the resolutions of one tied slot

A change to `.comp TiebreakResolutions<Key, Slot, Item>`: a readout beside `resolution` with no injectivity across slots. A pair has at most two accepted outputs. `resolution` drops an assignment that uses one item twice, so a slot whose item another slot also takes loses a valid resolution, and a caller with per-slot items keys them by slot.

Not: `resolution` as it stands, the injective assignment across every slot. Not a caller that keys its items by slot to avoid collisions: that keying stands in the caller, and it states the need for the change, not the change.

Match: a `TiebreakResolutions` instance whose `Item` type carries a field equal to its `Slot` type, or whose `cand` rule builds the item from the slot. Match with the parser: every `TiebreakResolutions` instantiation, read for its `Slot` and `Item` type arguments, with the `Item` record's field types and the instance's `cand` rules — a field whose type is the `Slot` type, or a `cand` head whose item argument holds the rule's slot variable.

Spec: what the non-injective readout reports.

Callers: 8e5c0c38 `ties`, whose `Placement` record carries the shape id that is also the slot. Two shapes can tie on one Shift, and injectivity would drop that resolution; the shape id in the record separates them.

Survey: 2026-09-11 14:55 — every solver.

Callers:
8e5c0c38 `ties` — the solver instantiates `TiebreakResolutions<Choice, Ident, Placement>` and its `cand` rule builds each item as `[Id, Delta]`, so the shape id that is the slot also sits inside the item; the non-injective readout would serve it by letting the item be the bare `Shift`.

No second caller. The parser matcher, over all 749 solvers, found three `TiebreakResolutions` instantiations in total. It read each instance's `Slot` and `Item` type arguments, the `Item` record's field types, and each instance's `cand` rules for an item argument holding the rule's slot variable. One instance matched. The same sweep also checked every top-level `out` declaration for a trailing column typed by a locally-declared ADT other than `Choice`, to catch a resolution enumeration written without the comp: the only such columns are the `TiebreakResolution` columns of those same three solvers, so no site enumerates resolutions by hand.

Near-misses:
89565ca0 `ties` — `TiebreakResolutions<Unit, number, Color>` seats frames in chart rows. The item is a bare `Color` with no slot field, and cross-slot injectivity is the model: one frame takes one row, and a frame seated twice is not a resolution. The first exclusion rules it out, since this is `resolution` as it stands.
b7cb93ac `ties` — `TiebreakResolutions<Unit, Position, Piece>` seats pieces at box margins. The `Piece` record's fields are `Color` and `Ident`, neither the `Position` slot type, and each piece is placed once across the whole packing, so cross-slot injectivity is again the model. The same exclusion rules it out.

Spec:
Caller-only. The one site the signature matches is the surfacing solver, so the sites establish no change to the interface or the definition.

Two results bear on the spec question, and both come from that one site.

1. The change must add a readout beside `resolution`, not relax `resolution`. Both near-misses read `resolution` for its injectivity across slots. A relaxed `resolution` would admit assignments those two tasks reject.
2. The caller's collision is not witnessed. The entry's caller line states that two shapes can tie on one `Shift`, and that injectivity would drop that resolution. I recomputed the solver's shape grouping, its mirrored-cell count per shift, and its mode shift set, over all four grids of 8e5c0c38 under both `ByColor` and `ByObject`. Every shape's mode shift set is disjoint from every other shape's in its grid. One shape in grid 2 carries two tied shifts, which is a tiebreak within one slot; no two shapes ever share a shift. So the `shape` field in `Placement` guards a collision this task's data never produces, and the solver would still resolve with the item as a bare `Shift`.

On what the readout reports, the caller's consumption fixes the shape of the interface: it reads `resolution(key, res)` to range `out` over the choices, and `assign(key, res, slot, item)` to read the chosen item per slot. A non-injective readout needs both relations, so it is a parallel pair, and its terms are the product of the per-slot candidate sets — one term per combination of independent per-slot picks. The limit of two accepted grids per pair sits in the caller, not in this readout.

Reimplementations: none.
