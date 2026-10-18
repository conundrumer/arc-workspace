# arcscene

The scene file of a solver, `<task_id>.arcscene`, beside its [arclog](arclog/arclog.md) and [arcdata](arclog/arcdata.md) files. The arclog file parses each input as far as solving needs and determines the task-wide values the program reads. This file factors the whole task into a set of facts over declared relations, with the clauses each way between those facts and the task.

The file is s-expressions, read by the arclog reader. A name the arclog file declares is imported with the arclog's meaning, and every other name is this file's.

## The two sides

A task is facts on two sides:

- **Task side**: the `ex_input` grid of each example, the accepted outputs of each train example, and the params as arcdata stores them.
- **Scene side**: the relations this file declares, each either task-wide, one set of rows per task, or per example, one set of rows per input, train and test alike.

Only a `parse` reads the task side, and the proposers over it.

A train example's accepted outputs are its `ex_output` grid, or, where a `tiebreak` alt gives several, the grids of its candidate, as [Alt outputs](handbook/solver-file.md#alt-outputs) gives. No declaration holds which grid of a candidate the task file lists first: 89565ca0's train 1 lists its output with two tied bars in one order, and its alt with them in the other.

The scene's built-in relations are sets of values that the driver supplies in generating and the observed data bounds in parsing:

- `ex`: the Example labels, `(ex ^E)` in every per-example key
- `color`: the colors, `(color *C)`
- `number`: the numbers, `(number *N)`
- `ident`: opaque labels, `(ident *Id)`, each of which carries nothing but its identity

The clauses between the sides run both ways. A **parse** derives a declared relation's rows from the task side. A **render** derives a task-side relation from the scene side. The factoring holds when parsing every input and rendering the result gives the input back, and rendering any instance the constraints admit and parsing it gives the instance back.

## Principles

- **The scene is the task, factored.** Each task the constraints admit has one instance, and each instance renders to one task.
    - A declaration takes a form in which two instances that render alike are one instance:
        - a set, where the members have no order
        - a `RIGID`, where a shape's pose is unobservable
        - a `Quotient` class, where the instance holds one value per class of its own members. 0dfd9992's `&class_color` gives a periodic pattern's color per class of the cells that whole periods take onto one another, in place of a tile and its origin.
        - the image as a set, where several values of a parameter, such as poses, offsets or maps of colors, give one image, and no `Quotient` over the parameter. 150deff5 holds each placement's cells, and 269e22fb each pair's colored chart.
        - a relation chosen only where the task shows it. 89565ca0's `&top` is chosen at each cell where two frames cross, in place of a stacking order.
    - The scene's instances are tasks the hypothesis solves, and Solves needs a defined output. So the file states each [constraint](#constraint) without which the round trip fails or the program's output on an instance's render is undefined, whether or not a claim states it. 0a1d4ef5 states that each input has a rectangle, and that each crossing of two bands holds one rectangle and no other. A constraint that no claim states is an input claim that the arclog file leaves out.
    - The file may state a constraint that every input holds where the round trip needs none. Such a constraint narrows the tasks the scene admits to the task's family, as 89565ca0's constraints that each frame's compartments tile its outline and that no frame lies beneath itself do. A constraint that the inputs hold only by an accident of the encoding is not stated.
    - A constraint may state what the arclog's determination needs from the observed data, as 0dfd9992's and 4cd1b7b2's constraints that some input shows `&hole` or `&bg` do.
- **The scene states what the task holds.** Each declaration and constraint states a property of the task, and none states a property of its encoding.
    - The file states no constraint whose only work is to keep one of several instances that render alike.
    - A bound is a relation over the task's cells or values, not a number: each side of the rectangle has a cell in the frame, not an extent of at least 3. Where the arclog's parse compares a count with a param, the bound compares the same count with that param: 0a1d4ef5's rectangle is at least `&min_side` long on each axis.
- **Each fact has one source.** The file states no fact that the solver or its other declarations give.
    - A declared relation holds nothing that follows from the other declared relations through the render clauses.
    - A declaration whose name the arclog file defines states no `parse`: it holds the value the arclog's determination gives, which the train pairs fix where a proposer gives several candidates.
    - `ex_output` is a [render](#render) target only where the instance holds what the inputs lose, as 150deff5's set of pieces and the colors they paint, which only the outputs show. Elsewhere the program gives the outputs.

## Program

```
;; aba27056

(INPUT background
  (CHOOSE &background
    (from (color *C))))

(INPUT container
  (CHOOSE &ink_color
    (for ((ex ^E)))
    (from (color *C)
          (NOT (&background C)))
    (parse (E C)
      (ex_input *E *P (:Col *C))
      (NOT (&background C))))

  (CHOOSE &extent
    (for ((ex ^E)
          (axis_elem ^A)))
    (from (number *N))
    (parse (E A N)
      (ex_input *E *P)
      (axis_elem *A)
      (frame_extent P A *N)))

  (INIT &cells Frame
    (key ((&extent ^E))
      (extent (A N)
        (&extent E *A *N))))

  ...)

(INPUT interior)

(OUTPUT fill-interior
  (CHOOSE &fill_color
    (from (color *C)
          (NOT (&background C))
          (NOT (&ink_color C)))))

(RENDER ex_input (E P Col)
  ...)

(ALTS $openings
  (ALT $EachOpening
    (INPUT container
      ...)
    (RENDER ex_input (E P Col)
      ...)))
```

The file's blocks are the arclog's `INPUT` and `OUTPUT` claims, by slug and in the arclog's order, with no text. A declaration stands under the claim whose text names what it holds. A block with nothing under it is a claim the scene satisfies by construction. `INIT` and `RULE` forms stand between the declarations, for the relations the declarations and the render read. A derived clause is a `RULE`, with `E` explicit where it is per example, since a `DET` is a value determined from the observed data. `RENDER` forms stand at the tail. `ALTS` and `ALT` are the arclog's forms, as [The `ALTS` form](arclog/arclog.md#the-alts-form) gives them: each `ALT` holds the blocks and tail forms its alt rederives, and each constraint that only the alt adds, which holds in the alt's cases alone. 0a1d4ef5's `$Overlap` adds that two rectangles that touch differ in color, and 351d6448's `$PanelAxisFromLines` that the lines across the other axis cut no frames. Each form reads a relation that an alt rederives as [The `ALTS` form](arclog/arclog.md#the-alts-form) gives.

An `ALT` may rederive, as a declaration with the same name and columns, a relation that the concept program derives by a `RULE`, and in that alt's cases the instance holds the relation. 351d6448's concept program derives each input's `&frame_count` and `&width` from one param for every input, and `$AnyPanelCount` and `$DividerWidthFromLines` declare them per input. `$PanelAxisFromLines` declares each input's `&axis`, and the end that time runs toward on each axis, and derives `&time` from them in place of `&time_dir`.

A case's scene is the declarations that its renders and the case's program read, directly or through the relations those declarations feed, and a declaration that none of them reads is no part of that case, nor is a constraint that reads such a declaration. Where the arclog file has no claims, the forms stand at the top level.

## Declaration

```
(CHOOSE &opening_cell
  (for ((ex ^E))
    (from (&side_cell E *P))
    (ANY))
  (parse (E P)
    (&opening *E *P)))
```

A declaration is arclog's `CHOOSE`, as [Choose](arclog/constraints.md#choose) gives it, with one more input, `parse`. Every `CHOOSE` of an arcscene file is a declaration, with a `never` or without one: a render must be a function of the instance, or the round trip fails, so the file has no other use for a `CHOOSE`. The rule of [Choose](arclog/constraints.md#choose) that a `CHOOSE` is written only for a pick with a `never` is a rule of the arclog file, and a scene does not follow it.

`parse` gives the chosen relation's rows from the task side. Its head sites name the relation's columns, the key's then the candidate's. The labels that `from` makes and the head names are the candidate's columns, and every other label that `from` makes is local to `from`: 0dfd9992's `&period` makes `P` and `K` in its `from`, and its head `(E A K)` makes `K` the candidate. In a declaration with no `parse`, each label that `from` makes is a column of the candidate. A declaration with no `parse` carries the name of an arclog relation, and that relation's definition parses it, as [Shared names](#shared-names) gives: `&background` and `&fill_color` above. The solver's own `CHOOSE` and `ONE` picks are imported names that a `parse` may read, and the file declares none of them. A `parse` is a determination, so it reads a chosen relation only where every model gives the same value, as [Semantics](arclog/constraints.md#semantics) gives for a `DET`.

A clause reads only relations that earlier forms declared, as arclog's [Program](arclog/arclog.md#program) rule gives, so a `parse` reads the relations this file derives from the declarations before it, as `&edge_color`'s reads `&edge_cell`.

A `RIGID` form is a container, and it chooses nothing itself. It groups declarations, with the relations an `INIT` or a `RULE` derives from them, that one D4 element moves together, and the instance holds the group up to pose. A reader reads each part as it reads a part of a [`RIGID_DET`](arclog/rigid.md), with `:Pose` before the part's columns, as `(&chart.cell_class (:Pose *G) *P *K)`, and a body that reads a pose gives the same rows in every frame of the group, as [The pose](arclog/rigid.md#the-pose) gives. A `parse` of a declaration inside a `RIGID` has `(:Pose G)` first in its head, as a `RENDER` into a part does: 269e22fb's `&extent` parses into `((:Pose G) A N)`.

A declaration is per example when its key holds an Example label, as an [instance](arclog/arclog.md#instance) is.

An instance of the scene is a model of the program, as [Semantics](arclog/constraints.md#semantics) gives.

```
(CHOOSE &edge_color
  (for ((&edge_cell ^E ^P))
    (from (color *C)
          (OR ((&ink_color E C))
              ((&background C)))))
  (parse (E P C)
    (&edge_cell *E *P)
    (ex_input E P (:Col *C))))
```

```
(CHOOSE &blank
  (for ((ex ^E))
    (from (&square_cand E *P))
    (ANY))
  (parse (E P)
    (ex_input *E *P *Col)
    (&bg (:C Col))))
```

A relation that holds any number of rows per key is a `CHOOSE` with the mark `(ANY)` beside its `from`. `(ANY)` is a mark of how many rows a model takes, as [`ONE`](arclog/constraints.md#one) is: each key row takes any subset of its candidates, none included, in place of exactly one, and a `never` names a pair of candidates that no row's subset holds together. A `CHOOSE` with no mark takes one candidate for each key row.

## Constraint

```
(ALL ((&opening_cell *E *P)
      (&opening_cell E (:P *Q))
      (&side_cell E (:P *R))
      (&side E *D)
      (perp_dir D *D2)
      (nearer (:D D2) P (:Q R))
      (nearer (:D D2) (:P R) Q))
     ((&opening_cell E (:P R))))
```

An `ALL` form that stands as a form, outside a clause, is a constraint on the instance: it holds as arclog's [Universal](arclog/arclog.md#universal) gives, and an instance where it fails is no instance of the scene. It reads any relation that earlier forms declared, chosen relations included, so it states what a declaration's `never` cannot: a fact about a relation derived after the declaration, or that some row exists. A constraint stands under the claim whose text it states, and otherwise under the block of the declarations it reads.

```
(ALL ((&period *E *A *K))
     ((&si.fundamental_period (:key E) A K)))
```

Where the arclog picks one completion of an input by a rule, the constraint that the round trip needs is over one instance. The file defines the rule's relation under the arclog's name, over the cells the instance renders, as [Shared names](#shared-names) gives, and the constraint states that the rule gives the instance's own value. In 0dfd9992, the arclog's `&si.fundamental_period` is the least period that no intact cell contradicts, and the file's `&si` reads the cells the damage leaves, so the constraint above states that the least period those cells show is `&period`.

## Demonstrated

A `DEMONSTRATED` form is arclog's, as [Demonstrated](arclog/arclog.md#demonstrated) gives, and stands between the declarations as an `INIT` does: it derives its relation and chooses nothing.

A nested task's scene declares no rule for an input. It declares the demonstrated pairs, and a constraint states that some rule of the `DEMONSTRATED` form confirms them, since the rules that apply to an inner task are the ones `confirmed` gives and no parameter stores them, as [Demonstrated choice](handbook/solver-file.md#demonstrated-choice) gives. 351d6448 declares each input's frames, and its constraint that `&shows_motion` holds at every input states that some rule confirms every checked step.

In a keyed form, the `DEMO_RULE` bodies read the key as [Demonstrated](arclog/arclog.md#demonstrated) gives. 351d6448's `&motion_shown` is keyed by `(&steady ^E)`, and each rule's `&prediction` makes `E`, as `(&steady *E *D *J)` does, so the form reads each prediction at its input.

## Render

```
(RENDER ex_input (E P Col)
  (&cells.cell (:key *E) *P)
  (&box2 E *B)
  (IF ((inside (:A P) B)
       (same_dist (:P1 P) (:P2 B))
       (NOT (&opening_cell E P)))
      ((&ink_color E (:C *Col)))
      ((&background (:C Col)))))
```

A `RENDER` form names its target, a task-side relation, then its head sites onto the target's columns, then its body over the scene side. `ex_input` is the target of the examples' grids, the test inputs among them. A param whose rows factor further is a target too, and its declarations stand under the claim that names it.

A render into a param that a `RIGID_DET` stores is compared with the param up to one D4 element, as [Semantics](arclog/rigid.md#semantics) gives for that form, and up to a renaming of its ids, as [Shared names](#shared-names) gives: the check holds where the reading that arcdata stores, in its own frame, equals the render's rows at one of the poses. 269e22fb's render into `&chart.cell_class` is such a render. Every other render into a param is compared with the param row for row.

## Shared names

A derived relation may be defined on both sides under one name. `&si` is a `Periods` over `&intact` in the arclog and over `&shown` here. A `parse` reads the arclog's definition, and `from`, `never` and `RENDER` read this file's. Two definitions under one name assert that the factoring makes them equal, and the check compares them row for row. That comparison needs one set of columns, so two definitions share a name only where they have the same columns. A scene relation that needs another column takes its own name: 0dfd9992's `&shown` has the `Id` column of a cell's class, which the arclog's `&intact` lacks.

An `Ident` column is compared up to a renaming of its ids: an id carries nothing of the value but its identity, as `Ident` in [lib-spec](lib-spec.md#types) gives, so the comparison holds where one renaming of the ids makes the two sides equal row for row.

A scene `RIGID` may share its name with an arclog `RIGID_DET`. The check then compares, row for row over the `:Pose` outputs, each part that both forms name, and a part that both name has the same columns on both sides. Either form may hold parts that the other lacks: 269e22fb's `&chart` holds `&extent` and `&frame` beside `&cell_class`, the one part of the arclog's `&chart`.

## Open

- **Lifted read of an instance.** A `parse` reads an instance of the arclog lifted, with `E` added. It reads 0dfd9992's `&si`, an unkeyed `Periods`, as `(&si.fundamental_period *E *A *K)`, and this file's `&si` is keyed by `E` and read as `(&si.fundamental_period (:key E) A K)`. It reads 269e22fb's `&occ`, an `Occurrences` keyed by a pose and a map of the chart's classes onto two colors, with `E` added to the key, as `(&occ.occurrence (:key *E *D *K *Col *K2 *Col2))`, and this file's `&occ` is keyed by `E` and the same fields. How the two compare row for row under one name is not stated.
- **One completion of a `CHOOSE`.** Where the arclog picks a completion by a rule, a [constraint](#constraint) over one instance gives the round trip. Where the parse is a `CHOOSE` with several models, none does. In 4cd1b7b2, an instance whose blanks admit several completions renders to an input whose `&fill` has several models, so the parse does not give the instance back. The constraint that excludes it compares the instance with the other completions of its input.
- **The period up to its multiples.** A pattern whose colors repeat at a divisor of its period renders as the pattern at that divisor does, so the two instances render alike, and no form makes them one instance. 0dfd9992 excludes the longer period by its `&si.fundamental_period` constraint. That constraint also excludes damage that leaves a shorter period uncontradicted, so it has work besides keeping one of the instances, and the file meets the [Principle](#principles) against such constraints only in the letter.
- **Train examples.** `ex` holds the train and the test examples alike, so no constraint can name a train example. 0dfd9992 and 4cd1b7b2 state that some input shows what a determination over the train pairs reads, which a test input alone may meet. Where no input shows the declaration whole, no such constraint exists: 269e22fb's chart needs a train output, since each input shows only a window of it.
- **Reach of `number`.** How far the numbers a declaration may take reach past the values the observed data shows, which [generators](generators.md#open-questions) leaves open too.
- **A param fixed by an accident of the outputs.** In 0a1d4ef5, every value of `&min_side` that is more than the shorter side of each solid noise region, and no more than the shorter side of any rectangle, renders alike. The arclog determines it by `ConstOutDim`, the output extent that every train pair shares, which is a count of bands and no part of the output claim, so no constraint states what that determination needs.
- **Open values per class.** 351d6448's `&time_end` is a param with open values, declared once per class of its values that some input shows: the end that time runs toward on each axis that some input's frames stack along. Its parse reads only where the train pairs fix the class, and that fails on an axis that only a test input stacks along.
