# f3e62deb

## Concept
- Fits every train and test pair (`work/task/f3e62deb/probe.py pairs`). The probe slides and labels in plain Python because no Souffle binary is installed (see `progress-analyze.md`).
- `direction_of_color` is one-to-one, and the determination reads the evidence's inputs, test inputs included. The train pairs fix `8` → right, `4` → down and `6` → up. Test 1's `3` is in no train pair, so it takes the one direction left over: left. Without the one-to-one constraint, the table has no entry for `3` and fails Fit (`$AnyTable`).
- The generator places one 3×3 ring of one color on a 10×10 field of `0` and moves it to the edge its color names. The concept's rule `slide-to-edge` states exactly this, with nothing approximated.
- Undefined where the content holds more than one color, holds none, or has a color with no entry.
- Witnesses with verdict `other`: none.

## Choice points
- `moving-unit`
    - `concept`: all non-background content moves as one rigid body
    - `$PerObject`: replaces `one-object` and `slide-to-edge`. Each 8-connected object slides toward its own color's heading. Objects with one heading fall together as rigid bodies, each stopping at the edge or at an object that has already stopped. Parameters `background`, `direction_of_color`. Undefined where an object holds two colors or a color with no entry, or where objects with different headings land on a common cell. Fits every pair. Witness `two-rings-one-color`: breaks `one-object`, stands at the stored assignment, plausibility `variant`, verdict `$PerObject`. It breaks the invariant that every input holds exactly one object.
    - `$PerColor`: replaces `one-object` and `slide-to-edge`. Each color class is one rigid body that slides toward its color's heading until it touches the edge. Parameters `background`, `direction_of_color`. Undefined where a color has no entry or two classes land on a common cell. Fits every pair. Witness `rings-of-two-colors`: breaks `one-object`, stands at the stored assignment, plausibility `variant`, verdict `$PerColor` (its output group is `$PerObject`, `$PerColor`). It breaks the invariant that every input's content is one object of one color.
- `object-orientation`
    - `concept`: the object arrives unchanged
    - `$Reflected`: replaces `slide-to-edge`. The object arrives mirrored across the axis perpendicular to its heading: left to right for a horizontal heading, top to bottom for a vertical one. Parameters `background`, `direction_of_color`. Undefined where the concept is. Fits every pair, because the ring maps to itself under every reflection. Witness `asymmetric-object`: breaks `object-shape`, stands at the stored assignment, plausibility `variant` (`shape` is a scene parameter, so a variant task routinely draws another shape), verdict `concept`. It breaks the invariant that every object is the 3×3 ring.
- `background-source`
    - `concept`: `background` stored, `0`
    - `background=DominantColor`: replaces the stored `background` with the color that has the most cells in the input, as DominantColor gives it, ties included. Reads `direction_of_color`. Undefined where the input ties for the most cells, and where the concept is undefined at the derived background. Fits every pair. Witness `background=DominantColor`: a field of `8` holding a `4` ring. It breaks `one-object` (the field is not `background`) and stands at the stored assignment. Plausibility `variant`: a variant task that swaps `0` and `8` has a field of `8`. Verdict `background=DominantColor`. It breaks the invariant that every input's field is `0`.
    - `background=RarestColor`: replaces the stored `background` with the color that has the fewest cells in the input. Fails Fit at train0: it derives `8`, so the content is the `0` cells, and `0` has no entry.
- `direction-table`
    - `concept`: `direction_of_color` is one-to-one from the evidence's object colors to the four directions
    - `$AnyTable`: drops the one-to-one constraint. Any color-to-direction table, stored from the train pairs alone. Undefined on an input whose color is no key. Fails Fit at test1, whose key `3` is unseen.
- `stop-rule`
    - `concept`: slide until the object touches the edge on its heading
    - `$FixedShift`: replaces `slide-to-edge` with a translation of a stored `shift` cells toward the heading. Parameters `background`, `direction_of_color`, `shift`. Fails Fit at train2: train0 moves its `8` ring five cells and train2 moves its `8` ring four, so no value fits both.
    - `$StoredTarget`: replaces `slide-to-edge` with a stored line per color, `target_of_color`, on which the object's leading side lands. Fails Fit at test1: `3` is no key, and no one-to-one constraint gives its line.
- `moving-unit` & `object-orientation`, `moving-unit` & `background-source`, `moving-unit` & `direction-table`, `moving-unit` & `stop-rule`, `object-orientation` & `background-source`, `object-orientation` & `direction-table`, `object-orientation` & `stop-rule`, `background-source` & `direction-table`, `background-source` & `stop-rule`, `direction-table` & `stop-rule`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Direction from the object's place: no relation of place gives the headings. train1 (`4`, rows 2–4, cols 3–5) goes down, while train2 (`8`, rows 3–5, cols 3–5) goes right from one row lower. train3 (`6`, rows 3–5, cols 4–6) goes up although it is no nearer the top than the right.
- Direction from an order of the colors: colors have identity and no other properties.
- `background` from SharedColor: a `@derive` run reads one input, where every color it holds is shared, the object's color included, so the run gives two backgrounds. From UnchangedColor, VanishedColor, ChangedColor or ChangedPairs: each reads outputs, which a `@derive` run does not have. From OutNewColor or AnyOutNewColor: no output holds a new color.
- Moving to the edge farthest from the object, or nearest to it: train3's ring is 3 from the top and 4 from the bottom and left, yet goes up, while train0's ring is 2 from the top and left and goes right.
- Alternate outputs: the task gives no `alt`.

## Tickets filed
- none
