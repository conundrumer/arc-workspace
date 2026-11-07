# arclog stream

The forms of an [arclog](../arclog/arclog.md) program that the engine shows: the token stream a language model emits, its trace form, its infix view, and the second spellings the decoder could block.

The stream has two renderings, and both are projections of it:

- The **program form** shows the program to a solver reader.
- The **trace form** shows one decode of the stream to a reader debugging the synthesis: the program with the engine's forced tokens, and on request the language model's top-k tokens at each decision.

Both are stored as s-expressions, read by one fixed reader. An infix view of the program form is printed on request and is never stored or parsed.

The decode ends at the first `OUT` form that holds, as [Decode interface](synthesis.md#decode-interface) gives.

## Token stream

The language model emits tokens from these sets, each a closed set of ids:

- control: `RULE` `DET` `INIT` `ONE` `SET` `CHOOSE` `RIGID_DET` `OUT` `OR` `IF` `ALL` `END` `SKIP` `ALSO` `NOT` `*` `^` `0`, the constraint operators, and `DEMONSTRATED` `DEMO_RULE` `PREDICT` `ALT_FORM`, which no stream holds. `^` marks a label of a key clause's body as a column of the key, as [Instance](../arclog/arclog.md#instance) gives, in an instance's `key`, a `CHOOSE`'s `for`, a `RIGID_DET`'s `instance` and `key`, and an `OUT`'s atoms, and the engine echoes the label after it as after `*`.
- lib relations and components, one token each; proposers, one token each
- fact relations: `input` `ex_input` `ex_output`
- derived relations: the index the engine assigned at the declaration
- column tokens: a relation's columns, which for a derived relation are the labels of its clause; the fields of a site on a record-valued column, by their position in the record; and the names the engine emits for a form's inputs and named clauses, by position: an instance's `key` at 0 and its component's input k at 1 + k, a `CHOOSE`'s `for`, `from` and `never` at 0, 1 and 2, a `RIGID_DET`'s `key` and `instance` at 0 and 1, a `DEMONSTRATED` form's `key`, `value` and `demonstration` at 0, 1 and 2, and the columns a `PREDICT` clause fills, by position; in an `INIT`, `CHOOSE` or `RIGID_DET` form, a read of a derived relation that is per input and is no relation of the form itself gives the Example column the column token 0 whether or not the read is lifted, and the relation's own columns follow it
- labels: the variables of the current clause, in order of creation

The engine emits the declaration of each derived relation, the declarations at each instance or `CHOOSE` form, the name of each input, each column name of a projection, and the label echo after each `*` and `^`. The declarations at an instance follow its component token: each output, then each input whose name no output shares, written or not. The engine names each input of the component, an unwritten one too, and the language model declines an unwritten one by `SKIP`. In a keyed instance, the key clause names each input, and after the key clause the engine names each input that the key clause did not write. A projection names each column of the input, and an empty one is answered by `END`. It emits the name of each named clause of a form as it emits the names of an instance's inputs: an instance's `key`, a `CHOOSE`'s `for`, `from` and `never`, and a `RIGID_DET`'s `instance` and `key`. The language model never emits a label it has not seen echoed, and never names a relation or a column with text.

The token sets are disjoint, so an atom's site list ends at the first token that is not a column token, and no separator exists. Every site opens with its column token, an elided one too.

The language model emits `END` where a decision to stop exists: at the end of a body, after each projection's labels, after the field sites of a site on a record-valued column, after each `ONE` mark's key labels, at the end of an `OR` form, and after each list of an `IF` or `ALL` form. It emits `ALSO` between the branches of an `OR` form, which are a repeat as the clause that may repeat below gives, so an `OR` in a branch after a conjunct opens a nested `OR` form. The decoder admits `END` at the end of a body once the clause is safe. It refuses the `END` that closes an `ALL` form's second list while that list holds no conjunct, as [Universal](../arclog/arclog.md#universal) gives. It refuses the `END` that closes the last projection of a `Cardinality` instance's `member` input, or of an `Excess` instance's `plus` or `minus` input, where the input's head holds no site, as [Instance](../arclog/arclog.md#instance) gives. A clause's `SET` mark, as `SET`, follows its body before its `ONE` marks. A clause's `ONE` marks follow its body, each as `ONE`, its key labels and `END`, before the clause's `END`. The decoder refuses the `ONE`, a label or the `END` of a mark after which every completion of the mark names a label twice or the set of labels of an earlier mark of the clause, as [One](../arclog/constraints.md#one) gives.

The language model emits `SKIP` after the name of an optional clause or input, to decline it. After the name of a required clause, the decoder refuses `SKIP`. An input of an `INIT` form is required where its component gives no output while the input holds no row. The inputs of a one-of group are those where the component gives no output while none of them holds a row. A component may have several one-of groups, and an input may belong to several. The lib registry marks each required input and each one-of group, as the module comment of `engine/arclog/src/registry.rs` gives. An input that the form does not write holds the rows that [Instance](../arclog/arclog.md#instance) gives it. A `SKIP` thus leaves an input with no row for certain where the input has no default rows and is not marked from the key, or where it is marked from the key and the form's key has no column: the form has no key clause, or its key clause has no `^` label. After the last name of a required input, the decoder refuses the `SKIP` that leaves the input with no row for certain. For each one-of group of the input, where the form writes no input of the group, the decoder refuses, after the last name of the group's last input in the component's order, the `SKIP` that leaves each input of the group with no row for certain. The text checker refuses the form that leaves such an input or group with no row, as [Instance](../arclog/arclog.md#instance) gives. Where the form's key has a column, the key fills an input marked from the key wherever its labels have the types that the input needs, and the decoder admits the `SKIP` of that input.

A `RIGID_DET` is written as `RIGID_DET`, then the `key` name and its body and `END`, or `SKIP`, then the `instance` name and its body and `END`, or `SKIP`, then its parts, each an atom, then `END`; the engine then declares the form's outputs.

An `OUT` form is written as `OUT`, then each atom as an atom of a key clause's body is written, a relation, then each site's column token, `^` and the engine's echo of the label, then `END`; the engine declares nothing after it, and the program's last form is its `OUT` form.

The grammar has no `DEMONSTRATED` form. The vocabulary holds the tokens `DEMONSTRATED`, `DEMO_RULE`, `PREDICT` and `ALT_FORM` so that no token id changes, and the decoder refuses each of them at every state. The writer gives no stream for a program that holds a `DEMONSTRATED` form. The form stays in the language, as [Demonstrated](../arclog/arclog.md#demonstrated) gives, for the reader and the evaluator. The resolved content of a query holds the form with no rule name, no rule text and no clause gloss.

A clause that may repeat, such as `never`, is written as its first instance, then `ALSO` and the next instance, for each further repeat. The next name the engine emits, or the `END` that closes the enclosing form, ends the run, so the repetition has no token of its own at its end. A `CHOOSE` form whose `never` clause is written closes with `END` after its last `never` clause, and the engine then declares the form's relation.

### Second spellings

Two spellings of one body are equivalent by syntax alone in these cases, and the decoder could block one of each pair. They are suggestions to consider, not rules of the stream.

- In an `OR` branch, a `NOT` of an atom that an earlier branch holds positively with the same joined labels: the `IF` form spells it.
- An `IF` whose test is one `NOT` atom: the same `IF` with the then and the else swapped spells it.
- `NOT` over a form: the domain with a negated body spells it, as "some member fails".
- Sites out of the relation's column order. The engine's writer of a decoded program writes the sites of each read of a derived relation in ascending order of the relation's slots, and names the labels in the order the text makes them. A read stays in its order where the new order would change the order of its `^` labels, which is the order of key columns, and where a join of the read would then stand before the site that makes its label.

Two spellings equivalent by meaning alone are left to the training data: a `NOT` on a derived relation whose own clause negates, against an `ALL`, which are the same only where the domain has a member at every binding of the clause that reads it, as each domain atom of the defect clause matching a positive atom of the reading clause, or being an element relation of the lib, gives, since an `ALL` over an empty domain fails, and otherwise the `NOT` is the only spelling; an else that re-reads an outer atom to carry a label, against `=`; the order of atoms; and a body written twice against a relation derived once.

## Trace form

The trace form is the program's tree with the engine's forced tokens in brackets, in the stream's order. Every other symbol is a generated token, one the language model emits. A site is `(:Col *[P])` at a fresh label, the `*` the language model's and the echo the engine's, or `(:Col P)` at a join.

```
(RULE (input (:P *[P]) (:Col *[Col]))
      (&bg (:C *[V]))
      (!= Col V)
      END)
[&fg]

(INIT Connectivity
  [&comps.component &comps.adjacent &comps.node &comps.step]
  [key] SKIP
  [node]
  ((&fg (:P *[P])) END
   [node key] (END)
   [node P] (P END))
  [step] SKIP)

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
- the declarations after an instance's component, each output and then each input whose name no output shares, `[&comps.component &comps.adjacent &comps.node &comps.step]`
- an input's name alone, before its body or its `SKIP`, is the input name, `[node]`, `[key]`
- an input's name with a column is the column name, `[node P]`, and the list that follows is the language model's answer, `(END)` for an empty projection
- a label after `*` is its echo, `[P]`

A clause's `END` is the language model's, and its declaration follows it as a sibling. An instance has no `END` from the language model: it ends when the engine has emitted the name of each input, and its declarations sit inside it, after its component.

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

