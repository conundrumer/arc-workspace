# b0c4d837

## Concept
- Fits every pair. Each claim it makes has a relational form, and no witness has the verdict `other`.
- The concept reads `fill_order` at its open values (snake, clockwise spiral). Those values part at the fifth rank, so the concept case is undefined on a cup with five or more empty rows (`count-past-four`), where the judged output is the snake's.
- The generator's rule, as the concept restates it: the count is the height of the wall color's rows, less the floor row, less the height of the liquid. On every input with a cup of equal walls, that count is the concept's count. The concept's rule approximates nothing.

## Choice points
- `render`: how the count becomes the output grid
    - `concept`: the count's first cells, in an order over a fixed frame, take the mark color; the other cells take the background
        - `order`: the order of the frame's cells
            - `concept`: a stored order, `fill_order` (open)
            - `$SnakeOrder`: replaces `output-frame` and `lay-marks` and the parameter `fill_order`. The program derives a boustrophedon order over an `out_dim` × `out_dim` frame: along the first line, then back along the next. Its parameters are `out_dim` (3) and `order_d4` (`D4_ID`), which give the start corner and the first axis. The model is undefined where the count exceeds the frame's cell count. It fits every pair. Witness `count-past-four` (a cup with five empty rows) stands at the stored assignment, breaks no scene claim, is `ordinary`, and has the verdict `$SnakeOrder`.
            - `$SpiralOrder`: replaces `output-frame` and `lay-marks` and the parameter `fill_order`. The program derives a spiral order over an `out_dim` × `out_dim` frame that runs along the border and then turns inward. Its parameters are `out_dim` (3) and `order_d4` (`D4_ID`), which give the start corner and the sense. The model is undefined where the count exceeds the frame's cell count. It fits every pair. Witness `count-past-four` stands at the stored assignment, breaks no scene claim, is `ordinary`, and has the verdict `$SnakeOrder`.
        - `mark-color`: the color of the marks
            - `concept`: the liquid's color, `fluid_color`
            - `$MarkColor`: replaces `lay-marks` with marks in a stored `mark_color` (8), apart from the liquid's color. It fits every pair. Witness `mark-color` (a cup with three empty rows) stands at the assignment `mark_color` = 2, breaks no scene claim, is `ordinary`, and has the verdict `concept`.
        - `background`: the output's background color
            - `concept`: stored `background` (0)
            - `background=DominantColor`: derives `background` as the input's commonest color. The model is undefined where two colors tie for commonest. It fits every pair. Witness `background=DominantColor` (a cup whose liquid outnumbers the background) stands at the stored assignment, breaks no scene claim, is `ordinary`, and has the verdict `concept`.
    - `$CountTable`: replaces `output-frame` and `lay-marks` and the parameters `fill_order` and `background` with a stored lookup table `count_table`: count → output grid, with the train counts 1–4 as keys. The model is undefined on a count that is not a key. It fits every pair, because the test count 1 is a train key. Witness `table-entry` (a cup with two empty rows) stands at the assignment that changes `count_table`'s entry for 2 to a grid with a mark at (0,0) and one at (1,1). It breaks no scene claim, is `ordinary`, and has the verdict `concept`.
- `rim`: the row that the count starts from
    - `concept`: the topmost row that holds `wall_color`
    - `$LowerRim`: replaces `count-empty-rows` with a count from the topmost row that holds `wall_color` in both the leftmost and the rightmost wall column, which is the top of the shorter wall. It fits every pair. Witness `uneven-rim` (a cup whose left wall rises two rows above its right wall) stands at the stored assignment. It breaks the scene claim `cup` (walls of equal height), is `foreign`, and has the verdict `concept`. The invariant of the inputs it breaks is that both walls of every input's cup have the same height.
- `liquid`: how the liquid is found
    - `concept`: the cells of stored `fluid_color` (8)
    - `fluid_color=RarestColor`: derives `fluid_color` as the input's rarest color. The model is undefined where two colors tie for rarest. It fits every pair. Witness `fluid_color=RarestColor` (a wide cup that holds more liquid cells than wall cells) stands at the stored assignment, breaks no scene claim, is `ordinary`, and has the verdict `concept`.
    - `$LiquidAnyColor`: replaces the parameter `fluid_color` with the color of the cells directly above the floor between the walls, read on each input. The model is undefined where those cells differ in color. It fits every pair. Witness `liquid-color` (a cup whose liquid is color 2) stands at the stored assignment. It breaks the scene claim `liquid` (its color is `fluid_color`), is `variant`, and has the verdict `$LiquidAnyColor`. The invariant of the inputs it breaks is that every input's liquid is color 8.
- `render` & `rim`, `render` & `liquid`, `rim` & `liquid`, `order` & `rim`, `order` & `liquid`, `mark-color` & `rim`, `mark-color` & `liquid`, `background` & `rim`, `background` & `liquid`, `order` & `mark-color`, `order` & `background`, `mark-color` & `background`: the two branches' changes applied together

## Open parameters
- `fill_order`: snake (0,0), (0,1), (0,2), (1,2), (1,1), (1,0), (2,0), (2,1), (2,2); clockwise spiral (0,0), (0,1), (0,2), (1,2), (2,2), (2,1), (2,0), (1,0), (1,1)

## Not formed
- A derived `wall_color`: no built-in derivation gives 5 on each input alone, because 5 is neither the commonest nor the rarest color of any input. `SharedColor` gives every color of an input. A program reading of the wall needs the cup found first by a color that no claim gives.
- `fluid_color` or `background` by `SharedColor`, `VanishedColor`, `OutNewColor`, `AnyOutNewColor`, `ChangedColor` or `UnchangedColor`: on one input alone, with `ex_out` empty, each one gives either every color of the input or no color. So the branch has no single value on any pair, and it fails Fit at train0.
- An output size by `ConstOutDim` or `ConstOutDimAxis`: each one reads `ex_out`, so it gives no value on one input alone. In the concept, the frame follows from the cells of `fill_order`.
- The count as the cup's empty interior cells divided by the interior width: a quotient counts nothing that the task has, so it has no relational form. It also agrees with the row count wherever the liquid's top is level.
- The count as the rows above the liquid, counted from the grid's top: fails Fit at train0 (four rows above the liquid, three marks).
- A row-major or a column-major fill order: fails Fit at train1 (the fourth mark is at (1,2)).
- A fill order from another corner or in the other sense: each is a value of `order_d4` under `$SnakeOrder` or `$SpiralOrder`, and a value of `fill_order` under the concept, so neither is a branch of its own.

## Tickets filed
- none
