# Finite orientation inputs of union branches

The fault class is inconsistent variable availability in the join planner.
Algebra modes and branch grounding accept a variable with a native finite
orientation domain, even before a concrete value is bound. The union read
check instead required every non-export branch column to be physically
placed. A nested union reading such an orientation could therefore be
blocked despite being executable. Completion could then order a dependent
algebra output before any source could bind it, reaching the runtime's
missing-domain invariant assertion.

`plan::bound_or_finite` is now the single availability predicate for
`grounds`, `Grounding::covers` and `mode_holds`. It uses the variable type of
that branch's checked ClauseIr and the caller's actual binding vector, plus
native `geometry::orientation_domain`. It changes neither the binding
vector nor the set of finite types. Recursive grounding and branch planning
use the same predicate at every nesting depth. The search assertion remains
unchanged, and the fix introduces no enumeration fallback, record skip,
expected-data assumption or work-cap change.

The exact 9b2a60aa `$FourDir $Fill` K=3 delete reproducer reaches native
mutant OUT, then Distance's INIT key, then a union branch search. It fails
before study body tables or extent derivation. Its checked key IR has a
nested union exporting Number variable 2 and Position variable 4 while
reading unplaced Dir variable 9. The old branch order begins with Position
variable 6, the neighbor result, which has no binding source yet. Recognizing
the finite Dir input allows the union to supply its exports before that
result is needed. Whole-gold tables succeeding alone did not establish this
cause; the native backtrace and the selected runtime's checked IR did.

The same rule applies to every union reading a finite orientation column,
regardless of task, form, branch depth or orientation subtype. Static safety
is a separate contract and remains unchanged. Runtime validation uses exact
identity replay on an immutable build after the repository merge checks.
