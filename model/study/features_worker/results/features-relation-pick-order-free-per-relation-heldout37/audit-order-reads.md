# Facts that read atom order: audit

Report only: nothing here was changed. Paths under `R/` are `work/lm/data-study/features-worker/results/features-relation-pick-per-relation-models-heldout37/`, and lines are at the files on disk on 2026-11-01. No owner file exists, so "Owner" is the lane by folder: the features lane for `feat_exp/` and the records of `features-worker/`, the sampler lane for `model/study/sampler/`.

Verdict uses the ban as corrected: lexical order is banned (last atom, an atom's index, position in a body, a form's place in gold's text). Counts and facts of the read graph are allowed.

## Banned: reads written order

| File and line | What it reads | Owner |
|---|---|---|
| `R/features_rel_data.py:57` `last`, `:58` `last_not`, `:79` `last_derived`, `last_lib`, `last_not` | The head of the last atom of the written prefix, and whether it's NOT, derived or lib | features |
| `R/features_rel_data.py:26,:78` `ord` | The count of atom starts so far, across OR branches: an index in the written walk | features |
| `R/features_rel_data.py:102,:160` | Passes `last` on to the fit | features |
| `R/features_perrel_data.py:200` `last:<head>` | The token of the last written atom | features |
| `R/features_perrel_lib.py:92` | Adds that `last:` token to the facts of every key | features |
| `R/features_perrel_lib.py:29` and `R/features_perrel_data.py:26,:183` `recency`, `recency_frac` | Distance of a form from the target in gold's text | features |
| `R/features_perrel_data.py:159,:192-193` `prevform1`, `prevform2` | The two forms written just before the target | features |
| `R/features_perrel_keys.py:11-12,:50-63,:94-110` `body_head`, `root` | The key of a derived form takes its root from the head of its first written atom | features |
| `R/features_perrel_keys.py:62` | The same: `ATOM.match(rest)` takes the first atom | features |
| `model/study/sampler/relfeat.py:147-148` `_last_atom`, `:151-155` `_fits_made`, `:165-171` `b_follows_crop`, `b_follows_relative`, `b_repeat`, `b_fits_enum` | The last written atom, and at `:155` which of its columns hold the `*` mark | sampler |
| `model/study/sampler/relfit.py:58,:62` `rec` | Slot distance, a form's place | sampler |
| `model/study/sampler/relnet.py:148-164,:173-174,:250,:256,:261` `last_rel`, `last_slot`, `last_ty`, `last_sub`, `hit_last`, `islast`, `ov_last` | The last written atom | sampler |
| `model/study/sampler/plugins/rk2/features/rk1a.py:63-66` `_parse_prefix` | Keeps each label's binding atom index and last reading index | sampler |
| `model/study/sampler/plugins/rk2/features/rk1c.py:88-100,:207-208,:233,:240,:347-355,:359-365` `last_t`, `touch_t`, `age_t`, `c2_last_*`, `c2_touch_*`, `c2_recent` | Labels of the last atom, a label's age in atoms, the `*` mark | sampler |
| `model/study/sampler/plugins/rk2/features/rk2d.py:68,:98,:127,:145,:208-214,:222-223,:245,:247` `d3_last_*`, `d3_x_*`, `d3_not_after_*`, `d1_cmp_both_last`, `d1_cmp_stale` | The kind of the last atom | sampler |
| `model/study/sampler/plugins/rk2/features/rk2e.py:141-150,:210-212` `e2_cmp_numfresh`, `e2_cmp_lastfresh` | The labels the last atom made | sampler |
| `model/study/sampler/plugins/rk2/features/rk2f.py:88,:214,:273,:419-425` `f5_last_*`, `f5_same_as_last`, `f5_run` | The class of the last atom, and the run at the end of the prefix | sampler |
| `model/study/sampler/choicefeat.py:131,:140,:169,:173,:287` `first_at`, `last_at`, `last_reads_new` | Age of a label in atoms, on the choice pick | sampler |
| `model/study/sampler/sample2_col.py:2078-2082` tilt `pos:` and `bi:` | The atom's place and the previous atom's kind. Live only under `TILT` | sampler |
| `model/study/sampler/sample2_col.py:1591-1596,:1998` `p_last` | The last atom's tokens, for the structural logits. Live only under `STRUCT_P=1` | sampler |
| `model/study/sampler/live.py:1328` `p_or` with `pri['compound']` | P(the k-th atom is an OR): a compound's place in the body | sampler |
| `model/study/sampler/live.py:621-622` `nest_first` | P(an OR is a branch's first atom) | sampler |
| `model/study/sampler/live_priors.py:319-337` `kinds`, `kinds1` | The next form's kind given the previous form's: a form's place in gold's text | sampler |
| `R/features_rel_data.py:17` and the rank record's `features_rel_walk.py`, class `Instr` | Not a fact: the pick's label and prefix come from gold's written walk, so every fact of the prefix is on written order's rows | features |

## Inherited through the offset

These read the steered prior, so each carries what the live steer reads.

| File and line | What it reads | Owner |
|---|---|---|
| `R/features_rel_data.py:25,:49-52` `lq`, `steer`, `rank`, `gap_top`, `der_rank`, `share_kind`, `entropy`, `top_q` | The steered weight, and functions of it | features |
| `R/features_perrel_lib.py:9-14,:100-104` the offset `q` | The steered prior as the model's start | features |
| `R/features_rel_data.py:94-99`, `EXTRA` ranks | Ranks broken by option place at ties, through a stable sort. Option place follows token number | features |

The live steer `relR4_o.pkl` holds 392 feature names, sets `b`, `ctx`, `dag`, `rk1a`, `rk1b`, `rk1c`, `rk2d`, `rk2e`, `rk2f`, `rk3o`, and more, on plugin `rk3_def.py`. `rk3o` restates the lexical features with no order, and the lexical ones are still among the names. `audit-live-steer-names.txt` lists the names the file holds that this table bans.

## Allowed, listed because the brief or the code might suggest otherwise

| File and line | What it reads | Why it stays |
|---|---|---|
| `R/features_rel_data.py:26,:78` `root2` | The pick sits under NOT, from `sample2_col.py:1043-1045` | A place in the atom tree. It isn't order, though the brief listed it |
| `R/features_rel_data.py:26,:77-78` `k`, `model/study/sampler/relfeat.py:129,:194,:200,:212` `c_k`, `k1`, `x:kk:*`, `relfit.py:57`, `rk1b.py:70,:85,:109`, `rk2d.py:209,:237`, `rk1a.py:172,:180` | Equal to the prefix's size plus 1. Allowed read as a size. Inside a walk it's the same number as the index, so a read that restores gold's order gets the index through it | Size of a prefix as a set |
| `R/features_rel_data.py:79-80` `ncmp`, `prefix_depth`, `nscope`, `uses`, `dead_join`, `own` | Counts and read-graph depth | Set and graph facts |
| `R/features_perrel_data.py:199` `prefix:<head>` | Heads of the prefix as a set | A set. Its rows still come from a written walk |
| `R/features_rel_content.py:172-214` `join_row`, `:217-233` `prefix_row`, `:20` `PREFIX`, `:19` `JOIN` | The table of the prefix as a join. No lexical read in this file | Set. Its prefix comes from the walk |
| `R/features_perrel_data.py:156-158` `rd`, `kept_reads`, `R/features_rel_data.py:26` `readers`, `depth`, `sibling`, `path` | Read-graph facts of a form | Graph facts |
| `model/study/feat_exp/features/dag_options.py:20-31` | Depth step and bases as a set | Graph facts |
| `model/study/sampler/live.py:1205,:1313-1322` the stop hazard by `k` | The count of atoms | A count |
| `model/study/sampler/sample2_col.py:1983-1994` P's relation weights `c['rel']`, `c['neg']` | A relation's count, with no place | The relation prior itself reads no order |
| `model/study/sampler/plugins/rk2/features/rk3o.py` | Written to be order-free | Set facts |
| `model/study/sampler/plugins/rk2/features/rk2e.py:170-177` `e1_idx`, `e1_first`, `e1_run_n`, `e1_from_end`, `e1_code` | An option's place among one form's slots, which is the registry's order of a component's ports | Not gold's text. Slot numbers elsewhere are a form's place: `relfit.py:58` is banned for that |

## Limits of this audit

`model/study/feat_exp/` was searched by pattern for the atom index, first atom, last atom and prefix reads, and no hit there reads atom order: the hits in `features/r4l.py` and `features/q5_split_filters.py` enumerate columns or unordered pairs. Its 80 feature files weren't read line by line. `rk1a.py`'s use of the index past `_parse_prefix` wasn't traced to each feature.
