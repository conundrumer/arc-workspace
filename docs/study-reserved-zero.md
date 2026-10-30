# Reserved `0` in study pairs — renderer contract

The decoder writes the reserved label `0`, not arbitrary literal values. Its
meaning comes from the resolved column/label **type**, not the argument's name.
It is not a variable, a wildcard, a missing value, or a fresh/key binding.

| Resolved type | Meaning of reserved `0` | Suggested renderer text |
| --- | --- | --- |
| `Number` (registry spelling `number`) | Integer zero. | “number zero” |
| `Box` | The zero box: all four margins `(top,bottom,left,right)=(0,0,0,0)`. Its edges coincide with the current reference frame's edges. | “zero box: all four frame margins are zero” |
| `Position` | The same zero box, interpreted at Position type. It is a reference to zero margins, **not** a row/column coordinate `(0,0)` or the top-left cell. In `same_corner(D,P,0)`, it supplies the whole-frame corner reference. | “zero box at Position type: all four frame margins are zero” |
| `Offset` | The zero box at Offset type; the identity translation under margin-wise composition. | “zero offset / no translation” |

There is no `Gap` type. Names such as `Gap`, `K`, `N`, `Base`, `P`, `P2`,
and `B` are columns or variables. Resolve their types before explaining `0`.
Examples:

- `divide(:Gap 0)` uses Number zero: no separator gap between parts.
- `gap(:K 0)` uses Number zero: zero cells strictly between the two positions;
  the direction, alignment and “ahead” conditions still apply.
- `margin(:K 0)` uses Number zero: no margin at the specified edge.
- `apply(:P 0)` uses the zero box on the resolved Box/Position/Offset column;
  it does not pin the argument to the top-left cell.
- A user-defined `Gap` column may instead be Box-valued: its name alone
  cannot select the Number explanation.

Reserved `0` is illegal at Color, Example, Ident, Unit, orientation types
(Dir, DiagDir, Dir8, Axis, DiagAxis, Axis4, C4, D4, Sym, Sense), Pose and a
whole record. In particular, it does not mean black at a Color column,
even though black's physical encoding is zero. A scalar field of a record
can admit `0` according to that field's own type.

An argument site with `0` joins that column to its typed zero value. A
comparison's second operand `0` takes the first operand's type. There is no
`*0`, `^0`, zero-valued head binding, or `0` site in OUT. The decoder's other
zero/equality restrictions still apply; type compatibility alone is not
sufficient to offer an edit.

Sources of truth: `ValueType::has_zero` in `engine/arclog/src/types/lattice.rs`,
`LabelUse::Zero` in `engine/arclog/src/program/arclog_nodes.rs`, the literal
term compilation in `engine/arclog/src/eval/ir.rs`, margin encoding and
interpretation in `engine/arclog/src/terms.rs`, and the reserved-label rules
in `docs/arclog/arclog.md` under negation and constraints.
