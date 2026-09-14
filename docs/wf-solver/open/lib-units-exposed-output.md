# Lib units: when the one step a program needs is an exposed output

Open question in `principles.md`, Fidelity — Lib units, the sub-items under the part-of-a-computation bullet.

## The question

The rule carries two sub-items, and they overlap when the one step a program needs is itself an exposed output.

## The text

> - Needing part of a unit's computation is not a reason to use it.
>     - A program that needs only one step of a unit writes that step with primitives or a local rule.
>     - A program may read one exposed output of a comp and leave the rest unread, as long as the task has the unit's concept.

## Candidate texts

1. **Add.** A third sub-item:

    > - When the one step a program needs is itself an exposed output, the concept decides: the program reads that output where the task has the unit's concept, and writes the step locally where it does not.

    Both sub-items stand, and 984d8a3e keeps its `Slide<Color>` instance.

2. **Narrow.** The first sub-item reworded:

    > - A program that needs one step of a unit's computation, and does not have the unit's concept, writes that step with primitives or a local rule.

    No line is added, and a reading that dropped a unit with the concept present loses its support.

## Solvers

- 984d8a3e (draft) — its create pass called the read a judgment call, shipped the `Slide<Color>` instance, and kept the local-rule version at `.scratch/984d8a3e/984d8a3e-local.dl`. Its refine pass changed the read from `run.rim_dir` to `run.rest`, to put the code on the concept side.

## Witness

The program needs the run's rest cell, which `Slide` exposes.
