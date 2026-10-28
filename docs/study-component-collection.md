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
