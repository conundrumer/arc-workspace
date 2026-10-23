# arclog

The language of solver programs. An autoregressive language model emits a program as a stream of tokens from closed sets, never text, and the program compiles to Souffle over the lib. The design keeps the constructs few, infers everything the engine can infer, and makes the determination give only task-wide data by construction.

A solver is two files. `<task_id>.arclog` holds the task's claims and structure: the program, its determination, its instances and its alts. `<task_id>.arcdata` holds the judgments and records on its cases: the witnesses, the excluded cases, and the stored assignment, as [arcdata](arcdata.md) gives it. The names the arclog file declares are the keys the arcdata file uses.

The stream has two renderings, and both are projections of it:

- The **program form** shows the program to a solver reader.
- The **trace form** shows one decode of the stream to a reader debugging the synthesis: the program with the engine's forced tokens, and on request the language model's top-k tokens at each decision.

Both are stored as s-expressions, read by one fixed reader. An infix view of the program form is printed on request and is never stored or parsed.

## Program

```
;; aba27056

(INPUT background "every cell outside the container is &background"
  (DET_OR_RULE &background DominantColor))

(INPUT container "one object of one color other than &background is the outline of a rectangle, with one side broken by one opening: a run of background cells along that side's line, which does not include the corners of the rectangle"
  (INIT &box BoundingBox
    (cell (P)
      (input *P *Col)
      (NOT (&background (:C Col)))))

  (RULE &corner
    (&box.box *B)
    (input *P)
    (inside (:A P) B)
    (same_corner (:P1 P) (:P2 B)))

  (RULE &opening
    (&box.box *B)
    (input *P *Col)
    (&background (:C Col))
    (inside (:A P) B)
    (same_dist *D (:P1 P) (:P2 B))
    (NOT (&corner P)))

  (INIT &runs Connectivity
    (node (P)
      (&opening *P)))

  (INIT &one_run Singleton
    (member ((:v Id))
      (&runs.component *Id))))

(INPUT interior "the cells strictly inside the rectangle are all &background")

(OUTPUT fill-interior "every cell strictly inside the rectangle becomes &fill_color"
  (DET &fill_color AnyOutNewColor))

(OUTPUT fill-opening "every cell of the opening becomes &fill_color"
  ...)

...

(OUTPUT rest-kept "every other cell keeps its input color")

(ALTS $openings "what the box does when its outline has more than one opening" $OneOpening
  ...)

...

(RULE &undefined
  (NOT (&one_run.value)))

(RULE &output
  (input *P (:Col *C_in))
  (NOT (&undefined))
  (IF ((&painted P))
      ((&fill_color (:C *Col)))
      ((= Col C_in))))
```

A program is `INPUT` and `OUTPUT` blocks in dependency order, then `ALTS` forms, then the tail. A block is a claim: its slug, its text, then the forms that serve it. A relation stands under the first claim that reads it, and a parameter under the first claim whose text names it, as `&background` or `&fill_color`, or under the first claim that reads it where that claim comes earlier: 9bebae7a's erase claim names `&bg`, and the arms claim before it reads `&bg`. A block with nothing after its text is a claim with no relations of its own. Where the program runs an approximation in place of an output claim, an `APPROXIMATED` form after the claim's text gives the rule the program runs, as in 1da012fc's `place` claim. The tail holds the relations that every output claim ends in. `&output` is the output relation.

A clause reads only relations that earlier forms declared, the fact relations, and the lib's relations, so a program is a DAG of relations, and local recursion does not exist: closures come from lib components. One component, `Unfold`, has inputs that read its outputs, under the rule [Instance](#instance) states. A choice among candidates is a [`ONE`](constraints.md#one) mark or a [`CHOOSE`](constraints.md#choose), and a `DET` reads a chosen relation only where that relation has one model.

A clause has no head. Every variable of its body is a column of the relation it derives, and a later clause selects the columns it reads by name. The engine names the relation after the clause ends. A clause with nothing after its name, `(RULE &live)`, is a fact.

A relation is derived by one clause. A relation that is the union of several bodies has an `OR` as its clause's whole body, with one branch per body, as [Disjunction](#disjunction) gives. An instance's input is derived by one clause in the same way.

The fact relations are `input`, the task input, `ex_input`, every example's input, train and test, and `ex_output`, each train example's output. `ex_input` and `ex_output` carry an Example column `E` first.

A clause form is its keyword, then the relation's name, then its body:

- `RULE`: a program clause, per input. It reads `input`, lib relations, and relations without an Example column. It reads a relation with an Example column only pooled: the read has no site on `E`, and holds where the row holds at some example.
- `DET`: a determination clause, task-wide. It reads `ex_input`, `ex_output`, lib relations, and any derived relation. It reads a `RULE` relation in its lifted form, with the Example column `E` first: the engine lifts every `RULE` relation and instance over the examples, so a parse written once runs on the task input and on every example.
- `DET_OR_RULE` and `RULE_OR_DET`: a relation that one hypothesis determines and another derives, as [Alts](#alts) gives. The first part is the concept case's reading.

```
(DET_OR_RULE &background DominantColor)

(DET &fill_color AnyOutNewColor)

(DET &first_axis AxisDomain)

(DET &changed
  (ex_input *E *P (:Col *Col_in))
  (ex_output E P *Col)
  (!= Col Col_in))
```

A proposer's name, `DominantColor`, stands for its derivation, defined once beside the lib. The proposers stand apart from the lib because a proposer reads the task's grids directly, where a lib component is abstract over its inputs. A proposer of one column gives a `DET` with no body a domain of one value per row of its rows over the task, each of one row, and the determination keeps the values of that domain at which the program solves every train pair; a type-domain proposer gives every value of the parameter's type that the task admits. A `DET` by a one-column proposer that ends in `(SET)` has a domain of one value, the proposer's whole set of rows. A proposer of several columns that the registry does not mark `domain` gives its `DET` a domain of one value, the whole set of its rows. So a parameter whose value holds several rows names no type-domain proposer, and its `DET` states a body or ends in `(SET)`. A frame of cells, or a frame cut into equal tiles, is an instance of a construction of the lib, such as `Frame` or `Division`, and each of its fields, such as an extent or a tile count, comes from a `DET` that the program states, by a proposer or a body, in a solver and in a decoded program alike. No field is a stored value. The type-domain proposers are `AxisDomain`, `ColorDomain`, `D4Domain`, `DiagAxisDomain`, `DiagDirDomain`, `DirDomain`, `NumberDomain`, `SenseDomain` and `SymDomain`, one per type, and `ColorColorDomain`, `DiagDirAxisDomain` and `NumberDirDomain`, one per pair of types, for a parameter of two columns.

An `INIT` form is per input where its input bodies read as a `RULE` clause does, and task-wide where they read as a `DET` clause does. A determination becomes task-wide through a pooled read, or through an instance whose key holds no Example label, which pools over the examples, and its outputs then have no Example column. 009d5c81's `&key_out` holds the color of each class of examples whose keys share a pattern, at the example that shows it, and `&output` reads it pooled, `(&key_out Id (:C *Col))`, so `&key_out` has no Example column: `&output` reads it with no `E`.

The engine finds the [grid columns](constraints.md#the-output-set) of `&output` by testing every pair of one Position column and one Color column against `ex_output` over the train examples, and a case's output on an input is a set of grids, one per model of the program's `ONE` marks, `CHOOSE` forms and `DEMONSTRATED` forms, as [Constraints](constraints.md#the-output-set) gives. In synthesis, the engine tests each `RULE` relation that way, and the first one that solves every train pair is `&output` and ends the program.

## Clause

```
(RULE &larger
  (&area.size (:key *B) *N)
  (&area.size (:key (:B *B2)) (:N *N2))
  (> N N2))
```

A body is a sequence of atoms, one per line. An atom is a list whose head is a relation and whose elements are sites. A site selects one column of the relation, and a column with no site is projected away. Every relation is read this way, fact relations and lib relations included.

### Sites

A site is a list whose head is the column's name with a leading colon, followed by labels: `(:C *V)`, `(:key Col)`, `(:key E Id)`. The colon marks the head as a column; the head of any other list, a form's, a clause's or an atom's relation, is bare. A column of a fixed type takes one label. A column of a type parameter takes one label, or a site on each field of its record that the site reads, as [Instance](#instance) gives.

A label marked `*` is fresh: the site introduces the variable, and the engine echoes the label it assigns. A bare label joins an existing variable. Each label is fresh at one site and joins at any number of others, so the marks show where each variable enters, and the order of sites and atoms carries no scoping.

A site of one label elides to the bare label when the label is the column's name: `*P` is `(:P *P)`, and `Col` is `(:Col Col)`. A site that renames keeps the list, `(:Col *Col1)`. A column of a fixed type is PascalCase, in fact, lib, instance and derived relations alike, so a site on it elides whenever its label is the column's name. A column of a type parameter is lowercase, and its site always keeps the head: `(&line_color.value (:key *A *L) (:v *Col))`.

The site rule applies at every level. Each argument of a site on a record-valued column is itself a site on one field of the record, `(:<Field> <label>)`, elided to the bare label when the label is the field's name: `(:key C A)` is `(:key (:C C) (:A A))`, a rename or a fresh bind writes the pair for that field, `(:key (:C C1) (:A *A1))` and `(:key (:B *B2))`, and a partial read drops a field, `(:key *E)` on a key whose fields are `E` and `Id`. A site names a record's fields only by projection, and no site gives them by position: on a record whose fields are `E` and `P`, a site that reads `Q` from `P` is `(:b E (:P Q))`, never `(:b E Q)`. A field's name is PascalCase, as a fixed-type column's is. No site uses `_`: a column or a field that is not read is left out.

A derived relation's columns are the labels of its clause, as written, so `&opening` derived from `B`, `P`, `Col` and `D` has those columns, and a site on it names a column by that label: `(&opening (:P *Q1) D)`. A lifted read selects the Example column by its label, `(&strip_fill *E C *P)`. A `DET`'s relation has as its columns the labels of its clause that a site of a read of the relation in any case names, in the concept program or in an alt's block, in the clause's order, and each other label of the clause is existential: be03b35f's `&template` makes `Diag`, `D4` and `E`, and `&output` reads it with `(&template *Diag (:D4 *D))`, so its columns are `Diag` and `D4`.

### Negation and constraints

`NOT` before an atom negates it, and every site of the atom joins: `(NOT (&corner P))`.

A constraint is an operator over two labels: `(= A B)`, `(!= A B)`, `(< A B)`, `(<= A B)`, `(> A B)`, `(>= A B)`. `=` may make its first label, and has these rules:

- `(= *X Y)` makes X equal to Y, and `(= *X 0)` makes X equal to `0`. X is bound through the `=` class. Only the first label is made: `(= Y *X)` is a second spelling, and the decoder blocks it.
- `=` makes a label in the first branch of an `OR` or in the then of an `IF`, and only a label that the form exports, so every later branch names X, as [Disjunction](#disjunction) gives. In a later branch, an else, a test, a list of an `ALL` form, or the top level of a body, `(= *X Y)` would only rename Y, so the decoder blocks it there, and it blocks a `=`-made label that the form does not export.
- At the top level of a body, `(= *X 0)` makes a column whose value is `0` in that clause. It stands only where the column cannot be dropped: in an input of an instance, whose columns the component fixes, and in a clause of a relation that another clause, in its block or in another block, gives a varying value at that column, as an `ALT` that rederives the relation can. Where the column is `0` in every clause of the relation, the relation drops the column, and the decoder blocks the `=`. It blocks `(= *X 0)` in a later branch, an else, a test and a list of an `ALL` form, as it blocks `(= *X Y)`.
- Y in `(= *X Y)` is not a label that a site of the same list made. That site could have made X. In a branch of a union, X may be a label the `OR` exports where Y is made in that branch, since no site there can make X.
- The first label of a `=` that makes nothing is not one that a site of the same list made. That site could have named its partner, so `=` on such a label is a second spelling and the decoder blocks it. A label made in an enclosing list, or an export of an earlier branch, passes.

`0` is a reserved label usable as the second label of a constraint. Its type comes from the first label: the number zero, or the zero box for a Box.

`0` also stands as a site's label, on a column of a number, a `Box`, a `Position` or an `Offset`, and its type is the column's. The site joins the column to zero, as `dist(P, D, 0)` does in the Souffle solvers, where a `0` counts nothing that is present: `(margin (:B P) D (:K 0))` reads a cell with no cell between it and edge D, and `(same_corner (:D C) (:P1 P) (:P2 0))` a cell at corner C of the whole frame. `(= K 0)` on a label that a site of the same list made is then a second spelling, and the decoder blocks it, as the rules above give. `0` is never made, so no site holds `*0` or `^0`, and no head site holds it.

A clause ends once it is safe. The safety condition is that each label's class holds a site with a positive atom, or `0`, where `=` spreads binding both ways.

### Disjunction

```
(RULE &prior
  (&axis_len *B *N)
  (&axis_len (:B *B2) (:N *N2))
  (OR ((> N N2))
      ((= N N2)
       (&larger B B2))))
```

An `OR` form holds the branches, each a list of atoms. A fresh variable made in the first branch is exported when every later branch names it; otherwise it is local to its branch. The first branch makes it at a site, or with `=` as `(= *X Y)` or `(= *X 0)`. A later branch names it at a site, or with `=` as `(= X Z)` or `(= X 0)`.

An `OR` that is a clause's whole body is a union: each branch is one body of the relation, and the relation's columns are the labels that the `OR` exports.

The order of atoms in a body is not decoder-enforced. The training data fixes it.

### Conditional

```
(RULE &output
  (input *P (:Col *C_in))
  (IF ((&painted P))
      ((&fill_color (:C *Col)))
      ((= Col C_in))))
```

An `IF` form holds three lists of atoms: the test, the then, and the else. The then holds where the test holds, and the else holds where no binding of the test's fresh labels makes it hold. A label fresh in the test is local to the test and the then. An `IF` with no else is a conjunction, so the decoder admits none.

The then and the else are two branches under the export rule of `OR`: a label fresh in the then is exported when the else names it. The then makes it at a site, or with `(= *X Y)` or `(= *X 0)`, and the else names it at a site, or with `(= X Z)` or `(= X 0)`. A `=` in the test makes no label.

The form compiles to two clauses, the else's with the test negated and its fresh labels projected away:

```
out(P, C_in, Col) :- in(P, C_in), painted(P), fill_color(Col).
out(P, C_in, Col) :- in(P, C_in), !painted(P), Col = C_in.
```

A test that reads a lib relation with a mode satisfies the mode through outer labels, since the negation leaves no other binding. A chain of tests nests an `IF` in the else of the one before.

### Universal

```
;; a spanned box of hole cells alone, with each side at least &min_side
(RULE &rect
  (&span.box *B)
  (ALL ((input *P *Col)
        (inside (:A P) B))
       ((&hole (:C Col))))
  (ALL ((&span.box (:key (:P *Pm)) B)
        (box_extent B (:P Pm) *N)
        (&min_side (:N *K)))
       ((>= N K))))
```

An `ALL` form holds two lists of atoms: the domain, then what each member of the domain must satisfy. It holds at a binding of the outer labels when the domain has a member there and no member fails the body. A binding with no member fails it: "every member of an empty set" is no claim about the input.

A label fresh inside the form, in either list, is per member and local to the form. A label joined from outside is an outer label of the form. `ALL` binds nothing outside itself: the clause binds its outer labels through its own positive atoms, and the decoder admits the form's end once the form's own labels are bound. The body may hold `OR`, `NOT` and `ALL` forms, and the domain is any atoms.

The form compiles to a counterexample relation and its negation, with the domain repeated as the existence test:

```
rect_cex(B) :- span_box(B), in(P, Col), inside(P, B), !hole(Col).
rect(B)     :- span_box(B), in(P, _), inside(P, B), !rect_cex(B), ...
```

A body of several atoms compiles through one more relation that holds where the body holds. Inside an input of `Unfold` that reads an output of its instance, `ALL` may not read that output, since the negation would recurse.

## Instance

```
(INIT &light Ray
  (key ((&light_mark (:Key ^D)))
    (source (P)
      (&light_mark (:Key D) *P))
    (node (P)
      (&light_mark (:Key D))
      (input *P))
    (dir (D)
      (&light_mark (:Key D)))))
```

An `INIT` form is the instance's name, the component, then its key clause where the instance is keyed, then its inputs that hold for every key. The name is the engine's, as a clause's is, and carries `&` as a derived relation does: `&` marks what the program declares, and a bare name is a fact relation or the lib's.

The key clause is `(key (<body>) <inputs>)`. A label marked `^` in its body is a column of the key, and the key's columns are those labels in order of appearance. A key is a record of those labels, a key of one label as well, so a site names its fields by projection: on the key `^Col`, `(:key Col)` reads the field as `Col`, and `(:key (:Col Col1))` reads it as `Col1`; a label in the body with no mark is local to the body. The inputs inside the key clause are keyed, and the key's labels are in scope in them. An input that reads no key label and no output of its instance holds for every key, a broadcast, and stands after the key clause. Each group keeps the component's declared order. An input whose every column is a key label of its type, and whose body would be empty, is not written: the engine fills it from the key, and the solver writes it only when the key has two labels of one type. The fill does not apply to an input the component marks as written explicitly. An instance with no key clause has the `Unit` key.

An input is a list whose head is the input's name, then one list of its head sites, then its body. The body is a sequence of atoms under the clause's safety condition. A head site projects labels the body or the key made onto a column of the input, so no head site carries `*`, and no head site holds `0`: where the column's value is `0`, the body makes the site's label with `(= *X 0)`, as `(gap (G) (= *G 0))` does. A label on no head site is existential. An input with no clause holds the lib's rows alone, and an input whose clause a stored reading takes holds the `DET`'s rows.

```
(INIT &bbox BoundingBox
  (key ((&obj2.component (:key ^E) *P ^Id))
    (cell (P)
      (&obj2.component (:key E) *P Id))))

(INIT &lex Order
  (key ((&scan ^C ^A))
    (before ((:a P) (:b P2))
      (&corner_cell *P)
      (&corner_cell (:P *P2))
      (OR ((corner_dir C A *D)
           (nearer D P (:Q P2)))
          ((diag_dirs (:D C) A (:D1 D) *D2)
           (same_dist D (:P1 P) P2)
           (nearer (:D D2) P (:Q P2))))))
  (member ((:t P))
    (&corner_cell *P)))
```

A read of a relation keyed by labels that are in scope joins on them without a key site: inside `&claim`, keyed by `C` and `A`, `(&claim_order.minimal (:t *B))` reads `&claim_order` at the same key. A key site on such a read is written only where the read is at another key.

The first projection onto a type parameter binds it. A projection of one label binds the parameter to that label's type, and every site on the parameter takes one label. A projection of several sites binds it to a record with one field per site, named by the site's head, or by its label where the site is elided, and typed by its label. Every later site on the parameter names the fields it reads by projection, as [Sites](#sites) gives. `Key` is a type parameter like the others, bound by the key clause, whose `^` labels name its fields. A type parameter that no site binds is `Unit`, as the key is of an instance with no key clause, and a head writes no site on its columns.

An instance is per example when its key holds an Example label. Otherwise it is per input when its bodies read `input`, or read without its Example column a relation that the case's reading derives by a `RULE` clause or an instance that is per input, and it pools over the examples in every other case. An `Unfold` instance's reads of its own outputs count toward neither kind.

The instance's outputs are read as `<name>.<output>`, with the key's columns first and a parameter's columns in place of the parameter: `(&comps.component *P *Id)`, `(&area.size (:key *B) *N)`, `(&recolor.value (:key (:Col Col1)) (:v *Col2))`.

```
(INIT &claim Unfold
  (key ((OR ((&claim_order.minimal (:key ^C ^A) (:t *B)))
            ((&claim_order.member (:key C A) (:t B)))
            ((&blocks C A (:B_last B) (:B *B2)))))
    (start ((:t B))
      (&claim_order.minimal (:t *B)))
    (initial_untaken ((:item B))
      (&claim_order.member (:t *B)))
    (conflict ((:item B) (:item2 B2))
      (&blocks C A (:B_last *B) (:B *B2)))
    (step ((:t B) (:t2 B2))
      (&claim_order.successor (:a *B) (:b *B2))
      (&claim.untaken (:t B) (:item B)))
    (skip ((:t B) (:t2 B2))
      (&claim_order.successor (:a *B) (:b *B2))
      (&claim.excluded (:t B) (:item B)))
    (take ((:t B) (:item B))
      (&claim_order.member (:t *B))
      (&claim.untaken (:t B) (:item B)))))
```

`Unfold` is the one component whose inputs read its outputs. Its inputs that bind the type parameters, `start`, `initial_taken` and `initial_untaken`, come first with `conflict` and `score`, and the engine declares `taken`, `untaken` and `excluded` once they are bound, before it emits the names of `step`, `skip` and `take`; a `take` input with no clause takes the item of least `score`. In those three bodies, every site of an atom of an output joins, so the body binds its labels through its other atoms, and the recursion filters a finite set. No other input reads an output of its instance.

## Constraints

```
(RULE &ties
  (&row *K)
  (&fewer.rank (:t *F) *R)
  (<= R K)
  (ONE K)
  (ONE F))
```

A clause may end in `ONE` marks, each naming key columns of its relation, and a model keeps one row of the relation for each value of each key. A `CHOOSE` form chooses one candidate for each row of its `for` clause, with the pairs that are never chosen together. The program reads a chosen relation like any other. [Constraints](constraints.md) gives the two forms, which pick each writes, their models and the output set.

## Rigid

```
(RIGID_DET &marker
  (&glyph *P)
  (&launch *P)
  (&aim *D))
```

A `RIGID_DET` form, a rigid determination, compares the parts of one assembly across its instances up to one D4 element per instance. The program reads each part through a `:Pose` column, and one pose read across several parts reads one placement of the whole assembly. [Rigid](rigid.md) gives the form, its outputs and what a pose may be tested by.

## Alts

An `ALTS` form gives a property that the train pairs underdetermine. The concept case answers it one way, and each alt is a hypothesis that answers it another way. The `OR` form joins its branches into one hypothesis; an `ALTS` form splits its alts into hypotheses.

Alts represent an ARC task's cases, and a solver session writes them. The language model emits none: a synthesized program takes no alt, so it is one case, and its stream holds no `INPUT`, `OUTPUT`, `ALTS` or `ALT` form.

### The `ALTS` form

```
(ALTS $overlap "which cells stay claimed when rectangles share cells" $LargestFirst
  (ALT $DropDominated
    (OUTPUT greedy-rect-fill "each rectangle that no other rectangle contains fills, unless such a rectangle of larger area overlaps it"
      (RULE &contained
        (&cand *B)
        (&cand (:B *B2))
        (!= B B2)
        (inside (:A B) (:B B2)))

      (RULE &maximal
        (&cand *B)
        (NOT (&contained B)))
      ...
      (RULE &kept_cell
        (&maximal *B)
        (NOT (&dominated B))
        (&rect_cell B *P)))

    (RULE &output
      (input *P (:Col *C))
      (IF ((&kept_cell P))
          ((&fill (:C *Col)))
          ((= Col C)))))

  (ALT $AxisFirst
    (OUTPUT greedy-rect-fill "rectangles claim in order of their extent along &first_axis, then of their area"
      (DET &first_axis AxisDomain)
      ...
      (RULE &prior
        ...))

    (ALT $ThicknessTwo
      ...)))
```

An `ALTS` form stands after the concept program: its name, its gloss, the concept case's name, then an `ALT` block per alt. An `ALT` block holds an `INPUT` or `OUTPUT` block for each claim the alt reads differently, with the alt's reading of the claim as its text, a block under a slug of its own for each claim the alt adds, as 9f27f097's `$Solid` adds `sole`, and the tail forms that the alt rederives; every relation it does not mention is the concept program's. An `ALT` inside an `ALT` holds what the combination of the two alts rederives. Where alts of two `ALTS` forms each rederive a relation, the nested `ALT` of their combination rederives it too, as the combination derives it. An `ALTS` form that exists only with the concept branch of another `ALTS` form stands in an `ALT` block of that concept branch's name, which holds only its `ALTS` form, as a5313dff's `$e` stands under `$FourPath`.

In an alt's cases, each form reads a relation that the alt rederives as the alt derives it: 351d6448's `$StepFromFirstTwo` rederives `&checked`, and in its cases the concept program's `&shift_defect` reads that `&checked`. A `DET` in the concept program reads the concept program's derivation in every case, since a parameter that the cases share has one determination: a09f6c25's `$Conn4` rederives `&member`, and the concept program's `DET` of `&kept` reads the concept program's `&member` in every case. A parameter determined in several blocks takes the values they all admit. A relation that no block of a case derives is undefined in that case, and a relation under `NOT` is derived in every case that reads it.

A relation of the concept program other than a `DET`'s has only the columns that the concept case reads. Where an alt's derivation of the relation has more columns, the alt rederives, in its own block, the first form that reads the relation, and that form reads the alt's columns. In 9f8de559 the concept case paints the exit cell in the field color, so the concept program's `&paint_of` has no color column. `$StoredPaint` rederives `&paint_of` with a `Col` column and rederives `&output`, which reads it. An alt of another point that rederives `&output`, as `$NearestBody` does, reads the concept program's `&paint_of`, and the combination of the two alts rederives `&output` with the `Col` column.

The cases are the product of the `ALTS` forms, restricted by the nesting of the blocks. A combination excluded for another reason is a judgment, and the arcdata file records it.

A `DET_OR_RULE` or `RULE_OR_DET` line is an `ALTS` form on its relation, whose readings are `&background=$Stored` and `&background=$Derived`, the concept case's reading first, and the other reading is its alt. A gloss, where the solver states one, stands after the relation's name, and the claim text of the derived reading is the proposer's. The arcdata file names the form by the relation, `&background`.

```
(DET_OR_RULE &tile_size ConstInDim SepTileDim TileCount TileDim)
```

A line with several proposers has a derived reading per proposer, each an alt of its own: `&tile_size=$Stored`, then `&tile_size=ConstInDim`, `&tile_size=SepTileDim`, `&tile_size=TileCount` and `&tile_size=TileDim`.

A line with no body has its first proposer's columns, in every reading, and each other proposer's columns map onto them by position. A `DET` that names one proposer, with no stored reading, has that proposer's columns: `(DET &bg ChangedColor)` is read as `(&bg (:C *C))`.

```
(DET_OR_RULE &marker_max_side "The longest side a marker's box may have." SepTileCount TileCount
  (&exact_split *N)
  (NOT (&unsplit (:M N)))
  (ONE))

(RULE_OR_DET &step_dir "The side each step moves toward."
  (&front_step *D))
```

Where one reading has clauses of its own, the line holds their body after its proposers, and the line is the relation's one clause. On a `DET_OR_RULE` line the body is the stored reading's determination: in ac0c5833, the stored reading keeps each longest marker side the pairs leave open, and each proposer's reading takes the length the proposer gives on the input. On a `RULE_OR_DET` line the body is the derived reading, the concept case's: in 351d6448, the concept derives the step's side, and the alt stores it.

A `DET_OR_RULE` or `RULE_OR_DET` line on a port of an instance, an input or an output, names the port as the program reads it, and holds no body. In the derived reading the instance derives the port, and the line is no clause. In the stored reading the line's `DET` is the port's one source: on an input, it stands for the `INIT` form's clause of that input, which that form then leaves out, and on an output, each read of the output reads the `DET`. In aa300dc3, `&ring` derives `(RULE_OR_DET &ring.value "The one color of the border ring.")` in the concept case, and the alt stores it.

### Demonstrated

```
(DEMONSTRATED &catalog
  (key ((OR ((&slot (:Answer ^Pan) (:Shown ^Pan1))
             (&content (:Pan *Pan3))
             (&pval (:Pan Pan3) *P_inner *Col))
            ((&slot (:Answer Pan) (:Shown Pan1) (:Done *Pan2)))))
    (value ((:o Pan3) (:i P_inner) (:v Col))
      (&slot (:Answer Pan) (:Shown Pan1))
      (&content (:Pan *Pan3))
      (&pval (:Pan Pan3) *P_inner *Col))
    (demonstration ((:o Pan1) (:o2 Pan2))
      (&slot (:Answer Pan) (:Shown Pan1) (:Done *Pan2))))
  (DEMO_RULE $Extend
    (INIT &spread Quotient ...)
    (INIT &canvas Singleton ...)
    (RULE &predict
      (&pval *Pan *P_inner (:Col *V))
      (&hole (:C *H))
      (OR ((= V H)
           (&canvas.value (:key Pan P_inner) (:v *Col)))
          ((!= V H)
           (= Col H))))

    (RULE &prediction
      (&slot (:Answer *Pan) (:Shown *Pan1))
      (&predict (:Pan *Pan3) *P_inner *Col)))
  (DEMO_RULE $Span
    ...)
  (DEMO_RULE $Reflect
    ...))

(RULE &output
  (&slot (:Answer *Pan) (:Shown *Pan1))
  (&catalog (:key Pan Pan1) (:o Pan) (:i *P) (:v *Col)))
```

4c7dc4dd: of three panels that hold marks, two stand as a demonstration, and the third, the answer, takes what the demonstrated rule predicts for it. A `DEMONSTRATED` form is a `DemonstrationConsistency` instance whose rules are its `DEMO_RULE` forms. `value` and `demonstration` are the component's inputs, written as an instance's are, and a keyed form takes its key clause as an instance does. The form is per input or task-wide by what its input bodies read, as an `INIT` form is, and each `&prediction` clause is the same. Each `DEMO_RULE` is a demonstrated rule: its name, the rule's text where the solver states one, then the clauses that read what the rule needs from the input, and it derives `&prediction` with the columns the `value` head names. A rule with fields names each field with a fresh label after its constructor, `(DEMO_RULE ($Move *D) "…" …)`. Its `&prediction` has a column for each field, and the form holds one rule for each value that the rule's clauses bind for the field.

In a keyed form, the key's labels are in scope in the inputs inside the key clause, as an instance's are, and not in the `DEMO_RULE` bodies, which stand after it. A `DEMO_RULE`'s clauses name the key's columns by the key's labels, and its `&prediction` has those columns beside the ones the `value` head names, so the form reads each prediction at the key whose labels it makes. A `&prediction` that makes no key label holds at every key, as a broadcast input does in an [Instance](#instance). Above, the key's labels are `Pan` and `Pan1`, the answer panel and the shown panel, and each rule's `&prediction` makes both from `&slot`, so it holds at each key that `&slot` gives.

The relation the form declares holds, at each key, the predictions of one rule that every demonstration of the key confirms. Each choice of one confirmed rule per key is a model, as [Demonstrated choice](../handbook/solver-file.md#demonstrated-choice) gives, and the case's output holds one grid per model, as [Constraints](constraints.md#the-output-set) gives. A demonstration confirms a rule where the rule's prediction for its first object equals its second object, at the same indices with the same value at each. A key with no demonstration holds no prediction. The relation's columns are the key's, then the `o`, `i` and `v` of the `value` head. It has no column for a rule or a field, so no read names one. The form states the test against every demonstration, so a program writes no test over `demonstration` of its own. Above, a key's demonstrations take the shown panel to each panel that `&slot` gives as done at that key.

The input determines the rules that stand, and no stored value records them. Demonstrated rules split no cases, so the form declares a relation and takes `&`.

### Open values

A parameter is open when the pairs do not separate the values a reader of the intended concept could take. Its determination ends in [`(ONE)`](constraints.md#one), so each value it keeps is a model, and the case's output is the set of grids its models give, as [Constraints](constraints.md#the-output-set) states:

```
(DET &start_corner
  (diag_dir_elem *D)
  (NOT (&start_contradicted (:C D)))
  (ONE))
```

a8d7556c: the corner a strip across the first axis starts at, where the pairs leave two. The [arcdata](arcdata.md#params) file holds the values as the parameter's `param` rows.

A determination by a proposer, and a `DET_OR_RULE` line, take the mark after their proposers: `(DET &quorum NumberDomain (ONE))`. On a `DET_OR_RULE` line the mark holds on both readings, so on the derived reading each value the proposer gives on the input is a model.

The mark `(SET)` stands in the same place on a `DET` or a `DET_OR_RULE` line with no body by proposers of one column, none marked `domain`: `(DET &palette UnchangedColor (SET))`. The parameter then has one value, the proposers' whole set of rows, where it has one value per row without the mark. A form with both marks takes `(ONE)` over the one value `(SET)` gives.

A session records a value as open where another task in the family of the case's hypothesis could fix it. Where none could, the parameter is absent and a symmetric form takes its place.

## Token stream

The language model emits tokens from these sets, each a closed set of ids:

- control: `RULE` `DET` `INIT` `ONE` `SET` `CHOOSE` `RIGID_DET` `OR` `IF` `ALL` `END` `SKIP` `ALSO` `NOT` `*` `^` `0` and the constraint operators. `^` marks a label of a key clause's body as a column of the key, as [Instance](#instance) gives, in an instance's `key`, a `CHOOSE`'s `for`, and a `RIGID_DET`'s `instance` and `key`, and the engine echoes the label after it as after `*`.
- lib relations and components, one token each; proposers, one token each
- fact relations: `input` `ex_input` `ex_output`
- derived relations: the index the engine assigned at the declaration
- column tokens: a relation's columns, which for a derived relation are the labels of its clause; the fields of a site on a record-valued column, by their position in the record; and the names the engine emits for a form's inputs and named clauses, by position: an instance's `key` at 0 and its component's input k at 1 + k, a `CHOOSE`'s `for`, `from` and `never` at 0, 1 and 2, and a `RIGID_DET`'s `key` and `instance` at 0 and 1; in an `INIT`, `CHOOSE` or `RIGID_DET` form, a read of a derived relation that is per input and is no relation of the form itself gives the Example column the column token 0 whether or not the read is lifted, and the relation's own columns follow it
- labels: the variables of the current clause, in order of creation

The engine emits the declaration of each derived relation, the declarations at each instance or `CHOOSE` form, the name of each input, each column name of a projection, and the label echo after each `*` and `^`. The declarations at an instance are each output, then each input whose name no output shares, written or not. The engine names each input of the component, an unwritten one too, and the language model declines an unwritten one by `SKIP`. In a keyed instance, the key clause names each input, and after the key clause the engine names each input that the key clause did not write. A projection names each column of the input, and an empty one is answered by `END`. It emits the name of each named clause of a form as it emits the names of an instance's inputs: an instance's `key`, a `CHOOSE`'s `for`, `from` and `never`, and a `RIGID_DET`'s `instance` and `key`. The language model never emits a label it has not seen echoed, and never names a relation or a column with text.

The token sets are disjoint, so an atom's site list ends at the first token that is not a column token, and no separator exists. Every site opens with its column token, an elided one too.

The language model emits `END` where a decision to stop exists: at the end of a body, after each projection's labels, after the field sites of a site on a record-valued column, after each `ONE` mark's key labels, at the end of an `OR` form, and after each list of an `IF` or `ALL` form. It emits `ALSO` between the branches of an `OR` form, which are a repeat as the clause that may repeat below gives, so an `OR` in a branch after a conjunct opens a nested `OR` form. The decoder admits `END` at the end of a body once the clause is safe. A clause's `SET` mark, as `SET`, follows its body before its `ONE` marks. A clause's `ONE` marks follow its body, each as `ONE`, its key labels and `END`, before the clause's `END`.

The language model emits `SKIP` after the name of an optional clause or input, to decline it. After the name of a required clause, and after the last name of a required input in the form, the decoder refuses `SKIP`, so no form lacks a required input and then waits on a decline that the decoder never admits.

A `RIGID_DET` is written as `RIGID_DET`, then the `key` name and its body and `END`, or `SKIP`, then the `instance` name and its body and `END`, or `SKIP`, then its parts, each an atom, then `END`; the engine then declares the form's outputs.

A clause that may repeat, such as `never`, is written as its first instance, then `ALSO` and the next instance, for each further repeat. The next name the engine emits, or the `END` that closes the enclosing form, ends the run, so the repetition has no token of its own at its end. A `CHOOSE` form whose `never` clause is written closes with `END` after its last `never` clause, and the engine then declares the form's relation.

### Second spellings

Two spellings of one body are equivalent by syntax alone in these cases, and the decoder could block one of each pair. They are suggestions to consider, not rules of the stream.

- In an `OR` branch, a `NOT` of an atom that an earlier branch holds positively with the same joined labels: the `IF` form spells it.
- An `IF` whose test is one `NOT` atom: the same `IF` with the then and the else swapped spells it.
- `NOT` over a form: the domain with a negated body spells it, as "some member fails".
- Sites out of the relation's column order.

Two spellings equivalent by meaning alone are left to the training data: a `NOT` on a derived relation whose own clause negates, against an `ALL`; an else that re-reads an outer atom to carry a label, against `=`; the order of atoms; and a body written twice against a relation derived once.

## Names

A derived relation's name, an instance's name and a label are the renderer's, chosen from lineage with a digit on a clash; the stream holds ids. An `ALTS` form's name, an alt's name, a demonstrated rule's name and a claim's slug are the solver session's. The arclog file writes each name once, from the stream, and keeps it, so the arcdata file keys on the file and not on the stream.

Each kind of name has its own spelling:

| kind | spelling |
| --- | --- |
| keyword | `RULE` `INIT` `CHOOSE` `OUTPUT` `DEMO_RULE` `DET_OR_RULE` |
| fact relation | `input` `ex_input` `ex_output` |
| lib relation, proposer | `margin` `inside` `DominantColor` |
| instance | `&comps` |
| instance relation | `&comps.component` |
| derived relation, chosen relation, demonstrated | `&fg` `&ties` `&catalog` |
| alts, alt | `$locate` `$Box` `&background=$Derived` |
| claim slug | `container` `fill-interior` |
| label, fixed-type column | `P` `Col1` |
| type-parameter column | `key` `t` `item` |

In a keyword, an underscore joins a modifier to a base form, so `X_Y` is a kind of `Y`: `DEMO_RULE` is a demonstrated rule, and `RIGID_DET` is a rigid determination. An `OR` in a keyword joins the two readings of an `ALTS` form on one relation: `DET_OR_RULE` is a determination or a rule, the concept case's reading first.

## Trace form

The trace form is the program's tree with the engine's forced tokens in brackets, in the stream's order. Every other symbol is a generated token, one the language model emits. A site is `(:Col *[P])` at a fresh label, the `*` the language model's and the echo the engine's, or `(:Col P)` at a join.

```
(RULE (input (:P *[P]) (:Col *[Col]))
      (&bg (:C *[V]))
      (!= Col V)
      END)
[&fg]

(INIT Connectivity
  [key] SKIP
  [node]
  ((&fg (:P *[P])) END
   [node key] (END)
   [node P] (P END))
  [step] SKIP
  [&comps.component &comps.connected &comps.adjacent &comps.node &comps.step])

(RULE (&axis_len (:B *[B]) (:N *[N]))
      (&axis_len (:B *[B2]) (:N *[N2]))
      (OR ((> N N2))
          ALSO
          ((= N N2)
           (&larger (:B B) (:B2 B2)))
          END)
      END)
[&prior]
```

The bracket's content says which kind of forced token it holds:

- a relation after a clause's `END` is its declaration, `[&fg]`
- the declarations after an instance's last input, each output and then each input whose name no output shares, `[&comps.component &comps.connected &comps.adjacent &comps.node &comps.step]`
- an input's name alone, before its body or its `SKIP`, is the input name, `[node]`, `[key]`
- an input's name with a column is the column name, `[node P]`, and the list that follows is the language model's answer, `(END)` for an empty projection
- a label after `*` is its echo, `[P]`

A clause's `END` is the language model's, and its declaration follows it as a sibling. An instance has no `END` from the language model: it ends when the engine has emitted the name of each input, and its declaration sits inside it.

A renderer flag adds the language model's top-k tokens after a symbol, in braces, each with its probability. The braces attach to the symbol whose decision they show:

```
(RULE (input (:P *[P]) (:Col *{* .94 P .06}[Col]))
      (&bg (:C *[V]))
      (!= Col V)
      END{END .83 &covered .11})
```

The braces also show the decoder's constraints: a column that admits no fresh label has no `*` among its top-k tokens, and `END` is absent until the clause is safe.

### From trace form to program form

The program form is the trace form under these rewrites, each a rewrite on the one tree:

- delete the bracket and brace nodes
- fold each echo into its site, `*[P]` to `*P`
- delete the `END`, `SKIP`, `ALSO` and `OR` symbols
- move each projection's answer into its input's head list, as head sites
- move each declared name into the head of the form that declared it

## Infix view

The infix view prints the program form as Prolog-shaped text with Souffle's spellings where Souffle has one. A clause is `<name> :- <body>.`, an atom is `relation(sites)`, a site is `column(labels)` or the elided label, negation is `!`, a disjunction is `( ; )`, and a constraint is an infix operator.

```
&fg :- in(*P, *Col), &bg(C(*V)), Col != V.

&light.source(P) :- &light_mark(Key(D), *P).
&light.node(P) :- &light_mark(Key(D)), in(*P).

&prior :- &axis_len(*B, *N), &axis_len(B(*B2), N(*N2)),
    ( N > N2
    ; N = N2, &larger(B, B2) ).
```

## Example

A task where each object's bounding box fills with the object's color under a fixed recoloring, and every other cell keeps its color. Its arcdata file is the example in [arcdata](arcdata.md#example).

```
(INPUT background "every cell outside the objects is &bg"
  (DET_OR_RULE &bg DominantColor))

(INPUT objects "each object is a connected group of cells other than &bg"
  (RULE &fg
    (input *P *Col)
    (&bg (:C *V))
    (!= Col V))

  (INIT &comps Connectivity
    (node (P)
      (&fg *P)))

  (RULE &obj_col
    (&comps.component *P *Id)
    (&fg P *Col)))

(OUTPUT fill "every cell of an object's bounding box becomes the color &recolor.value gives the object's color"
  (INIT &boxes BoundingBox
    (key ((&comps.component ^Id))
      (cell (P)
        (&comps.component *P Id))))

  ;; an object's color beside the color its box fills with
  (DET &pair
    (&fg *E *P *Col)
    (ex_output E P (:Col *Col2)))

  (INIT &recolor Singleton
    (key ((&pair ^Col))
      (member ((:v Col2))
        (&pair Col *Col2))))

  (RULE &covered
    (input *P)
    (&boxes.box (:key *Id) *B)
    (inside (:A P) B)))

(OUTPUT rest-kept "every other cell keeps its input color")

(RULE &output
  (input *P (:Col *C_in))
  (IF ((&covered P *Id))
      ((&obj_col Id (:Col *Col1))
       (&recolor.value (:key (:Col Col1)) (:v *Col)))
      ((= Col C_in))))
```

`&pair` reads `&fg` lifted, so it has the Example column `E`. `&recolor` keys on `Col` alone, so it pools over the examples, and `&recolor.value` has no Example column and is read by a `RULE` clause. `&comps` has no key clause, so it has the `Unit` key.
