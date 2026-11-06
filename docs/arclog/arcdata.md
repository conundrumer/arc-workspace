# arcdata
- The record file of a solver, `<task_id>.arcdata`, beside its [arclog](./arclog.md) file.
- The file is s-expressions, read by the arclog reader, with a closed set of head symbols. Prose is a quoted string. A name is one the arclog file declares, in that file's spelling: `&background`, `&one_run.value`, `$openings`, `$EachOpening`, `&background=$Derived`, `container`.
- The file's forms stand in this order:
    1. `representative`, if any
    2. `param`
    3. `exclude`
    4. `approximated` and `alts`, with the witnesses

## Header
- `(representative <task_id> [<name>])` marks a solver whose cases are the representative's, with the name of its case when it has one case of the representative's alts.
- The claims of a solver with a `representative` line belong to the representative's file, so that solver's arclog file holds no `INPUT` or `OUTPUT` block, and its forms stand at the top level and in its `ALT` blocks:
    ```
    ;; 0c786b71

    (DET &tile_d4 TileD4)

    (INIT &output_tiling Tiling
      ...)

    (ALTS $choice "how each tile's content derives from the input" $Lookup
      (ALT $Mirror
        (RULE &mirror
          ...)
        ...))
    ```

## Params
```
(param &background Color (0))
(param &fill_color Color (4))
(param &first_axis Axis (AXIS_V))
(param &recolor (Color Color)
  (3 1)
  (5 4))
(param &start_corner DiagDir (DIAG_TL) (DIAG_BL))
```
- A form gives the parameter's column types after its name, one type or a list, and then its rows, one per line where they do not fit on the form's line.
- A relation with a Position column is given as a grid, one row per line:
    ```
    (param &template Position
      (grid
        (1 1 1 1)
        (1 _ _ 1)
        (1 1 1 1)))
    (param &lookup_grid (number Position Color)
      (1 (grid
        (1 0 0)
        (0 0 0))))
    ```
- A grid's rows are of one length. Each cell gives one row: its position in the grid's frame, then its value. A relation with no column after the position marks its cells `1`. A `_` cell gives no row, and values before the grid fill the columns before the position. A grid of an Offset column marks one cell with `@`, as `@_` or `@1`, and a grid of a Position column marks none; a grid of a column that no form writes as Position or Offset may mark one cell or none. Each cell of a grid with a marked cell gives its offset from that cell in place of its position; the marked cell may be empty.
- A field of a frame of cells, or of a frame cut into equal tiles, is no stored value of its own: its `param` form is that of the `DET` that gives it.
- Every `param` form stands at the top level. The arclog block that declares the parameter says which cases read it. The rows of an open parameter, as [Open values](./arclog.md#open-values) gives it, are its open values, except where its `DET` ends in `ONE` marks over a set of rows: the rows are then what those marks choose from, and each open value is one model of them.
- A `param` form and a witness's `output` forms are records of a run, not its source: a run whose determination or whose output set disagrees with the entry is a fault.

## Alts
```
(exclude ($OneOpening $PaintBackground) "OneOpening & PaintBackground is left out: wherever it is defined, EachOpening & PaintBackground gives the same grid.")

(alts $openings
  (alt $EachOpening
    (witness two-openings variant $EachOpening
      (relaxed container)
      (separates "The top wall of the box has two openings, ...")
      (input (grid
        (0 0 0 0 0 0 0 0 0)
        ...
        (0 6 6 6 6 6 6 6 0)))
      (output concept undefined)
      (output $EachOpening (grid
        ...))
      (output $SideSpan (grid
        ...))))
  (alt $SideSpan
    (witness two-openings variant $EachOpening)))
```
- Each name in an `exclude` or `output` form, other than `concept`, is an alt or a reading of a line of the arclog file, and the reader refuses any other.
- An `alts` form is named as the arclog file's `ALTS` form or `DET_OR_RULE` line is. It holds an `alt` form per alt that has a witness, and an `alt` form holds that alt's witnesses and a nested `alt` form per combination with an alt of another `ALTS` form that has one. An `ALTS` form with no witness has no `alts` form.
- An `approximated` form is named for an output claim whose arclog block holds an `APPROXIMATED` form, and holds the witnesses on which the approximation differs from the rule.
    ```
    (approximated fill-interior
      (witness w2 variant other
        ...))
    ```

## Witnesses
```
(witness <id> <plausibility> <verdict>
  (relaxed <slug>)
  (separates "<the feature of the input on which the hypotheses differ, and each hypothesis's output>")
  (assign <relation> <row> ...)
  (input (grid
    <row>
    ...))
  (output <name> (grid
    <row>
    ...))
  (output (<name> ...) (<name> ...) (grid
    ...))
  (output <name> undefined))
```
- `<id>` is unique within the file.
- `<plausibility>` is `ordinary`, `variant`, `borderline` or `foreign`.
- `<verdict>` is `concept`, an alt's name, `any` or `other`. A witness that breaks an input claim holds `(relaxed <slug>)`.
- `assign` reassigns a relation for this witness, with rows in the form a `param` form takes. An `assign` of the output of a part of a `RIGID_DET` assembly, `&pair.footprint`, gives that output's rows, as [Semantics](./rigid.md#semantics) gives its columns: the key's columns, the pose, and the part's columns. An `assign` of the output of an instance's port, `&lex.rank`, gives rows to no reading: the stored reading of a `RULE_OR_DET` line on that port takes an `assign` of its own `DET`'s name alone, so a case that holds that reading faults on a witness that assigns the port.
- `output` gives each distinct output with the fewest names whose cases together give it; a name that fixes several alts is a list; `undefined` where those cases are undefined; several grids where the cases give one per model of a [One](./constraints.md#one) mark or a [Choose](./constraints.md#choose), as [The output set](./constraints.md#the-output-set) gives. With the verdict `other`, one `output` form with no name holds the annotator's judged grid.
- A grid's rows stand one per line, two spaces in from the form that holds the grid.
- A `witness` form with no body, `(witness two-openings variant $EachOpening)`, is the witness of that id given in full under an earlier alt.
