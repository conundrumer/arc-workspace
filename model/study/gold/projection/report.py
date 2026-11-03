"""The trial's result per stem, from the last row of each stem in trial/out/rows-*.jsonl.

  python3 report.py [RUN_DIR]   (default trial)

Per stem: worst form before and after (bits, line, kind), forms over 25 before and after, each landed step (shape, the form's bits, the new
forms with their bits), whether the program bar held at the commit (program_fail), rows_differ, and the end reason. Then the counts the
trial is judged on: worst forms that fell by 3 bits or more, stems under 25 and under 21.5.
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
last = {}
for p in sorted(glob.glob(HERE + '/' + (sys.argv[1] if len(sys.argv) > 1 else 'trial') + '/out/rows-*.jsonl')):
    for l in open(p):
        try:
            r = json.loads(l)
        except ValueError:
            continue
        last[r['task']] = r



fell3 = under25 = under215 = 0
for t, r in sorted(last.items()):
    print('==', t, 'skipped' if r.get('skipped') else '', r.get('skipped') or '', 'late' if r.get('late') else '', r.get('error') or '')
    bef, aft = r.get('before') or {}, r.get('after') or {}
    wb, wa = bef.get('worst'), aft.get('worst')
    print('   worst before', wb, ' after', wa, ' commits', (r.get('commit') or {}).get('count'), ' program_fail', r.get('program_fail'))
    over = lambda b: sum(isinstance(x, (int, float)) and x >= 25 for x in b.get('bits') or [])
    print('   worst line before %s after %s; forms over 25 before %d after %d; sum before %s after %s; forms %s -> %s' % (
        bef.get('worst_line'), aft.get('worst_line'), over(bef), over(aft), bef.get('sum'), aft.get('sum'), bef.get('forms'), aft.get('forms')))
    for s in r.get('steps') or []:
        print('   step %s rank %s form %s (%s) %.2f -> worst %.2f, committed %s, rows_differ %s' % (s['shape'], s['rank'], s['form'], s['kind'], s['bits'] or -1, s['worst'] or -1, s.get('committed'), s.get('rows_differ')))
        for text, b, st in s['new']:
            print('      %7s %-6s %s' % (b, st, text[:200]))
    print('   kept out:', r.get('kept_out'))
    if isinstance(wb, (int, float)) and isinstance(wa, (int, float)):
        fell3 += wb - wa >= 3
        under25 += wa < 25
        under215 += wa < 21.5
print('\nstems %d; worst form fell 3+ bits: %d; worst under 25: %d; under 21.5: %d' % (len(last), fell3, under25, under215))
