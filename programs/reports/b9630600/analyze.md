# b9630600

## Concept
- Fits every pair: the probe `work/task/b9630600/probe.py` gives each train output and the test output exactly. `shortest-joins` has a relational form: a facing pair is kept unless reachability over the facing pairs of strictly smaller gap links its two rooms.
- The rule as the generator applies it: the corridors form one spanning tree of the facing pairs with the least total gap, and where several such trees exist, any one of them. The concept file's `shortest-joins` keeps every pair that some such tree holds, so on a loop whose largest gaps tie it draws a loop.
- Witness `tied-loop`: four rooms in a loop, every gap 2. Stored assignment; breaks no scene claim; plausibility `borderline`; verdict `other` (a tree that leaves out one of the four corridors, any one). Invariant broken: in every input, the one loop of facing pairs (train0) has a single largest gap.

## Choice points
- `join-selection`: which facing pairs get a corridor
    - `concept`: a rule that measures each facing pair and selects by that measure
        - `measured-rule`: how the measure selects the pairs
            - `concept`: `shortest-joins`, the pairs of a minimum spanning tree
            - `$GapLimit`: replaces `shortest-joins`; joins each facing pair whose gap is at most `max_gap`; parameter `max_gap` = 7 (train2 joins a gap of 7, train0 leaves out a gap of 8); defined on every input. Fits every pair. Witness `four-room-loop`: stored assignment; breaks no scene claim; plausibility `ordinary`; verdict `concept`.
            - `$NearestJoin`: replaces `shortest-joins`; joins each room to the facing rooms at its smallest gap; defined on every input. Fails Fit on train1: the rooms at rows 10–15, cols 0–9 and rows 10–15, cols 15–22 (gap 5) are each nearer another room, so their corridor at rows 11–14 is not drawn. It also fails test0.
        - `join-weight`: what measures a facing pair
            - `concept`: the gap
            - `$AreaWeight`: replaces the measure in `shortest-joins` with the gap times the count of lines in the corridor's span; defined on every input. Fits every pair. Witness `four-room-loop`: stored assignment; breaks no scene claim; plausibility `ordinary`; verdict `concept`.
    - `$AllFacing`: replaces `shortest-joins`; joins every facing pair; no parameter; defined on every input. Fails Fit on train0: it joins the rooms at rows 4–10, cols 2–9 and rows 19–22, cols 4–7 (gap 8) with a bar at cols 5–6, rows 11–18.
    - `$NearestPerSide`: replaces `shortest-joins`; joins each room to the nearest facing room on each of its four sides; defined on every input. Fails Fit on train0: the room at rows 4–10, cols 2–9 has the room at rows 19–22, cols 4–7 as its nearest facing room below, so it draws the bar at cols 5–6, rows 11–18.
- `corridor-span`: which lines a corridor covers
    - `concept`: the lines the two interiors share (`corridor-shape`)
    - `$NarrowerSpan`: replaces `corridor-shape`; the corridor covers every line of the interior of the room whose interior is narrower; undefined on an input where two facing rooms have interiors of one width at different lines. Fits every pair. Witness `staggered-pair`: stored assignment; breaks no scene claim; plausibility `variant`; verdict `concept`. Invariant broken: in every input, the interior spans of each facing pair nest, one inside the other.
- `facing-blocking`: what may stand between two facing rooms
    - `concept`: only `background` (`facing-pair`)
    - `$IgnoreBlocking`: replaces `facing-pair`; two rooms face when their interiors share lines on one axis, whatever stands between them; defined on every input. Fits every pair. Witness `room-in-band`: stored assignment; breaks no scene claim; plausibility `borderline`; verdict `concept`. Invariant broken: in every input, the rooms that stand in the band between two rooms that share interior lines link those two rooms through facing pairs.
- `background`
    - `concept`: stored, 0
    - `background=DominantColor`: the color with the most cells in the input; undefined where two colors tie for the most cells. Fits every pair. Witness `background=DominantColor`: stored assignment; breaks `hollow-rooms` (the field is 1, not `background`); plausibility `variant`; verdict `derived`. Invariant broken: every input's field is 0.
- `room_color`
    - `concept`: stored, 3
    - `room_color=RarestColor`: the color with the fewest cells in the input; undefined where two colors tie for the fewest cells. Fits every pair. Witness `room_color=RarestColor`: stored assignment; breaks `hollow-rooms` (the walls are 2, not `room_color`); plausibility `variant`; verdict `derived`. Invariant broken: every input's walls are 3.
- `measured-rule` & `corridor-span`, `measured-rule` & `background`, `measured-rule` & `room_color`, `join-weight` & `corridor-span`, `join-weight` & `facing-blocking`, `join-weight` & `background`, `join-weight` & `room_color`, `join-selection` & `corridor-span`, `join-selection` & `facing-blocking`, `join-selection` & `background`, `join-selection` & `room_color`, `corridor-span` & `facing-blocking`, `corridor-span` & `background`, `corridor-span` & `room_color`, `facing-blocking` & `background`, `facing-blocking` & `room_color`, `background` & `room_color`: the two branches' changes applied together
- `measured-rule` & `join-weight`: the selection rule of the `measured-rule` branch applied to the measure of the `join-weight` branch
    - `$GapLimit` & `$AreaWeight`: joins each facing pair whose gap times span is at most a stored limit; fails Fit, since train0 leaves out a pair of 16 (rows 11–18, cols 5–6) and train2 joins a pair of 35 (rows 3–7, cols 16–22).
    - `$NearestJoin` & `$AreaWeight`: joins each room to the facing rooms of its smallest gap times span; fails Fit on train0.
- `measured-rule` & `facing-blocking`: the selection rule of the `measured-rule` branch over the facing pairs of the `facing-blocking` branch
    - `$GapLimit` & `$IgnoreBlocking`: joins every pair with shared interior lines and a gap of at most 7; fails Fit on train0, where it joins the rooms at rows 4–10, cols 13–17 and rows 18–23, cols 10–20 (gap 7) across the room at rows 12–16, cols 12–18.

## Open parameters
none

## Not formed
- The corridor's wall lines placed elsewhere (inside the shared span, or on the boxes' outer lines): the pairs fix the walls on the outermost shared interior lines, and the spans of 2 lines (train0, rows 20–21) and 1 line (train2, col 11) fix the solid bar.
- A choice among tied corridors in a loop: the generator leaves it free, so it is a tiebreak and gives no case; the concept witness `tied-loop` records it.
- The gap measured as the distance between the facing walls in place of the count of cells between them: the two differ by 1 on every pair, so they order the pairs alike and give one model.
- `background=SharedColor`, `room_color=SharedColor`: each gives both colors of every input, where the program reads one color.
- `room_color` or `background` by `ChangedColor`, `UnchangedColor`, `VanishedColor`, `OutNewColor`: no color of any pair keeps all its cells, changes all its cells, leaves the output, or is new in it, so each gives no value.

## Tickets filed
none
