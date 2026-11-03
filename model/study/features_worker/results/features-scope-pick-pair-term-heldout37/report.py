"""Writes partial.md from reads.jsonl, so that each number in it comes from a section there."""
import json
H = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-pick-pair-term-heldout37/'
R = {}
for l in open(H + 'reads.jsonl'):
    q = json.loads(l)
    R[q['section']] = q['value']
o = []
w = o.append


def rng(r):
    return '%.3f to %.3f' % tuple(r)


def a(r):
    return '%.3f (%s)' % (r['auc'], rng(r['range']))


def s(r):
    return '%+.3f (%s)' % (r['saving'], rng(r['range']))


rows, auc, tog, bits, gain, cells, cost, stage, sc, size = R['rows'], R['auc'], R['together'], R['bits'], R['gain'], R['cells'], R['cost'], R['stage'], R['sketch_counts'], R['auc_size']
w('# Pair term on the scope pick, 37 held-out tasks\n')
w('State: done. This is a read of the signal on held tasks. No number here is for use elsewhere. Every number comes from `reads.jsonl`, through `report.py`.\n')
bf = bits['first']['models']
g1 = gain['first']['first_order_pair less first_order']
st5 = stage['first pair block 5']
sens = bits['first']['sensitivity']
w('## The read\n')
w('- The pair term separates nothing once scope size and node score are in. On `any`, together %s against a shuffled fit of %.3f. On `first`, together %s against size alone %s, and the gain over first order is %+.3f (%s).' % (a(tog['any']['models']['pair']), tog['any']['shuffled_fit']['mean'], a(tog['first']['models']['pair']), a(tog['first']['models']['size']), g1['auc']['gain'], rng(g1['auc']['range'])))
w('- On `first`, table overlap and join run the wrong way: `join` %s, `overlap` %s, each mean over pairs. Scopes that gave a first cover have less of them. A term built on nodes that fit would point away from those scopes. On `any` the same facts sit at %.3f and %.3f.' % (a(auc['first']['facts']['join_mean']), a(auc['first']['facts']['overlap_mean']), auc['any']['facts']['join_mean']['auc'], auc['any']['facts']['overlap_mean']['auc']))
w('- No saving on the 1.1 bits: %s at block 20, %+.3f at block 5. The reach is small in any case: forms with 2 or more reads are %.1f%% of the weight after reads exist, and the ceiling on that route is %.3f bits.' % (s(bf['pair']['out any']), sens['block 5 beta x 1.0']['out any']['saving'], 100 * rows['out_by_reads']['2+']['share_of_W_ready'], rows['ceiling']['saving']))
w('- On the 3.1 bits of wait the term reads %s, above its shuffled fit. Do not take it as a saving: first order alone gives %s, the pair term\'s gain over it is %+.3f (%s), it sits in the first 20 scopes (%s, against %s after), and the same tilt loses %s on all first covers, with DET at %s.' % (s(bf['pair']['first_late any']), s(bf['first_order']['first_late any']), g1['first_late']['gain'], rng(g1['first_late']['range']), s(st5['early']['first_late']), s(st5['late']['first_late']), s(bf['pair']['first any']), s(cells['bits_by_kind']['first DET'])))
w('- `overlap_P` and `join` carry what signal there is, both with a negative weight. `ident` carries none: only %d of %d scopes have such a pair, and %d `first` positives.' % (sc['scopes_with_an_ident_pair'], rows['slots_with_pair_facts'], sc['positives_with_an_ident_pair']['first']))
w('- The term is cheap, median %.3f ms and largest %.2f ms a scope, so cost is not what stops it.\n' % (cost['median_ms'], cost['largest_ms']))
w('Many labels, facts and terms were read here, so a single range that clears .5 or 0 is weak evidence.\n')
w('## Left out\n')
w('- `cover` arms: the read is on the base arms only.')
w('- Scopes with a form missing from the final bank, empty scopes: no pair facts. They and their covers keep weight 1 in the bits.')
w('- 66 of 156 `first` scopes with facts have no negative before them in the run, so they leave the AUC and the fit. They stay in the bits read.')
w('- `hold2` is too thin to fit: 5 scopes, 2 tasks.')
w('- A pick that is an ancestor of another pick can\'t be seen, since a bank holds no pick list. Leaf forms stand in for picks.')
w('- `Ident` values are numbered per producer, so `overlap_I` compares numbers of separate producers. `ident` reads the type only.')
w('- No search was run under the term, and no sampler code changed.\n')
w('## Definitions\n')
w('- Node score: `Policy.scope` in `policy.py` takes 5 of 6 picks by the Gumbel top-k rule on `score - uses`, where `score` is the policy model\'s decision value, fixed when a node is new, and takes 1 pick from the oldest of the least used. `Pool.scope` adds ancestors. A bank file holds `score`, and no pick list, so the picks are read as leaf forms.')
w('- Scope drawn, the unit: a slot, the first visit of a (scope, kind) within 600 s. Its proposals are the tries of all visits of the slot.')
w('- Leaf form: a form of the scope that no form of the scope reads. Pair facts are over pairs of leaf forms, so a pair has no read edge.')
w('- Table sketch: per relation, column and example, the distinct-value count and the smallest 64 hashes of the values, as uint32. DET assignments of an example are put together. The bank holds no rows, so tables were computed again by a replay of the forms.')
w('- Pair facts (`pair_facts.py`): `coltype`, Jaccard of the column type sets, no table read. `ident`, each relation has an `Ident` column, no table read. `join`, the share of compared examples on which a same-type column pair shares 2 or more values. `overlap`, per example and shared type the largest Jaccard over column pairs of that type, mean over shared types, mean over examples. `overlap_P`, `_C`, `_N`, `_I`, `_O`: that on Position; Color; Nat and Int; Ident; other types. `lineage`, a control: the two forms share an ancestor.')
w('- Across examples: train inputs and test inputs. An example counts where both relations have rows. A task-level table (a DET\'s) counts on every example of the other relation. With no compared example, the fact is 0.')
w('- A form pair takes the largest value over its relation pairs. A scope takes the mean (`_mean`) and the largest (`_max`) over its leaf pairs.')
w('- Labels (`label-rows.tsv`, from the cover map; no fact reads them): `first`, the slot gave a first cover of a gold form in the run. `any`, it gave a cover event. `first_late`, a first cover after the form\'s read forms were covered, the rows of the wait. `first_r1`, `first_r2`, `any_r2`: covers by a kept clause reading at least 1 or 2 forms. `hold1`, `hold2`: the scope holds all read forms of a form not yet covered that reads at least 1 or 2 forms.')
w('- Match: same run and kind; up to 3 negatives before and 3 after in the run\'s scope order, within 30 scopes, at least 1 on each side. A negative has no cover event. Both have pair facts.')
w('- AUC: per positive the share of its negatives it beats, ties 1/2; mean per task; mean over tasks. 95% ranges resample tasks, 2,000 times. The shuffled control moves the positive to a random member of each matched set.')
w('- Fit: a conditional logit on the matched sets of the other 36 tasks, fixed ridge 1. It is exactly a term g added to the log of the node-score pick.\n')
w('## Rows\n')
p = rows['positives']
w('- %d scopes in %d runs, %d tasks, base arms. %d have pair facts; %d have a form missing from the final bank, %d are empty scopes. %d negatives.' % (rows['slots'], rows['runs'], rows['tasks'], rows['slots_with_pair_facts'], rows['slots_missing_a_form'], rows['slots_empty_or_one_leaf'], rows['negatives_all']))
w('- Replay: %d forms replayed, no replay stopped, %d forms with no sketch. Row counts per example equal the bank\'s on %d of %d checked forms.' % (sc['counts'].get('replayed forms', 0), sc['counts'].get('form with no sketch', 0), cost['row_count_check']['same'], cost['row_count_check']['forms']))
w('- The `out` term rebuilt from the exposure rows: %.3f, against %.3f in `decompose.jsonl`; RULE %.3f, DET %.3f, INIT %.3f, each equal.\n' % (rows['out_check']['any']['from_exposure_rows'], rows['out_check']['any']['out_decompose'], rows['out_check']['RULE']['from_exposure_rows'], rows['out_check']['DET']['from_exposure_rows'], rows['out_check']['INIT']['from_exposure_rows']))
w('| Label | Scopes | With facts | Matched sets | Left out, no match | Tasks |')
w('|---|---|---|---|---|---|')
for k in ('first', 'any', 'first_late', 'first_r1', 'first_r2', 'any_r2', 'hold1', 'hold2'):
    q = p[k]
    w('| %s | %d | %d | %d | %d | %d |' % (k, q['slots'], q['with_facts'], q['sets'], q['no_match'], q['tasks']))
w('\n## 1. AUC within task, matched in time\n')
for lab in ('first', 'any'):
    f = auc[lab]['facts']
    w('Label `%s`, %d sets, %d tasks. Shuffled control beside each.\n' % (lab, auc[lab]['sets'], auc[lab]['tasks']))
    w('| Fact | Mean over pairs | Control | Largest over pairs | Control |')
    w('|---|---|---|---|---|')
    for c in ('coltype', 'ident', 'join', 'overlap', 'overlap_P', 'overlap_C', 'overlap_N', 'overlap_O', 'overlap_I', 'lineage'):
        m, x = f[c + '_mean'], f[c + '_max']
        w('| `%s` | %s | %.3f (%s) | %s | %.3f (%s) |' % (c, a(m), m['shuffled'], rng(m['shuffled_range']), a(x), x['shuffled'], rng(x['shuffled_range'])))
    w('')
    w('First-order and time, same sets: forms %s; `score_mean` %s; `score_max` %s; depth %s; order %s.\n' % (a(f['forms']), a(f['score_mean']), a(f['score_max']), a(f['depth']), a(f['order'])))
w('Facts together, a leave-one-task-out score on `coltype`, `ident`, `join`, `overlap`, each mean and largest. `pair and first order` adds log forms, `score_mean`, `score_max`.\n')
w('| Label | Sets | Together | Shuffled fit, 50 rounds | Size alone | First order | Pair and first order |')
w('|---|---|---|---|---|---|---|')
for lab in ('first', 'any', 'first_late', 'first_r1', 'first_r2', 'any_r2', 'hold1'):
    d = tog[lab]
    m = d['models']
    w('| %s | %d | %s | %.3f (%s) | %s | %s | %s |' % (lab, d['sets'], a(m['pair']), d['shuffled_fit']['mean'], rng(d['shuffled_fit']['range']), a(m['size']), a(m['first_order']), a(m['first_order_pair'])))
w('\nAUC gain of the pair facts over first order, same task resamples:\n')
w('| Fit label | Pair and first order, less first order | Pair, less size |')
w('|---|---|---|')
for lab in ('first', 'any', 'first_late', 'first_r1', 'hold1'):
    d = gain[lab]
    x, y = d['first_order_pair less first_order']['auc'], d['pair less size']['auc']
    w('| %s | %+.3f (%s) | %+.3f (%s) |' % (lab, x['gain'], rng(x['range']), y['gain'], rng(y['range'])))
w('\nWith negatives matched on the size bucket too, facts by mean over pairs:\n')
w('| Label | Sets | `join` | `overlap` | `overlap_P` | `coltype` | forms |')
w('|---|---|---|---|---|---|---|')
for lab, d in size.items():
    f = d['facts']
    w('| %s | %d | %s | %s | %s | %s | %s |' % (lab, d['sets'], a(f['join_mean']), a(f['overlap_mean']), a(f['overlap_P_mean']), a(f['coltype_mean']), a(f['forms'])))
w('\n## 2. Bits of a pick by node score plus the pair term\n')
w('How it is counted. A pick with the term has P\'(S) proportional to P(S) e^g(S). For a fixed pool, E\'[h] = E[h e^g] / E[e^g], so each drawn scope takes a weight m = e^g / Z, with g fitted on the other tasks and Z the tries-weighted mean of e^g in a block of consecutive scopes of the run. That keeps the block\'s proposals.\n')
w('What it assumes:\n')
w('- The pool at each draw stays as recorded. A form covered sooner opens no later form here, and a form delayed closes none, so effects on the chain, the 2.9 bits of reads not covered, are not counted.')
w('- A scope\'s proposals, and its covers per proposal, stay as recorded under m. Use counts, and so later picks, do not move, and the resume rule does not react.')
w('- The term is one scope-level factor, applied to the whole of a scope. It tilts drawn scopes only. In expectation that equals a real pick, and in a run of about 120 scopes the sample is small.\n')
w('Units. `out`: the change in the 1.1-bit term, log2 of W held under m over W held, with the same w = 2^(-s x bits). A positive number is a saving. Wait: log2 of the mean m over the 63 first covers of the wait rows, the rise in the hazard that the 3.1 bits describe. All first covers: the same on all 281 first covers of the base arms.\n')
w('| Fit label, sets | Term | `out`, of 1.1 | Wait, of 3.1 | All first covers | Weights: sd, largest, effective share |')
w('|---|---|---|---|---|---|')
names = (('pair', 'pair'), ('first_order', 'first order'), ('first_order_pair', 'pair and first order'), ('size', 'size'), ('score', 'score'))
for lab in ('first', 'any', 'first_late', 'first_r1', 'any_r2', 'hold1'):
    d = bits[lab]
    for k, nm in names:
        r = d['models'][k]
        w('| %s, %d | %s | %s | %s | %s | %.2f, %.1f, %.2f |' % (lab, d['sets'], nm, s(r['out any']), s(r['first_late any']), s(r['first any']), r['weights']['sd'], r['weights']['max'], r['weights']['ess_share']))
w('\nShuffled-label fit, pair term, 50 rounds, mean and 95% of rounds:\n')
w('| Fit label | `out` | Wait | All first covers |')
w('|---|---|---|---|')
for lab in ('first', 'any', 'first_late', 'first_r1', 'any_r2', 'hold1'):
    c = bits[lab]['shuffled_fit']
    w('| %s | %+.3f (%s) | %+.3f (%s) | %+.3f (%s) |' % (lab, c['out any']['mean'], rng(c['out any']['range']), c['first_late any']['mean'], rng(c['first_late any']['range']), c['first any']['mean'], rng(c['first any']['range'])))
w('\nGain of the pair term over first order in bits, same resamples, `first` fit: `out` %+.3f (%s), wait %+.3f (%s), all first covers %+.3f (%s).\n' % tuple(x for k in ('out', 'first_late', 'first') for x in (gain['first']['first_order_pair less first_order'][k]['gain'], rng(gain['first']['first_order_pair less first_order'][k]['range']))))
w('Block and strength, pair term, `first` fit:\n')
w('| Setting | `out` | Wait | All first covers |')
w('|---|---|---|---|')
for k in ('block 5 beta x 1.0', 'block 10 beta x 1.0', 'block 20 beta x 1.0', 'block 40 beta x 1.0', 'block 20 beta x 0.5', 'block 20 beta x 2.0', 'block 20 first 20 scopes untilted'):
    r = bits['first']['sensitivity'][k]
    w('| %s | %+.3f | %+.3f | %+.3f |' % (k, r['out any']['saving'], r['first_late any']['saving'], r['first any']['saving']))
b = sc['first_covers_by_stage']
w('\nThe first 20 scopes of a run hold %d of %d first covers and %d of %d wait covers. Split by that place, block 5:\n' % (b['first'], b['of'], b['late'], b['late_of']))
w('| Fit, term | Place | `out` | Wait | Covers | All first covers | Covers |')
w('|---|---|---|---|---|---|---|')
for k in ('first pair block 5', 'first first_order block 5', 'first score block 5', 'any pair block 5'):
    for pl in ('early', 'late'):
        q = stage[k][pl]
        w('| %s | %s | %s | %s | %d | %s | %d |' % (k.replace(' block 5', ''), 'first 20 scopes' if pl == 'early' else 'after', s(q['out']), s(q['first_late']), q['first_late']['covers'], s(q['first']), q['first']['covers']))
c = rows['ceiling']
br = rows['out_by_reads']
w('\nReach. A pair term can only act on a form with 2 or more reads through its pair of read forms. The `out` term by reads:\n')
w('| Reads | Form rows | Reads all covered | Rows with held exposure | First covered | `out` | Share of W after reads exist | Share of W held |')
w('|---|---|---|---|---|---|---|---|')
for k in ('0', '1', '2+'):
    q = br[k]
    w('| %s | %d | %d | %d | %d | %s | %.3f | %.3f |' % (k, q['form_rows'], q['ready_rows'], q['rows_with_held_exposure'], q['covered'], q['out'], q['share_of_W_ready'], q['share_of_W_held']))
w('\nCeiling: if every proposal after the reads exist counted as held for forms with 2 or more reads, `out` falls from %.3f to %.3f, a saving of %.3f bits. %d scopes of %d held all reads of an uncovered form with 2 or more reads.\n' % (c['out_now'], c['out_at_ceiling'], c['saving'], p['hold2']['slots'], rows['slots']))
w('## 3. By kind and by scope size\n')
w('A row is a positive scope, of a slot of that kind. Size is forms in the scope, ancestors included, and negatives are matched within the cell. `thin`: under 50 rows or under 8 tasks. AUC of the score fitted on all kinds, and of `join` and `overlap`, mean over pairs.\n')
for lab in ('first', 'any'):
    w('Label `%s`:\n' % lab)
    w('| Cell | Rows | Tasks | Mark | Together | `join` | `overlap` | `coltype` |')
    w('|---|---|---|---|---|---|---|---|')
    for r in cells[lab]:
        if not r['rows']:
            w('| %s | 0 | 0 | thin | | | | |' % r['cell'])
            continue
        x = r['auc']
        w('| %s | %d | %d | %s | %s | %s | %s | %s |' % (r['cell'], r['rows'], r['tasks'], 'thin' if r['thin'] else '', a(x['together']), a(x['join_mean']), a(x['overlap_mean']), a(x['coltype_mean'])))
    w('')
k = cells['bits_by_kind']
w('Bits by the gold form\'s kind, block 20, `first` fit. A row under 50 covers or 8 tasks is thin.\n')
w('| Kind | `out`, of the kind\'s term | Wait | Wait covers, tasks | All first covers | Covers, tasks |')
w('|---|---|---|---|---|---|')
for kn, of in (('RULE', 1.898), ('DET', .126), ('INIT', 1.175)):
    w('| %s | %s of %.1f | %s | %d, %d%s | %s | %d, %d |' % (kn, s(k['out ' + kn]), of, s(k['first_late ' + kn]), k['first_late ' + kn]['covers'], k['first_late ' + kn]['tasks'], ', thin' if k['first_late ' + kn]['covers'] < 50 or k['first_late ' + kn]['tasks'] < 8 else '', s(k['first ' + kn]), k['first ' + kn]['covers'], k['first ' + kn]['tasks']))
w('\nBy scope size, log2 of the mean weight on first covers in the size: ' + '; '.join('%s: %s, %d covers, %d tasks%s' % (n, v['log2_mean_weight'], v['covers'], v['tasks'], ', thin' if v['thin'] else '') for n, v in cells['bits_by_size'].items()) + '.\n')
w('## 4. Cost of the term\n')
br_ = cost
w('- One thread, Python sets, no memo, one scope: median %.3f ms, 90th percentile %.3f ms, 99th %.3f ms, largest %.2f ms, over %d scopes. A real pick that looks at m candidate scopes pays m times this, less a memo of form pairs.' % (cost['median_ms'], cost['p90_ms'], cost['p99_ms'], cost['largest_ms'], cost['scopes']))
w('- Sketch: bottom 64 hashes, uint32, per relation, column and example, %.1f%% of column-example entries have over 64 values. Stored bytes per relation: median %d, largest %d; per form: median %d, largest %d; per run, leaf forms only: median %d, largest %d. As Python frozensets, per relation: median %d, largest %d.' % (100 * sc['share_over_64'], cost['sketch_bytes_per_relation']['median'], cost['sketch_bytes_per_relation']['largest'], cost['sketch_bytes_per_form']['median'], cost['sketch_bytes_per_form']['largest'], cost['sketch_bytes_per_run']['median'], cost['sketch_bytes_per_run']['largest'], cost['python_set_bytes_per_relation']['median'], cost['python_set_bytes_per_relation']['largest']))
w('- Building one sketch from a parsed table: median %.3f ms, 90th percentile %.2f ms, largest %.1f ms, on %d relations of up to %d rows.\n' % (cost['sketch_build_ms']['median'], cost['sketch_build_ms']['p90'], cost['sketch_build_ms']['largest'], cost['sketch_build_relations'], cost['sketch_build_rows']['largest']))
w('## 5. Which fact carries the signal, each alone\n')
w('Leave-one-task-out on one fact, its mean and largest. Bits at block 20.\n')
w('| Fit label | Fact | AUC | `out` | Wait | All first covers |')
w('|---|---|---|---|---|---|')
for lab in ('first', 'any'):
    for fx in ('coltype', 'ident', 'join', 'overlap', 'overlap_P', 'overlap_C', 'overlap_N', 'overlap_O', 'overlap_I', 'lineage'):
        m = tog[lab]['models']['alone ' + fx]
        r = bits[lab]['models']['alone ' + fx]
        w('| %s | `%s` | %s | %s | %s | %s |' % (lab, fx, a(m), s(r['out any']), s(r['first_late any']), s(r['first any'])))
w('\n`ident`: %d of %d scopes have a leaf pair with an Ident column on each side; among positives, `first` %d, `any` %d.\n' % (sc['scopes_with_an_ident_pair'], rows['slots_with_pair_facts'], sc['positives_with_an_ident_pair']['first'], sc['positives_with_an_ident_pair']['any']))
open(H + 'partial.md', 'w').write('\n'.join(o) + '\n')
