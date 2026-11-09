# Corpus survey

The output of `uv run python scripts/corpus_survey.py`, which rewrites the sections it is given, and with no name the sections that run no solver: change the script, never this file. Run a section only where a decision needs its numbers on the current corpus.

## Forms

Count of list nodes with the head, and the number of files with at least one.

| form | count | files |
| --- | --- | --- |
| RULE | 8900 | 953 |
| INIT | 4542 | 904 |
| NOT | 4411 | 905 |
| DET | 3622 | 897 |
| OR | 2409 | 839 |
| ALT | 1624 | 653 |
| ALTS | 1227 | 653 |
| OUTPUT / INPUT | 1096 / 815 | 167 / 166 |
| ALL | 278 | 179 |
| DET_OR_RULE / RULE_OR_DET | 169 / 33 | 112 / 24 |
| IF | 138 | 119 |
| ONE | 62 | 42 |
| DEMO_RULE / DEMONSTRATED | 19 / 7 | 6 / 6 |
| CHOOSE | 18 | 18 |
| APPROXIMATED | 14 | 14 |
| RIGID_DET | 14 | 11 |

- `ONE` by shape: 43 bare `(ONE)` in a DET, 13 with columns in a RULE, 4 with columns in a DET, 1 bare `(ONE)` in a RULE, 1 bare `(ONE)` in a DET_OR_RULE. The open parameters, a bare `(ONE)` in a DET or a DET_OR_RULE: 44.
- Declaration forms per file: median 15, p90 32, max 121 (a32d8b75). All headed nodes per file: median 117, p90 301, max 1259 (20a9e565).
- TODO markers: 9 in total; head-term 5, alt-undefined 4.

Inputs: the 953 `.arclog` files of `programs/arclog/`. Computed on 2026-10-19.

## Alts structure

Here an `ALTS` form includes each `DET_OR_RULE` and `RULE_OR_DET` line, and its depth is one more than the `ALTS` forms it stands in. A combination block is an `ALT` that stands directly in an `ALT`. The cases of a file are the cases that the file's record in the snapshot `.cache/parity/` holds, as `docs/engine/cases.md#cases` gives them.

| measure | value |
| --- | --- |
| files with an `ALTS` form | 655 |
| `ALTS` forms per file, max | 13 (ae3edfdc) |
| ALTS nesting depth, max | 3 (a48eeaf7); 72 files at depth 2 or more |
| combination ALT blocks | 72 |
| cases per file | median 2; max 1177 (b2bc3ffd), then a1aa0c1e 1080, a416fc5b 884, b10624e5 768, af24b4cc 736, ae3edfdc 640, ac3e2b04 576, aa300dc3 528 |
| files with excludes | 60; 376 excludes; max 34 per file (a2d730bd) |

| cases | files |
| --- | --- |
| 1 | 297 |
| 2 | 321 |
| 3–4 | 151 |
| 5–8 | 58 |
| 9–16 | 26 |
| 17–64 | 52 |
| more than 64 | 48 |

Inputs: the 953 `.arclog` files of `programs/arclog/` and their `.arcdata` files, and the records of `.cache/parity/` of the 953 of them that have one. Computed on 2026-10-19.

## Instances

`INIT` forms per component; a `DEMONSTRATED` form counts as DemonstrationConsistency. The key width is the number of `^` labels in the key clause. Most instances in one file: 27 (a64e4611).

| component | instances | key widths {width: n} | max width (stem) |
| --- | --- | --- | --- |
| Order | 755 | 0:395 1:248 2:83 3:24 4:4 5:1 | 5 (9f8de559) |
| BoundingBox | 681 | 0:213 1:360 2:95 3:12 5:1 | 5 (a25697e4) |
| Cardinality | 552 | 0:76 1:355 2:103 3:14 4:4 | 4 (4 files) |
| Connectivity | 479 | 0:276 1:185 2:17 3:1 | 3 (4290ef0e) |
| Singleton | 359 | 0:122 1:146 2:75 3:11 4:5 | 4 (5 files) |
| Frame | 265 | 0:227 1:33 2:5 | 2 (5 files) |
| Ray | 261 | 0:136 1:104 2:17 3:3 8:1 | 8 (351d6448) |
| Division | 236 | 0:170 1:41 2:23 3:1 4:1 | 4 (351d6448) |
| Tiling | 170 | 0:160 1:10 | 1 (7 files) |
| Inclusion | 109 | 0:109 | 0 (82 files) |
| Propagation | 83 | 0:51 1:22 2:9 3:1 | 3 (20a9e565) |
| Quotient | 76 | 0:76 | 0 (66 files) |
| Occurrences | 75 | 0:23 1:29 2:16 3:6 5:1 | 5 (269e22fb) |
| Boundary | 73 | 0:45 1:27 2:1 | 2 (136b0064) |
| Enclosure | 64 | 0:35 1:27 2:2 | 2 (2 files) |
| Distance | 60 | 0:27 1:25 2:8 | 2 (8 files) |
| Walk | 55 | 0:36 1:18 3:1 | 3 (a6f40cea) |
| Flood | 53 | 0:35 1:13 2:5 | 2 (5 files) |
| Agreement | 43 | 0:9 1:15 2:18 4:1 | 4 (409aa875) |
| Outlines | 25 | 0:9 1:16 | 1 (16 files) |
| Periods | 25 | 0:12 1:13 | 1 (13 files) |
| CellDistance | 22 | 0:15 1:7 | 1 (3 files) |
| Excess | 12 | 0:3 1:2 2:6 4:1 | 4 (c663677b) |
| DemonstrationConsistency | 7 | 0:2 1:3 2:1 5:1 | 5 (351d6448) |
| Wallpaper | 4 | 0:4 | 0 (3 files) |
| Unfold | 3 | 0:1 1:1 2:1 | 2 (a8d7556c) |
| ExtentDivisions | 2 | 1:2 | 1 (2 files) |

- The components no instance of which takes a key clause: Inclusion, Quotient, Wallpaper.
- The `CHOOSE` `for` key widths {width: n}: 1:13, 2:3, 3:2.

Inputs: the 953 `.arclog` files of `programs/arclog/`. Computed on 2026-10-19.

## Recursion

Each declaration's `&` reads, with `&x.out` counted as a read of `&x`; a read under `NOT`, under `ALL` or in an `IF` test is negated. Cycles are the strongly connected components over three graphs: every derivation merged, the concept program alone, and each alt path with its derivations in place of the concept program's. The cycles of one kind are listed up to 8, the largest first.

| measure | result |
| --- | --- |
| relations that read themselves | 3; 3490cc26 `&state`; 696d4842 `&crawl`; a8d7556c `&claim` |
| a clause that reads its own relation | 0 |
| cycles in the concept program's graph | 3 |
| 3490cc26 | 1 relations, 0 negated edges: `&state` |
| 696d4842 | 1 relations, 0 negated edges: `&crawl` |
| a8d7556c | 1 relations, 0 negated edges: `&claim` |
| cycles on an alt path and in no concept graph | 0; 0 through a negation |

Inputs: the 953 `.arclog` files of `programs/arclog/`. Computed on 2026-10-19.

## Arcdata

| measure | value |
| --- | --- |
| params, total / max per file | 2923 / 15 (136b0064) |
| largest param | 441 rows (73251a56 `&label`) |
| witnesses with a body | 1020; max 20 per file (abbfd121); 161 files have one |
| bodiless back-references | 118 |
| plausibility | variant 432, borderline 370, ordinary 127, foreign 91 |
| verdict | concept 494, an alt 462, any 48, other 16 |
| top-level heads | param 2923, alts 819, exclude 376, representative 47, approximated 14 |

A `grid` value of a param counts one row per cell that is not `_`.

Inputs: the 953 `.arcdata` files of `programs/arclog/`. Computed on 2026-10-19.

## Columns

A derived relation is one a clause with a body derives, and its columns are its body's top-level `*` labels plus what its `OR` and `IF` forms export, over every such clause. A read projects when the columns its sites select, `E` aside, are a strict subset of the relation's.

| measure | value |
| --- | --- |
| widest derived relation | 24 columns (a57f2f04 `&copy`) |
| widest lib relation read | 5 (`divide`) |
| arity distribution | 0:64, 1:909, 2:2404, 3:1775, 4:1341, 5:894, 6:529, 7:325, 8:147, 9:104, 10+:142 |
| derived-relation reads that project | 15711 of 21687 |
| lib atoms with fewer sites than the lib arity | 993 of 13049 |
| instance-output atoms | 4583 |

Inputs: the 953 `.arclog` files of `programs/arclog/`, with the lib's columns from `src/arclog_convert/lib-signature.dl`. Computed on 2026-10-19.

## Rare constructs

- Keywords: the thinnest are DEMONSTRATED 7, APPROXIMATED 14, RIGID_DET 14, CHOOSE 18.
- Components under 5 instances: ExtentDivisions 2, Unfold 3, Wallpaper 4.
- Proposers: 40 of the 42 proposers are named by a DET or a DET_OR_RULE; DominantColor has the most uses, 569. Under 5: ConstInDimAxis 1, NumberDirDomain 1, VanishedNewPairs 1, ColorColorDomain 2, OutNewColor 2, Period 2.
- Lib relations: 66 of 67 read. Under 5: corner_outset 1, axis_outset 2, d4_identity 2, corner_inset 3, d4_compose 3, d4_inverse 4, edge_outset 4.
- Param column-type tuples: 48 kinds under 5 uses, such as `Color Dir`, `Color Offset`, `DiagDir DiagDir`, `Position Position`, `number Position`.
- Constraint operators: `=` 746, `!=` 668, `<` 256, `>` 114, `<=` 80, `>=` 67.

Inputs: the 953 `.arclog` files of `programs/arclog/` and `.arcdata` files, with the proposers of `src/arclog_convert/lib.py`. Computed on 2026-10-19.

## Tasks

| measure | value |
| --- | --- |
| tasks | 1147 |
| largest grid | 30×30, 900 cells (05a7bcf2) |
| most train pairs | 10 (794b24be) |
| most test inputs | 4 (8dab14c2) |

Inputs: the 1147 task files of `data/tasks/`. Computed on 2026-10-19.

## Bodies

A body is the body of a `RULE`, `DET`, `DET_OR_RULE`, `RULE_OR_DET` or `RIGID_DET` form, an instance's key clause or input, or a `CHOOSE` form's `from` or `never` list: 22298 bodies. An atom counts each atom, negated atom, constraint and `ONE` mark at every depth. A label counts each variable once, a label local to an `OR` branch, an `IF` test or an `ALL` once per form it is local to.

| measure | p50 | p90 | p99 | max (stem, relation) |
| --- | --- | --- | --- | --- |
| atoms | 2 | 5 | 11 | 29 (88bcf3b4 `&walk`) |
| labels | 2 | 5 | 10 | 24 (a57f2f04 `&copy`) |
| vertices of the atom–variable graph | 6 | 13 | 24 | 60 (88bcf3b4 `&walk`) |
| nesting depth of `OR`, `IF`, `ALL`, `NOT` | 0 | 1 | 1 | 3 (83302e8f `&output`, a09f6c25 `&output`, 10 more) |

Inputs: the 953 `.arclog` files of `programs/arclog/`. Computed on 2026-10-19.

## Body symmetry

Each body is a graph: a vertex per atom, colored by its relation and its negation; a vertex per label; a vertex per constant; a vertex per `OR`, branch, `IF` part, `ALL` part and `NOT` group; an edge from an atom to each label it reads, labeled by the column path (`key.C` for a field); `>` and `>=` turned into `<` and `<=`, and `=`, `!=` with unordered sides; a head site, a key column by its index. The relation is colored by its name. Color refinement is 1-dimensional Weisfeiler–Leman over the labeled edges. Each body that refinement leaves with ties is searched in full by individualization–refinement, with no automorphism pruning, under three cell selectors: the first smallest non-singleton cell, the first largest, the first.

| measure | value |
| --- | --- |
| bodies that refinement leaves discrete | 22093 of 22298 |
| bodies with ties | 205: `RULE` 152, `DET` 19, key 18, input 9, never 7 |
| non-singleton cells per tied body | 1:18, 2:121, 3:24, 4:25, 5:11, 6:5, 8:1 |
| largest cell after refinement | 2 in 201 bodies, 3 in 2 bodies, 4 in 2 bodies |
| automorphism group order | 2:193, 4:8, 6:2, 8:1, 24:1 |
| bodies whose search leaves differ from the automorphism count | 0 |
| search tree nodes, first smallest | p50 3, p99 10, max 41 (c803e39c `&roles`) |
| search tree nodes, first largest | p50 3, p99 10, max 41 (c803e39c `&roles`) |
| search tree nodes, first | p50 3, p99 10, max 41 (c803e39c `&roles`) |
| individualization depth | first smallest: 1 in 193 bodies, 2 in 10 bodies, 3 in 2 bodies; first largest: 1 in 193 bodies, 2 in 11 bodies, 3 in 1 bodies; first: 1 in 193 bodies, 2 in 10 bodies, 3 in 2 bodies |
| searches stopped at the node cap | 0 |

- The bodies of the largest automorphism group: c803e39c `&roles`.

Inputs: the 953 `.arclog` files of `programs/arclog/`. Computed on 2026-10-19.

## Join shapes

The top-level positive atoms of each clause body and instance input, 19957 bodies, with `(= X Y)` as an edge. Acyclic is GYO reducibility of the hypergraph of their labels. A self-join is a relation read by two or more of those atoms. An atom joined on a computed key is an algebra atom checked against an output already bound while its input comes from a stored atom written later. A body cyclic through stored relations is cyclic with its algebra atoms and orientation tables removed.

| measure | value |
| --- | --- |
| top-level positive atoms | p50 1, p90 4, p99 8, max 23 (4522001f `&fit_cell`) |
| connected components | 0:3678, 1:14826, 2:1344, 3:85, 4:23, 5:1 (269e22fb `&render`) |
| cyclic bodies | 1899: `RULE` 1395, input 268, `DET` 230, `DET_OR_RULE` 4, `RULE_OR_DET` 2; largest 4522001f `&fit_cell` 23 atoms, a57f2f04 `&copy` 21 atoms |
| bodies with a self-join | 1463; 841 of them cyclic; most reads of one relation 4 |
| lib atoms per body | p90 2, p99 4, max 19 |
| algebra outputs joined on a computed key | 212 bodies: input 118, `RULE` 80, `DET` 12, `RULE_OR_DET` 2; by relation split 95, margin 25, sub_extent 25, neighbor 16, divide 14, relative 11, box_extent 6, frame_extent 6, compose 4, axis_extents 3, apply 2, diag_dist 2, frame_offset 2, jump_offset 1, jump 1 |
| bodies cyclic through stored relations | 98 |

Inputs: the 953 `.arclog` files of `programs/arclog/`, with the lib's columns from `src/arclog_convert/lib-signature.dl`. Computed on 2026-10-19.

## Prefix sizes

The row count of each written prefix of a body's top-level items, against the body's. Each solver of `gen/` ran on Souffle on train input 0 and its largest train input, with every relation of its name map written out, and the prefixes were joined from those rows, with the orientation tables, the Box and number relations, the checks and the comparisons applied; the bodies measured are those of a `RULE`, `DET_OR_RULE` or `RULE_OR_DET` clause and an instance's key clause and inputs, each on the rows of the case its alts pin. `divide`, `frame_offset`, `OR`, `IF`, `ALL` and `ONE` are not applied, so a body that holds one has an upper bound for its count. A prefix's count is the product of its parts, so a prefix of two parts that share no label counts as their cross product. A body's largest prefix is taken on the input where it is largest.

| measure | value |
| --- | --- |
| bodies measured | 11523 of 927 solvers; other outcomes: failed 9, no rows 1, no run 28, no stored atom 2800, unresolved 5426 |
| largest prefix | ≤10^3 in 10820 bodies; over 10^4 in 110, over 10^5 in 31, over 10^6 in 6, over 10^7 in 1 |
| largest prefix over 100 times the full body | 142 |
| prefix over 10^5 with the full body under 1/100 of it | 9 |
| prefix over 10^6 with the full body under 1/100 of it | 0 |
| bodies over 10^4 that another order the modes allow brings under it | 23 of the 103 of at most 12 items whose search ended within 120 s, such as 80214e03 `&separated`, 309256 rows to 1368 |

Inputs: Souffle runs of the solvers of the 953 `.arclog` files of `programs/arclog/`, on their tasks' train inputs, with the converter's name maps under `work/arclog/names/`. Computed on 2026-10-19.

## Join orders

An algebra check applies once its labels are bound, and a function once the inputs of one of its modes are bound. The written order takes each variable at its first appearance; the rule's order takes each function output directly once a mode's inputs are bound, else the variable of the smallest relation, ties broken by the written order. The best order minimizes each measure over every order that the modes allow, for bodies of at most 9 variables. Each body is taken on the input where its written order has the largest intermediate. `unresolved` is a body that reads a relation the name map does not reach from the top level.

| bodies | order | largest intermediate, max / sum | work, max / sum |
| --- | --- | --- | --- |
| computed key, 144 of 201 | written | 83520 / 239217 | 90120 / 520473 |
|  | the rule | 83520 / 224356 | 102186 / 541494 |
|  | the rule with no computed-key index | 83520 / 224356 | 194092 / 867420 |
| computed key, the 138 of at most 9 variables | the rule | 83520 / 222214 | 102186 / 527109 |
|  | best | 83520 / 221941 | 90120 / 449815 |
| cyclic, 47 of 92 | written | 46076 / 57775 | 164514 / 234547 |
|  | the rule | 46076 / 52596 | 87358 / 125498 |
|  | the rule with no computed-key index | 46076 / 52596 | 87358 / 125532 |
| cyclic, the 41 of at most 9 variables | the rule | 896 / 5008 | 2134 / 11484 |
|  | best | 896 / 4413 | 1436 / 8262 |

- computed key: 1 bodies reach a count past 100000000 rows or 6.0 s under some order, and stand outside the table: 50a16a69 `&output`.
- computed key: 0 bodies under the rule have a largest intermediate over 10^4 and over 10 times the best order's, or work over 10^5 and over 10 times the best order's.
- computed key: 56 bodies are not measured: unresolved 54, no order 2.
- cyclic: 1 bodies reach a count past 100000000 rows or 6.0 s under some order, and stand outside the table: 50a16a69 `&output`.
- cyclic: 0 bodies under the rule have a largest intermediate over 10^4 and over 10 times the best order's, or work over 10^5 and over 10 times the best order's.
- cyclic: 44 bodies are not measured: unresolved 43, timeout 1.

Inputs: the rows of Prefix sizes, over the bodies of Join shapes of the 953 `.arclog` files of `programs/arclog/`. Computed on 2026-10-19.

## `DET` domains

`DET` and `DET_OR_RULE` forms with no body, by the proposers they name, in `gen/`, and the Souffle tooling's determination plans. A file's product multiplies, over its forms with no body that name a type-domain proposer, the size of the largest `DET`'s domain that a proposer the form names gives, in a task of 30×30 grids.

- The largest products of type-domain proposers with no body per file: baf41dbf 300, a32d8b75 128, ba26e723 120, c62e2108 120, 239be575 100; 4 files are over 100.
- The forms with no body that name `BoxDomain` or `PositionDomain`: none.
- The 20318 plans under `.cache/determination-plan/`, from every version of the Souffle solvers, with each covered line's `enumerable(n)` or `narrowed(n)` multiplied: product 1 in 8078, 2 to 10 in 9509, 11 to 100 in 2727, over 100 in 4. The tool's `ENUMERATION_LIMIT` is 100. 86 plans report a product over it, up to 2258530576.

Inputs: the 953 `.arclog` files of `programs/arclog/`, and the plans of `.cache/determination-plan/`. Computed on 2026-10-19.

## Open values and constraint search

- 43 parameters of a `DET` or `DET_OR_RULE` with `(ONE)` have a `param` record: rows 2:17, 3:1, 4:9, 6:1, 7:1, 8:12, 16:2.
- The largest products of those rows per file: 9f8de559 64, a2d730bd 64, abc82100 64, abbfd121 16, b7f8a4d8 16.
- `gen/` has 18 `CHOOSE` forms, 8 `RULE` clauses with `ONE` marks in 7 files, and 7 `DEMONSTRATED` forms.

Inputs: the 953 `.arclog` files of `programs/arclog/` and `.arcdata` files. Computed on 2026-10-19.

### Models per case per input

The models of a case on an input are the distinct values of the `OpenValue` and `TiebreakResolution` columns of the Souffle `out` relation under one value of its `Choice` column, on each train and test input, over the 5 solvers of the largest products of open values and each solver whose `out` holds a `TiebreakResolution` column.

| stem | tie column | most models of a case on an input | inputs with no count, and why |
| --- | --- | --- | --- |
| 9f8de559 | no | 64 | none |
| a2d730bd | no | 64 | none |
| abc82100 | no | 64 | none |
| b7f8a4d8 | no | 25 | none |
| abbfd121 | no | 16 | none |
| a3325580 | yes | 4 | none |
| 8e5c0c38 | yes | 2 | none |
| c4d067a0 | yes | 2 | none |
| c61be7dc | yes | 2 | none |
| b15fca0b | yes | 1 | none |
| b7999b51 | yes | 1 | none |
| b99e7126 | yes | 1 | none |
| bd283c4a | yes | 1 | none |
| 89565ca0 | no | none | no Choice column |
| a6953f00 | no | none | no Choice column |
| b7cb93ac | no | none | no Choice column |

Inputs: Souffle runs of the 16 solvers of `programs/solvers/` above, on the tasks of `data/tasks/`. Computed on 2026-10-19.

## Forms per solver

Declaration forms per file, a relation that more than one block derives, and such a relation whose clauses have more than one set of top-level labels, for the 4 files of the most cases and the file of the most forms.

| stem | cases | forms | relations | rederived | with another column set |
| --- | --- | --- | --- | --- | --- |
| b2bc3ffd | 1177 | 39 | 26 | 8 | 3 |
| a1aa0c1e | 1080 | 55 | 43 | 8 | 3 |
| a416fc5b | 884 | 67 | 57 | 8 | 4 |
| b10624e5 | 768 | 41 | 37 | 3 | 2 |
| a32d8b75 | 48 | 121 | 111 | 9 | 7 |

- 439 files have a relation rederived with another column set.

Inputs: the 953 `.arclog` files of `programs/arclog/`, and the records of `.cache/parity/`. Computed on 2026-10-19.

## Runs

The solvers: those of the most CPU seconds in the snapshot `.cache/parity/`, of the most cases, of the bodies and the cyclic bodies of the most atoms, of the body of the most components, of the most Ident instances and of the most box arithmetic, as the sections above give them. A Souffle solver holds every case in one relation, under its choice columns, so a relation's tuples bound the rows that one case's clause gives. A relation whose path has a segment that starts with `_` is internal to a lib component, which the engine builds natively; the others are public. A call's time is the profile's wall time, and `run_dl.py run` makes its Souffle calls in parallel, so the times include contention.

| stem | calls | slowest call | largest public relation | slowest public rule |
| --- | --- | --- | --- | --- |
| c663677b | 31 | 6.6 s | `tile_vote` 3214148 | 1.2 s, `tile_area.tally`, 2704 tuples |
| ac0c5833 | 955 | 4.1 s | `out` 122400 | 3.8 s, `parse.triple`, 36528 tuples |
| 20a9e565 | 25 | 2.1 s | `repeat` 10488 | 1.9 s, `mirror_defect`, 1240 tuples |
| a57f2f04 | 51 | 801 ms | `out` 183040 | 369 ms, `parse.copy`, 23040 tuples |
| b10624e5 | 924 | 587 ms | `scaled` 17496 | 397 ms, `lacked`, 4 tuples |
| a416fc5b | 229 | 269 ms | `out` 249984 | 80 ms, `out`, 222208 tuples |
| 269e22fb | 14 | 128 ms | `occ.placement` 31414 | 98 ms, `occ.placement`, 31414 tuples |
| b2bc3ffd | 91 | 126 ms | `out` 32720 | 24 ms, `out`, 3768 tuples |
| ad38a9d0 | 92 | 90 ms | `out` 1701 | 16 ms, `shape_match.observed_member`, 5 tuples |
| the other 8 |  | under 85 ms | at most 12492 |  |

- The largest internal relations: c663677b `tile_major._key` 807192, a416fc5b `_cls_rec` 249984.
- The tooling's limit per call is 20.0 s of CPU; the solvers whose slowest call passes it in wall time: none.

Inputs: profiled Souffle runs of the 17 solvers above, of `programs/solvers/`. Computed on 2026-10-19.

### Box values

The values of the form `[t, b, l, r]` in every dumped row of the solvers of Runs, outside `in`, `ex_in` and `ex_out`. An intermediate value of an inline functor, such as `@box_compose` in a body, is in no relation, so this section does not see it.

- The largest margin is 43 (995c5fa3 `countrankasc.counts.counts.item [0, 3, 0, 43]`), and the smallest is -43 (995c5fa3 `period.inv._cand [0, 0, 43, -43]`).

Inputs: the dumps of Runs. Computed on 2026-10-19.

### Idents

An Ident group is a distinct row of a relation whose last column is `id`, less its `p` or `a` column, outside `_ident`, summed over the relations of one call: the components, classes and enclosures that the call labels.

- Per call, at most 48 (af24b4cc), then 28 (ae58858e), then 16 (c0f76784), then 9 (88bcf3b4).

Inputs: the dumps of Runs. Computed on 2026-10-19.
