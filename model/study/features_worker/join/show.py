import json, subprocess, sys, glob
sys.argv = ['x', 'show', sys.argv[1], sys.argv[2]]
rec, t = sys.argv[2], sys.argv[3]
import importlib.util, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE + '/../policy5')
from nodefeat import Pair, columns
src = open(HERE + '/union.py').read().split('t0 = time.time()')[0].replace("tag, rec, tf = sys.argv[1:4]\n", "").replace("OUT = f'{HERE}/out/{tag}'\nos.makedirs(OUT, exist_ok=True)\n", "")
exec(src)
d = json.load(open(f'data/tasks/{t}.json'))
pairs = [Pair(x['input'], x['output']) for x in d['train']]
f = glob.glob(f'{rec}/{t}*.zst')[0]
for raw in subprocess.Popen(['zstd', '-dcq', f], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout:
    try:
        r = json.loads(raw)
    except ValueError:
        continue
    if paint(r, pairs):
        print(t, r['token'], 'depth', r['depth'], r['types'], r['table_types'], 'parents', r['parents'], 'examples', [(e[0], e[1], e[2]) for e in r['examples']])
        print(' ', (r['clause'] or '')[:300], '| rows kinds', [x[0] for x in (r['x_rows'] or [])][:8])
