# Rigid

The `RIGID_DET` form, a rigid determination, is the arclog form for parameters that a task states in a frame of their own. The parts of one assembly are read off each instance in the observed data and compared up to one D4 element per instance, and the program reads them only through a placement of the whole assembly.

## Form

```
(DET &glyph
  (&bbox.cell (:key (:E *K_e) (:P *K_p)) (:P *P2))
  (&bbox.box (:key (:E K_e) (:P K_p)) *B)
  (inside (:A P2) B)
  (relative (:Base B) (:X P2) (:X_rel *P)))

(DET &launch
  (&bbox.box (:key (:P *P_l)) *B)
  (inside (:A P_l) B)
  (relative (:Base B) (:X P_l) (:X_rel *P)))

(DET &aim
  (&pick.representative (:a *E (:P *P_l)) (:b E (:P P_l)))
  (&launch_cell E P_l *D))

(RIGID_DET &marker
  (&glyph *P)
  (&launch *P)
  (&aim *D))

(RULE &launch2
  (&occ.occurrence (:key (:D *D2) *Col) (:P *A))
  (&marker.launch (:Pose D2) (:P *P_l))
  (compose A (:B P_l) (:C *P))
  (&marker.aim (:Pose D2) *D))
```

142ca369: each marker launches a diagonal ray. A marker is an L-triomino with a cell the ray leaves from and the diagonal it heads along, and the markers of one input stand in different orientations. The determination reads one representative marker: `&pick` takes one launch cell that the training outputs show, and `&bbox` is the box of that marker's cells.

- The `DET` forms are tables over the observed data that read the representative marker, with its cells in the frame of its box.
- Each atom of the form is a part, and its sites are that part's reading. The program reads the part under the atom's relation name in the form's path: `&marker.glyph`, or `&marker.bbox.box` for a part that reads `&bbox.box`. A part that reads `input`, `ex_input`, `ex_output` or a lib relation has no output.
- A form with no `instance` clause has one instance. Its parts read no instance label, and each part's `DET` table is that one instance's reading.
- In a form with an `instance` clause, a part whose atom holds no label of that clause is a frame part: no instance's reading holds it, and the other parts place it, as [Semantics](#semantics) gives.

```
(DET &member
  (&bbox.cell (:key *E (:Col *C) (:Id *Id2)) (:P *P2))
  (&bbox.box (:key E (:Col C) (:Id Id2)) *B)
  (inside (:A P2) B)
  (relative (:Base B) (:X P2) (:X_rel *P))
  (&color_id.class (:a C) *Id))

(RIGID_DET &piece
  (&member *Id *P))
```

150deff5: a marked region packs with two pieces, a 2×2 block in one color and a 1×3 line in another. The determination reads one lone piece region of each color in a training output, and `&member` gives each piece's cells under the id of the color it paints.

- The outputs hold `:Pose` and then the part's columns, so a read at one pose and one `Id` places one piece: `(&piece.member (:Pose ^D) ^Id (:P *S))`.

A form may also hold an `instance` clause, and a `key` clause:

- `instance` is written as a [key clause](arclog.md#instance) is, and one of its rows is one instance. Each atom inside `instance`, after its body, is a part, and it reads the instance's labels, other than a frame part. Each other label of the part, one that neither the instance clause nor the key gives, is the part's own, made at a site of the part's atom.
- `key` is a key clause with the meaning it has in an `INIT`: each key row is an independent assembly, aligned on its own and posed on its own, other than where a key column holds the assembly's own Idents, as [Semantics](#semantics) gives. A form with no `key` has one assembly. The outputs hold the key's columns first, as an instance's outputs do.
- Where a form has a `key` clause, the rest of the form stands inside it, after its body: the `instance` clause where the form has one, and the parts otherwise. The key's labels are in scope there, as they are in the keyed inputs of an `INIT`.

## Semantics

An instance's reading is, for each part that reads an instance label, the part's rows at that instance. A model of one assembly is a common reading, one set of rows per part, together with, for each instance, the D4 elements that, each with one one-to-one renaming of the assembly's own Idents, take the common reading of those parts onto the instance's reading. One element and one renaming act on every part of an instance at once. The common reading also holds the rows of each frame part, in the frame of the assembly, and `&marker.<part>` gives their image at each pose as it does for any part.

An element acts by type. A `Box`, `Position` or `Offset` goes through `apply`, and a `Dir`, `DiagDir` or `Dir8` goes through the direction actions. An `Axis` or `DiagAxis` goes through the swap the element induces on its directions. A `Sense` stays as it is under a rotation and reverses under a reflection. A renaming moves the assembly's own Idents. Every other type is left as it is.

An `Ident` column of a part or of the key is the assembly's own where no label at it stands at an `Ident` site outside the assembly's parts and key and the relations that take their types from them, other than a site in the body of a determination relation that a `key` or `instance` clause of the assembly reads, or in the body of a determination relation that one of those reads, at any depth. Those bodies give each instance its reading and its key, which the model takes up to the renaming. Every other `Ident` column is a plain `Ident`, and a renaming leaves it as it is.

Where a key column holds the assembly's own Idents, the renaming of an instance also takes the key of the common reading onto the instance's key. Two instances whose readings are images of each other under one D4 element and one renaming that takes the key of the one onto the key of the other stand at one key: the form has one assembly per class of such instances, and each output gives that assembly one key, the key of the class's instance whose reading is least by content. Where instances of two classes stand at one key row, the assembly has no value.

If the instances of an assembly admit no common reading, the assembly has no value. Where a common reading `R` exists, every image of `R` under D4 is one too. The choice among them is the assembly's frame. Nothing in the task makes that choice, and the outputs are defined so that no read observes it.

The form has two kinds of output:

- `&marker.<part>` holds the key's columns, `:Pose`, and then the part's columns, other than those at a label of the `instance` clause. At each D4 element `D`, it holds the image of the part's common reading under `D`. One pose read across several parts reads one placement of the whole assembly.
- `&marker.pose` holds the key's columns, the instance's columns and then `:Pose`: the elements that take the common reading onto that instance's reading. An instance has several where the assembly has a symmetry.

## The pose

A change of frame relabels every pose of an assembly in the same way, by composing each with one element. The value of a single pose depends on the frame, and the relations between poses do not. So a `:Pose` column has the type Pose of its assembly, and a Pose label stands only at these sites:

- A `:Pose` column of the same assembly. Two reads that join on one pose label read one placement.
- A column of a derived relation, of an instance's key or of an instance's input, which then takes the type.
- `=` and `!=`.
- `d4_elem`, whose column takes the type of its label, since every D4 element is a pose.
- `pose_difference(a, b, d)`, where d is the element that takes the placement at pose a onto the placement at pose b. It is the same in every frame, a D4 value in the grid frame, and it is the one way from a Pose to a D4 value. A label of no type at a or b takes the Pose type of the other labels at a and b, where their types meet in a Pose type. A label at a or b that has a type other than a Pose type is refused, and so is a label that has no type once its form is complete.

Under a `key` clause each key row is an assembly of its own, and the Pose type of a pose read is that assembly's at the key labels the read gives, so two pose reads meet only where they read the same key labels. A pose of a keyed assembly that reaches a column of a derived relation, of an instance's key or of an instance's input takes the Pose type at the key that another column of the same relation holds, where the pose label stands at the pose column and the key's label at that other column. A read that binds a label at the key column and another at the pose column gives the second the Pose type at the first. A join of poses at two different key labels is refused.

The checker refuses a Pose label at any other site. So `(d4_identity D)` and `(c4_elem D)` on a pose, which would test a single pose, are type errors, and every body that reads a pose gives the same rows in every frame of its assembly.

The assembly's own Idents have a type of their own, and a label at such a column stands only at these sites:

- A column of the assembly's own Idents of the same assembly.
- A column of a derived relation, or a column of an `INIT` form's key, input or output that its component types by a type parameter, which then takes the type.
- `=` and `!=`.

A site in the body of a determination relation that an `instance` clause reads is not counted, since that body gives the instance its reading. In 269e22fb, `&cell_class` joins `&class_id.class`, and in 150deff5, `&member` joins `&color_id.class`. A label that stands at any other `Ident` site makes the column a plain `Ident`, a later read of the part included: in 150deff5, `&piece_color` reads `&piece.member`'s `Id` in `&output`. The checker refuses nothing for it.

## Subgroups

A task may admit an assembly in only some orientations. For example, the instances stand rotated but never mirrored. The program says so by comparing each placement with the training instances' poses:

```
(RULE &launch2
  (&occ.occurrence (:key (:D *D2) *Col) (:P *A))
  (&marker.pose (:Pose *D0))
  (pose_difference (:A D0) (:B D2) (:D *T))
  (c4_elem (:D T))
  (&marker.launch (:Pose D2) (:P *P_l))
  (compose A (:B P_l) (:C *P))
  (&marker.aim (:Pose D2) *D))
```

A placement is kept where its difference from a training instance's pose is a rotation. The clause reads the two poses only through `pose_difference`, so it gives the same rows in every frame. When a training output shows a mirrored instance as well, the training poses cover both hands, and the same clause keeps every placement. A narrowing to any subgroup of D4 is written in the same way, with `sym_member` at a `Sym` parameter in place of `c4_elem`. Where no training input shows an instance outside the subgroup, the narrowing is an alt, and an instance outside it is the witness.

## What it replaces

- The Souffle `RIGID` block, with its placed names `<block>_<rel>` and the lint category that keeps them out of reach. A stored part that the block's determination does not write is a frame part.
- The runner's comparison of a chart instance with the stored value up to pose. With an `instance` clause, the form also replaces the determination that picks one instance as the chart.

## Evidence

A survey of the solvers that do not use the Souffle `RIGID` block, for stored data that a task states in a frame of its own:

- In 4522001f, ad38a9d0 and b27ca6d3, the instances stand in several orientations. Each solver closes a stored shape over D4 or C4 by hand, and takes one instance as the chart through `Quotient`. 4522001f restricts to rotations, and ad38a9d0 holds an open choice among `SYM_1`, `SYM_C4` and `SYM_D4`. Each restriction is a narrowing against the training poses.
- 1e5d6875 lists one row of its step table per orientation the observed data shows, and searches C4 by hand. Its stored `rot` is a pose difference, which is already frame-free.
- 3f23242b, 3ac3eb23, 8403a5d5, 7447852a, 3618c87e, 0becf7df and 08573cc6 store a stamp, and the direction attached to it, separately. Every instance in their observed data has one pose. A `RIGID_DET` makes the two one assembly, and no output changes.
- No solver stores a shape in one orientation where its inputs show the shape in several. Where the inputs do, the solver finds the template in the input it runs on.

Values that look posed and are not:

- A D4 value that is the turn between two placements, such as 291dc1e1's `rot` and 3e980e27's `stamp_d4`.
- A symmetry of the grid, or the transform of a tile in a tile arrangement.
- An orientation the task distinguishes. In 626c0bcc each orientation of the L-triomino paints its own color, and in ed74f2f2 two mirrored keys name different colors.
- A stored shape that is symmetric under D4.

Note from principal: It seems RIGID was not used as often as it should have because its gloss in patterns.md was unclear. 

## Implementation

The Souffle backend takes one instance's reading as each assembly's frame. For each instance, it finds the elements that take the frame's reading onto that instance's reading over every part at once, as `Agreement` does for one cell set with its D4 images as the correspondences. When every instance has such an element, it writes `&marker.<part>` as the closure of the frame's reading over D4, and `&marker.pose` as the elements it found. An element is found for an instance where the image of the frame under it, at the part columns that are the assembly's own Idents, maps onto the instance's reading by one one-to-one renaming of those Idents, the same renaming at every part. The choice of the frame instance is arbitrary, and the Pose type and the own-Ident type of [The pose](#the-pose) make it unobservable.
