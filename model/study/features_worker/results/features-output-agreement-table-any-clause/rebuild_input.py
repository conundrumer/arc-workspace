"""On one task: an output-side clause rebuilds the input, and each non-gold form runs on that rebuilt grid in place of `input`. Prints each form's table against its table on the real input."""
import json, os, re, sys
sys.argv = [sys.argv[0], 'import'] + sys.argv[1:]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agree_tables.py')).read().split("if sys.argv[1] == 'one'")[0]
exec(src)
T = sys.argv[2]; d = f'{W}/{T}'; p = open(f'{d}/prog/{T}.arclog').read()
i = re.search(r'\((RULE|INIT|DET) &f\d+', p).start(); j = p.rindex('(OUT'); E = p[i:j]
E2 = re.sub(r'&f(\d+)', r'&r\1', E.replace('(input ', '(&recon '))
hand = '''(RULE &nonbg
  (input *P *Col)
  (NOT (&bg (:C Col))))

(INIT &region Flood
  (node (P)
    (&nonbg *P))
  (source (P)
    (&nonbg *P *Col)
    (&block (:C Col))))

(RULE &recon
  (OR ((&region.reached *P)
       (&block (:C *Col)))
      ((input P Col)
       (NOT (&region.reached P)))))

'''
os.makedirs(f'{d}/rebuilt', exist_ok=True)
open(f'{d}/rebuilt/{T}.arclog', 'w').write(p[:j] + hand + E2 + '\n\n' + p[j:]); subprocess.run(['cp', f'{d}/prog/{T}.arcdata', f'{d}/rebuilt/'])
tb, amb = tables(f'{d}/rebuilt', f'{d}/tasks', T); n = len(json.load(open(f'{ROOT}/data/tasks/{T}.json'))['train'])
print('&recon equals the input:', all(tb['&recon'].get((2, e)) == tb['&recon'].get((1, e)) for e in range(n)))
for x in sorted((x for x in tb if x.startswith('&f')), key=lambda s: (int(re.match(r'&f(\d+)', s)[1]), s)):
    y = x.replace('&f', '&r', 1); a = [tb[x].get((1, e), frozenset()) for e in range(n)]; b = [tb.get(y, {}).get((2, e), frozenset()) for e in range(n)]
    if not any(a): continue
    print(f'{x:26}', 'ambiguous' if x in amb or y in amb else 'equal' if a == b else 'differ')
