"""Label counts per run and per task from rows/<set>/*.json."""
import glob, json, os, sys, collections, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
for which in ('fit', 'read'):
    rs = [json.load(open(p))['info'] for p in sorted(glob.glob(C.REC + '/rows/%s/*.json' % which))]
    for grp in sorted({r['group'] for r in rs}):
        g = [r for r in rs if r['group'] == grp]
        pos = [r['positives'] for r in g]
        bt = collections.defaultdict(int)
        for r in g: bt[r['task']] += r['positives']
        print(which, grp, 'runs', len(g), 'tasks', len(bt), 'nodes', sum(r['nodes'] for r in g), 'positives', sum(pos), 'first-cover label', sum(r['positives_first'] for r in g),
              'self', sum(r['self_covers'] for r in g), 'per run min/med/max', min(pos), st.median(pos), max(pos), 'runs with 0 pos', sum(p == 0 for p in pos),
              'tasks with 0 pos', sum(v == 0 for v in bt.values()))
        if which == 'read':
            print('   cover lines', sum(r['cover_lines'] for r in g), 'held', sum(r['cover_lines_held'] for r in g), 'dropped (node not in bank)', sum(r['cover_lines_dropped'] for r in g),
                  'events', sum(r['events'] for r in g), 'exposed nodes', sum(r['exposed_nodes'] for r in g))
        else:
            print('   rows without a table', sum(r['rows_no_table'] for r in g), 'covering nodes', sum(r['covering_nodes'] for r in g))
        print('   per task positives', dict(sorted(bt.items())) if len(bt) <= 60 else '')
