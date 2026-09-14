# Coverage rules: what a pass admits, when a removal settles, what a part is

Open question in `principles.md`, Coverage: the ordered-rules bullet and the Exercised bullet under Evidence.

## The question

Three gaps in one section:

- Exercised is written as a removal, and its closing clause says a peer that adds no part "passes it". A pass reads either as admitting the peer's case or as leaving the case to the rules that admit one.
- The rules "apply in order", and nothing says that the first rule which removes a peer settles it. A removed peer reads either as out of the check or as still weighed by every later rule, Subsumption included, which removes the current model rather than the peer.
- Exercised tests the "parts" a peer adds and gives "part" no size. A comp whose inner test no pair reaches is exercised as a whole unit, since every pair's output derives through it, and idle as the test inside it.

## The text

> - The rules of this section apply in order:
>     1. Prior or setup.
>     2. Evidence.
>     3. Subsumption.
> - A peer that Evidence removes gets no case, even when it subsumes the current model.
>
> - **Exercised.** A peer model has rules, parameters, or comps that the current model does not. If no pair exercises them, that peer gets no case.
>     - A pair exercises a part of the peer when that pair's output derives through it:
>         - even where a narrower rule would give the same output on every pair
>         - even where the part's result matches the current model's on every pair
>     - Exercised tests only the parts the peer adds; a peer that adds none passes it.

## Candidate text

> - A peer gets a case unless a rule of this section removes it. The rules apply in order: […]
> - The first rule that removes a peer settles it, and a removed peer takes no part in a later rule.
>     - A peer that Evidence removes gets no case, even when it subsumes the current model.
>
> - **Exercised.** […]
>     - A part is a rule, a parameter, or a comp the peer adds, taken whole. A test inside a rule both models hold is no part of its own.

The whole-unit reading is the one the clause "even where the part's result matches the current model's on every pair" already states. The narrow reading, asked for in 7c9b52a0, reverses that clause: "A part is the finest test the peer adds, and a pair exercises it only where that pair's output turns on the test's result."

The precedence gap has three readings:

1. **Precedence.** The candidate text above: a removed peer takes no part in a later rule. 9473c6fb keeps `Separate | Span`, with `Count` out.
2. **Scoped.** Refused input decides subsumption alone, and a peer that Prior or setup removed can still subsume the shipped model at rule 3.
3. **Merged.** The strict-and-tolerant sentence moves from Refused input to Peer priors, so 9473c6fb and 97239e3d keep both readings as cases.

## Where the approved corpus stands

Three approved solvers hold a case that the inner-test reading removes: 8e5c0c38 (`ByObject`, whose `Components8` separates nothing on the pairs), 1a6449f1 (`Enclose`, whose `Closed` agrees with `Outlines` on every pair), 4c416de3 (`Fill`, whose fill test never bites on the pairs). Approved reports that record an Exercised ground the whole-unit reading does not support: 4c416de3, 898e7135, 332efdb3, bdad9b1f, 57edb29d, 264363fd, 928ad970; each such peer is then decided by the rules after Evidence.

## Solvers

Drafts, with what is at stake:

- 54dc2872 — `Slide` kept beside `Translate` because the pairs exercise it, with no rule of Prior or setup applied. Under the candidate text the case rests on `peer-priors.md`.
- 67e490f4 — the into-reading peer passed Exercised and was refused under Peer priors. The candidate text states that reading.
- 668eec9a — the lex-order peer was removed at Prior or setup and again at Evidence, as adding a secondary key no pair exercises. Under the whole-unit reading its `LexOrder` is exercised, and the peer reaches Subsumption unless Prior or setup removes it. Its tie witness below makes the nearest-row rank conflict where the lex peer is total. The clash was raised again in the refine and finalize passes, each of which shipped one case.
- 7c9b52a0 — the precedence fold runs on every pair with singleton candidate sets; the peer was dropped under Underdetermined choice (`underdetermined-scope.md`). Under the whole-unit reading Exercised does not remove it, and on the overlap witness below the union fold conflicts where the precedence peer is total.
- 9720b24f — 2 cases; the whole-unit reading gives 4, since the parity peer's walk runs on every pair.
- 8a6d367c — six combinations; the whole-unit reading gives twelve, the strict peer refusing the ragged witness that every shipped case renders.
- 9473c6fb — `Count` dropped under Peer priors; without precedence `Count` subsumes `Separate`.
- 97239e3d — `$Touch()` kept beside `$Nearest()` under Refused input.

## Witnesses

668eec9a, two lines tied on the nearest row (background 7):

```
7 3 7 7 7 1 7 7
7 7 3 7 7 7 1 7
7 7 7 3 7 7 7 1
7 7 7 7 7 7 7 7

nearest-row rank: the last row holds 3 and 1 at once
lex order with a secondary key: 3 3 3 above 1 1 1, total
```

7c9b52a0, two panels inking one canvas cell:

```
1 1 1 1 1 1 1 1
1 2 . 1 1 1 1 1
1 . . 1 1 1 1 1
1 1 1 1 1 1 1 1
1 1 1 1 3 . 1 1
1 1 1 1 . . 1 1
1 1 1 1 1 1 1 1
1 1 1 1 1 1 1 1

union fold: cell (0, 0) holds 3 and 2 at once
precedence, first panel foremost:
2 .
. .
```

9720b24f, a comb of 3 with one 2 in its third tooth; the shipped two cases erase the 2, and the parity peer keeps it:

```
input          shipped        parity peer
3 3 3 . .      3 3 3 . .      3 3 3 . .
3 . . . .      3 . . . .      3 . . . .
3 3 3 . .      3 3 3 . .      3 3 3 . .
3 . 2 . .      3 . . . .      3 . 2 . .
3 3 3 . .      3 3 3 . .      3 3 3 . .
```

9473c6fb, four marks on background 7, two sharing a row and three sharing a column, so both axes hold a tie; `Separate` and `Span` name no axis and leave every mark uncolored, while `Count` names the axis with more lines and is total:

```
input              Separate, Span     Count
7 7 7 7 7          7 7 7 7 7          7 7 7 7 7
7 9 7 9 7          7 . 7 . 7          7 2 7 2 7
7 7 7 7 7          7 7 7 7 7          7 7 7 7 7
7 9 7 7 7          7 . 7 7 7          7 5 7 7 7
7 7 7 7 7          7 7 7 7 7          7 7 7 7 7
7 9 7 7 7          7 . 7 7 7          7 2 7 7 7
7 7 7 7 7          7 7 7 7 7          7 7 7 7 7
```
