# Corpus survey

A survey of the 904 `.arclog` and 904 `.arcdata` files under `work/arclog/gen/` on 2026-10-15, and of the tasks under `data/tasks/`. The engine design of [overview.md](overview.md) rests on these numbers. The script is one pass over the s-expressions, about 1 s, with column names from `src/arclog_convert/lib-signature.dl`.

## Forms

Count of list nodes with the head, and the number of files with at least one.

| form | count | files |
| --- | --- | --- |
| RULE | 8083 | 904 |
| NOT | 3920 | 854 |
| INIT | 3914 | 851 |
| DET | 3229 | 853 |
| OR | 2219 | 790 |
| ALT | 1402 | 606 |
| ALTS | 1066 | 606 |
| OUTPUT / INPUT | 801 / 582 | 118 / 117 |
| ALL | 236 | 154 |
| IF | 138 | 118 |
| DET_OR_RULE / RULE_OR_DET | 120 / 25 | 77 / 16 |
| ONE | 47 | 31 |
| CHOOSE | 18 | 18 |
| DEMO_RULE / DEMONSTRATED | 13 / 5 | 4 / 4 |
| APPROXIMATED | 12 | 12 |
| RIGID_DET | 9 | 9 |

- `ONE` by shape: 38 bare `(ONE)` in a DET, 1 bare in a DET_OR_RULE, 1 bare in a RULE, 7 with columns, all in a RULE. 39 open parameters in total.
- Declaration forms per file: median 14, p90 30, max 101 (a64e4611). All headed nodes per file: median 109, p90 286, max 1327 (20a9e565).
- TODO markers: 13 in total; alt-undefined 3, record-shape 2, head-term 2, rigid-part 2, demonstrated-select 1, term 1.

## Alts structure

Here an `ALTS` form includes each `DET_OR_RULE` and `RULE_OR_DET` line. The cases of a file are the cases that [Cases](cases.md#cases) gives, where such a line splits only the bases that read its relation, less the excluded ones: on 2026-10-19, the cases that the file's record in the snapshot `.cache/parity/` holds. The script is `case_counts.py` in the directory of [Open values and constraint search](#open-values-and-constraint-search), `python3 case_counts.py` from the repo root.

| measure | value |
| --- | --- |
| files with an `ALTS` form | 607 |
| `ALTS` forms per file, max | 13 (ae3edfdc) |
| ALTS nesting depth, max | 3 (a48eeaf7); 53 files at depth 2 or more |
| combination ALT blocks | 52 |
| cases per file | median 2; max 1177 (b2bc3ffd), then a1aa0c1e 1080, a416fc5b 884, b10624e5 768, af24b4cc 736, ae3edfdc 640, ac3e2b04 576, aa300dc3 528 |
| files with excludes | 48; 336 excludes; max 46 per file (a2d730bd) |

| cases | files |
| --- | --- |
| 1 | 297 |
| 2 | 321 |
| 3–4 | 151 |
| 5–8 | 58 |
| 9–16 | 26 |
| 17–64 | 52 |
| more than 64 | 48 |

## Instances

`INIT` forms per component; a `DEMONSTRATED` form counts as DemonstrationConsistency. The key width is the number of `^` labels in the key clause, 0 for the `Unit` key. Most instances in one file: 27 (a64e4611).

| component | instances | key widths {width: n} | max width (stem) |
| --- | --- | --- | --- |
| Order | 656 | 0:338 1:218 2:77 3:21 4:1 5:1 | 5 (9f8de559) |
| BoundingBox | 611 | 0:198 1:321 2:78 3:12 4:1 5:1 | 5 (a25697e4) |
| Cardinality | 477 | 0:68 1:309 2:85 3:12 4:3 | 4 (4290ef0e) |
| Connectivity | 425 | 0:258 1:155 2:11 3:1 | 3 (4290ef0e) |
| Singleton | 287 | 0:80 1:130 2:62 3:10 4:5 | 4 (212895b5) |
| Ray | 240 | 0:128 1:90 2:18 3:3 8:1 | 8 (351d6448) |
| Division | 226 | 0:166 1:38 2:20 3:1 4:1 | 4 (351d6448) |
| Tiling | 137 | 0:127 1:10 | 1 |
| Frame | 125 | 0:88 1:32 2:5 | 2 (21897d95) |
| Inclusion | 105 | 0:105 | 0 |
| Quotient | 82 | 0:82 | 0 |
| Propagation | 74 | 0:41 1:23 2:9 3:1 | 3 (20a9e565) |
| Boundary | 68 | 0:41 1:26 2:1 | 2 (136b0064) |
| Occurrences | 63 | 0:17 1:24 2:15 3:6 5:1 | 5 (269e22fb) |
| Distance | 58 | 0:25 1:25 2:8 | 2 (28a6681f) |
| Enclosure | 54 | 0:28 1:24 2:2 | 2 (8ba14f53) |
| Walk | 52 | 0:35 1:16 3:1 | 3 (a6f40cea) |
| Flood | 50 | 0:32 1:12 2:6 | 2 (142ca369) |
| Agreement | 39 | 0:10 1:13 2:15 4:1 | 4 (409aa875) |
| Outlines | 24 | 0:8 1:16 | 1 |
| Periods | 23 | 0:12 1:11 | 1 |
| CellDistance | 19 | 0:13 1:6 | 1 |
| Excess | 11 | 0:3 1:2 2:6 | 2 (137eaa0f) |
| DemonstrationConsistency | 6 | 0:1 1:3 2:1 5:1 | 5 (351d6448) |
| Unfold | 3 | 0:1 1:1 2:1 | 2 (a8d7556c) |
| ExtentDivisions | 2 | 1:2 | 1 |
| Wallpaper | 2 | 0:2 | 0 |

- Inclusion and Quotient never take a key clause; their records are in the type parameters.
- The `CHOOSE` `for` key has width 1 in 13 forms, 2 in 3 and 3 in 2.

## Recursion

Each declaration's `&` reads, with `&x.out` counted as a read of `&x`; a read under `NOT`, under `ALL` or in an `IF` test is negated. Cycles are the strongly connected components over three graphs: every derivation merged, the concept program alone, and each alt path with its derivations in place of the concept program's.

| measure | result |
| --- | --- |
| relations that read themselves | 3, all Unfold instances (3490cc26 `&state`, 696d4842 `&crawl`, a8d7556c `&claim`), none through a negation |
| a RULE or DET that reads itself | 0 |
| cycles in the concept program's graph | 1: 17cae0c1, 9 relations, no negation: `&panel_division`.side → `&size` → `&tile_size` → `&glyph_member` → `&panel_mark` → `&mark` → `&panel` → `&panel_division` |
| cycles on an alt path | 3; 2 through a negation |
| 351d6448, alt `$PanelAxisFromLines` | 32 relations, 15 negated edges |
| ac0c5833, alt `$RectMarker` | 7 relations: `&exact_split` −NOT→ `&split_fault` → `&triple_cell` → `&box_triple` → `&marker_max_side` −NOT→ `&unsplit` −NOT→ `&exact_split`; a `DET_OR_RULE` with `(ONE)` reads the program it parameterizes |

## Arcdata

| measure | value |
| --- | --- |
| params, total / max per file | 2797 / 15 (136b0064) |
| largest param | 441 rows, a 21×21 grid (73251a56 `&label`) |
| Frame / Division params | 67 / 25 |
| witnesses with a body | 769; max 22 per file (abbfd121); 112 files have one |
| bodiless back-references | 89 |
| plausibility | variant 335, borderline 273, ordinary 97, foreign 64 |
| verdict | concept 362, an alt 353, any 40, other 14 |
| top-level heads | param 2797, alts 599, exclude 336, representative 47, approximated 12 |

## Columns

A derived relation's columns are its body's top-level `*` labels plus what its `OR` and `IF` forms export. A read projects when the columns its sites select, `E` aside, are a strict subset of the relation's.

| measure | value |
| --- | --- |
| widest derived relation | 24 columns (a57f2f04 `&copy`) |
| widest lib relation | 5 (`divide`) |
| arity distribution | 0:31, 1:705, 2:2196, 3:1553, 4:1180, 5:784, 6:487, 7:297, 8:136, 9:91, 10+:127 |
| derived-relation reads that project | 13513 of 18858 |
| lib atoms with fewer sites than the lib arity | 1046 of 11740 |
| instance-output atoms | 7123 |

## Rare constructs

- Keywords: the thinnest are DEMONSTRATED 5, RIGID_DET 9, APPROXIMATED 12, DEMO_RULE 13.
- Components under 5: DemonstrationConsistency as INIT 1, ExtentDivisions 2, Wallpaper 2, Unfold 3.
- Proposers: 41 of the 34 declared comps plus domains are used; DominantColor 543 uses. Under 5: BoxDomain 1, since gone from 48d8fb45, ColorColorDomain 1, NumberDirDomain 1, SepTileCountAxis 1, VanishedNewPairs 1, OutNewColor 2, Period 2, PositionDomain 2, DiagDirAxisDomain 3, ChangedPairs 4.
- Lib relations: 66 of 69 used. Under 5: corner_outset 1, sym_elem 1, axis_outset 2, d4_identity 2, corner_inset 3, edge_outset 3, reflection 4.
- Param column-type tuples: 46 kinds under 5 uses, such as `Position Sym`, `Dir8 Dir8`, `number C4`, `Color Offset Color`, `Ident Dir8`.
- Constraint operators are all common: `=` 685, `!=` 580, `<` 229, `>` 88, `<=` 71, `>=` 57.

## Tasks

| measure | value |
| --- | --- |
| tasks | 1147 |
| largest grid | 30×30, 900 cells (e12f9a14) |
| most train pairs | 10 (794b24be) |
| most test inputs | 4 (8dab14c2) |

## Bodies

A survey of the 905 `.arclog` files of `gen/` on 2026-10-16. A body is the body of a `RULE`, `DET`, `DET_OR_RULE`, `RULE_OR_DET` or `RIGID_DET` form, an instance's key clause or input, or a `CHOOSE` form's `from` or `never` list: 20241 bodies. The script is `survey_caps.py`, one pass of about 2 s, and `summarize.py` reads its JSON, both under `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/129de8fc-2a0d-4d4d-b950-3a0194c762e2/scratchpad/corpus-caps/`: `uv run python survey_caps.py work/arclog/gen > out.json`, then `python3 summarize.py out.json`.

An atom counts each atom, negated atom, constraint and `ONE` mark at every depth. A label counts each variable once, a label local to an `OR` branch, an `IF` test or an `ALL` once per form it is local to.

| measure | p50 | p90 | p99 | max (stem, relation) |
| --- | --- | --- | --- | --- |
| atoms | 2 | 5 | 11 | 33 (20a9e565 `&fill`) |
| labels | 2 | 5 | 10 | 24 (20a9e565 `&fill`, a57f2f04 `&copy`) |
| vertices of the atom–variable graph | 6 | 14 | 25 | 65 (20a9e565 `&fill`) |
| nesting depth of `OR`, `IF`, `ALL`, `NOT` | 0 | 1 | 1 | 3 |

## Body symmetry

Each body is a graph: a vertex per atom, colored by its relation and its negation; a vertex per label; a vertex per constant; a vertex per `OR`, branch, `IF` part, `ALL` part and `NOT` group; an edge from an atom to each label it reads, labeled by the column path (`key.C` for a field); `>` and `>=` turned into `<` and `<=`, and `=`, `!=` with unordered sides; a head site, a key column by its index. The relation is colored by its name. Color refinement is 1-dimensional Weisfeiler–Leman over the labeled edges. Each body that refinement leaves with ties is searched in full by individualization–refinement, with no automorphism pruning, under three cell selectors: the first smallest non-singleton cell, the first largest, the first.

| measure | value |
| --- | --- |
| bodies that refinement leaves discrete | 20081 of 20241 |
| bodies with ties | 160: 125 `RULE`, 19 `DET`, 7 `never`, 6 input, 3 key |
| non-singleton cells per tied body | 1:12, 2:92, 3:25, 4:18, 5:7, 6:5, 8:1 |
| largest cell after refinement | 2 in 156 bodies, 3 in 3, 4 in 1 |
| automorphism group order | 2:151, 4:5, 6:3, 8:1 |
| bodies whose search leaves differ from the automorphism count | 0: every tie that refinement leaves is a symmetry of the body |
| search tree nodes, first smallest | p50 3, p99 10, max 15 (a6f40cea `&joined`) |
| search tree nodes, first largest | p50 3, p99 10, max 13 (a6f40cea `&joined`) |
| individualization depth | first smallest: 1 in 151 bodies, 2 in 8, 3 in 1; first largest: at most 2 |

- The symmetric bodies are self-joins of one relation with two labels that swap, such as a6f40cea `&joined` `(&piece_color *B *Id *Col) (&piece_color B (:Id *Id2) Col)`, with each `ALL` adding a swap of its own locals.
- The order 8 bodies: 4c7dc4dd `&slot`, a32d8b75 `&pattern_many` and `&pattern_many2`, a6f40cea `&joined`.

## Join shapes

The top-level positive atoms of each clause body and instance input, 18103 bodies, with `(= X Y)` as an edge. Acyclic is GYO reducibility of the hypergraph of their labels. A self-join is a relation read by two or more of those atoms.

| measure | value |
| --- | --- |
| top-level positive atoms | p50 1, p90 4, p99 8, max 23 (4522001f `&fit_cell`) |
| connected components | 0:3569, 1:13263, 2:1174, 3:78, 4:18, 5:1 (269e22fb `&render`) |
| cyclic bodies | 1737: 1276 `RULE`, 247 input, 213 `DET`, 1 `RULE_OR_DET`; largest 4522001f `&fit_cell` 23 atoms, a57f2f04 `&copy` 21 |
| bodies with a self-join | 1348; 771 of them cyclic; most reads of one relation 4 |
| lib atoms per body | p90 2, p99 4, max 19 |
| algebra outputs joined on a computed key | 207 bodies: 117 input, 75 `RULE`, 11 `DET`; by relation split 95, margin 28, sub_extent 25, divide 14, neighbor 13, relative 11, box_extent 8, frame_extent 6 |
| bodies cyclic through stored relations, with the algebra atoms removed | 103; 15 of them in the solvers of [Runs](#runs) |

- The last two rows are of 2026-10-17, over `gen/` converted again: `ckjoin.py` and `cyc.py` under `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/129de8fc-2a0d-4d4d-b950-3a0194c762e2/scratchpad/evaluator-evidence/`. An atom joined on a computed key is an algebra atom checked against an output already bound while its input comes from a stored atom enumerated later.
- A body with two or more components is a cross product. The inputs `before` of `Order` instances form most of the 4-component bodies, as a pair of cells by design.

## Prefix sizes

The row count of each written prefix of a body's top-level items, against the body's, on 2026-10-17. Each solver of `gen/` ran on Souffle on train input 0 and its largest train input, with every relation written out, and the prefixes were joined from those rows, with the orientation tables, the Box and number relations, the checks and the comparisons applied. 8718 bodies of 911 solvers were measured; the rest read `ex_input` or `ex_output`, a relation renamed by the converter or a keyed input, or are `DET` bodies. `divide`, `frame_offset`, `OR`, `IF`, `ALL` and `ONE` are not applied, so a body that holds one has an upper bound for its count. A prefix's count is the product of its parts, so a prefix of two parts that share no label counts as their cross product. The scripts are under `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/129de8fc-2a0d-4d4d-b950-3a0194c762e2/scratchpad/prefix-probe/`: `dump.py`, then `measure.py` with `alg.py`, `reorder2.py` and `analyze2.py`.

| measure | value |
| --- | --- |
| largest prefix | ≤10^3 in 8097 bodies; over 10^4 in 102, over 10^5 in 30, over 10^6 in 4, none over 10^7 |
| largest prefix over 100 times the full body | 117 bodies |
| prefix over 10^5 with the full body under 1/100 of it | 7 |
| prefix over 10^6 with the full body under 1/100 of it | 0 |
| bodies over 10^4 that another normal order brings under it | 20 of the 93 the reorder reached, such as 80214e03 `&separated`, 309K rows to 1368, with `neighbor` before the `!=` |

- The large prefixes are mostly a cross product of two cell sets, or of cells and boxes, before the check that relates them: `inside`, `interior`, `same_line`, `nearer`. a6f40cea `&hole`, `input` against `&rings.box` before `interior`, is 6.39M rows, and its body 104K.

## Join orders

The variable order of [Joins](evaluator.md#joins), simulated on 2026-10-17 on the bodies of [Join shapes](#join-shapes) that join on a computed key or are cyclic through stored relations. The rows are those of [Prefix sizes](#prefix-sizes), on the same train inputs, with the relations of a solver's instances from a second Souffle run of each solver whose dump lacked them. The count of a set of variables is the number of its bindings that agree with each atom projected onto the set. An algebra check applies once its labels are bound, and a function once the inputs of one of its modes are bound. The work of an order is the sum, over its variables, of the fewest extensions that one atom gives the bindings so far, plus the rows of each computed-key index the order builds. The written order breaks ties of relation size, in place of the canonical order. The best order minimizes each measure over every order that the modes allow, for bodies of at most 9 variables. Each body is taken on the input where its written order has the largest intermediate. The scripts are `sim.py` and `ana.py` under `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/129de8fc-2a0d-4d4d-b950-3a0194c762e2/scratchpad/join-order/`: `python3 sim.py OUT.json <stem> targets.json` for each stem, then `python3 ana.py`.

| bodies | order | largest intermediate, max / sum | work, max / sum |
| --- | --- | --- | --- |
| computed key, 133 of 207 | written | 401408 / 628782 | 440611 / 938789 |
| | the rule | 83520 / 248760 | 102186 / 590762 |
| | the rule with no computed-key index | 83520 / 248760 | 194092 / 915683 |
| computed key, the 125 of at most 9 variables | the rule | 83520 / 221250 | 102186 / 517662 |
| | best | 83520 / 220963 | 90120 / 445386 |
| cyclic, 39 of 103 | written | 401408 / 533614 | 440611 / 941474 |
| | the rule | 46076 / 93935 | 87358 / 253596 |
| cyclic, the 32 of at most 9 variables | the rule | 896 / 4521 | 1436 / 10347 |
| | best | 896 / 3777 | 1436 / 7696 |

- No measured body under the rule has a largest intermediate over 10^4 and over 10 times the best order's, or work over 10^5 and over 10 times the best order's. The largest ratios of work are b7f8a4d8 `&covered`, 1621 against 54, which binds the colors of `&paint` before the ranks of the `&draw_rank` atoms it joins, and c7f57c3e `&tiling.side`, 18666 against 6600, and b71a7747 `&kept`, 6554 against 1762, which bind a table of 2 rows (`axis_elem`, `perp`) before the stored relation.
- The computed-key index cuts the work of b71a7747 `&band_square` from 282424 to 2249, an index on `split` over `input`, and of a32d8b75 `&cover` from 139396 to 1924, an index on `diag_dist` over `&field_at`.
- An output of an algebra relation that is bound after every variable of a stored relation, in place of directly after the inputs of its mode, gives a32d8b75 `&cover` a largest intermediate of 138240 against 288, and 9b2a60aa `&copy` work of 9973 against 145.
- Of the bodies over 9 variables, the largest under the rule are 4e34c42c `&layout.edge`, 46076, as in its written order, 50a16a69 `&output`, 25088 against 401408 written, and b10624e5 `&scaled`, 5194 against 63219 written.
- 74 computed-key bodies and 64 cyclic bodies are not measured. Most read a relation whose arclog name resolves to no Souffle relation, as a converter rename gives, such as 00dbd492 `same.equal` for Souffle's `same.equals`: 62 and 60. 10 computed-key bodies and 5545f144 `&hop` bind a label only through `divide`, `frame_offset` or a form that the simulation does not apply. 1d0a4b61 `&output` reaches the limit of 6 s on one count. The rest, such as 351d6448 `&advance`, match no body that the simulation parses.

## Determination candidates

`DET` and `DET_OR_RULE` forms with no body, by the proposers they name, in `gen/`, and the Souffle tooling's determination plans.

- Domain proposers with no body per file, at the domain's size in a full task (Color 10, Number 30, Sym 16, Position 900, Box 216225): the largest products are 48d8fb45 `BoxDomain` 216225, ca8de6ea and 7fe24cdd `PositionDomain` 900, 4522001f 160, ba26e723 120; 5 files are over 100.
- On 2026-10-18, no `DET` of `gen/` names `BoxDomain`: 48d8fb45's `win_box` states a body. Two name `PositionDomain`, 7fe24cdd `&anchor` and ed74f2f2 `&target_tile`, and ca8de6ea names none.
- `uv run python scripts/run_dl.py determination-plan <stem>` gives the domain of the values the task admits: 48d8fb45 `win_box` 95 values, 7fe24cdd `anchor` 52, ba26e723 72 joint assignments; in ca8de6ea and 4522001f every such parameter has a determination relation.
- The 8951 plans under `.cache/determination-plan/`, from every version of the Souffle solvers, with each covered line's `enumerable(n)` or `narrowed(n)` multiplied: product 1 in 3533 plans, 2 to 10 in 4178, 11 to 100 in 1240, and none over 100. The tool's `ENUMERATION_LIMIT` is 100 (`src/checker/determination_plan.py`). 83 plans report a product over it, up to 2258530576, and for those the solver adds determination relations until the product is under 100.

## Open values and constraint search

- 34 parameters of a `DET` or `DET_OR_RULE` with `(ONE)` have a `param` record: rows 2:14, 3:1, 4:7, 6:1, 7:1, 8:10. The 8-row ones are D4 orientations, such as abbfd121 `&scan`. The script is `open_values.py` in the same directory, `python3 open_values.py out.json work/arclog/gen`.
- On 2026-10-17, 42 such parameters: rows 2:17, 3:1, 4:9, 6:1, 7:1, 8:11, each row a single value, and 96:2, b7f8a4d8 `&draw_rank` and bc93ec48 `&precedence`, each 24 open values of 4 rows under an Ident column. `gen/` has 18 `CHOOSE` forms, 8 `RULE` clauses with `ONE` marks in 7 files, and 7 `DEMONSTRATED` forms. The script is `picks.py` under `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/129de8fc-2a0d-4d4d-b950-3a0194c762e2/scratchpad/cases-models/`, `python3 picks.py work/arclog/gen`.
- Models per case per input, on 2026-10-17: the distinct (`OpenValue`, `TiebreakResolution`) pairs of each case in the Souffle `out` on each train and test input, by `run_dl.py relation <stem> out`, over the 7 solvers with `TiebreakResolutions` and the 5 with the largest products of open values. The largest is 64, in a2d730bd, abc82100 and 9f8de559, each two D4 parameters of 8 open values. Among the tie solvers, the largest is 4: a3325580, 4 lead corners and no tie on any input, and b7cb93ac train 2. The product of the open values per file of every other solver is at most 16 (abbfd121), and its arclog form 24 for b7f8a4d8 and bc93ec48. So 64 bounds the models per case per input of these forms. The `CHOOSE` forms with no tie in their Souffle solvers and the `DEMONSTRATED` forms are not measured. The script is `ties.py` in the same directory, `python3 -u ties.py <stem>...` from the repo root.
- Models per case per input and search nodes per cluster, on 2026-10-19: `arclog-cli compare .cache/parity work/arclog/gen data/tasks` over the concept cases of `work/arclog/gen/`, under a model cap of 1 000 000 and a node cap of 10 000 000, counted with instrumentation that is not committed. The largest are 8 models and 14 nodes, each of 9f8de559, among the 840 solvers of 953 whose concept case ran to its end; 6 hold a `DEMONSTRATED` form and are not compared. The outlier 97a05b5b searches 4 147 798 nodes for its one model, with an engine run of 22.6 s against Souffle's 0.7 s, and is a fault of its solver or of the lib. The node cap 2^5 = 32 is about twice the 14 nodes, and the model cap 2^7 = 128 is about twice the 64 models that the item above gives as the bound of the open-value forms, which covers a2d730bd and abc82100, solvers that gave no engine count.
- The [Evidence](../../docs/arclog/constraints.md#evidence) of the constraint doc measures the covers of the nine `CoverForcing` solvers: each key has one cover or none. For the other picks, it states that propagation alone solves the pick on every corpus input, and no run measures it.

## Forms per solver

Declaration forms per file, a relation that more than one block derives, and such a relation whose clauses have more than one set of top-level labels. The script is `forms_shared.py` in the same directory, `python3 forms_shared.py work/arclog/gen`.

| stem | cases | forms | relations | rederived | with another column set |
| --- | --- | --- | --- | --- | --- |
| af24b4cc | 736 | 54 | 46 | 4 | 2 |
| b2bc3ffd | 1177 | 39 | 26 | 8 | 3 |
| ae3edfdc | 640 | 36 | 26 | 7 | 1 |
| ac0c5833 | 428 | 50 | 38 | 9 | 3 |
| a32d8b75 | | 161 | 145 | 15 | 11 |

- 399 files have a relation rederived with another column set.

## Runs

17 Souffle solvers, each run once by `run_dl.py run <stem>` with each Souffle call profiled by `souffle -p` and the run store bypassed, on 2026-10-16. They were chosen as the extremes above: the slowest runs of the gate's `accepted-times.json` (a934301b, abbfd121, a5f85a15, a61ba2ce, 0dfd9992, aa62e3f4), the most cases (af24b4cc, b2bc3ffd), the largest and the cyclic bodies (20a9e565, 4522001f, a57f2f04, a395ee82), the 5-component body (269e22fb), the most Ident instances (ae58858e, b2862040, 21897d95), and the most box arithmetic with the most forms (a32d8b75). For 15 of them, all but a395ee82 and 269e22fb, each call was made a second time with an `.output` for every relation its profile names, and the rows were read. The scripts are `profile_run.py` and `profiles.py` in the directory of [Bodies](#bodies): `uv run python profile_run.py [--dump] DIR <stem>...` from the repo root, then `python3 profiles.py DIR`.

A Souffle solver holds every case in one relation, under its choice columns, so a relation's tuples bound the rows that one case's clause gives. A relation whose path has a segment that starts with `_` is internal to a lib component, which the engine builds natively; the others are public.

| stem | calls | slowest call | largest public relation | slowest public rule |
| --- | --- | --- | --- | --- |
| a57f2f04 | 51 | 28.5 s | `parse.scan_order.before` 2440832 | 21.2 s, `parse.copy`, 38400 tuples |
| a32d8b75 | 17 | 4.6 s | `out` 64000 | 4.5 s, `parse.cover`, 20800 tuples |
| abbfd121 | 92 | 4.2 s | `parse.shade_reach.edge` 499455 | 0.47 s, `clash`, 4536 tuples |
| 20a9e565 | 105 | 3.2 s | `grown_box.cell` 89090 | 2.9 s, `mirror_defect`, 1240 tuples |
| b2bc3ffd | 91 | 1.1 s | `out` 32720 | 0.28 s, `landing` |
| a395ee82 | 39 | 1.0 s | `out` 21780 | 1.0 s, `determine.covered` |
| 0dfd9992 | 5 | 0.9 s | `orbit.edge` 42591 | 7 ms |
| af24b4cc | 3249 | 0.32 s | `commonest.item` 2880 | 0.18 s |
| b2862040 | 182 | 0.29 s | `determine.ex.off_wall` 17304 | 0.11 s |
| the other 8 | | under 0.2 s | at most 31414 (269e22fb `occ.placement`) | at most 0.13 s |

- The largest internal relations are Wallpaper's: abbfd121 `wp._pair` 1708260 and 0dfd9992 `wp._reach` 1312968, the slowest internal rule 1.3 s.
- a57f2f04's `parse.scan_order.before` is the `before` input of an `Order` instance, a pair relation over its members.
- The tooling's limit per call is 20 s of CPU (`src/cli/common.py`). Of the 17, a57f2f04 is the one solver whose slowest call reaches 28.5 s of the profile's wall time.
- `run_dl.py run` makes its Souffle calls in parallel, so the times above include contention: a57f2f04 took 47 s of user time over 18 s of wall time. Each call rerun alone, under a load average of 11 to 17, gives a57f2f04's slowest call 6.35 s of wall time, its largest `parse.copy` 4.93 s, and abbfd121's slowest call 2.25 s of program and about 1.3 s of Souffle's frontend. `capture.py` and `rerun.sh` in `scratchpad/slow-solvers/` keep each call's program and facts and rerun one call alone.

### Causes of the outliers

Each outlier above was read and, where a fix was tried, rerun with the fix, and every fix kept the output, by an md5 of the sorted `.output` files. None is a cost of its task's intended concept. The class column judges by principle: a form that does more work than another is a fault only where a principle rules it out, since the principled form is right whatever it costs, as [Performance](../../docs/handbook/encoding.md#performance) gives.

| clause | cause | class | measured fix |
| --- | --- | --- | --- |
| a57f2f04 `parse.copy` | each row is derived on 32 paths of about 30 functor calls each: `diag_dirs` takes each corner once per axis order, 2×; `box_extent` inlines `axis_of`, whose 2 rows give one extent, 4× over two calls; `Parse` is keyed by the whole `Choice`, though the copy varies with no `PanelExtent`, 2×; and on one input 57600 rows hold 900 distinct contents, since the cases' relations hold the same rows there | the key: solver, by the rule that a comp is keyed by the `Choice` fields it varies with; the axis order: the principled form, which states the corner on either axis with no axis literal; `box_extent`: lib; the rest: Souffle (no shared subexpressions, no sharing across cases) | one axis order and `box_extent` without the hidden direction: 2.76 s to 0.36 s on call 21 |
| a57f2f04 `parse.scan_order.before` | `Order.first` by subsumption over the `before` pairs, O(m²) per key against O(m) for a minimum; 512 keys hold 24 distinct contents, since the scan is keyed by the whole `Choice` | `first` by pairs: lib; the key: solver, by the same rule | two minimum aggregates in place of `LexOrder`: 2440832 rows to none, 3.4 s to 0.03 s |
| abbfd121 `parse.shade_reach.edge` | a `Propagation` keyed by source color copies the colorless `map_link` edges once per color, 3×, and its closure chains past the output claim's text | solver, by fidelity: the closure states a hypothesis that the output claim does not | a direct read of `map_link`: 504k rows less, the same output |
| abbfd121 Wallpaper internals | `wp._reach` and `wp._pair`, 1708260 rows each, test every candidate on every pair of a lattice class, where a test per class decides it | lib | a test per class: `_pair` gone, `_reach` 256k, the program 2.0 s to 0.73 s |
| a32d8b75 `parse.cover` | each of 15600 rows enumerates about 660 field cells and filters on an equal computed `diag_dist`: about 20M probes | Souffle (no index on a computed key) | a relation of the computed key, 10560 rows: 2.94 s to 0.014 s |
| 20a9e565 `mirror_defect` | a universal by defect negation that enumerates every P after the defect row is derived: about 3.7M probes for 1240 defects | Souffle (no early exit on an existential) | none clean; a rewrite changed 6 rows |
| a395ee82 `determine.covered` | a cell's place in its block is computed per pair of cells, the join is on a computed key, and the axis and `box_extent` factors of `parse.copy` | Souffle (no hoisting, no index on a computed key); the axis order: the principled form; `box_extent`: lib | a relation of the places, 11371 rows: 1.11 s to 0.065 s |

- Past the fixes, the largest rows are those of the orbit as cell pairs, abbfd121's `wp.action` 256038 and `map_link` 166485, and the rows that cases whose relations hold the same rows on an input give once each.

### Box values

The values of the form `[t, b, l, r]` in every dumped row of the 15, outside `in`, `ex_in` and `ex_out`:

- The largest margin is 29, and the smallest is −22 (abbfd121 `determine.parse.period._cand [22, -22, 0, 0]`), then −20 (0dfd9992 `si._cand`). 0dfd9992 `wp._image [1, 19, 28, -8]` is the widest box past the frame.
- The determination plan of 48d8fb45 gives `win_box` `[1, -3, -1, -1]`.
- An intermediate value of an inline functor, such as `@box_compose` in a body, is in no relation, so this survey does not see it.

### Idents

An Ident group is a distinct row of a relation whose last column is `id`, less its `p` or `a` column, outside `_ident`, summed over the relations of one call: the components, classes and enclosures that the call labels.

- Per call, at most 340 (b2862040), then 146 (a934301b), 48 (af24b4cc) and 28 (ae58858e).
