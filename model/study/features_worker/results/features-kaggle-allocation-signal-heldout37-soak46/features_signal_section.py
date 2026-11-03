#!/usr/bin/env python
"""Writes the results section from the read and recount files of this folder, and adds the result to manifest.json. The prediction field stays as it is.

  features_signal_section.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(HERE + '/signal-read-round50.json'))
O = json.load(open(HERE + '/signal-read-census-refit-8a5ffec60.json'))
D = json.load(open(HERE + '/signal-read-round50-drop-undrawable.json'))
X = json.load(open(HERE + '/repair-recount-round50.json'))
X2 = json.load(open(HERE + '/repair-recount-census-refit-8a5ffec60.json'))
CUTS = '60', '300', '600'
OBS = 'nodes', 'forms', 'proposals', 'best_out', 'shape_forms'
NAME = dict(nodes='Nodes', forms='Forms', proposals='Proposals', best_out='Best OUT gain', shape_forms='Forms of the output shape', joint='Joint, cross-fit', area='Grid area, smaller first', same_size='Outputs keep the input size')
NAME['covered (needs gold)'] = 'Forms covered, needs gold, reference'
POOL = 'pooled, arms with tables'
S37 = '37 held, search arms with tables (job 23, gate)'
S46 = '46: Kaggle version 5 and soak, tasks with a target'
SC = '37 held, every search arm, cheap observables'
ARM = {'job23 control_search': 'Job 23 control', 'job23 factored_search': 'Job 23 factored', 'gate control_search': 'Gate control', 'gate gate_search': 'Gate', 'context control': 'Context control', 'context context_cover': 'Context cover', 'job17 search': 'Job 17 search', 'job17 draws': 'Job 17 sampling', 'kaggle-v5 draws': 'Kaggle version 5, sampling', 'soak search': 'Soak, search', 'soak draws': 'Soak, sampling'}
LABEL = dict(nodes='nodes', forms='forms', proposals='proposals', best_out='best OUT', shape_forms='shape')


def f(x):
    s = f'{abs(x):.2f}'
    s = s[1:] if s.startswith('0') else s
    return ('-' if x < 0 and s != '.00' else '') + s


def ci(v):
    return f'{f(v[0])} ({f(v[1])} to {f(v[2])})' if v and v[0] is not None and v[1] is not None else (f(v[0]) if v and v[0] is not None else 'none')


def p(v):
    return f(v[0]) if v and v[0] is not None else 'none'


def best(c, obs=OBS):
    return max(((c[o]['auc_third'][0], o) for o in obs if o in c and c[o].get('auc_third')), default=None)


def row(name):
    o = R['sets'][name]['cuts']
    h = R['sets'][name]['header']
    out = []
    for S in CUTS:
        b = best(o[S])
        ref = o[S].get('covered (needs gold)')
        out.append(f"{LABEL[b[1]]} {ci(o[S][b[1]]['auc_third'])}; joint {ci(o[S]['joint']['auc_third'])}; area {p(o[S]['area']['auc_third'])}; covered {p(ref['auc_third']) if ref else 'none'}")
    return h, out


L = []
L.append('### Allocation signal\n')
L.append('Whether pool observables that read no gold and no test output tell how close a task is to a candidate, at a time that the kernel can spend on a task. Read 2026-11-01, 08:40 EST. Run folder: `features-kaggle-allocation-signal-heldout37-soak46/`, with `manifest.json`.\n')
L.append('- Target: census of `gold-v3-rigid-round50`, as the ast corpus of gen-v3 holds it, parents context, priors that leave out the 99 evaluation tasks, sampler 8a5ffec60. 79 tasks: the 37 held tasks and 42 evaluation tasks of the pool reads. 1,554 forms, 1,516 valid. The census has no row for 4 forms, of kinds with no walk.')
L.append('- Forms with no bits: 38 forms that aren\'t valid, 25 of them with a RIGID_DET or CHOOSE form in scope, which the walk can\'t replay, and the 4 forms with no walk, on 14 tasks. Such a task ranks above every task on total bits and is negative on each binary target.')
L.append('- Observables: nodes, forms, proposals, the best `gain` of `outfeat.py` over nodes, and forms with a Position column that gives exactly the output grid\'s cells on every train pair. Forms covered needs gold, so it is a reference column and it isn\'t in a joint score.')
L.append('- Cut at S seconds: in events, the visits to S give the proposals and the forms, and nodes count to that draw. In worker logs, the last line at or before S, about every 12 s, gives the counts, and nodes count to that number in record order. The clock of a log adds the time before each renewal.')
L.append('- Joint: logistic regression on within-arm ranks, 5 task folds, 5 repeats. Its weights are fit on held tasks by cross-fit, and weights for the kernel must be refit on non-held tasks.')
L.append('- A pooled read compares tasks inside an arm, gives each task weight 1 over its arms, and takes a 95% task bootstrap of 2,000 draws.\n')
L.append('Time on the kernel, by [Proposal rate on Kaggle](#proposal-rate-on-kaggle): 1 pod CPU s is 1.3 to 1.7 Kaggle CPU s, and a Kaggle worker gets .90 of a CPU, so 1 pod s is 1.4 to 1.9 Kaggle wall s.\n')
L.append('| Pod s | Kaggle wall minutes |')
L.append('|---|---|')
L.append('| 60 | 1.4 to 1.9 |')
L.append('| 300 | 7.2 to 9.4 |')
L.append('| 600 | 14.4 to 18.9 |\n')
L.append('The 300 s and 600 s cuts stand inside 5 to 20 minutes, 600 s nearest 20 minutes and 300 s nearest 5 minutes. Kaggle version 5 ran on Kaggle, so its cuts are 1, 5 and 10 Kaggle minutes, on sampling. No record ran search on Kaggle.\n')
L.append('Gold\'s worst form under 25 bits: 0 positive tasks, 79 negative. Each of the census row sets on the 37 also gives 0 positive tasks. No AUC on that bar exists. The tables read a substitute target: worst form at or under %.2f bits, the lowest third of the 65 tasks with every form drawable.\n' % R['third_bar'])
h = R['sets'][POOL]['header']
L.append(f"Pooled, arms with tables, {h['tasks']} tasks, {h['rows']} rows, {h['arms']} arms, {h['low_third_pos']} positive and {h['low_third_neg']} negative on the substitute. Each cell gives the Spearman correlation with total bits, then the AUC. A negative correlation means more of the observable, fewer bits.\n")
L.append('| Observable | ' + ' | '.join(f'{S} s' for S in CUTS) + ' |')
L.append('|---|---|---|---|')
o = R['sets'][POOL]['cuts']
for n in OBS + ('joint', 'area', 'same_size', 'covered (needs gold)'):
    L.append(f'| {NAME[n]} | ' + ' | '.join(f"{ci(o[S][n]['rho'])}; {ci(o[S][n]['auc_third'])}" for S in CUTS) + ' |')
L.append('\nBy read, AUC on the substitute. "Best" is the largest of the five no-gold observables at that time. Intervals are task bootstraps.\n')
L.append('| Read | Tasks, positive, negative | ' + ' | '.join(f'{S} s' for S in CUTS) + ' |')
L.append('|---|---|---|---|---|')
for name, label in ((S37, '37 held, job 23 and gate search arms'), (S46, 'The 46: Kaggle version 5 and the soak, tasks with a target'), (POOL, 'Pooled')):
    h, cells = row(name)
    L.append(f"| {label} | {h['tasks']}, {h['low_third_pos']}, {h['low_third_neg']} | " + ' | '.join(cells) + ' |')
o = R['sets'][SC]['cuts']; h = R['sets'][SC]['header']
L.append(f"| 37 held, 7 search arms, nodes, forms and proposals only | {h['tasks']}, {h['low_third_pos']}, {h['low_third_neg']} | " + ' | '.join(f"{LABEL[best(o[S], ('nodes', 'forms', 'proposals'))[1]]} {ci(o[S][best(o[S], ('nodes', 'forms', 'proposals'))[1]]['auc_third'])}; joint {ci(o[S]['joint']['auc_third'])}; area {p(o[S]['area']['auc_third'])}; covered {p(o[S]['covered (needs gold)']['auc_third'])}" for S in CUTS) + ' |')
L.append('\nBy arm, AUC on the substitute. An arm with no node records has the three cheap observables. A joint value under .5 means that no signal stays under cross-fit. Every run reached its cuts unless noted below.\n')
L.append('| Arm | Tasks, positive, negative | Best at 60 s | Best at 300 s | Best at 600 s | Joint at 600 s | Covered at 600 s |')
L.append('|---|---|---|---|---|---|---|')
for k, label in ARM.items():
    v = R['arms'][k]; h = v['header']; c = v['cuts']
    cells = []
    for S in CUTS:
        b = best(c[S])
        cells.append(f'{LABEL[b[1]]} {f(b[0])}' if b else 'none')
    ref = c['600'].get('covered (needs gold)')
    L.append(f"| {label} | {h['tasks']}, {h['low_third_pos']}, {h['low_third_neg']} | {cells[0]} | {cells[1]} | {cells[2]} | {p(c['600']['joint'].get('auc_third'))} | {p(ref['auc_third']) if ref else 'none'} |")
L.append('\nCall against the bar of AUC .7 on a no-gold observable: it fails. On the 25-bit target no AUC exists. On the substitute, the pooled best no-gold observable reads .62 at 60 s, .64 at 300 s and .62 at 600 s, each interval crosses .5, and the joint score reads .49, .48 and .53. Forms covered, which needs gold, reads .66 at 300 s. Grid area reads .52, so grid size doesn\'t explain the signal, and there is little signal to explain. No allocation score for the kernel comes from these observables.\n')
oo = O['sets'][POOL]['cuts']; dd = D['sets'][POOL]['cuts']
L.append(f"- Rank correlation with total bits: the best no-gold pooled value is forms of the output shape, {f(R['sets'][POOL]['cuts']['60']['shape_forms']['rho'][0])} at 60 s and {f(R['sets'][POOL]['cuts']['600']['shape_forms']['rho'][0])} at 600 s.")
L.append(f"- Gold revision moves the read. On census `sampler-census-refit-heldout37-8a5ffec60`, its gold and the same 79 tasks, forms of the output shape read {p(oo['60']['shape_forms']['auc_third'])}, {p(oo['300']['shape_forms']['auc_third'])} and {p(oo['600']['shape_forms']['auc_third'])}, and joint {p(oo['60']['joint']['auc_third'])}, {p(oo['300']['joint']['auc_third'])} and {p(oo['600']['joint']['auc_third'])}, with its own bar of {O['third_bar']:.2f} bits and 300 bootstrap draws. A shift of .10 at 22 positive tasks means a read near the bar isn't stable.")
L.append(f"- With the 14 undrawable tasks left out, 65 tasks, 22 positive, forms of the output shape read {p(dd['60']['shape_forms']['auc_third'])}, {p(dd['300']['shape_forms']['auc_third'])} and {p(dd['600']['shape_forms']['auc_third'])}, and joint {p(dd['60']['joint']['auc_third'])}, {p(dd['300']['joint']['auc_third'])} and {p(dd['600']['joint']['auc_third'])}.")
L.append('- Thin arms: the soak\'s sampling arm has 7 tasks and 2 positive, and its search arm has 8 tasks and 0 positive, so neither reads alone.')
L.append('- The soak is `kernel-soak-8a5ffec6`, 46 tasks. 31 of them have no target: training tasks, whose gold the priors hold, and evaluation tasks outside the 99. Its bundle\'s priors count every corpus task, so its pools aren\'t held out. The census bits are.')
L.append('- Kaggle version 5 has 45 of its 46 tasks read; 981571dc has no gold in the list. The manifest of its run names no priors, so its pools are not known to be held out.')
L.append('- The rows headed Kernel soak in [Gold helper rank by distance to OUT](#gold-helper-rank-by-distance-to-out) come from the records of Kaggle version 5, at about 1,196 s, and not from a soak of 1,800 s. The node counts match that record.')
L.append('- Run status: job 23 and the gate arms reached their 600 s deadline, with no crash. Context control and cover ran to 3,600 s, with 68 of 74 workers killed past their end. Job 17 ran to 3,600 s, with worker deaths on 3 sampling tasks. Kaggle version 5 ran 1,165 to 1,196 s. In the soak, 6 workers were killed past their end. One sampling task, 0607ce86, ended at 424 s, and it has no target.\n')
L.append('Recount with repairs. A form that a repair step finds costs no search bits, so it is set to 0 here, and each task\'s worst form is taken again. The 0 positive read above stands as it is: it is the census with no repair.\n')
L.append('| Repair | Tasks on the list | Of the 79 | Outside the 79 | Forms set to 0 |')
L.append('|---|---|---|---|---|')
L.append(f"| ONE repair, the `--one` set of `sampler-one-repair/check.sh` | {X['one_list']} | {len(X['one_in_read'])}: {', '.join(X['one_in_read'])} | {X['one_outside']} | 1 on each |")
L.append(f"| CHOOSE lift, commit 96f903721 | {X['choose_list']} | {len(X['choose_in_read'])} | {X['choose_outside']} | none |")
L.append('')
L.append('| Bar, bits | Before: every form drawable | After: every form drawable | After: over forms with bits |')
L.append('|---|---|---|---|')
for b in ('25', '28', '32'):
    L.append(f"| {b} | {X['before'][b]['every_form_drawable']} | {X['after'][b]['every_form_drawable']} | {X['after'][b]['forms_with_bits']} |")
L.append('')
L.append(f"- The lists name tasks and not forms. Rule for ONE: a form of a listed task whose text holds a `(ONE` mark. Rule for CHOOSE: a form of kind CHOOSE on a listed task. b7cb93ac is on both lists and outside the 79.")
L.append(f"- On the 2 tasks, the worst form doesn't change: 65.52 bits on 8e5c0c38 and 267.57 on f560132c. 8e5c0c38 has every form drawable after the recount, and f560132c keeps 1 undrawable form. Tasks with an undrawable form fall from {X['undrawable_tasks_before']} to {X['undrawable_tasks_after']}.")
L.append(f"- The lowest worst form on a task with every form drawable is {X['lowest_after'][0][0]:.2f} bits, on {X['lowest_after'][0][1]}, and {X2['lowest_after'][0][0]:.2f} bits on the earlier gold. The 1 task in the last column is 269e22fb, 18.38 bits, with 7 forms that have no bits.")
L.append('- A ONE repair adds marks to a form, and the search still draws the rest of that form, so 0 bits for the whole form is an upper limit on the gain. No count depends on it, because neither form is its task\'s worst form.')
L.append('- `sampler-one-drive.jsonl` has no trigger and no find on either task: gold without its marks passes its OUT test with an attempt on each test input. The 0 bits on these 2 forms is an assumption here, and no record of a find.')
L.append('- cbebaa4b has 2 CHOOSE forms and is not on the list, so they stay undrawable.')
with open(HERE + '/results-section-allocation-signal.md', 'w') as g:
    g.write('\n'.join(L) + '\n')

p_ = HERE + '/manifest.json'
m = json.load(open(p_))
pred = m['prediction']
m.update(
    command={
        'cuts and rows': 'features_signal_rows.py cheap signal-cheap.jsonl; features_signal_rows.py tables signal-tables.shardK.jsonl K 4, K 0 to 3',
        'census': 'SAMPLER_CODE=<extract of 8a5ffec60> SEARCH_GOLDS=points-round50.json SEARCH_MODELS=<sampler-priors-refit-heldout-8a5ffec60> features_census.py census-round50-tasks.txt census-round50-parents.shardK.jsonl K 2, K 0 and 1',
        'target': 'GOLD_POINTS=points-round50.json features_targets.py NAME target-census-round50.jsonl census-round50-parents.shard0.jsonl census-round50-parents.shard1.jsonl',
        'read': 'features_signal_read.py target-census-round50.jsonl signal-read-round50.json',
        'swap the target to a later gold': 'features_targets.py NAME TARGET.jsonl CENSUS.jsonl, then features_signal_read.py TARGET.jsonl OUT.json',
        'repair recount': 'features_repair_recount.py repair-recount-round50.json census-round50-tasks.txt points-round50.json census-round50-parents.shard0.jsonl census-round50-parents.shard1.jsonl',
        'section': 'features_signal_section.py',
    },
    commit={'reads': 'worktree at 118556b5f; the scripts here are not committed', 'census walk': '8a5ffec60, extract of model/study and src, with study_paths_census.py in place of model/study/study_paths.py so that it reads the main checkout\'s data; its totals match the existing census on the two forms tried'},
    task_set={
        '37 held': 'held/tasks.txt, with job 23 on 35 of them',
        'the 46': 'kernel-soak-8a5ffec6-linux-23eval-23training-1800s, 15 tasks with a target, 8 on search and 7 on sampling; runs/kaggle-v5, 45 of 46 tasks with a target, on sampling',
        'pooled': '79 tasks: a task in more than one set counts once',
        'held-out status': 'the census leaves out the 99 evaluation tasks, so bits are held on all 79. The pools of job 23, gate, context and job 17 leave them out. The soak\'s priors count every corpus task, and Kaggle version 5\'s priors are not stated in a manifest.',
        'left out': '31 soak tasks with no target: training tasks and evaluation tasks outside the 99; 981571dc of Kaggle version 5',
    },
    budget={'cuts': '60, 300 and 600 s of wall time per task', 'runs': 'job 23 and gate 600 s, context and job 17 3,600 s, soak 1,174 s of a 1,800 s supervisor, Kaggle version 5 1,196 s'},
    measures=['Spearman rank correlation with total bits', 'AUC for worst form under 25 bits: no positive task', 'AUC for worst form in the lowest third, a substitute target', '95% task bootstrap, 2,000 draws'],
    gold_revision={
        'read': 'gold-v3-rigid-round50, gold_sexp of gold/gen-v3-11f6a212c/ast-corpus, which each round overlays; points-round50.json',
        'difference from corpus/gen': 'forms of the ast corpus and of corpus/gen/<task>.arclog differ in kind counts on 58 of 79 tasks; on the task checked, the text has one RULE more that the ast corpus leaves out',
        'pending': 'gold-v3-cheapest-round50: swap by the command above',
        'sensitivity': 'sampler-census-refit-heldout37-8a5ffec60 and its gold, with census-extra-parents.shard0.jsonl and shard1 for the 42 other tasks',
    },
    wheel_engine={'census walk': {'commit': 'not known: the venv build of 2026-10-31 14:09', 'sha256': '7ff1dc490c04c383ad05a8b2a18c87e8be0d94f6980ba089a66ecf42f5d24a89', 'file': 'ast/run/runtime-kaggle-py313/venv arclog.abi3.so', 'machine': 'Mac'}, 'pool reads': 'no engine ran; saved records only'},
    machine={'pod second': '1 pod CPU s is 1.3 to 1.7 Kaggle CPU s, and 1.4 to 1.9 Kaggle wall s at a .90 share', 'cut nearest 5 to 20 minutes': '300 s is 7.2 to 9.4 Kaggle minutes and 600 s is 14.4 to 18.9', 'Kaggle version 5': 'its cuts are Kaggle wall seconds, on sampling'},
    training_eligible='no: this folder keeps counts per task and no node records',
    end='2026-11-01T08:42 EST',
    result={
        'call': 'fails the bar. Worst form under 25 bits has 0 positive tasks of 79, so no AUC exists. On the substitute, pooled best no-gold AUC is .62, .64, .62 at 60, 300, 600 s; joint .49, .48, .53; grid area .52; forms covered, needs gold, .52, .66, .65',
        'files': 'signal-read-round50.json, signal-tables-round50.md, results-section-allocation-signal.md, repair-recount-round50.json',
        'prediction_check': 'The band of .55 to .65 held at 300 s and 600 s on the substitute, except best OUT gain at 300 s, .50; at 60 s three observables read .47 to .54. Joint about .65 at 300 s did not hold: .48. Spearman -.3 at best held: -.26 pooled. Forms covered about .75 did not hold: .66. Pool size and proposals did not track grid size: grid area .52. AUC rises by less than .05 from 60 s to 600 s held for 4 of 5 observables; best OUT gain rises .14.',
        'partial_note': 'partial.md read the census at 8a5ffec60. Forms of the output shape read .72 at 300 s there and .62 here at the round 50 census.',
        'repair_recount': {'one': '2 of 79, 13 outside', 'choose': '0 of 79, 11 outside', 'under 25, 28, 32 bits': '0, 0, 0 with every form drawable; 1, 1, 1 over forms with bits, which is 269e22fb'},
    })
m['prediction'] = pred
with open(p_ + '.new', 'w') as g:
    json.dump(m, g, indent=1)
os.replace(p_ + '.new', p_)
print('\n'.join(L))
