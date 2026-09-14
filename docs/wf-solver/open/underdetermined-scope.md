# Underdetermined choice: over the task, or over the family

Open question in `principles.md`, Invariance — Underdetermined choice.

## The question

The rule removes a choice from the parameterization when "every assignment permits" it, and the program enumerates its class. The text does not say whether "every assignment permits" ranges over this task's pairs or over every task of the model's family. The approved corpus stands on both sides: 28a6681f enumerates its pour order, both orders fitting every pair; 1da012fc stores `corner(DIAG_TL)` although all four corners reproduce every train and test output.

A parameter the sweep admits two or three values of, out of ten, is task data under either scoping, since some values are refused; its stored value is the determination's matter (`determinable.md`). A grid outside the task on which two values give different outputs is a task that fixes the value, so it is the family test carried out.

## The text

> If every assignment permits a program choice, that choice is not task data.
>
> - A parameter for it is unwitnessed.
> - A literal hides it.
> - The program enumerates its class and derives `out` per member, so the output is defined where the members agree.
>     - 28a6681f

## Candidate texts

Family scoping:

> If every assignment permits a program choice, in every task of the model's family, that choice is not task data.
>
> + ∀T′ ∈ fam(M) ∀v ∈ Θᵢ. M(θ(T′)[i ↦ v]) ⊨ T′
>     + θ[i ↦ v] — θ with parameter i at v
>
> - A parameter for it is unwitnessed: no task of the family separates its values.
> - A choice that some task of the family fixes is task data, and its value on a task that leaves it open is the determination's matter.
>     - 1da012fc

This is the form Closure's Reassigned set already uses (∃T′ ∈ fam(M) ∖ {T}. θ(T′)ᵢ ⊊ C), and Invariance opens "Generalization happens at the family level".

Task scoping:

> + ∀v ∈ Θᵢ. M(θ(T)[i ↦ v]) ⊨ train(T)

Under it a choice every value of which fits this task's pairs is enumerated, whatever a sibling would fix.

## Consequences

- Family scoping. Approved: no change; 1da012fc gains the citation. Drafts: 7c9b52a0's panel precedence and 668eec9a's tie-break key are data, since a sibling with an overlap or a tie fixes them. Those peers then pass Exercised (`coverage-rules.md`) and reach Subsumption, where each is total exactly where the current model conflicts, so each draft's model changes: the precedence fold with a stored order in 7c9b52a0, the lex order with a stored secondary key in 668eec9a.
- Task scoping. Approved: 1da012fc's `corner` leaves Params and the program enumerates `diag_dir_elem`. Drafts: 7c9b52a0 and 668eec9a stand; their orders enumerate into the models they hold.
- Either scoping. The drafts whose sweep admits a second value keep their parameters: 23b5c85d, 36fdfd69, 1f85a75f, 72ca375d (`bg`), 1caeab9d (`align_dir`), 5961cc34 (`source`), 3befdf3e (`fig_core_box`), 92e50de0 (`anchor`). The literal bullet is unavailable for a color, which `style.md` bans in the program.

## Witness

1da012fc, two shapes tied along the reading axis; a task holding this pair fixes the corner:

```
. . . . . . . . . 5 5 5 5 5
8 8 . . . 8 8 8 . 5 2 5 5 5      DIAG_TL: the left shape takes 2, the right takes 3
8 8 . . . 8 8 8 . 5 5 5 5 5      DIAG_TR: the left takes 3, the right takes 2
. . . . . . . . . 5 5 3 5 5
```

## Tool gap

`run_dl.py sweep` varies the color a one-fact parameter holds and does not add members to a set-valued parameter, so 72ca375d's finding (`bg(0). bg(1).` passes every pair) is not reproducible from the sweep output.
