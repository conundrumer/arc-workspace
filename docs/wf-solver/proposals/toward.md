# `toward` — the king heading from one position to another

The Dir8 a walker at p steps in to close on g: the cardinal g lies toward when p is in line with g on the other axis, else the diagonal that pairs the two cardinals g lies toward. It is the step rule of a walk that homes on a goal cell, and the heading is undefined at p = g. Lib target: composite beside `nearer`.

```
.decl toward(p: Position, g: Position, d: Dir8) inline
toward(P, G, D8) :-
    dir_elem(D), nearer(D, G, P),
    ( axis_of(D, A), same_line(A, P, G), D8 = D
    ; dir_elem(D2), nearer(D2, G, P), diag_dirs(D8, _, D, D2)
    ).
```

Not: the strict quadrant of g about p (the diagonal half alone, with no cardinal fallback — af902bf9 `quad_mark`, 4938f0c2 `obj_quad`); the quadrant about the frame's midlines (`DiagPlacement.quadrant`); a heading read off contact (`Abut`); a heading fixed by a stored direction and carried along a walk (`Ray`, `Slide`); a heading turned by a rule at each step (212895b5 `turtle`); the fewest-hop route over an edge relation (`MinHops`).

Match: a rule that binds a direction from `nearer` with the goal as the nearer position, and either tests `same_line` on that direction's axis over the same two positions or pairs it with a second `nearer` on the same two positions through `diag_dirs`; and the walk form, where that direction feeds `neighbor` out of p in a recursive rule whose goal is carried in the head. Grep `nearer(` beside `diag_dirs` and beside `same_line`, then confirm the two positions are the same pair with the parser (`tests/test_ast_match.py`).

Survey: 2026-09-10 20:43 — the whole corpus.

Callers:
- 88bcf3b4 `toward` (L104–109): the king heading from the walker's cell p to the leg's goal g, the cardinal when p is in line with g and the pairing diagonal otherwise; `step` (L130) feeds it to `neighbor` in the recursive leg walk.
- dc433765 `axis_step` (L22–27) with `moved` (L29–33): the same king step as a Shift — per axis, `step_delta` toward the edge the target is strictly nearer, `ORIGIN` when aligned on that axis — composed onto the mover; `toward(Pm, Pt, D), neighbor(Pm, D, P)` states it directly, the aligned axis being the cardinal branch.

Negative evidence across the corpus: `nearer` appears in 41 solvers. The parser matcher (`.scratch/surveys/toward/2026-09-10-204303/match.py`) found `nearer` paired with `same_line` over the same two positions in 9 rules, paired with a second `nearer` on the same pair through `diag_dirs` in 3 rules, and its direction feeding `neighbor`/`step_delta`/`jump_delta` in 5 rules. No recursive rule outside 88bcf3b4 binds a direction from `nearer` and feeds it to `neighbor` with the goal carried in the head. Every hit besides the two above is listed below.

Near-misses:
- af902bf9 `quad_mark`, 4938f0c2 `obj_quad`: two `nearer` through `diag_dirs` with no cardinal fallback — the strict quadrant, named in Not.
- 2dd70a9a `target_side`: the set of cardinals the target lies toward, used only to filter which wall leg the walker turns onto; the heading comes from the leg structure (a heading read off contact), and no in-line or diagonal reading arises.
- 18286ef8 `look`: the Dir8 from the gaze's tile to the target's tile, read off `neighbor` — a heading read off contact; it asserts adjacency, which toward would drop.
- 28e73c20 `walk`: recursive, `nearer(D, B, P)` feeding `neighbor`, but D is the carried heading and `nearer` only tests short-of-the-margin; the heading turns by rule at the margin (the turtle exclusion).
- 29c11459 `pair`: `same_line` on `params.axis` and `nearer` over the same two marks orders two marks that the task puts on one line; the cardinal half alone, restricted to a stored axis, not a step rule.
- 1a07d186 `arrive`, 2faf500b `moved`: `axis_of(D, A)` on a task-fixed axis, `nearer` between a cell and a line, one `neighbor` step — the goal is a line, so the heading is a stored-axis cardinal (heading fixed by a stored direction).
- 5ffb2104 `room`, 6ad5bdfd `room`, 84ba50d3 `pierced`, 6e453dd6 `fill`, 54dc2872 `moves`: `same_line` plus `nearer` with the direction bound from `dir(Ky, D)`, `params.fall_dir`, a cast stop, or the L's bend — a test that a cell lies ahead along a fixed heading (`Ray`/`Slide` exclusion).
- 5207a7b5 `out`: `nearer(D, P, Q)` picks the paint color by which side of the bar the cell lies on — sidedness, not a heading.
- 35ab12c3 `leans`: `nearer` at a Dir8 tests sidedness about a diagonal line through p, not a step heading.

Spec: no interface or definition change from the sites. dc433765 reaches the operation as a Shift composed from per-axis `step_delta`s, and the Dir8 form serves it through one `neighbor` after the call, so the Dir8 interface stands; the aligned-axis `ORIGIN` branch is the cardinal branch under another name, so the definition stands. The cardinal-set reading in 2dd70a9a and the adjacent-only reading in 18286ef8 rest on one site each and are reported as caller-only. One clarification the near-misses suggest for the Not line: the cardinal half alone over a task-fixed axis (29c11459 `pair`), the mirror of the strict-quadrant exclusion it already names.

Reimplementations: none.
