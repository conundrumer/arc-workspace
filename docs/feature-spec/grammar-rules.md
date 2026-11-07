# Feature grammar refusal rules

Each rule is a reason the encoder gives no derivation to a term. Code is in `engine/arclog-encoder/src/`.

## Reading notes

- Classes of what a rule refuses: C = a term that is constant, E = a term equal to another term, O = a second order of steps that commute.
- No count of rejections per rule exists in the saved data.
  - The saved families under `work/feature-spec/results/gate-full-spec/families_main/` hold only the surviving terms (`SavedFamily`, `generate.rs:169-181`).
  - No log or document holds a tally.
  - `Generated.rejected_by_rule` (`generate.rs:195`, `generate.rs:1399`) counts them. `feature-encoder term-stats` prints them as `rejected<TAB>count<TAB>rule` (`bin/feature-encoder.rs:1579`). That command was not run.
  - So the order below is from reading the code. Rules that fire on every project, select or pair of filters come first.
- Examples follow from reading each rule. None was run.
- Facts: the `Refined` fields (`refine.rs:34`) are keys, low/high, within, outside, complete and count_follows. `Form` (`generate.rs:112`) records how a term was built.
- Key sources: T has all its columns as a key (`generate.rs:1035`). `input` and `output` have key P (`refine_parts.rs:1481`). A lib relation has its `(refines R (key ..))` forms, or the keys of its rows where it has no modes (`refine_parts.rs:193`). A component output has its `refines` forms (`refine_parts.rs:928`, `:1104`). A part has the keys that follow from its fragment's atoms by closure over labels (`refine_parts.rs:729`).
- Arclog map: project is a column with no site. select is a constraint atom. semijoin is a positive atom that joins labels. antijoin is `(NOT atom)`. all is `(ALL ..)`. join is a positive atom with a fresh `*X` site. A part is a read of a lib relation, a component output or a derived relation.
- A body is an unordered conjunction (`docs/arclog/arclog.md:26`). So a rule about the order of steps has a reading only as the order in which atoms are written.

## Batch 1

1. project-over-project, `generate.rs:1097`
   - Reads: `Form.kind` of the first relation is Project (set at `generate.rs:1111`). No table fact.
   - Refuses (E): `(project (project T T0 T1) T0)` equals `(project T T0)`.
   - Arclog: no atom, since one site list drops many columns at once. It shows only in a split body. A derived relation &b has a clause that is one positive atom of &a (`Facts.alias`, `refine_parts.rs:838`), and a later clause reads &b with fewer sites. Refuse that read, and the writer names &a. The engine needs only the shape of the clause.

2. project-over-filter, `generate.rs:1098`
   - Reads: `Form.kind` is Filter, and the project keeps every column that the filters read (`filter_reads`, `generate.rs:1227`).
   - Refuses (E): `(project (select T T0 != T1) T0 T1)` equals `(select (project T T0 T1) T0 != T1)`.
   - Arclog: a flat body has one form for both orders, so nothing is refused there. In a split body, a derived relation has one positive atom and constraint, `NOT` or `ALL` atoms. A later clause reads it with sites on all labels that those atoms read, and drops the rest. Refuse that read. The engine needs the labels that each filter atom reads (`count_labels`, `refine_parts.rs:414`).

3. filter-order, `generate.rs:1242`
   - Called from select (`:1125`), semijoin and antijoin (`:1150`) and a row-wise part that adds no column (`:1335`).
   - Reads: `Form.last_filter`, the order key of the last filter, against the order key of the new filter. A filter that drops a column that an earlier filter reads is not refused.
   - Order keys: a select hashes its pair and op (`:1124`). A semijoin or antijoin hashes its right relation and pairs (`:1149`). A part hashes its call and second relation (`:1332`). The top bits rank the classes: select 0, semijoin or antijoin 1, part 2. So one order of filters is generated.
   - Refuses (O): `(select (select T T1 != 0) T0 != 0)` stands in one order only.
   - Arclog: atoms commute. Accept a filter atom (constraint, `NOT` atom, positive atom whose labels are all bound, `ALL`) only if its key is not below the key of the filter atom before it. Do not refuse where one atom binds a label that the other needs: a lib relation's `needs` (`docs/arclog/lib.md:6`), a label that `=` makes (`arclog.md:37`), or a fresh `*X`. The engine needs the modes and `needs` of lib relations (`engine/lib/registry.sexpr`) and the labels that each atom binds. The key can be any fixed total order. If a query is mapped back to this encoder's term text, use the hashes above.

4. project-keeps-key, `refine.rs:147`
   - Reads: the keys of the first relation. The kept columns hold a key, and there are fewer kept columns than columns.
   - Refuses (E, on count): `(project (count T (T0 T1)) T0 T1)` has the row count of `(count T (T0 T1))`, since T0 T1 is its key. The claim is `SameCount`.
   - Arclog: a read that leaves out columns but keeps a declared key has the relation's row count. Refuse a count (or other aggregate that reads only the count) over that read, as it repeats the count of the unprojected read. The engine needs the keys of the relation. For a derived relation, close the key labels over the keys of its atoms, as `Reader::body` does (`refine_parts.rs:473`).

5. select-zero-same-op, `refine.rs:277`
   - Reads: low and high of the column, the op, and whether the column is a number (Int or Nat).
   - Sources: low is 0 for a Nat column (`generate.rs:1037`, `refine_parts.rs:163`). A lib `(at-least C n)` form sets low (`refine_parts.rs:177`). An earlier select sets a range (`refine.rs:283-292`). A semijoin intersects ranges (`refine.rs:350`).
   - Refuses (E): the op kept is the first of `= != < <= > >=` (`expression.rs:31`) with the same outcomes. On a Nat column, `<= 0` equals `= 0`, and `> 0` equals `!= 0`: `(select T N <= 0)` equals `(select T N = 0)`.
   - Arclog: refuse the constraint atom `(<= K 0)` or `(> K 0)` where K has low 0, and write `(= K 0)` or `(!= K 0)`. The engine needs the label's type (a `Nat` column, `docs/arclog/lib.md:11`, narrowed by the types at its sites) and the ranges from lib `at-least` forms and from other constraints in the body. Ranges do not depend on atom order.

6. select-zero-no-op, `refine.rs:274`
   - Reads: as rule 5. The op keeps every outcome that the range allows.
   - Refuses (E, equal to its own relation): `(select T N >= 0)` on a Nat column.
   - Arclog: refuse `(>= K 0)` on a Nat label, and `(> N 0)` where the lib gives `(at-least N 1)` (`frame_extent`, `registry.sexpr:97`). Same facts as rule 5.

7. filter-below-extension, `generate.rs:1245`
   - Reads: `Form.kind` is Extension (a join, or a row-wise part that adds columns). The filter reads only columns of `Form.own`, the extension's relation. It drops no column that the extension reads (`Form.reads`).
   - Source: `Form` is set at `generate.rs:1171` for a join and `generate.rs:1342` for a part. A part is row-wise where its facts have `rowwise_on == &r` over the whole relation (`refine_parts.rs:1414`).
   - Refuses (O): `(select (neighbors T T0) T1 != 0)` equals `(neighbors (select T T1 != 0) T0)`, so only the second stands.
   - Arclog: same reading as rule 3. A filter atom whose labels were all bound before an atom that adds columns must be written before that atom. The adding atoms are a join atom with a fresh `*X`, a lib relation with an unbound output column, and a component output. The engine needs the labels that each atom binds and the output columns it adds.

8. project-over-extension, `generate.rs:1102`
   - Reads: `Form.kind` is Extension. The kept columns include `Form.reads` and every column that the extension adds.
   - Refuses (E): `(project (join T U (T0 U0)) T0 T1 U1)` equals `(join (project T T0 T1) U (T0 U0))`.
   - Arclog: no atom in a flat body. In a split body, a derived relation holds a join or a row-wise read, and a later clause reads it and drops only columns of the base that the join does not read. Same engine needs as rule 2.

## Batch 2

9. semijoin-within, `refine.rs:339`
   - Reads: `complete`, or `within` of the left columns in the right relation (`is_within`, `refine.rs:117`, depth 2). The call is at `generate.rs:1153`.
   - Sources of within: T is within itself (`generate.rs:1042`). A semijoin adds one (`refine.rs:347`), and a join adds one (`refine.rs:429`). A project or select keeps them. A part gives its fragment's origins (`refine_parts.rs:1396`), which come from atoms and from the `copies` rows of a component output (`refine_parts.rs:967`). `input` and `output` give theirs through `relation_input` (`generate.rs:1251`).
   - Sources of complete: a lib relation column whose rows cover every value of an orientation type, as `dir_elem(D)` does (`lib_leaf`, `refine_parts.rs:1468`). It needs one column pair, and the left column's type must be at or under the right's (`is_complete`, `generate.rs:1055`). A select, semijoin or antijoin clears it.
   - Refuses (E, same rows as the left relation): `(semijoin (select T T1 != 0) T (T0 T0))`, and `(semijoin X dir_elem (D D))` where X's D is a Dir.
   - Arclog: refuse a positive atom that joins labels which earlier atoms already bind from that same source column, or from a column that is a copy of it. Also refuse `(dir_elem D)`-style atoms on a label whose type is at or under the column's type. `arclog.md:43` already treats such labels as bound. The engine needs the origin of each label (a `copies` row of a component output, a grid, a fragment's origin), the `each` facts of lib relations (`registry.sexpr`, `(refines R (each ..))`), and label types.

10. antijoin-within, `refine.rs:365`
    - Reads: the same facts as rule 9. Call at `generate.rs:1153`.
    - Refuses (C, no rows): `(antijoin (select T T1 != 0) T (T0 T0))`.
    - Arclog: refuse `(NOT atom)` where the atom's joined labels are already within that atom's columns. The body has no row. Same needs as rule 9.

11. all-within, `refine.rs:440`
    - Reads: the same facts as rule 9. Call at `generate.rs:1187`.
    - Refuses (C, true wherever the domain has a row, so it follows from the domain's count): `(all (select T T1 != 0) T () (T0 T0))`.
    - Arclog: refuse `(ALL (domain..) (atom ..))` where each labelled column of the domain is already within the atom's columns, with the domain's atoms read as one clause. The engine needs the same origin facts as rule 9, applied to the labels of the domain list.

12. select-zero-empty, `refine.rs:271`
    - Reads: low and high of the column, as in rule 5.
    - Refuses (C, no rows): `(select T N < 0)` on a Nat column. Also `= 0` on a column with low 1, as `frame_extent`'s N.
    - Arclog: refuse a constraint atom that no value of its label meets: `(< K 0)` on a Nat label, `(= N 0)` where the lib has `(at-least N 1)`. Same facts as rule 5. The range of a label is the meet of the ranges at all its sites and constraints in the body.

13. select-twice, `generate.rs:1117`
    - Reads: `Form.selects`, the (column name, other column name or `0`) pairs of the selects below. The op is not compared.
    - Refuses (E, claim `Follows`): `(select (select T T0 > 0) T0 = 0)`. Selects carry through later filters. A project, an extension or a part ends the list (`Form::default`).
    - Arclog: refuse a second constraint atom on the same pair of labels, whatever the op. The engine needs only the label names.

14. match-in-project, `generate.rs:1205`
    - Reads: `Form.kind` of the second relation is Project. It runs for semijoin, antijoin and all (`second_relation_form`, `generate.rs:1201`).
    - Refuses (E): `(semijoin T (project U U0 U1) (T0 U0))` equals `(semijoin T U (T0 U0))`. A project keeps all matches over the columns that the pairs read.
    - Arclog: refuse a positive, `NOT` or `ALL` atom whose relation is a derived relation that only drops columns of one positive atom (`Facts.alias`, `refine_parts.rs:838`). Name the base relation. Needs the clause shape of the derived relation.

15. match-in-extension, `generate.rs:1206`
    - Reads: the second relation's `Form.kind` is Extension and `total`, and the right columns are in `Form.own`. `total` is set where every row of its relation stands in the part's output (`like.fan_out` known, `refine_parts.rs:1428`). A join is never total.
    - Refuses (E): `(semijoin T (neighbors U U0) (T0 U0))` equals `(semijoin T U (T0 U0))`.
    - Arclog: refuse an atom of a relation that adds columns and keeps every row of a base relation (a component output with `each-key` or `each-row` in its `refines`, `refine_parts.rs:1120`, or a lib relation with an `each` fact), where the joined labels are base columns. Name the base relation. The engine needs `Facts.like` with a known fan-out.

16. project-below-extension, `generate.rs:1105`
    - Reads: `Form.kind` is Extension and `total`, and every kept column is in `Form.own`.
    - Refuses (E): `(project (neighbors T T0) T0 T1)` equals `(project T T0 T1)`.
    - Arclog: an atom that adds only fresh labels that no other atom reads (`used` in `refine_parts.rs:818`), and that has a row for each value of the labels it joins (a lib `each` fact, as `margin` has `(each (B) 4)`, `registry.sexpr:86`), changes no row. Refuse it. The engine needs the `each` facts and the use count of each label.

## Batch 3

17. semijoin-outside, `refine.rs:342`
    - Reads: `outside` of the first relation (`is_outside`, `refine.rs:136`). It holds where an `outside` entry has the same second term, and each of its column pairs is among the pairs read now.
    - Sources: an antijoin adds an entry (`refine.rs:373`). A select, a semijoin and a join keep them. A project keeps an entry only if it keeps all its columns (`refine.rs:170`). A part gives none.
    - Refuses (C, no rows): `(semijoin (antijoin T U (T0 U0)) U (T0 U0))`.
    - Arclog: refuse a positive atom of relation S whose joined sites include those of an earlier `(NOT (S ..))` in the body. The body has no row. The engine needs the relation name and the (column, label) pairs of each `NOT` atom. It compares the relation by name. Every site of a `NOT` atom joins (`arclog.md:35`), so the pairs are all its sites.

18. antijoin-outside, `refine.rs:368`
    - Reads: the same facts as rule 17.
    - Refuses (E): `(antijoin (antijoin T U (T0 U0)) U (T0 U0))` equals the inner antijoin.
    - Arclog: refuse a second `(NOT (S ..))` whose pairs include those of an earlier `NOT` of S.

19. all-outside, `refine.rs:443`
    - Reads: the same facts as rule 17. The call is at `generate.rs:1187`.
    - Refuses (C, false): `(all (antijoin T U (T0 U0)) U () (T0 U0))`.
    - Arclog: refuse an `ALL` whose body atom is S on pairs that the domain's `(NOT (S ..))` already holds. No row of the domain can meet the body.

20. join-outside, `refine.rs:380`
    - Reads: the same facts as rule 17.
    - Refuses (C, no rows): `(join (antijoin T U (T0 U0)) U (T0 U0))`.
    - Arclog: the same refusal as rule 17. A join and a semijoin are one positive atom in arclog.

21. join-over-its-semijoin, `generate.rs:1163`
    - Reads: `Form.kind` is Filter, and `Form.semijoins` holds the key of this join (`semijoin_key`, `generate.rs:1216`): the same second term and the same (left name, right place) pairs. A project, an extension or a part ends the list.
    - Refuses (E): `(join (semijoin T U (T0 U0)) U (T0 U0))` equals `(join T U (T0 U0))`.
    - Arclog: refuse an atom of S that only tests a match (no fresh label) when an atom of S joined on the same labels stands in the same body. Write the atom that adds labels. Same-relation, same-site test on atom text only.

22. join-no-new-column, `refine.rs:383`
    - Reads: `kept` is empty: every column of the right relation is in a pair.
    - Refuses (E): `(join T V (T0 V0))` with V of one column equals `(semijoin T V (T0 V0))`.
    - Arclog: no reading. Arclog has one positive atom for both. An atom with no fresh label is a semijoin already. Nothing is refused.

23. select-pair-no-op, `refine.rs:320`
    - Reads: low and high of both columns (`refine.rs:298`). The op keeps every outcome (less, same, more) that the ranges allow.
    - Sources: as rule 5.
    - Refuses (E, equals its relation): on A with high -1 and B with low 1, `(select X A < B)`. Such ranges come from `(select T A < 0)` and `(select T B > 0)` or from lib `at-least` forms.
    - Arclog: refuse `(op A B)` that the ranges of the labels already decide as true. The ranges of a label are the meet over its sites and its `(op K 0)` atoms. Needs lib `at-least` forms, Nat types and the constraints of the body.

24. select-pair-empty, `refine.rs:317`
    - Reads: as rule 23. No outcome of the op is allowed.
    - Refuses (C, no rows): on the same ranges as rule 23, `(select X A >= B)`.
    - Arclog: refuse `(op A B)` that the ranges decide as false. Same facts as rule 23.

## Batch 4

25. all-over-project, `generate.rs:1177`
    - Reads: `Form.kind` of the domain is Project.
    - Refuses (E): `(all (project T T0 T1) U () (T0 U0))` equals `(all T U () (T0 U0))`. The rows of a domain over the columns that the form reads are all it reads.
    - Arclog: refuse an `ALL` whose domain atom is a derived relation that only drops columns of one atom (`Facts.alias`, `refine_parts.rs:838`). Name the base relation. Needs the clause shape.

26. all-below-extension, `generate.rs:1183`
    - Reads: the domain's `Form.kind` is Extension and `total`, and the left columns and the outer columns are all in `Form.own`.
    - Refuses (E): `(all (neighbors T T0) U () (T0 U0))` equals `(all T U () (T0 U0))`.
    - Arclog: as rule 16, inside the domain list of an `ALL`. Refuse an atom there that adds only unused fresh labels and keeps each row of its base.

27. all-outer-key, `refine.rs:446`
    - Reads: `outer` is not empty, and its columns hold a key of the domain relation.
    - Refuses (E, claim `Follows`): `(all (count T (T0)) U (T0) (N U0))`. Each outer value has one domain row, so `all` is a semijoin there.
    - Arclog: refuse an `ALL` whose outer labels, at their columns in the domain's atoms, hold a key of the domain's relation. Write a positive atom or a `NOT` atom. The engine needs the keys of the domain's relation, found by closure over the keys of its atoms (`refine_parts.rs:729`). An outer label is one that `ALL` joins from outside (`arclog.md:57`).

28. flag-over-key, `generate.rs:1278`
    - Reads: the key columns of the part hold a key of the first relation (`is_key`).
    - Refuses (C, claim `Follows`): `(determines-flag (count T (T0)) U (T0) N U0)` is true at every group, since a group has one row.
    - Arclog: `determines-flag` is a fragment (`engine/lib/features.arclog:1508`) that expands to `Cardinality` instances and an `ALL` over their sizes. Its reading exists for a query that calls the fragment. Refuse the call where its key columns hold a key of the first relation. The same fact appears inside the expansion as `(single member (at-most N 1))` in the `refines` of `Cardinality.size` (`registry.sexpr:159`). The engine needs the keys of the first relation.

29. flag-within, `generate.rs:1281`
    - Reads: the first column is within the second relation's column (`is_within`, depth 2), or is outside it (`is_outside`), or the pair is complete (`is_complete`). The flag is the same at every group.
    - Refuses (C): `(determines-flag T T (T0) T1 T1)`. Every row has a match, so the flag is true.
    - Arclog: the same call as rule 28. Refuse it where the origin facts of rule 9 (all match) or rule 17 (none match) decide the match. Needs the origin and outside facts of the labels.

30. part-over-project, `generate.rs:1298`
    - Reads: `PartPlan.reads_only_holes` is true, and `Form.kind` is Project. That flag is computed by expanding the call over a relation one column wider and finding that the value reads no extra column and gives none (`refine_parts.rs:1253`). Parts that copy their relation's other columns (`neighbors`, `margin`, `count`) have it false.
    - Refuses (E): `(around (project T T0 T1) T0)` equals `(around T T0)`.
    - Arclog: refuse a read of a part (a fragment call, a component output) whose value depends only on the labels it names (`Facts.reads`, `refine_parts.rs:68`), when its relation is a derived relation that only drops columns of one atom. Name the base relation. The engine needs `Facts.reads` for the part's clause and `Facts.alias` for its relation.

31. part-below-extension, `generate.rs:1301`
    - Reads: `reads_only_holes`, and `Form.kind` is Extension and `total`, and the hole columns are all in `Form.own`.
    - Refuses (E): `(around (neighbors T T0) T0)` equals `(around T T0)`.
    - Arclog: refuse a read of a part that depends only on labels bound by a base atom, when its relation is a derived relation that adds columns it does not read and keeps each row of the base. Same needs as rules 15 and 30.

32. extension-order, `generate.rs:1339`
    - Reads: the part is row-wise and adds columns (`PartResult.row_wise`, `adds_columns`, `refine_parts.rs:1412-1413`). `Form.kind` is Extension. The part's hole columns are all in `Form.own`. Its order key is below `Form.order`.
    - Order keys: a part hashes its call and second relation (`generate.rs:1331`). A join hashes its second term and key (`generate.rs:1170`). A join over an extension has no order rule, so a join is never refused here.
    - Refuses (O): `(margin (neighbors T T0) T0)` and `(neighbors (margin T T0) T0)` are equal. One stands.
    - Arclog: the same reading as rule 3, for atoms that add columns. An atom that adds columns and reads only labels bound before the previous adding atom must not have an order key below that atom's. The engine needs the labels each atom binds, its added columns and an order key. Use these hashes if the query maps back to the encoder's text.

## Batch 5

The four rules below are returned by `PartPlan::judge` (`refine_parts.rs:1368`). It reads the facts of the part's fragment, as `Reader::body` finds them (`refine_parts.rs:473`). Examples follow from reading the rule. None was run.

33. part-empty, `refine_parts.rs:1419`
    - Reads: `Facts.empty` of the fragment's result.
    - Sources: a component output whose `refines` form has an `empty` claim that holds, as `(single member empty)` of `Singleton.plural` (`registry.sexpr:177`) when each key has one row of the input (`Reader::single`, `refine_parts.rs:902`). A positive atom with a `0` site at a column whose low is above 0 (`refine_parts.rs:618`).
    - Refuses (C, no rows): `(several (count T (T0)) (T0) N)`. T0 is a key of the count, so no group has several values.
    - Arclog: refuse an atom that reads such an output, as `(&s.plural (:key K))` where the instance's `member` input has one row per key. Refuse a `0` site at a column with low above 0, as `(frame_extent P A (:N 0))`, since `frame_extent` has `(at-least N 1)` (`registry.sexpr:97`). The body has no row. The engine needs the `refines` claims of component outputs (`apply_claim`, `refine_parts.rs:1072`), `Reader::single`, and the low of lib columns.

34. part-holds-on-domain, `refine_parts.rs:1423`
    - Reads: `Facts.holds_on_domain`, and the result has no column. It is set where the fragment has an `ALL` whose body relations each stand for the same base rows as the domain (`all_holds`, `refine_parts.rs:849`).
    - Refuses (C, true wherever the relation has a row): a call whose fragment is `(ALL ((R ..)) ((R ..)))`. Which calls in the lib meet this was not checked. It depends on the fragment bodies in `engine/lib/features.arclog`.
    - Arclog: refuse an `ALL` whose body atoms each read rows that stand one for one with the domain's rows (`Facts.like` on the same base). The form is true wherever the domain has a row. The engine needs `Facts.like`.

35. part-no-op, `refine_parts.rs:1431`
    - Reads: the result's `like` base is `&r` (the first relation). Each column that it shares with `&r` stands at its own column. Each column it adds is constant. The fan-out is 1. It has all of `&r`'s columns.
    - Refuses (E, same rows as its relation): `(cells-on (project input P) P input)` equals `(project input P)`.
    - Arclog: refuse a read of a derived relation that keeps each row of one driver atom (`Facts.like` fan-out 1), adds only constant columns, and keeps all the driver's columns. Name the driver. The engine needs `Facts.like` and `Facts.constant`.

36. part-is-project, `refine_parts.rs:1433`
    - Reads: as rule 35, but the result has only some of `&r`'s columns.
    - Refuses (E, claim `Follows`): `(cells-on input P input)` equals `(project input P)`.
    - Arclog: as rule 35, for a read that keeps some of the driver's columns. Name the driver and drop the sites.

## Batch 6

The five items below are refusals that stand outside `judge`. `rejected_by_rule` does not count them.

37. count-follows, `generate.rs:680-684` (`name_roots`)
    - Reads: `Refined.count_follows`. It is set where the count of rows follows from a smaller term's: a project of a relation with one row (`refine.rs:176`), a semijoin on a complete key column (`refine.rs:355`), a join whose right side is keyed on the pairs (`refine.rs:433`), a part over rows with a known fan-out (`refine_parts.rs:1438`, `:1441`). A select, antijoin and semijoin clear it.
    - Refuses (E, on count): the term stands, but its `cardinality` root (and its ratio) does not. `(join T U (T0 U0))` with U0 a key of U has the count of `(semijoin T U (T0 U0))`.
    - Arclog: refuse an aggregate `count` over a read whose count follows from another read's count. Same facts as rules 4 and 9 to 11: keys, `each` facts, fan-out (`Facts.like`).

38. named-diff, `generate.rs:2164` and `generate.rs:396`
    - Reads: the left or right term text is `output-diff` or `input-diff`, with one pair.
    - Refuses (E): a semijoin or antijoin with a grid's diff on one cell is a part's call, which is smaller. Terms over the diff of the two grids are not extended (`diff_terms`).
    - Arclog: no reading. It depends on which named features the lib holds, not on a fact.

39. no-pair and type-meets, `generate.rs:232-258` (`meets`, `pair_sets`), `generate.rs:1737-1767` (`unary_operators`)
    - Reads: column types. A pair of columns joins only where their types meet. Two Ident columns meet only at one source. A pair set holds one or two pairs. A relation order other than `=` and `!=` needs two number columns. A compare with `0` needs a type with a zero (Int, Nat, Box and the types under it).
    - Refuses (C, count follows): a join, semijoin, antijoin or `all` with no column pair has no term. Its count follows from its parts' counts.
    - Arclog: the checker already refuses Ident joins of two sources (`lib.md:17`) and type meets. A positive atom that shares no label with the rest of the body, and no constraint relates it, is the product. Refuse it. Needs only the labels of each atom.

40. ratio-one-row, `generate.rs:420-423`
    - Reads: `Refined::one_row` (the empty key holds) of a grid part used as the second relation of a ratio.
    - Refuses (C, follows from the other count): a `ratio` with a relation of at most one row.
    - Arclog: refuse a `ratio` root against a relation with the empty key. Needs the keys of the relation.

41. width and size limits, `generate.rs` (`MAX_COLUMNS`, `MAX_PROJECTED`)
    - Reads: the number of columns.
    - Refuses: a term with more than `MAX_COLUMNS` columns, and a project of more than `MAX_PROJECTED` columns. These are limits of size. They do not follow from any fact of the data.
    - Arclog: no reading unless the engine adopts the same limits.
