# Ambient bindings in CHOOSE never bodies

The fault class is a disagreement between checked lexical scope and the
runtime clause compiler. `check/safety.rs::bodies` gives every CHOOSE never
body its row-key and candidate header labels. Previously
`eval/picks.rs::never_pairs` compiled the body independently twice: once to
discover its first two candidate reads, then again to project the columns
needed for pair matching. Neither compilation supplied the given labels.
A valid reference to an ambient label could therefore fail with `Unbound`.
Even a label also bound locally lacked the ambient domain restriction.

Both compilations now use `ir::compile_ambient_body`. If the body mentions
an ambient label, its context is the CHOOSE for/from option domain projected
to the row-key and candidate headers. A KeyRead supplies those bindings to
the never clause using the same mechanism as keyed INIT inputs. The context
is a separate relation, so private witnesses of for/from cannot accidentally
bind labels in the never body. The projected pair query keeps its original
columns; context-only variables are existential witnesses, not extra pair
coordinates. Native faults, undefined values and stops propagate normally.

A never body with no reference to any given label retains its independent
query. This is lexical independence, not a task-specific exception or a
recovery from a failed compilation. All never clauses, with or without a
for key and with either kind of from body, take the same compilation path.
The existing keyed INIT and keyed CHOOSE from paths already supply their
ambient context; they do not have this missing-binding condition.

The observed 4cd1b7b2 concept mutation changes `same_line` from local P2 to
ambient key P. Its candidate reads still bind P2 and P3, but cannot bind P.
The checker correctly accepts this body; the native evaluator must obtain P
from the option context rather than reject it, invent a value, or skip it.

Validation uses exact corpus identity replay on an immutable runtime built
from the landed revision. No live corpus settings or bounds are changed.
