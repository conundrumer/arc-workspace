# Columns of per-pick-unread.tsv

One row per pick of a derived relation: an atom of a form of the base gold of `gold-v3-helper-forms-a036da074` whose relation belongs to an earlier form. The task set is the 37 held tasks. Tab-separated, first line the column names. An empty cell means no value.

To sum bits over a task, take each form's `form_bits` once, by `task` and `form_line`. A form with no derived pick has no row: its bits are in `census-base.jsonl`, or in `part1-forms.jsonl` of this folder, which has one row per form.

## The pick

- `task`: task id.
- `form_line`: index of the form's line in gold, the `line` of the census.
- `form_kind`: RULE, INIT, DET, or CHOOSE, RIGID_DET, OUT, which have no census row.
- `form_head`: the form's head name in gold's text.
- `form_valid`: 1 where the census row has no `bad`, no `dead` and no tokens left. A form with 0 has no usable total.
- `has_bits`: 1 where the row has relation bits. 0 for a form with no census row, whose row comes from a read in the text.
- `form_bits`: the form's total bits in the census, scope of all earlier forms.
- `form_bits_parents`: the same, parents scope.
- `atom_index`: index of the atom in the walk's order. In a form with no census row, the index of the read in the text.
- `atom_k`: the atom's position in its body, the census's `k`, from 1.
- `position`: first, second, third or later, from `atom_k`.
- `place`: the census's context of the atom, such as `top`, `key`, `port`, `br1`. `text` for a form with no census row.
- `negated`: 1 where the atom is under NOT.
- `repeat_relation`: 1 where an earlier atom of the form picked the same relation.
- `repeat_form`: 1 where an earlier atom of the form read the same earlier form, by any of its relations.
- `relation`: the relation's slot name in the atom's text, in the census's `before` numbering.
- `target_line`, `target_kind`, `target_head`: gold's target form: the form that owns the slot.
- `bits_relation`: bits paid on the relation pick, the atom's `cur.relation` in the census, scope of all earlier forms. This is the steered prior's bits.
- `bits_relation_parents`: the same, parents scope.
- `bits_not`: bits of the NOT pick of the atom, the census's `cur["relation (op)"]`. Empty where the atom has no NOT.
- `bits_atom`: the atom's bits in the census.
- `atom_text`: the atom's text in the census.

## Unread sets

Each count is of forms in scope. Scope: every form before the pick's form, or for the `_parents` columns the forms that the pick's form reads, directly or not. Read status comes from gold's text in both scopes.

- `n_scope`, `n_scope_parents`: forms in scope.
- `n_unread_gold`, `n_unread_gold_parents`: forms read by no form of gold, the pick's own form included.
- `n_unread_later`, `n_unread_later_parents`: forms read by no form of gold other than the pick's form. This set uses forms after the pick.
- `n_unread_before`, `n_unread_before_parents`: forms read by no form before the pick's form.
- `n_unread_so_far`, `n_unread_so_far_parents`: forms read by no form before the pick's form and by no earlier atom of that form.
- `in_unread_gold`, `in_unread_later`, `in_unread_before`, `in_unread_so_far`: 1 where gold's target is in that set. `in_unread_gold` is 0 on every row, as the pick's form reads the target.

## Options at the pick

These come from `walk-held-before.jsonl`, scope of all earlier forms. They are empty for a form with no walk row.

- `options_relation`: relation options offered at the pick that belong to earlier forms. An INIT form has one option for each of its relations.
- `options_unread_later`, `options_unread_before`, `options_unread_so_far`: of those options, the count whose form is in that set.
- `target_offered`: 1 where the pick's relation is among the options.

## Pool columns

The same columns come once for each arm of `search-pool-factored-priors-heldout35-600s-ship7`, with the prefix `control_` (arm `control_search`) or `factored_` (arm `factored_search`). They are empty for 269e22fb and cbebaa4b, which the run leaves out.

A pool form is the nodes that share a head `&f<id>`. A pool form is read when a node of another form has one of its nodes in `parents`.

- `source`: the run's record that decides whether the target is found. `cover`: the `cover` events, as the target's line matches a line of the run's first gold by text with names taken out. `cover2`: the `cover2` events, for a line that matches only the factored gold, or that `cover` didn't find and `cover2` did. Empty: no line of either gold has the target's text, so the record can't tell.
- `found`: 1 where the record has the target by 600 s, 0 where it doesn't. Empty where `source` is empty. An event marks a table equal to a table of one relation of the target form, not always the relation of this pick.
- `found_seconds`, `found_draw`: seconds and draw of the first such event.
- `covering_node`: the node token of the `cover` event. Empty for a `cover2` hit, which names no node.
- `covering_kind`: the kind of that node's clause. An INIT target with a RULE here has a table of one of its relations in a RULE node.
- `forms_at_found`, `unread_at_found`: pool forms and unread pool forms at that draw.
- `forms_end`, `unread_end`: pool forms and unread pool forms at the end of the 600 s.
- `in_unread_at_found`, `in_unread_end`: 1 where the covering node's form is unread at that time. `in_unread_at_found` is 1 on every row with a node: a new form has no reader yet.
- `readers_end`: pool forms that read the covering node's form at the end.
