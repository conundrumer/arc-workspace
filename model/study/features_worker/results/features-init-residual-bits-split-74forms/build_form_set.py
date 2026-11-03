"""Builds form-set.jsonl: the forms whose most costly form in rewrite-by-form-copy.json is an (INIT at 25 bits or more, with the trial row and the census text each one needs.

  python3 build_form_set.py

One row per form, not-held rows first. Stdlib only. Run once: rewrite-by-form-copy.json is the copy of the file at the start of this job, and the trial rows are copied here so that a later row in the live files changes nothing.
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
ROOT = '/Users/davidlu/code/arc-workspace/'
ANATOMY = ROOT + 'work/lm/data-study/gold/form-anatomy-top-tenth/'
TEXTS = ROOT + 'work/lm/data-study/census/census-bands-cheapest/texts.json'
HELD = ROOT + 'work/lm/data-study/sampler/sampler-worker/held/tasks.txt'
BAR = 25


def main():
    by_form = json.load(open(HERE + 'rewrite-by-form-copy.json'))
    held = set(open(HELD).read().split())
    stems = json.load(open(TEXTS))['stems']
    groups = {(r['task'], r['form']): r['group'] for r in map(json.loads, open(ANATOMY + 'forms.jsonl'))}
    trials = {}
    for step in sorted({e['step'] for e in by_form.values()}):
        for line in open(ANATOMY + step):
            try:
                t = json.loads(line)
            except json.JSONDecodeError:  # a live file's last line, part written
                continue
            trials[step, t['task'], t['replace'][0][0]] = t
    rows, kinds = [], collections.Counter()
    for key, e in by_form.items():
        task, form = key.split()
        form = int(form)
        read = [(k, f) for k, f in enumerate(e['forms']) if f[0] is not None]
        if not read:
            kinds['no form read'] += 1
            continue
        k, worst = max(read, key=lambda x: x[1][0])  # the first of equal ones, as max gives
        kinds[worst[1].split()[0].lstrip('(')] += 1
        if not (worst[1].startswith('(INIT') and worst[0] >= BAR):
            continue
        t = trials[e['step'], task, form]
        f = t['forms'][k]
        assert f['bits'] == worst[0] and f['text'].startswith(worst[1]), key
        rows.append(dict(key=key, task=task, form=form, held=task in held, group=groups.get((task, form)), step=e['step'], census_bits=worst[0], new_forms=e['n'], forms_refused=e['refused'], later_refused=e['later_refused'],
                         worst=e['worst'], index=f['form'], target=f['text'], replace=t['replace'], lines=stems[task]['lines']))
    rows.sort(key=lambda r: (r['held'], r['task'], r['form']))
    with open(HERE + 'form-set.jsonl', 'w') as out:
        for r in rows:
            out.write(json.dumps(r) + '\n')
    summary = dict(entries=len(by_form), worst_kind=dict(kinds), in_set=len(rows), held=sum(r['held'] for r in rows), not_held=sum(not r['held'] for r in rows), tasks=len({r['task'] for r in rows}), held_tasks=len({r['task'] for r in rows if r['held']}),
                   by_group=dict(collections.Counter(r['group'] for r in rows)), by_step=dict(collections.Counter(r['step'] for r in rows)), with_refused_new_form=[r['key'] for r in rows if r['forms_refused']],
                   with_refused_later_form=sum(1 for r in rows if r['later_refused']))
    json.dump(summary, open(HERE + 'form-set-summary.json', 'w'), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
