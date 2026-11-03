"""Writes results-section.md and the fields of manifest.json from the read files. The manifest's prediction stays as it is.

Held rows are read at the score and the bar that the non-held read chose.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
train = json.load(open(HERE + 'read-train.json'))
chosen = json.load(open(HERE + 'read-chosen-train.json'))
held = json.load(open(HERE + 'read-held.json'))
sweep = json.load(open(HERE + 'read-sweep.json'))
rows_held = [json.loads(x) for x in open(HERE + 'rows-held.jsonl')]
NAMES = {
    'base': 'Base form',
    's4': '4-connected',
    'm8': 'Multi-color component',
    'cs': 'All cells of one color',
    'win': 'Tight window',
    'free': 'Colors free',
    'embed': 'Cells anywhere in the output',
    'chg': 'Copy in changed cells',
    'across': 'Source in another pair',
    'task': 'Pose in no input of the task',
    'other': 'At least 2 poses in the pair',
    'several': 'At least 3 poses in the pair',
    'size3': 'At least 3 cells',
    'size6': 'At least 6 cells',
    'size8': 'At least 8 cells',
    'img2': 'At least 2 images',
    'img8': '8 images',
    'm8-free': 'Multi-color, colors free',
    'm8-chg': 'Multi-color, changed cells',
    'free-chg': 'Colors free, changed cells',
    'other-chg': '2 poses, changed cells',
    'free-other-chg': 'Colors free, 2 poses, changed cells',
    'm8-other-chg': 'Multi-color, 2 poses, changed cells',
    'several-free': '3 poses, colors free',
    'task-several': 'At least 3 poses in the task',
    'across-free-chg': 'Source in another pair, colors free, changed cells',
    'embed-chg': 'Cells anywhere, changed cells',
    'win-chg': 'Tight window, changed cells',
    'task-free-chg': 'Pose in no input of the task, colors free, changed cells',
    'sweep-best': 'Best of the grid: tight window, colors free, 8 images, changed cells, source in another pair, 2 poses',
}


def num(x, d=3):
    s = f'{x:.{d}f}'
    if s.startswith('0.'):
        return s[1:]
    return s


def rate(x):
    return '0' if x == 0 else '<.001' if x < .0005 else num(x)


def score_of(v, name):
    return dict(bool=v[0], pairs=v[2], size=v[3], share=(v[4] / v[5] if v[5] else 0))[name]


def held_cell(n):
    src = chosen['forms'][n]['pos']
    e = held['forms'][n]
    sc = src['score']
    cell = f"{e['rate']['positive'][0]}, {e['rate']['plain'][0]}; AUC {num(e['pos']['auc_' + sc])}; control {rate(e['control']['positive'])}, {rate(e['control']['plain'])}"
    return cell, sc


def bars(n):
    """Bits on held rows at each bar that the non-held read chose."""
    src = chosen['forms'][n]['pos']
    sc = src['score']
    out = {}
    pos = [r for r in rows_held if r['group'] == 'positive']
    neg = [r for r in rows_held if r['group'] == 'plain']
    base = len(pos) / (len(pos) + len(neg))
    for key in ('r5', 'r3'):
        if src[key] is None:
            out[key] = None
            continue
        bar = src[key][1]
        tp = sum(score_of(r['forms'][n], sc) >= bar for r in pos)
        fp = sum(score_of(r['forms'][n], sc) >= bar for r in neg)
        out[key] = dict(bar=bar, tp=tp, fp=fp, bits=None if not tp else round(math.log2(tp / (tp + fp) / base), 3))
    return out


lines = ['| Form | Positive, of 10 | One pose, of 8 | Looks posed, of 3 | Plain, of 978 | Same pose, positive and plain | AUC, 95% interval | Bits at recall .5 | Bits, best bar at recall .3 | Control, positive and plain | Held: positive of 2, plain of 35 |', '|---|---|---|---|---|---|---|---|---|---|---|']
order = list(train['forms']) + ['sweep-best']
for n in order:
    e = (chosen if n in chosen['forms'] else train)['forms'][n]
    p = e['pos']
    r = e['rate']
    auc = f"{num(p['auc_' + p['score']])} ({num(p['auc_ci'][0])} to {num(p['auc_ci'][1])})"
    r5 = 'no bar' if p['r5'] is None else f"{num(p['r5'][0], 2)} ({num(p['r5_ci'][0], 2)} to {num(p['r5_ci'][1], 2)})"
    r3 = 'no bar' if p['r3'] is None else f"{num(p['r3'][0], 2)} ({num(p['r3_ci'][0], 2)} to {num(p['r3_ci'][1], 2)})"
    h = held_cell(n)[0] if n in held['forms'] else ''
    lines.append(f"| {NAMES[n]} | {r['positive'][0]} | {r['one-pose'][0]} | {r['looks-posed'][0]} | {r['plain'][0]} | {e['same']['positive'][0]}, {e['same']['plain'][0]} | {auc} | {r5} | {r3} | {rate(e['control']['positive'])}, {rate(e['control']['plain'])} | {h} |")
table = '\n'.join(lines)
hb = {n: bars(n) for n in held['forms']}
print(json.dumps(hb))
sb = sweep['pos']
meta = train['meta']
text = f"""Whether a shape in a train input that reappears in a train output at another D4 pose says a task has a rigid assembly. The statistic reads train inputs, train outputs and test inputs. A task is positive where a case of its gold file, revision `gold-v3-rigid-round50`, has a `RIGID_DET` form. The non-held tasks hold 10 positive tasks with several poses, 9 of them with the form in the smallest case, and 8 with one pose, 5 of them with the form in the smallest case and 5 added at round 50. The 99 tasks of `held/leave_out.txt` are left out of the non-held read: its 37 held tasks are read once, for 4 forms, and the other 62, with 2 positive tasks among them, are not read. The 20 evaluation tasks outside that list are plain tasks. {meta['apart']} plain tasks whose output is or holds a D4 image of the whole input are set apart, and no positive task is among them. That leaves {meta['groups']['plain']} plain tasks and a base rate of {100 * meta['base_pos']:.1f}%. The base form is a single-color 8-connected component of at least 4 cells and at least 4 D4 images, colors kept, that the output of its pair holds at a pose the pair's input lacks. Each other row changes what its name says. AUC is positive against plain, at the highest of the boolean and three graded scores: share of pairs, largest shape, and classes hit over classes copied. Intervals are from a task bootstrap, and a resample with no bar counts as 0 bits. At 0 positive hits the interval has no width on the positive side: 0 of 10 allows a true rate up to .31. The control replaces each train output with an output of another plain task of the same size, {100 * meta['exact_donor']:.0f}% of them exact, mean of 5 draws. The sweep of all {2808:,} form combinations is a maximum over that grid: random labels give a higher best boolean AUC on {100 * sb['null_share']:.0f}% of 2,000 draws, with a median of {num(sb['null_auc'][0])}. On all 18 positive tasks, for single-color and multi-color components of at least 3 cells and 2 images with colors free, no train output has a component at a pose that the task's inputs lack. Of the 45 plain hits of the base form, 17 have same-size grids and also a copy of the shape at an input pose (6855a6e4, 845d6e51), 12 have same-size grids and an output with a symmetry the input lacks (b8825c91, 981571dc), 11 have an output smaller than the input (e78887d1, 0934a4d8), 2 have an output larger than the input (3cd86f4f), and 3 are others (0e206a2e). The gold of 23 of those 45 uses a D4 relation, against 7.6% of plain tasks. Of the tasks set apart, 6 hit the base form. The held rows hold 2 positive and 35 plain tasks, with the score of the non-held read. At the bars of the non-held read, on 1 of 2 positive tasks each, tight windows give {hb['win']['r3']['bits']:.2f} bits, and the best of the grid gives {num(hb['sweep-best']['r5']['bits'], 2)} bits at recall .5 and {hb['sweep-best']['r3']['bits']:.2f} at the best bar. Cost is {num(meta['ms_median'], 1)} ms median and {num(meta['ms_max'], 0)} ms at most per task for all forms in Python on the Mac, most of it tight windows. Run: `work/lm/data-study/features-worker/results/features-rigid-input-shape-posed-in-output-corpus`.

{table}

Call: no form is good enough to condition `RIGID_DET`'s prior. Exact components hit at most 2 of 10 positive tasks across the whole grid, tight windows hit 3 of 10 at the plain rate, and the form with the highest AUC stays at its control rate.
"""
open(HERE + 'results-section.md', 'w').write(text)
m = json.load(open(HERE + 'manifest.json'))
keep = m['prediction']
m.update({
    'command': 'features_labels.py; run_heavy.py --cpus 1 --need soon venv/bin/python features_shape_posed.py --shard i/3 --draws 5 rows-i.jsonl; features_sweep.py --shard i/3 sweep-i.jsonl; features_shape_posed.py --forms chosen-forms.json --draws 5 rows-chosen-train.jsonl; features_shape_posed.py --split held --forms chosen-forms.json --draws 5 rows-held.jsonl; features_read.py, features_sweep_read.py, features_cases.py, features_label_noise.py, features_write_record.py. Python and numpy from runtime-kaggle-py313.',
    'commit': 'f6fcad8df4d223dd94b607eafe3c30e889f91cca',
    'task_set': '1,044 non-held tasks: every task with gold outside held/leave_out.txt, the 99 evaluation tasks (arc-agi-2 evaluation.txt holds all 99). The 37 of held/tasks.txt are inside that list and are read once. The 62 others of that list are not read, with 2 positive and 1 looks-posed task. 21 evaluation tasks are outside the list: 20 are plain tasks here, and 20a9e565 has no gold. 4 tasks with no gold have no label.',
    'groups': 'labels.tsv. Positive 10, one-pose 8, looks-posed 3, plain 1,023, of which 45 are set apart. One-pose stems are the group of the grid read in features-rigid-instance-d4-fact-corpus-pool-seed1-ship7, all with the form at this revision. Held: positive 2 (269e22fb in the smallest case, 142ca369 not), plain 35.',
    'budget': '3 shards of 1 process, about 2 minutes for 29 forms and 5 control draws; the sweep of 2,808 forms in 3 shards of 1 process, about 1 minute.',
    'measures': 'read-train.json for all 29 fixed forms, read-sweep.json for the grid with a label null, read-chosen-train.json for the 4 forms chosen for held, read-held.json for the held rows, results-section.md for the table.',
    'chosen_for_held': 'base (reference), task-several (highest AUC of the fixed forms), win (the one fixed form with recall at least .3), sweep-best (highest AUC of the grid). All chosen on non-held tasks. read-held.json picks a score on held rows, so held_at_train_bar is the reading to use.',
    'held_at_train_bar': hb,
    'gold': 'gold-v3-rigid-round50, gen-v3-11f6a212c/corpus/gen',
    'engine': 'No engine ran. No pool, no engine and no gold enter the statistic: gold gives only the labels and the plain tasks that give control outputs.',
    'test_outputs': 'Dropped at load and never read.',
    'training_eligible': 'No model is fitted and no weight is set in a shipped model. Forms and bars were chosen on non-held tasks. The held rows were run once, for the chosen forms. The sweep and the check of D4 relations in plain gold came after the fixed forms were read.',
    'result': 'Fails. Best fixed form by AUC, at least 3 poses in the task: positive 1 of 10, one pose 0 of 8, looks posed 0 of 3, plain 42 of 978, AUC .530 (.474 to .633), no bar at recall .5 or .3, control 0 and .003, held 0 of 2 and 1 of 35. Tight window: 3 of 10 against 314 of 978, AUC .498, .23 bits at recall .3, held 2 of 2 and 25 of 35. Best of 2,808 forms: 5 of 10 against 221 of 978, AUC .645 by pairs, control .48 and .42, and random labels beat its boolean AUC on 64% of draws. No train output of the 18 positive tasks has a component at a pose that the inputs lack. The prediction missed: 60% against 20%, AUC .68 and 1.2 bits did not occur on a form that clears its control. One-pose tasks are lower than several-pose tasks on the forms that hit any positive task, on few tasks. Tasks that turn or flip the whole grid are not the largest false hit: 6 of 45 hit the base form, and same-size tasks that keep a shape in place are the largest kind, 17 of 45 plain hits.',
    'side_finding': '23 of the 45 plain hits of the base form have gold with a D4 relation (d4_, c4_ or a :D4 column), against 74 of 978 plain tasks, 2.75 bits. The match on the gold text is broad, and it was read after the forms. The statistic follows hand-written D4 use in gold more than RIGID_DET.',
    'not_read': 'One-pose stems are taken from the earlier group file, not derived again here. Shapes over 150 cells, windows past 400 per size per input grid, and more than the 60 largest classes for the embed match are cut. Assemblies whose parts are not components or tight windows of 3 to 5 cells are out of the statistic.',
    'write_location': 'Written under the scratchpad record folder as the coordinator directed. labels.tsv and features_labels.py were written into the work/ run folder before that direction and stay there.',
})
assert m['prediction'] == keep
json.dump(m, open(HERE + 'manifest.json', 'w'), indent=1)
print(text[:400])
