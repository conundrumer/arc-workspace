* comment: when editing this doc
    - [Arclog documents](prompts/arclog.md) includes this document with each section that has the attribute `undisclosed` left out, and gives each such section a line with its condition.
    - This document holds what a user of arclog needs. What an implementer of the engine needs stands in [Engine overview](docs/engine/overview.md).

# arclog
- The language of solver programs. The language has few constructs, infers what the engine can, and gives the determination only task-wide data.
- A solver is two files. `<task_id>.arclog` holds the task's claims and structure: the program, its determination, its instances and its alts. `<task_id>.arcdata` holds the judgments and records on its cases: the witnesses, the excluded cases and the stored assignment, as [arcdata](./arcdata.md) gives it. The names the arclog file declares are the keys the arcdata file uses.
- A file that `arclog_convert.convert` writes under `gen/` (a solver's two files and each file of `gen/cases/<task_id>/`) is read-only and begins with the comment lines `;; inputs <inputs hash> programs/solvers/<task_id>.dl` and `;; converter <code hash>`. A Python program that reads such a file reads it through `arclog_convert.readback.read_checked`, which raises `Stale` where the header's inputs hash is not that of the solver's files now, or the file does not match its record in `case_records/`. `python -m arclog_convert.readback` checks each file against its record and the current code hash.

## Program
- A program is `INPUT` and `OUTPUT` blocks in dependency order, then `ALTS` forms, then the tail. A block is a claim, `(INPUT <slug> "<text>" <form>...)` or `(OUTPUT <slug> "<text>" <form>...)`: its slug, its text, then the forms that serve it. A relation stands under the first claim that reads it. A parameter stands under the first claim whose text names it, as `&fill_color`, or under the first claim that reads it where that claim comes earlier. A block with nothing after its text is a claim with no relations of its own. Where the program runs an approximation in place of an output claim, an `APPROXIMATED` form after the claim's text gives the rule the program runs. The tail holds the relations that every output claim ends in, then the `OUT` form ([The OUT form](#the-out-form)).
- A clause reads only relations that earlier forms declared, the fact relations and the lib's relations, so a program is a DAG of relations with no local recursion: closures come from lib components. `Unfold` alone has inputs that read its outputs. A choice among candidates is a [One](./constraints.md#one) mark or a [Choose](./constraints.md#choose).
- A clause has no head: every variable of its body is a column of the relation it derives, and a later clause selects the columns it reads by name. A clause with nothing after its name, `(RULE &live)`, is a fact.
- A relation is derived by one clause. A relation that is the union of several bodies has an `OR` as its clause's whole body, with one branch per body ([Disjunction](#disjunction)). An instance's input is derived the same way.
- A clause form is its keyword, then the relation's name, then its body:
    - `RULE`: a program clause, per input. It reads `input`, lib relations, and relations without an Example column. It reads a relation with an Example column only pooled: the read has no site on `E`, and holds where the row holds at some example.
    - `DET`: a determination clause, task-wide. It reads `ex_input`, `ex_output`, lib relations, and any derived relation. It reads a `RULE` relation in its lifted form, with the Example column `E` first: the engine lifts every `RULE` relation and instance over the examples, so a parse written once runs on the task input and on every example. A lifted read whose `E` site holds a label that a positive `ex_output` atom binds, as a conjunct of the same body as the read or of the guard of the `ALL` whose body holds the read, reads the train examples alone, so the relation's definedness on a test input does not enter.
    - `DET_OR_RULE` and `RULE_OR_DET`: a relation that one hypothesis determines and another derives, as [Stored readings](#stored-readings) gives. The first part is the concept case's reading.
- A `DET` or `RULE` names at most one proposer. A `DET` that names a proposer, such as `DominantColor`, has no body, and a `DET` that names none holds a body, since a `DET` of no body and no proposer gives no value. The proposer's values, as [Proposers](docs/arclog/lib.md#proposers) gives them, are the values the determination gives, and the stage after the determination keeps those at which the program solves every train pair. A one-column proposer gives one value per row, each of one row. A type-domain proposer gives every value of the parameter's type that the task admits. Any other proposer of several columns gives one value, the whole set of its rows. So a parameter whose value holds several rows names no type-domain proposer.
- A frame of cells, or a frame cut into equal tiles, is an instance of a lib construction such as `Frame` or `Division`. Each of its fields, such as an extent or a tile count, comes from a `DET` that the program states, by a proposer or a body.

## Clause
- A body is a sequence of atoms, one per line. An atom is a list whose head is a relation and whose elements are sites. A site selects one column of the relation, and a column with no site is projected away. Every relation is read this way, fact relations and lib relations included.

### Sites
- A site is a list whose head is the column's name with a leading colon (the head of any other list is bare), followed by labels: `(:C *V)`, `(:key Col)`, `(:key E Id)`. A column of a fixed type takes one label. A column of a type parameter takes one label, or a site on each field of its record that the site reads, as [Instance](#instance) gives.
- A label marked `*` is fresh: the site introduces the variable. A bare label joins an existing variable. A label is made at one site per body and joins at any number of others, so the order of sites and atoms scopes nothing.
- A `*X` or `^X` is refused that makes a name another site of its body makes, the lists of the body's `OR`, `IF` and `ALL` forms included. In a keyed input, it is also refused when it makes a name that a `^` label of the key holds.
- A bare `X` joins the label of the first site, and a label local to a later branch of an `OR` or to an `IF`'s else takes a name of its own.
- A site of one label elides to the bare label when the label is the column's name: `*P` is `(:P *P)`, and `Col` is `(:Col Col)`. A site that renames keeps the list, `(:Col *Col1)`. A column of a fixed type is PascalCase, in fact, lib, instance and derived relations alike. A column of a type parameter is lowercase, and its site always keeps the head: `(&line_color.value (:key *A *L) (:v *Col))`.
- The site rule applies at every level. Each argument of a site on a record-valued column is a site on one field of the record, `(:<Field> <label>)`, elided to the bare label when the label is the field's name: `(:key C A)` is `(:key (:C C) (:A A))`, a rename or a fresh bind writes the pair, `(:key (:C C1) (:A *A1))`, and a partial read drops a field, `(:key *E)` on a key whose fields are `E` and `Id`. A site names a record's fields only by projection, never by position: on a record whose fields are `E` and `P`, a site that reads `Q` from `P` is `(:b E (:P Q))`, never `(:b E Q)`. A site holds one site on each field it reads, as an atom holds one site on each column. A field's name is PascalCase. No site uses `_`: a column or a field that is not read is left out.
- A derived relation's columns are the labels of its clause, as written, and a site on it names a column by that label: `(&opening (:P *Q1) D)`. A lifted read selects the Example column by its label, `(&strip_fill *E C *P)`.
- A `DET`'s relation has as its columns the labels of its clause that a site of a read of the relation names in any case of the program, in the clause's order, together with each label that a `ONE` mark of the clause names. Each other label of the clause is existential. A `DET` clause that makes `Diag`, `D4` and `E`, read as `(&template *Diag (:D4 *D))`, gives the relation the columns `Diag` and `D4`.

### Negation and constraints
- `NOT` before an atom negates it, and every site of the atom joins: `(NOT (&corner P))`.
- A constraint is an operator over two labels: `(= A B)`, `(!= A B)`, `(< A B)`, `(<= A B)`, `(> A B)`, `(>= A B)`. Its second label is not its first: the comparison of a label with itself holds wherever the label is bound under `=`, `<=` and `>=`, and nowhere under `!=`, `<` and `>`. `=` may make its first label, and has these rules:
    - `(= *X Y)` makes X equal to Y, and `(= *X 0)` makes X equal to `0`. X is bound through the `=` class. Only the first label is made: `(= Y *X)` is refused.
    - `=` makes a label in the first branch of an `OR` or in the then of an `IF`, and only a label that the form exports, so every later branch names X ([Disjunction](#disjunction)). In a later branch, an else, a test, a list of an `ALL` form, or a `NOT`, `(= *X Y)` would only rename Y, so it is refused there, and so is a `=`-made label that the form does not export. Under a `NOT`, `(= *X Y)` and `(= *X 0)` would also make the `NOT` hold nowhere.
    - At the top level of a body, `(= *X 0)` makes a column whose value is `0` in that clause. It stands in an input of an instance, whose columns the component fixes, and in a clause of a relation that another clause, in its block or in another block of the solver, gives a varying value at that column. The same holds at the top level of a `CHOOSE` form's `from`, of a `RIGID_DET` form's `instance` clause, and of a clause of a `DEMO_RULE` other than its `&prediction` clause, whose columns the `DEMONSTRATED` form fixes as a component fixes an input's.
    - In the first branch of an `OR` and the then of an `IF`, Y in `(= *X Y)` is not a label that a site of the same list made, a field site or a site on a column of a type parameter included, as in `(:key (:F *Y))`, since that site could have made X. In a branch of a union, X may be a label the `OR` exports where Y is made in that branch, since no site there can make X.
    - At the top level of a body, Y in `(= *X Y)` is not a label that a site of the same list made, a field site or a site on a column of a type parameter included, as in `(:key (:F *Y))`, since that site could have made X: `(:key (:F *X))` makes the column X without the `=`.
    - The first label of a `=` that makes nothing is not one that a site of the same list made, and such a `=` is refused, since that site could have named its partner. A label made in an enclosing list, or an export of an earlier branch, passes.
- `0` is a reserved label. As the second label of a constraint, its type comes from the first label: the number zero, or the zero box for a Box, a Position or an Offset. As a site's label, on a column of a number, a `Box`, a `Position` or an `Offset`, its type is the column's, and the site joins the column to zero, where a `0` counts nothing that is present: `(margin (:B P) D (:K 0))` reads a cell with no cell between it and edge D. `(= K 0)` on a label that a site of the same list made is then refused. `0` is never made: no site holds `*0` or `^0`, and no head site holds `0`.
- A clause ends once it is safe: each label is of an orientation type, or its class holds a site with a positive atom, or `0`, where `=` spreads binding both ways.

### Disjunction
- An `OR` form holds the branches, each a list of atoms. A fresh variable made in the first branch is exported when every later branch names it; otherwise it is local to its branch. The first branch makes it at a site, or with `(= *X Y)` or `(= *X 0)`. A later branch names it at a site, or with `(= X Z)` or `(= X 0)`.
- An `OR` that is a clause's whole body is a union: each branch is one body of the relation, and the relation's columns are the labels that the `OR` exports.
- A label that the `OR` exports has one type over its branches. Branches that give an exported label `Ident` columns of two sources are refused ([Ident](lib.md#types)). The same holds for the branches of an `IF`, and for the clauses of one relation.

### Conditional
- An `IF` form holds three lists of atoms: the test, the then, and the else. The then holds where the test holds, and the else holds where no binding of the test's fresh labels makes it hold. A label fresh in the test is local to the test and the then. An `IF` with no else would be a conjunction, so it is refused.
- The then and the else are two branches under the export rule of `OR`: a label fresh in the then is exported when the else names it. A `=` in the test makes no label.
- The else is the test negated with its fresh labels projected away, so a test that reads a lib relation with a mode satisfies the mode through outer labels. A chain of tests nests an `IF` in the else of the one before.

### Universal
- An `ALL` form holds two lists of atoms: the domain, then what each member of the domain must satisfy. It holds at a binding of the outer labels when the domain has a member there and no member fails the body. A binding with no member fails it: "every member of an empty set" is no claim about the input. An `ALL` with an empty body would hold wherever its domain has a member, so it is refused.
- A label fresh inside the form, in either list, is per member and local to the form. A label joined from outside is an outer label of the form. `ALL` binds nothing outside itself: the clause binds its outer labels through its own positive atoms, and the form may end once its own labels are bound. The body may hold `OR`, `NOT` and `ALL` forms, and the domain is any atoms.

### Frames
- [Box](lib.md#types) gives what a frame is. The checker finds the grids that hold of a label at a Box or Position column. A grid holds of a label where, in every row of the label's form, the label's value stands in that grid. Two labels are in one frame where a grid holds of both.
- The grids of a label come from its sources: each site of a positive atom that binds the label, and each such site of a label that an `=` makes equal to it. A bare label that joins an existing variable adds its site as a source. A `NOT` atom, an `ALL` form and a constraint other than `=` bind nothing. A label that an `=` makes equal to `0` has a source with no grid.
- A frame rule names the columns that give a column its frame. A rule makes a frame where it is `new` or `(new ...)`, also where the made frame lies in the frame of the columns that the rule names. A column that makes a frame gives no grid, so a label that only such columns bind has none. A column with no declared rule takes the columns that have a frame: those that the mode binds, for a lib relation, and for a component output the input columns whose values it copies, as the `copies` rows of the output in `engine/lib/registry.sexpr` declare, or, where it copies none, those of the component's inputs other than `key`. The `frames` forms of `engine/lib/registry.sexpr` declare the other rules, so a column whose rule there is `new` or `(new ...)` makes a frame.
- A source gives grids by the relation of its site:
    - `input` at `P` gives the input of the current example. The current example is the one that a per-input form runs on.
    - `ex_input` and `ex_output` at `P` give the input and the output of the example that the label at `E` holds. A site with no label at `E` gives none.
    - A relation that clauses derive gives the grids of its column. The grids of a column are those that hold of its head label in every clause that derives it, over the current example and the relation's Example columns. A grid that names a label which is no Example column of the relation is dropped. At a read, the current example becomes the label at the read's `E` site where the read is lifted ([Program](#program)), and an Example column becomes the label at that column of the read. A grid with no such label is dropped. A relation that a `CHOOSE`, `RIGID_DET`, `DEMO_RULE` or `DEMONSTRATED` form gives has no grids, and neither does an instance input.
    - An instance output column gives the grids that hold of the labels at the input columns that its frame rule names, in the instance's input bodies, where its frame rule makes no frame. The grids are those that hold of all of them. A key label of the instance becomes the label at the key field of the read, and a grid with no such label is dropped.
    - A lib relation column gives the grids that hold of the labels at the columns that its frame rule names, where the rule makes no frame. A label of type `Offset` is left out. The columns are the bound columns of a mode that leaves the column unbound, and the grids are those that hold in every such mode whose bound columns all have a label in the atom. A site at a column that every mode binds is no source.
- A grid holds of a label where every one of its sources gives it. Where the site of every source is of type Position, a grid holds where one source gives it, since a value that is a cell of two grids shows that they have one extent.
- An `OR` or an `IF` that binds the label is taken branch by branch: a branch of the `OR`, and for the `IF` the test with the then, or the else. A grid holds of the label where it holds in every choice of one branch for each such form. A branch that does not bind the label gives it no grid. A label with more choices than a bound that the engine sets has no grids. A label has no grids either where finding them needs the grids of that same label.
- A type rule of a lib relation can read frames. Its condition `same-frame` on two columns holds where a grid holds of the labels at both columns. The other conditions of the rule hold where each column named has a label whose type is at or under the condition's type. A column's type at a site is the meet of its declared type and the types that the rules which hold give it. The grids are found again as the types of labels narrow, so a rule that holds keeps holding.
- `relative` has such a rule: where `Base` and `X` are Positions in one frame, `X_rel` is an Offset, since two cells of one frame differ by a move. A site that puts that `X_rel` at a Position column is then refused, since a label never stands at a Position column and an Offset column. Where no grid holds of both `Base` and `X`, the rule does not hold, and `X_rel` takes its type from its other sites.
- A lib relation that the lib defines through other lib relations has type rules that read no grids. Its columns take frame rules as other lib relation columns do.

## Instance
- An `INIT` form is the instance's name, which starts with `&`, the component, then its key clause where the instance is keyed, then its inputs that hold for every key.
- The key clause is `(key (<body>) <inputs>)`. A label marked `^` in its body is a column of the key, and the key's columns are those labels in order of appearance. A key is a record of those labels, a key of one label as well. A label in the body with no mark is local to the body. A key clause with no `^` label gives one key of no column where its body holds. An instance with no key clause has no key, and its relations have no key column.
- The inputs inside the key clause are keyed, and the key's labels are in scope in them. An input that reads no key label and no output of its instance holds for every key, a broadcast, and stands after the key clause. Each group keeps the component's declared order.
- An input is a list whose head is the input's name, then one list of its head sites, then its body. The body is a sequence of atoms under the clause's safety condition. A head site projects a label that the body or the key made onto a column of the input, so no head site holds `*` or `0`: where the column's value is `0`, the body makes the label with `(= *X 0)`, as `(gap (G) (= *G 0))` does. Each column of the input other than `key` has a head site, other than a column of a type parameter that no site binds and its component gives no bound. The head of a `Cardinality` instance's `member` input, and of an `Excess` instance's `plus` or `minus` input, holds a site, since an input whose head holds no site holds at most one row at each key, and the count of its rows is then 0 or 1. A head site on a column of a fixed type holds one label. A label on no head site is existential. An input with no clause holds the lib's default rows, or the key's own values where the lib marks it from the key, and otherwise no row, and an input whose clause a stored reading takes holds the `DET`'s rows.
- An `INIT` form leaves an input with no row for certain where it writes no clause for the input, the input has no default rows, and the key does not fill it, which the key does where the lib marks the input from the key and the form's key has a column. The form is refused where it leaves an input that its component requires, or each input of a `one-of` group of its component, with no row for certain, since its component then gives no output. A component may have several `one-of` groups, and an input may belong to several. The lib registry marks them, as the module comment of `engine/arclog/src/registry.rs` gives. A `DEMONSTRATED` form takes no such refusal.
- A read at the key in scope writes the key site: a read of a relation keyed by `C` and `A` writes `(:key C A)`, and a read with no key site is not at that key.
- The first projection onto a type parameter binds it. A projection of one label gives the parameter that label's type, and every site on the parameter takes one label. A projection of several sites gives it a record with one field per site, named by the site's head, or by its label where the site is elided, and typed by its label. Every later site on the parameter names the fields it reads by projection, as [Sites](#sites) gives. A later site on a parameter that one label binds that holds more than one label is refused.
- An instance is per example when its key holds an Example label. Otherwise it is per input when its bodies read `input`, or read without its Example column a relation that the case's reading derives by a `RULE` clause or an instance that is per input. In every other case it pools over the examples, and its outputs have no Example column. An instance that is per example or pooled is task-wide, as a `DET` clause is.
- The instance's outputs are read as `<name>.<output>`, with the key's columns first and a parameter's columns in place of the parameter: `(&comps.component *P *Id)`, `(&area.size (:key *B) *N)`, `(&recolor.value (:key (:Col Col1)) (:v *Col2))`.
- An input that the form writes is read as an output is. An input with no clause holds its rows for the construction alone, and a read of it is refused.

### Type parameters
+ undisclosed
- A type parameter that its component bounds binds to the join of the types that every projection onto it gives, and projections with no join are refused. A binding of a type parameter that its component bounds to a type that is neither the bound nor under it is refused. A type parameter other than `Key` that no site binds takes the bound its component gives it, and is an empty record where the component gives none. An empty parameter contributes zero row positions, and a head writes no site on it. The successful relation of zero positions contains one empty tuple; it remains distinct from an empty relation.

### Unfold
+ undisclosed
```
(INIT &claim Unfold
  (key ((OR ((&claim_order.minimal (:key ^C ^A) (:t *B)))
            ((&claim_order.member (:key C A) (:t B)))
            ((&blocks C A (:B_last B) (:B *B2)))))
    (start ((:t B))
      (&claim_order.minimal (:t *B)))
    (initial_untaken ((:item B))
      (&claim_order.member (:key C A) (:t *B)))
    (conflict ((:item B) (:item2 B2))
      (&blocks C A (:B_last *B) (:B *B2)))
    (step ((:t B) (:t2 B2))
      (&claim_order.successor (:key C A) (:a *B) (:b *B2))
      (&claim.untaken (:t B) (:item B)))
    (skip ((:t B) (:t2 B2))
      (&claim_order.successor (:key C A) (:a *B) (:b *B2))
      (&claim.excluded (:t B) (:item B)))
    (take ((:t B) (:item B))
      (&claim_order.member (:key C A) (:t *B))
      (&claim.untaken (:t B) (:item B)))))
```
- `Unfold` is the one component whose inputs read its outputs. Its inputs that bind the type parameters, `start`, `initial_taken` and `initial_untaken`, come first with `conflict` and `score`, and the engine declares `taken`, `untaken` and `excluded` once they are bound, before it emits the names of `step`, `skip` and `take`; a `take` input with no clause takes the item of least `score`. In those three bodies, every site of an atom of an output joins, so the body binds its labels through its other atoms, and the recursion filters a finite set. Such an atom reads the rows of the current state at the current key. Where one of them names the `key` column, those atoms, one that leaves out `key` among them, also read the rows of the other keys, at each state their walks reach, and the walks run again until those rows stop growing. Such an instance holds none of those atoms under `NOT`, in an `ALL`, or in the test of an `IF`, since their rows would depend on the order of those runs. No other input reads an output of its instance. Inside an input that reads an output of its instance, `ALL` may not read that output, since the negation would recurse. The instance's reads of its own outputs count toward neither kind of the per-input rule in [Instance](#instance).

## Constraints
+ undisclosed
```
(RULE &ties
  (&row *K)
  (&fewer.rank (:t *F) *R)
  (<= R K)
  (ONE K)
  (ONE F))
```
- A clause may end in `ONE` marks, each naming key columns of its relation, and a model keeps one row of the relation for each value of each key. A `CHOOSE` form chooses one candidate for each row of its `for` clause, with the pairs that are never chosen together. The program reads a chosen relation like any other. [Constraints](./constraints.md) gives the two forms, which pick each writes, their models and the output set.

## The OUT form
- An `OUT` form states the program's output. It is `(OUT <atom>)`, whose atom holds two sites, or `(OUT <atom> <atom>)`, whose atoms hold one site each. Each atom is in parentheses and reads `input` or a relation the program declares, as a `RULE` body reads it. Each site selects one column, or one field of a record column, with one label marked `^` and nothing else: no `*`, no label with no mark, no `0`. The first site in written order selects a column of type Position or Box and the second a column of type Color. An `OUT` form that breaks one of these rules is refused.
- A site is elided as `^<name>`, with `<name>` the name of the column or of the field: `(OUT (&r ^C_out ^Col))` selects the columns `C_out` and `Col` of `&r`, and `(:t ^V)` selects the field `V` of the record column `t`. No site gives a label of its own, and no later form reads the labels of an `OUT` form.
- The rows of an `OUT` form are the rows of its two selected columns, Position then Color: the projection of its one atom's relation, or the product of the projections of its two atoms' relations. A case's output on an input is the set of grids those rows give, one per model of the program's `ONE` marks, `CHOOSE` forms and `DEMONSTRATED` forms, as [The output set](./constraints.md#the-output-set) gives. A two-atom `OUT` form whose second relation holds two colors on an input gives no grid there.
- Every program has an `OUT` form. The tail of a solver file holds one, after every other form, under no claim. A solver file whose tail holds no `OUT` form, a block that holds two, or an `OUT` form under a claim or at another place in its block is refused. No program's output is inferred from a relation. An `OUT` form holds where its output set solves every train pair, as the Solves section of [Cases and judge](../engine/cases.md) gives.

## Rigid
+ undisclosed
```
(RIGID_DET &marker
  (&glyph *P)
  (&launch *P)
  (&aim *D))
```
- A `RIGID_DET` form, a rigid determination, compares the parts of one assembly across its instances up to one D4 element per instance. The program reads each part through a `:Pose` column, and one pose read across several parts reads one placement of the whole assembly. [Rigid](./rigid.md) gives the form, its outputs and what a pose may be tested by. No two parts of the form begin their outputs with one name, and a form with two such parts is refused.

## Alts
- An `ALTS` form gives a property that the train pairs underdetermine. The concept case answers it one way, and each alt is a hypothesis that answers it another way. The `OR` form joins its branches into one hypothesis; an `ALTS` form splits its alts into hypotheses.
- Alts represent an ARC task's cases, and a solver session writes them. A file with no `ALTS` form and no `DET_OR_RULE` or `RULE_OR_DET` line has one case.

### The `ALTS` form
- An `ALTS` form stands after the concept program: its name, its quoted gloss, the concept case's name, then an `ALT` block per alt.
- An `ALT` block, `(ALT $<Name> <form>...)`, holds:
    - an `INPUT` or `OUTPUT` block for each claim the alt reads differently, with the alt's reading of the claim as its text.
    - a block under a slug of its own for each claim the alt adds.
    - the tail forms that the alt rederives, the `OUT` form among them.
    - the forms that derive the relation an `OUT` form of the block, or of a block that holds it, reads, which is the output relation of the block's cases as the tail's is of the concept case.
- Every relation an `ALT` block does not mention is the concept program's.
- An `ALT` inside an `ALT` holds what the combination of the two alts rederives. Where alts of two `ALTS` forms each rederive a relation, the nested `ALT` of their combination rederives it too, as the combination derives it.
- An `ALTS` form that exists only with the concept branch of another `ALTS` form stands in an `ALT` block of that concept branch's name, which holds only its `ALTS` form.
- In an alt's cases, each form reads a relation that the alt rederives as the alt derives it.
- A `DET` in the concept program reads the concept program's derivation in every case, since a parameter that the cases share has one determination.
- A case has one deriving form for each relation: the forms of the blocks of greatest depth, a `DET` as a `RULE`. So a `DET` that an alt rederives replaces the concept program's `DET` of that relation in the alt's cases, and blocks of equal depth from different `ALTS` forms each keep their forms.
- No alt rederives a relation that a `DET` of the concept program reads, directly or through other relations. Where the solver's determination reads its own derivation of a relation that an alt rederives, the concept program holds that derivation under names of its own (`&x2` for `&x`), which the `DET` reads. A case where such a read stands is refused.
- A relation that no block of a case derives is undefined in that case, and a relation under `NOT` is derived in every case that reads it.
- A case takes the `OUT` form of its most specific blocks that hold one: each such block of the case, the tail included as the block of no alt, whose alts no other such block of the case holds with more. Equal forms of those blocks are one.
- Where those blocks hold different `OUT` forms, the case is refused, unless a combination block holds an `OUT` form of its own.
- An `ALT` block may hold an `OUT` form, after each of its forms other than its `ALT` blocks and `ALTS` forms, under no claim. It holds none equal to the `OUT` form of each most specific block whose alts it holds, the tail included, since its cases take that form without it.
- A relation of the concept program other than a `DET`'s has only the columns that the concept case reads. Where an alt's derivation of the relation has more columns, the alt rederives, in its own block, the first form that reads the relation, and that form reads the alt's columns.
- The cases are the product of the `ALTS` forms, restricted by the nesting of the blocks.

## Stored readings
- A `DET_OR_RULE` or `RULE_OR_DET` line is an `ALTS` form on its relation, whose readings are `&background=$Stored` and `&background=$Derived`, the concept case's reading first, and the other reading is its alt. A quoted gloss, where the solver states one, stands after the relation's name and before its proposers, and the claim text of the derived reading is the proposer's. The cases are the product of the `ALTS` forms, with a line counting as one in each base whose `OUT` form reads its relation, as [Cases](../engine/cases.md#cases) gives.
- A line with several proposers has a derived reading per proposer and, where it has no body, a stored reading per proposer, each in the order of the proposers, and each reading other than the concept case's is an alt of its own: `(DET_OR_RULE &tile_size ConstInDim SepTileDim)` has `&tile_size=$Stored.ConstInDim`, `&tile_size=$Stored.SepTileDim`, `&tile_size=ConstInDim` and `&tile_size=SepTileDim`. The clause of a reading by a proposer names that proposer alone, as `(DET &tile_size SepTileDim)` and `(RULE &tile_size SepTileDim)`.
- A line with no body has its first proposer's columns, in every reading, and each other proposer's columns map onto them by position. A `DET` that names one proposer, with no stored reading, has that proposer's columns: `(DET &bg ChangedColor)` is read as `(&bg (:C *C))`.
- Where one reading has clauses of its own, the line holds their body after its proposers, and the line is the relation's one clause.
    - On a `DET_OR_RULE` line the body is the stored reading's determination.
    - On a `RULE_OR_DET` line the body is the derived reading, the concept case's.
- The stored reading is a `DET` of the relation whose rows are the rows that the body's derivation gives at every train example, over the columns that a read of the relation names in any case, the Example column left out, as the column rule of a `DET` gives in [Sites](#sites).
- A `DET` of the concept program that reads the relation reads the body's derivation, and so does each other read of the relation with a site on `E`; where a block of the case derives the relation anew, they read that derivation in place of the body's.
- In the stored reading of a `RULE_OR_DET` line with a body, where a block of the case derives the relation anew with a `RULE`, the `DET` holds the rows that the `RULE` gives at every train example, and stands in that block.
- A `DET_OR_RULE` or `RULE_OR_DET` line on a port of an instance, an input or an output, names the port as the program reads it, and holds no body.
    - In the derived reading the instance derives the port, and the line is no clause.
    - In the stored reading of a `RULE_OR_DET` line, the `DET` holds the rows that the port's derivation gives at every train example.
        - On an output, the instance stays, and each read of the port other than a `DET` of the concept program's, and other than a read with a site on `E`, reads those rows.
        - On an input, the `INIT` form's clause of that input is replaced by a read of those rows, since the instance still declares the port.
    - Only a `DET_OR_RULE` stored reading, and a line whose input has a head site on a record or a `^` label, leave the input out of the `INIT` form.
    - The stored reading of a `RULE_OR_DET` line on an output of an instance that has a key clause has value columns, as [arclog expansion](../engine/arclog-expansion.md) gives them.

## Demonstrated
+ undisclosed
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
- A `DEMONSTRATED` form is a `DemonstrationConsistency` instance whose rules are its `DEMO_RULE` forms. `value` and `demonstration` are the component's inputs, written as an instance's are, and a keyed form takes its key clause as an instance does. The form is per input or task-wide by what its input bodies read, as an `INIT` form is, and each `&prediction` clause is the same. Each `DEMO_RULE` is a demonstrated rule: its name, the rule's text where the solver states one, then the clauses that read what the rule needs from the input, and it derives `&prediction` with the columns the `value` head names. A `&prediction` clause makes a label named as each of those columns, and a clause that leaves one out is refused. A rule with fields names each field with a fresh label after its constructor, `(DEMO_RULE ($Move *D) "…" …)`. Its `&prediction` has a column for each field, and the form holds one rule for each value that the rule's clauses bind for the field.
- In a keyed form, the key's labels are in scope in the inputs inside the key clause, as an instance's are, and not in the `DEMO_RULE` bodies, which stand after it. A `DEMO_RULE`'s clauses name the key's columns by the key's labels, and its `&prediction` has those columns beside the ones the `value` head names, so the form reads each prediction at the key whose labels it makes. A `&prediction` that makes no key label holds at every key, as a broadcast input does in an [Instance](#instance). Above, the key's labels are `Pan` and `Pan1`, the answer panel and the shown panel, and each rule's `&prediction` makes both from `&slot`, so it holds at each key that `&slot` gives.
- A `*X` or `^X` in a clause of a `DEMO_RULE` is refused when it makes a name that a field of the `DEMO_RULE` holds.
- The relation the form declares holds, at each key, the predictions of one rule that every demonstration of the key confirms. Each choice of one confirmed rule per key is a model, as [Demonstrated choice](../handbook/solver-file.md#demonstrated-choice) gives, and the case's output holds one grid per model, as [The output set](./constraints.md#the-output-set) gives. A demonstration confirms a rule where the rule's prediction for its first object equals its second object, at the same indices with the same value at each. A key with no demonstration holds no prediction. The relation's columns are the key's, then the `o`, `i` and `v` of the `value` head. It has no column for a rule or a field, so no read names one. The form states the test against every demonstration, so a program writes no test over `demonstration` of its own. Above, a key's demonstrations take the shown panel to each panel that `&slot` gives as done at that key.
- The input determines the rules that stand, and no stored value records them. Demonstrated rules split no cases, so the form declares a relation and takes `&`.

## Open values
+ undisclosed
- A parameter is open when the pairs do not separate the values a reader of the intended concept could take. Its determination ends in [One](./constraints.md#one), so each value it keeps is a model, and the case's output is the set of grids its models give, as [The output set](./constraints.md#the-output-set) states:
    ```
    (DET &start_corner
      (diag_dir_elem *D)
      (NOT (&start_contradicted (:C D)))
      (ONE))
    ```
- The arcdata file holds the values as the parameter's `param` rows, as [Params](./arcdata.md#params) gives them.
- A determination by a proposer, and a `DET_OR_RULE` line, take the mark after their proposers: `(DET &quorum NumberDomain (ONE))`. On a `DET_OR_RULE` line the mark holds on each reading, so on a derived reading each value the proposer gives on the input is a model.
- The mark `(SET)` stands in the same place on a `DET` or a `DET_OR_RULE` line with no body by proposers of one column, none marked `domain`: `(DET &palette UnchangedColor (SET))`. The parameter then has one value, the proposer's whole set of rows, where it has one value per row without the mark. A form with both marks takes `(ONE)` over the one value `(SET)` gives. A clause's `(SET)` mark stands before its `ONE` marks.
- A session records a value as open where another task in the family of the case's hypothesis could fix it. Where none could, the parameter is absent and a symmetric form takes its place.

## Names
- Each kind of name has its own spelling:
    | kind | spelling |
    | --- | --- |
    | keyword | `RULE` `INIT` `CHOOSE` `OUT` `OUTPUT` `DEMO_RULE` `DET_OR_RULE` |
    | fact relation | `input` `ex_input` `ex_output` |
    | lib relation, proposer | `margin` `inside` `DominantColor` |
    | instance | `&comps` |
    | instance relation | `&comps.component` |
    | derived relation, chosen relation, demonstrated | `&fg` `&ties` `&catalog` |
    | alts, alt | `$locate` `$Box` `&background=$Derived` |
    | claim slug | `container` `fill-interior` |
    | label | `P` `Col1` |
