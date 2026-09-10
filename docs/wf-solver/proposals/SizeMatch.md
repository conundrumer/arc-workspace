# `SizeMatch<Key, Ref, Member>` — the keyed sets as large as a reference set

The keys whose member count equals a reference set's member count. A task
whose content fills a region exactly sizes the region here: the pieces count
as the reference, the candidate regions count per key, and the region is the
key whose count matches.

```
.comp SizeMatch<Key, Ref, Member> {
    // The candidate sets, per key.
    .decl item(key: Key, m: Member)  // input

    // The reference sets, per ref.
    .decl ref(ref: Ref, m: Member)   // input

    .init size = Tally<Key, Member>
    size.item(K, M) :- item(K, M).

    .init ref_size = Tally<Ref, Member>
    ref_size.item(R, M) :- ref(R, M).

    // The key's set and the ref's set have the same count.
    .decl match(key: Key, ref: Ref)
    match(K, R) :- size.tally(K, N), ref_size.tally(R, N).
}
```

Not: `KeyedSetCompare.equals` (the same members, not the same count); `Tally`
with the count read downstream as a number (a rank, a placement, an extent);
`Extremes` over tallies (the largest or smallest set); a count compared against
a stored parameter.

Match: two `Tally` instances, or two `count` aggregates, whose `tally` readouts
share the count variable in one rule, and that rule reads neither count
further. Grep: `\.tally\(.*, N\).*\.tally\(.*, N\)` on one line, plus rules
whose two `.tally(` atoms sit on different lines and share a variable.

Survey: 2026-09-10 05:21

The pass ran the grep over the whole corpus and a parser pass over rules with
two count readouts sharing the count variable, on one line or across lines.
No solver holds a `count :` aggregate.

## Callers

- 7b3084d4 — `side` (`:73`): the square side whose cell count is the pieces' cell count. Key = number, Ref = Unit.
- 446ef5d2 — `rect` (`:103`): the anchor-spanned box whose cell count is the pieces' cell count. Key = Position, Ref = Unit.
- 42f14c03 — `fits(H, O, $Size())` (`:94`): hole and object with equal cell counts. Key = Hole, Ref = Ident.
- 7acdf6d3 — `fit` (`:43`): the container whose hollow count equals a color's piece count, filtered after the match to the other color. Key = Ident, Ref = Color.
- 3d6c6e23 — `apex` (`:61`): the (line, apex) pairs whose cone count equals the line's pixel count, filtered after the match by `cand`. Key = Position, Ref = Position.
- 2685904e — `paint` (`:65`): the color whose frequency equals the bar's length. Key = Color, Ref = Unit. Another rule reads the same length tally as a depth.
- 62593bfd — `paired(Id, $Size())` (`:44`): a blob with another blob of equal size, one Tally self-joined with `Id != Id2`. Key = Ref = Ident over one set.

## Near-misses

- Two tallies in different disjunction branches, with the count read as a jump length: 12422b43 `copy` (`:54`).
- A tally joined with an extent readout: 3ee1011a `innermost.cand` (`:56`).
- Strict inequality between two tallies, feeding `Order` or `Extremes`: 230f2e48 `:94`, 271d71e2 `:145`, `:148`, 31f7f899 `:70`, 3d6c6e23 `:96`, 3dc255db `:36`, 4df5b0ae `:48`, 694f12f3 `:72`, 89565ca0 `:91`, 9caf5b84 `:33`.
- A tally against a stored parameter: 00dbd492, 0a2355a6, 12eac192, 2c0b0aff, 31aa019c, 37d3e8b2, 5582e5ca, 642d658d, 6d1d5c90, 758abdf0, 794b24be, 79cce52d, aabf363d.
- `!Excess.excess`, a ≤ test: 22806e14 `erase` (`:69`).

## Spec question

- **Self-match.** 62593bfd matches one set against itself and excludes the identity after the match. Under this interface it feeds `item` and `ref` from one relation and the comp tallies that set twice. Whether a self-match form belongs in the interface — `ref` defaulting to `item`, or a `peer(key, key2)` readout that excludes the identity — is open.
- The filtered readers (3d6c6e23, 7acdf6d3) filter after the match, so the interface needs no filter input. The reference count that 2685904e reads elsewhere is reachable as `ref_size.tally` through the instance path.
