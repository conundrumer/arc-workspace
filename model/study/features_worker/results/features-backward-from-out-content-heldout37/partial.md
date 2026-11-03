# Backward from OUT: content of a read form

Status: finished through the held read. Numbers are in `read-held.md`, `read-held.json`, `read-candidate-held.json`, and the situations are in `situations.tsv`.

## Unit and state

- An edge is (reader, read form, atom). The reader is OUT or a gold form. A body is a set.
- Depth: OUT is 0, and a form is 1 plus the least depth of its readers.
- Primary edge: the form's reader of least depth. A hash of the texts breaks ties.
- A form with no primary edge saves 0. On held, 53 of 1,011 forms have none.

## Facts

Each fact reads the output side only. The read atom is masked: its relation name, port and column names are gone.

- `out`: the output need at OUT and the grids.
- `body`: the reader's body as a set, with hole types from the lib signature. Role, reader component, join partners, shared labels, set sizes, depth, and whether a hole column carries OUT's position or color.
- `body+cols`: also the reader's own head columns. A head column can give a hole column's type where nothing else in the body does.
- `full`: all of these. It is the primary tier, and on fit it picked the same keys as `body+cols`.
- `open`: also the read atom's port and column names. This is the read form's own text, so it is an upper bound and not a fact a search has before the form exists.

## Targets

Component or lib relations, head columns, geometric shape, relational shape, as in `features-next-form-content-given-task-heldout37`, on the table the atom reads. Kind is added.

## Models

- Tables per situation, with a Dirichlet fallback, and a softmax over weighted lifts. Keys are picked greedily on 5 task folds of the fit tasks.
- Need per candidate: a conditional logit on binned facts per situation, over the tables of gold's forms outside the reader and outside the forms that read it.

## Lexical order

No model fact or target reads lexical order. The marks `*` and `^` aren't read, because the site that makes a label depends on written order. These stand in the baseline or in the plumbing only:

- The census walk draws atoms in written order, its weights read the prefix, and its options are the forms before the form in gold's text. The candidate tilt uses those same options.
- The replay steps forms in gold's order to make tables. A table doesn't depend on that order.
- Parsed atoms are aligned to a row's reads by written order, only to find each atom's owner.
- A head table with no read ordinal is the lowest declared ordinal of the component, a declaration order and not a body order.

## How a backward step maps onto census bits

A search draws forward, so the tilt acts at the forward draw of the read form, at its component pick and its relation picks. The change in those picks is exact. The number assumes:

1. The search holds the reader's body and columns before it draws the read form, at no cost. The reader's own text isn't charged.
2. The search knows which reader goes with this draw. With M open goals and draws split evenly, subtract log2 M per form. At M = 2 the primary number is about 0.
3. Each form uses one reader, the primary edge.
4. The read form's own reads exist, as in the census.

Kind, column, label, join and stop picks are outside the number.

The candidate tilt is a different quantity. It acts at the reader's own pick of a derived relation, and it needs the rest of that reader's body and its head columns at that pick. A forward search has neither there. Only arm `out` reads no reader, apart from the kind of form being drawn.

## Results

Fit: 14,981 primary edges of 1,011 tasks. Held: 958 primary edges of 37 tasks, 1,006 forms with census bits, 347 at 25 bits or more. See `read-held.md` for each table.

## Prediction check

See `prediction-agent.md`. Primary +1.01 against about +.8, then about +1.2: held. Output need adds nothing: held. Columns saved most: held on all forms at +2.24. Depth 1 saves little: missed, at +1.19. Need per candidate beats need per state by about .5: missed for the arm a forward search has, at +.08 against +.03.
