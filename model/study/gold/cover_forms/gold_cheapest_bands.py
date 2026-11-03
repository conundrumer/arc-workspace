"""Task bands of revision gold-v3-cheapest-round50 before and after its rebuild: tasks with every form under 25, 28 and 32 bits, in the all-earlier-forms context, on the 37 held-out tasks and the 99 evaluation tasks. Before is round-out/view-before.json, the view's text of the 99 tasks before the rebuild. After is the view's text, or points-eval.json for a stem with no folder.

  <runtime python> gold_cheapest_bands.py run
  <runtime python> gold_cheapest_bands.py child STEM...

Rows go to round-out/bands-rows.jsonl, one per stem and each with both figures. Rows of forms.jsonl of census-bands-cheapest are read, so a form it holds is not read again. Counts go to round-out/bands.json and to the views entry of manifest.json. A task with a form with no bits, or set aside at a cap, is in no band.
"""
import json, os, sys
from gold_cheapest_common import *
import gold_cheapest_case as C

OUT = HERE + 'round-out/bands-rows.jsonl'
BANDS = 13, 18, 21.5, 25, 28, 32


def texts(name):
    return {p['task']: p['gold_sexp'] for p in json.load(open(HERE + name))}


def child(stems):
    bits, a, b = Bits(), texts('round-out/view-before.json'), texts('points-eval.json')
    b.update({t: view_row(t)['gold_sexp'] for t in stems if view_row(t)})
    tick = lambda: print('tick', flush=True)
    for t in stems:
        print('stem', t, flush=True)
        print(json.dumps(dict(stem=t, before=bits.whole(t, program_lines(a[t]), tick), after=bits.whole(t, program_lines(b[t]), tick), taken=None, why='')), flush=True)


def in_band(f, b):
    return f is not None and not f['undrawable'] and f['worst'] < b


def tables():
    rows = {r['stem']: r for r in map(json.loads, open(OUT))}
    got = dict(context='every earlier form', sets={}, set_aside=sorted(t for t, r in rows.items() if 'set_aside' in r))
    for name, stems in (('held_out', HELD), ('evaluation', EVAL)):
        got['sets'][name] = dict(tasks=len(stems), bands={})
        for b in BANDS:
            d = {side: sorted(t for t in stems if in_band(rows[t].get(side), b)) for side in ('before', 'after')}
            got['sets'][name]['bands'][str(b)] = dict(before=len(d['before']), after=len(d['after']), gained=sorted(set(d['after']) - set(d['before'])), lost=sorted(set(d['before']) - set(d['after'])), tasks_after=d['after'])
    json.dump(got, open(HERE + 'round-out/bands.json', 'w'), indent=1)
    m = json.load(open(HERE + 'manifest.json'))
    m['views']['corpus-view']['bands'] = dict(got, file='round-out/bands.json', rows='round-out/bands-rows.jsonl')
    with open(HERE + 'manifest.json.new', 'w') as f:
        json.dump(m, f, indent=1)
    os.replace(HERE + 'manifest.json.new', HERE + 'manifest.json')
    print(json.dumps({k: {b: (v['before'], v['after']) for b, v in s['bands'].items()} for k, s in got['sets'].items()}))


def run():
    done = {json.loads(l)['stem'] for l in open(OUT)} if os.path.exists(OUT) else set()
    left = [t for t in HELD + [t for t in EVAL if t not in HELD] if t not in done]
    with open(OUT, 'a') as out:
        while left:
            part, left = left[:C.PER_CHILD], left[C.PER_CHILD:]
            while part:
                part = C.watch(part, out, os.path.abspath(__file__))
                out.flush()
    tables()


if __name__ == '__main__':
    child(sys.argv[2:]) if sys.argv[1] == 'child' else run()
