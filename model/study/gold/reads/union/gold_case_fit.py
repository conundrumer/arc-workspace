"""Whether each case that the union left out with 'OUT rows differ' fits train after all: its output on each train pair is that pair's output or the grid of the pair's `alt` in the task file. Writes case-fit-<set>.jsonl in this folder.

  <runtime python> gold_case_fit.py SET

A case's OUT rows on each train pair are drawn as a grid: the OUT form's first ^label is the position, read as (row, rows below, column, columns right), and the second is the color.
"""
import ast, json, os, re, sys
from gold_cheapest_common import Bar, program_lines, ROOT
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..'))  # model/study
import study_zst as Z  # the union files are zstd streams or plain files, whichever is on disk

HERE = os.path.dirname(os.path.abspath(__file__))


def grid(rows, out_line):
    labels = re.findall(r'\^(\w+)', out_line)
    color_first = sorted(labels[:2])[0] == labels[1]
    cells = {}
    for r in rows:
        v = ast.literal_eval(r)
        c, p = (v[0], v[1:5]) if color_first else (v[4], v[0:4])
        cells[p[0], p[2]] = c
        h, w = p[0] + p[1] + 1, p[2] + p[3] + 1
    return [[cells.get((i, j)) for j in range(w)] for i in range(h)] if rows else []


def main():
    s = sys.argv[1]
    progs = {}
    for l in Z.open_text(HERE + '/cases-%s.jsonl' % s):
        r = json.loads(l)
        progs[r['task'], r['case']] = r['gold_sexp']
    with open(HERE + '/case-fit-%s.jsonl' % s, 'w') as out:
        for l in Z.open_text(HERE + '/union-%s.jsonl' % s):
            u = json.loads(l)
            bad = {h for h, why in (u.get('left_out') or {}).items() if why == 'OUT rows differ'}
            if not bad:
                continue
            task = json.load(open(ROOT / 'data/tasks' / ('%s.json' % u['task'])))
            bar = Bar(u['task'])
            for case, h in u['cases'].items():
                if h not in bad:
                    continue
                text = progs[u['task'], case]
                ls = program_lines(text)
                rows = bar.walk(ls)[0]
                outl = next(x for x in ls if x.startswith('(OUT'))
                pairs = []
                for i, p in enumerate(task['train']):
                    g = grid(rows.get('(1, %d)' % i, []), outl)
                    alt = (p.get('alt') or {}).get('grid')
                    pairs.append('output' if g == p['output'] else 'alt' if alt is not None and g == alt else 'neither')
                out.write(json.dumps(dict(task=u['task'], case=case, pairs=pairs, fits=all(x != 'neither' for x in pairs), alt_used='alt' in pairs)) + '\n')
                out.flush()


if __name__ == '__main__':
    main()
