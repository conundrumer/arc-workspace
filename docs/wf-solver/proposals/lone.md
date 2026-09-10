# `lone` — a set member that touches no other member

The cells of a keyed cell set with no cardinal neighbor in the set, and their complement, the members that touch another member. It is how a solver tells a stray dot from the body it lies beside without individuating components: the block is the ink that touches ink, and the marker is the ink that stands alone. Under 4-adjacency it coincides with `multi_cell` over the set's components, stated with no component ids.

```
.comp Lone<Key> {
    // The set, per key.
    .decl cell(key: Key, p: Position)

    // A member with a member one cardinal step away.
    .decl touching(key: Key, p: Position)
    touching(Ky, P) :- cell(Ky, P), dir_elem(D), neighbor(P, D, Q), cell(Ky, Q).

    .decl lone(key: Key, p: Position)
    lone(Ky, P) :- cell(Ky, P), !touching(Ky, P).
}
```

Not: `multi_cell` (a keyed set of more than one member, keyed by an object id); `Rim.rim_dir` and `Rim.interior` (which sides are open, and the members with no open side); `Abut` (contact between two sets, with the heading); `Surround` (walled in by another set); a contact test between a member and a second set (`beside` rules over two relations).

Match: a rule whose body joins one cell relation to itself through a single `neighbor` atom whose direction ranges over `dir_elem` and whose head keeps the first cell alone, with or without a consumer that negates it over the same set; and the same predicate stated through `Rim.rim_dir` negated over `dir_elem`, or through a `Tally` or `multi_cell` over `Components` of the set.

Survey: 2026-09-10 06:09

Result: the whole corpus, 684 solvers. Matcher at `.scratch/7ddcd7ec/lone_match.py`.

Every site derives touching positively and states lone as its negation; none derives lone directly. Of the callers, eight consume both heads, two touching only, one lone only. The `neighbor` self-join under a class enumerator is the corpus form (eight sites); `Rim.rim_dir` reaches the predicate at one site, and elsewhere only where the direction is kept; `Tally` never states it; `Unanimous`/`multi_cell` over `Components` states it at eleven sites, nine of which individuate components for other reasons, so the id-free form is what two sites (39e1d7f9, 2c737e39) would gain. Three sites key by color, which `Key` covers. No `// family:` sibling points at any site.

Survey: 2026-09-10 06:35 — scope: the solvers whose file time is at or after the line above, 7e0986d6 excluded: 264363fd, 759f3fd3, 7d419a02, 7d7772cc, 7ddcd7ec, 7df24a62, 7f4411dc, d9fac9be. Matcher at `.scratch/7e0986d6/lone_scope.py`. No new caller. The `neighbor` self-join matched at 7ddcd7ec `block` (the listed caller, unchanged), at 759f3fd3 `Determine.ring_cycle` (head keeps neither cell: it reads the output colors of a neighbor pair one ring apart), and at 7d7772cc `rest` (a gate lookup across two relations, not a self-join). Negated `rim_dir` under `dir_elem` matched at 264363fd and 7f4411dc, both keeping the direction. No `Tally`, no `multi_cell`; the one `Components` instance (264363fd `pieces`) feeds `BoxFrame` and `Mode`, so its ids serve elsewhere. Near-misses in scope: 7f4411dc `support` (now `!rim.rim_dir` over `dir_elem` with the direction kept; the earlier `neighbor` self-join form is gone); 7d7772cc `thick` and 759f3fd3 `Parse.rings.seed` (`!rim` over the set, `Rim.interior`'s reading); d9fac9be `gap` and `defect` (a grid cell whose eight neighbors all lie in a second set, the `Surround` reading). No site in scope bears on adjacency or the interface. Two sites state the `Not:` line's `Rim.interior` as `!Rim.rim` over the set, so the `Not:` line can name that lib readout instead of the proposal.

## Spec question

- **Adjacency.** Six sites state the predicate under 8-adjacency: 3e980e27, 7491f3cf, and 42a50994 through `dir8_elem`; 39e1d7f9, 2c737e39, and 1b59e163 through `Components8`. The `Rim`/`Rim8` and `Components`/`Components8` precedent (an internal `dir` relation, a `Lone8` subclass) covers both. 7b80bb43 `chain`, touching under `diag_dir_elem` alone, is a peer class under Closure and stays out.
- `Rim.interior` in the `Not:` line is a proposal, not a lib readout.

## Near-misses

- Single-cell test over `Components` whose ids the program needs elsewhere, the `multi_cell` entry's callers: 0e206a2e `part_cell`, 1b59e163 `obj_pos` (`Components8`), 2f0c5170 `alone`, 581f7754 `lone`, 54dc2872 `multi_cell`, 5af49b42 `multi_cell`, 4b6b68e5 `outline` (by color), 14b8e18c `multi_cell` (by color), 64efde09 `bar`.
- Direction kept in the head, `Rim.rim_dir`'s reading: 15663ba9 `arm`, 71e489b6 `figure_nbr`, 7f4411dc `support`, 264363fd `attached.item` (`Unanimous.value` over the direction), 642d658d `arm` and 0962bcdd `Parse.arm` (direction and neighbor color kept), 508bd3b6 `aim` (diagonal, direction alone in the head), 1d61978c `streak` (diagonal axis kept).
- Contact with a second set: 2b9ef948 `beside_trail`, 2dd70a9a `at_target`, 508bd3b6 `side_wall`, 54d82841 `walled`, f0df5ff0 `painted`, 7b3084d4 `by_color.equiv`.
- Contact between two objects (`Abut`): 3dc255db `holds`, 7b0280bc `touch`, 4364c1c4 `Parse.side`, 72322fa7 `touch`.
- 7b80bb43 `chain` — touching under `diag_dir_elem` over the loose cells, a peer class.
- 3eda0437 `region` — some two box cells a diagonal step apart, the head keeping the box key.
- No `Tally` instance reads a component's cell count against 1 or 2 for this predicate; 16de56c4 `crowded` counts line marks.

## Callers

Self-join through `neighbor`, touching derived positively and lone as its negation:

- 7ddcd7ec `block`, `!block` in `tail` — ink with an inked cardinal neighbor is the block; a tail is the ink that is not.
- 2c608aff `block`, `marker` — the block is the ink that touches ink; the marker stands alone.
- 67385a82 `grouped`, `!grouped` in `out` — grouped ink repaints; the rest keeps its color.
- aedd82e4 `grouped`, `isolated` — isolated ink takes the mark color; grouped ink the ink color under `$Repaint`.
- 195c6913 `swatch_cell`, `seed` — a legend cell touching another is a swatch; a lone one seeds a walk.
- 3e980e27 `Parse.joined`, `Parse.lone` — under `dir8_elem`.
- 7491f3cf `Parse.line`, `Parse.marker` — under `dir8_elem`.
- 42a50994 `grouped`, `!grouped` in `out` — under `dir8_elem`; `$Self` keys the set by color, `$Ink` by `Unit`.

Through `Rim.rim_dir`:

- 7e0986d6 `touching`, `!touching` in `sprinkle_color` — `!rim.rim_dir` over `dir_elem`, ink keyed by color under `$Isolated`; the color of a lone ink cell is the sprinkle color, and the other ink color is the rectangle color.
- 696d4842 `link`, `dot` — `link` is `!rim.rim_dir` over `dir_elem` keyed by color and keeps its direction for `behind` and `crawl`; `dot` is the lone head, the only part `Lone` would replace.

Through a single-cell test over `Components` whose ids serve nothing else:

- 39e1d7f9 `obj_cell` — `Unanimous<Ident, Position>` over `Components8`; `motif` reads `clash`, `seed` reads `value`.
- 2c737e39 `drawing` — hand-written `multi_cell` over `Components8`; touching head only.
