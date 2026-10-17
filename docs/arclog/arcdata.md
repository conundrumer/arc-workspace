# arcdata

The record file of a solver, `<task_id>.arcdata`, beside its [arclog](arclog.md) file. The arclog file holds the task's claims and structure, and this file holds the judgments and records on its cases: the witnesses that separate its cases, the cases it excludes, and the stored assignment the determination produced.

The file is s-expressions, read by the arclog reader, with a closed set of head symbols. Prose is a quoted string. A name is one the arclog file declares, in that file's spelling: `&background`, `&one_run.value`, `$openings`, `$EachOpening`, `&background=$Derived`, `container`.

The file's forms stand in this order:

1. `representative`, if any
2. `param`
3. `exclude`
4. `approximated` and `alts`, with the witnesses

## Header

- `(representative <task_id> [<name>])` marks a solver whose cases are the representative's, with the name of its case when it has one case of the representative's alts.

The claims of a solver with a `representative` line belong to the representative's file, so that solver's arclog file holds no `INPUT` or `OUTPUT` block, and its forms stand at the top level and in its `ALT` blocks:

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

A form gives the parameter's column types after its name, one type or a list, and then its rows, one per line where they do not fit on the form's line.

A relation with a Position column is given as a grid, one row per line:

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

Each cell gives one row: its position, then its value. A relation with no column after the position marks its cells `1`. A `_` cell gives no row, and values before the grid fill the columns before the position. A grid of an Offset column marks one cell with `@`, as `@_` or `@1`, and each cell gives its offset from that cell in place of its position; the marked cell may be empty, as in 0ca9ddb6's `&template`.

A parameter whose value is a table that a fixed derivation gives is written as the values the table derives from. A frame of cells is its extent on each axis, and a frame cut into equal tiles is the tile count, tile size and gap on each axis, under the name of the derivation:

```
(param &frame Position (Frame
  ((:A AXIS_V) (:N 6))
  ((:A AXIS_H) (:N 4))))
(param &tile_decompose (Position Position Position) (Division
  ((:A AXIS_V) (:Count 2) (:Size 6) (:Gap 1))
  ((:A AXIS_H) (:Count 1) (:Size 4) (:Gap 0))))
```

Every `param` form stands at the top level. The arclog block that declares the parameter says which cases read it. The rows of an [open](arclog.md#open-values) parameter are its open values.

A `param` form and a witness's `output` forms are records of a run, not its source: a run whose determination or whose output set disagrees with the entry is a fault.

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

An `alts` form is named as the arclog file's `ALTS` form or `DET_OR_RULE` line is. It holds an `alt` form per alt that has a witness, and an `alt` form holds that alt's witnesses and a nested `alt` form per combination with an alt of another `ALTS` form that has one. An `ALTS` form with no witness has no `alts` form.

```
(approximated fill-interior
  (witness w2 variant other
    ...))
```

An `approximated` form is named for an output claim whose arclog block carries an `APPROXIMATED` form, and holds the witnesses on which the approximation differs from the rule.

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
- `assign` reassigns a relation for this witness, with rows in the form a `param` form takes.
- `output` gives each distinct output with the fewest names whose cases together give it, as [Witness file](../handbook/solver-file.md#witness-file) gives them; a name that fixes several alts is a list; `undefined` where those cases are undefined; several grids where the cases give one per model of a [`ONE`](constraints.md#one) mark or a [`CHOOSE`](constraints.md#choose), as [Constraints](constraints.md#the-output-set) gives. With the verdict `other`, one `output` form with no name holds the annotator's judged grid.
- A grid's rows stand one per line, two spaces in from the form that holds the grid.
- A `witness` form with no body, `(witness two-openings variant $EachOpening)`, is the witness of that id given in full under an earlier alt.

## Example

The arcdata file of the task in the [arclog example](arclog.md#example).

```
(param &bg Color (0))
(param &recolor.value (Color Color) (3 1) (5 4))

(alts &bg
  (alt &bg=$Derived
    (witness bg=DominantColor variant &bg=$Derived
      (relaxed background)
      (separates "train 0 with 0 and 7 swapped: &bg=$Stored reads every cell as one object and fills the grid 1; &bg=$Derived reads the object of 3 and fills its box 1")
      (input (grid
        (7 7 7 7)
        (7 3 3 7)
        (7 3 7 7)
        (7 7 7 7)))
      (output &bg=$Stored (grid
        (1 1 1 1)
        (1 1 1 1)
        (1 1 1 1)
        (1 1 1 1)))
      (output &bg=$Derived (grid
        (7 7 7 7)
        (7 1 1 7)
        (7 1 1 7)
        (7 7 7 7))))))
```
