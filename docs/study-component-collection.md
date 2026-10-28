# Bounded component collection

Component and continuation table collection retain the materialized table
prefix when native work, time, memory or cancellation bounds end collection.
`gold_assignment_map` and `mutant_assignment_map` always describe exactly the
returned relation tables, including an empty array when none were reached.
They are never null and never imply an unsupported program.

Each side has its existing status plus a `*_collection` object containing
`materialization_complete`, `returned_relation_tables` and `terminal`.
A terminal stop carries its native bound and form; a fault carries its reason.
Entry-level stops/faults remain in native tables and the aggregate status.
A complete metadata walk can still have incomplete entries. No new FITS
search or substitute assignment is performed.

Render returned rows/maps and label stopped or faulted collection as partial
native evidence, showing the native reason. Do not infer that unreturned
relations are empty, unsupported, or complete. Historical v1 null maps must
be interpreted together with the side's status: stopped/fault collection
has no returned relation-table evidence in that old implementation.

The 0607ce86 `$Copy` holds expose the old error path: a bound checked between
relations became a RunFault, then the entire successful prefix was discarded
by unwrap_or_default and the maps became null. Replays can finish or stop at
a different relation depending on session warming and host load; that must
not change whether evidence already collected has a map.

Pair reports also expose `gold_kept_assignment_map` and
`mutant_kept_assignment_map` for their kept clause tables. These use the same
array of table records and native `table_entry`, `kept_assignment`, example
and `model` fields as component maps. Table indices include the two evidence
tables. A single kept DET assignment can produce several native models in
each example, with different counts across examples and programs. Consumers
must group by the explicit kept assignment and retain all models; neither
entry count nor model index identifies a shared assignment across programs.
Stopped/fault/no-entry placeholders retain their native status and a null
kept assignment rather than an invented model correspondence.

On 6108dd6e, task 184a9768 `concept` at body `[13,0]` has one kept assignment
with two, four and one native models across its train examples. The recovery
filter's former entry-count-equals-FITS-count assumption rejects this valid
case. The explicit maps preserve the native model families without searching
for a different assignment or inferring original DET names from body slots.
