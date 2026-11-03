# Prediction, written before any read

- A pair term on join, shared `Ident` type or value overlap separates scopes with a cover from scopes without one at AUC about .60, against .50 for shuffled labels.
- A scope pick by node score plus that term saves .2 to .5 of the 1.1 bits on read forms in the pool but not in scope, leave-one-task-out, and little of the 3.1 bits on the wait.
- Most of the gain comes from a column join between nodes, and value overlap adds under .1 bits. The earlier node pair score added +.012 on content.
- The term costs under 2 ms per draw with a per-node table sketch, which is cheap against a proposal of about 180 ms.
