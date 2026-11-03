"""Lower bound on the store of a held-reader search: kept forms of a 600 s bank whose clause reads a method of a pool INIT at a key site, where every
label of that key site is bare (a join on a label that another site makes). Each is one sketch by swap: that INIT's atoms become the hole. Forms whose
try gave an equal table also give sketches and are not in the bank, so this is a lower bound. The bank pickle is read with a loader that makes only
superdag.Form and superdag.Node and refuses every other class.
  python3 sketch_count.py BANK..."""
import collections, pickle, re, sys, statistics as st
class Stub:
    def __setstate__(self, s):
        self.__dict__.update(s if isinstance(s, dict) else s[1] or {})
class Safe(pickle.Unpickler):
    def find_class(self, mod, name):
        if mod == 'superdag' and name in ('Form', 'Node'):
            return Stub
        if mod == 'builtins' and name in ('set', 'frozenset'):
            return getattr(__builtins__, name) if hasattr(__builtins__, name) else __builtins__[name]
        if mod == 'collections' and name in ('defaultdict', 'Counter', 'OrderedDict'):
            return getattr(collections, name)
        raise pickle.UnpicklingError('refused %s.%s' % (mod, name))
def key_sites(atom):
    i = atom.find('(:key')
    if i < 0:
        return None
    d = 0
    for j in range(i, len(atom)):
        d += atom[j] == '('; d -= atom[j] == ')'
        if d == 0:
            return atom[i:j + 1]
rows = []
for path in sys.argv[1:]:
    with open(path, 'rb') as fh:
        bank = Safe(fh).load()
    forms = bank['forms'] if isinstance(bank, dict) else bank.forms
    inits = {'&f%d' % f.id for f in forms.values() if f.kind == 'INIT'}
    n = holes = 0
    for f in forms.values():
        n += 1
        got = set()
        for m in re.finditer(r'\((&f\d+)\.\w+ ', f.text):
            if m[1] not in inits or m[1] == '&f%d' % f.id:
                continue
            d = 0
            for j in range(m.start(), len(f.text)):
                d += f.text[j] == '('; d -= f.text[j] == ')'
                if d == 0:
                    break
            ks = key_sites(f.text[m.start():j + 1])
            if ks and '*' not in ks and '^' not in ks:
                got.add(m[1])
        holes += len(got)
    rows.append((path.split('/')[-3], n, holes))
for r in rows:
    print(*r)
print('per task: forms median %s, sketches by swap median %s, quartiles %s, total %d over %d tasks' % (
    st.median(r[1] for r in rows), st.median(r[2] for r in rows), st.quantiles([r[2] for r in rows], n=4), sum(r[2] for r in rows), len(rows)))
