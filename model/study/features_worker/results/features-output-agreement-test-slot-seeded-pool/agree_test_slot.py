"""Per task: gold's concept forms and sampled non-gold node forms, each run on the train inputs and on the train outputs placed as test inputs.
A form agrees where its rows are equal on every train example. A form whose rows also equal those of another example's output is grid-independent and is left out.
Usage: agree_test_slot.py one <task> <k>, or agree_test_slot.py run <tasks-file> <k> <out.jsonl>. `run` streams one line per task and skips finished tasks."""
import array, collections, json, os, random, re, subprocess, sys, time
import arclog
ROOT = '/Users/davidlu/code/arc-workspace'; HERE = os.path.dirname(os.path.abspath(__file__)); W = f'{HERE}/w'
GOLD = f'{ROOT}/work/lm/data-study/gold/gen-v3-11f6a212c/corpus/gen'; NODES = f'{ROOT}/work/lm/data-study/features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search'
CODE = {n: c for c, n in arclog.orientation_names()}
FORMS = {'uint8': 'B', 'uint32': 'I', 'int32': 'i', 'uint64': 'Q'}

def ints(c, part, k):
    a = array.array(FORMS[c.dtypes[f'{part}.{k}']]); a.frombytes(getattr(c, part)[k]); return a

def params(path):
    out = {}
    for n, v in re.findall(r'\(param (&\S+) \S+ \((\S+)\)\)', open(path).read()):
        if v in CODE or re.fullmatch(r'-?\d+', v): out[n] = (CODE[v] if v in CODE else int(v),)
    return out

def tables(corpus, tasks, task):
    """{relation: {(kind, example): rows}} at the stored assignment, with the relations left ambiguous by an unstored DET in `ambiguous`."""
    cases, lines = arclog.corpus_tables(corpus, tasks, task_ids=[task], all_cases=False)
    if not cases: raise RuntimeError(str(lines)[:200])
    c = cases[0]; t = c.tables
    vals = array.array('i'); vals.frombytes(c.values)
    et, kind, ei, model, nrows, off = (ints(c, 'entries', k) for k in ('table', 'example_kind', 'example_index', 'model', 'rows', 'offset'))
    ae, ad, ar, ao = (ints(c, 'assigned', k) for k in ('entry', 'det', 'rows', 'offset'))
    assigned = collections.defaultdict(dict)
    for a in range(len(ae)):
        e = ae[a]; assigned[e][t['det_relations'][et[e]][ad[a]]] = tuple(vals[ao[a]:ao[a] + ar[a]].tolist())
    slot = {}
    for i, n in enumerate(t['relation_name']):
        if n and len(t['det_relations'][i]) == 1 and n not in slot: slot[n] = t['det_relations'][i][0]
    want = {slot[n]: v for n, v in params(f'{corpus}/{task}.arcdata').items() if n in slot}
    def rows(i):
        ti = et[i]; ws = [4 if x in ('Position', 'Box', 'Offset') else 1 for x in t['column_types'][ti]]; W_ = sum(ws); o = off[i]; out = set()
        for r in range(nrows[i]):
            cells = vals[o + r * W_:o + (r + 1) * W_]; p = 0; row = []
            for w, ty in zip(ws, t['column_types'][ti]):
                row.append('id' if ty == 'Ident' else (tuple(cells[p:p + w]) if w == 4 else cells[p])); p += w
            out.add(tuple(sorted(map(repr, row))))
        return frozenset(out)
    out = {}; ambiguous = set()
    for i in range(len(et)):
        name = t['relation_name'][et[i]]
        if not name or name.startswith('ex_') or kind[i] not in (1, 2) or model[i] != 0 or t['fault'][et[i]]: continue
        if any(s in want and v != want[s] for s, v in assigned[i].items()): continue
        r = rows(i); k = (kind[i], ei[i]); d = out.setdefault(name, {})
        if k in d and d[k] != r: ambiguous.add(name)
        d[k] = r
    return out, ambiguous

DOMAIN = {'Color': 'ColorDomain', 'Dir': 'DirDomain', 'number': 'NumberDomain', 'Axis': 'AxisDomain', 'DiagDir': 'DiagDirDomain', 'D4': 'D4Domain', 'Sym': 'SymDomain', 'Sense': 'SenseDomain', 'DiagAxis': 'DiagAxisDomain'}

def forms(s, head):
    """The (start, end) of each form of s that starts with head."""
    out = []; i = s.find(head)
    while i >= 0:
        d = 0
        for j in range(i, len(s)):
            d += (s[j] == '(') - (s[j] == ')')
            if d == 0: break
        out.append((i, j + 1)); i = s.find(head, j)
    return out

def concept(g, data):
    """Gold's text without its ALTS forms, each proposer DET of a one-value param read from its type domain, so that test inputs don't change its value; and the param forms alone."""
    for i, j in reversed(forms(g, '(ALTS ')): g = g[:i] + g[j:]
    ps = [data[i:j] for i, j in forms(data, '(param ')]
    for p in ps:
        m = re.fullmatch(r'\(param (&\S+) (\S+) \((\S+)\)\)', p)
        if not m or m[2] not in DOMAIN: continue
        for head in (f'(DET_OR_RULE {m[1]} ', f'(DET {m[1]} '):
            for i, j in reversed(forms(g, head)):
                if head.startswith('(DET_OR') or re.fullmatch(r'\(DET \S+ \w+( \(ONE\))?\)', g[i:j]): g = g[:i] + f'(DET {m[1]} {DOMAIN[m[2]]})' + g[j:]
    return g, ';; params\n\n' + '\n'.join(ps) + '\n'

def nodes(T):
    txt = subprocess.run(['zstd', '-dcq', f'{NODES}/{T}.nodes.jsonl.zst'], capture_output=True, text=True).stdout
    return {str(r['token']): r for r in map(json.loads, txt.splitlines())}

def extras(T, g0, g, k):
    """The non-gold clauses to add, each with its ancestors, and the heads of the sampled ones. A seeded DET by a proposer takes the name of the one gold DET that states that proposer."""
    by = nodes(T); seed = {t for t, r in by.items() if (r.get('tags') or {}).get('seeded')}
    form = lambda r: (r['clause'] or '')[1:].split(' ')[0]
    def closure(t, s):
        if t in s: return True
        if t not in by or (t not in seed and form(by[t]) == 'DET'): return False
        s.add(t); return all(closure(str(p), s) for p in by[t]['parents'])
    ids = [t for t in by if t not in seed and form(by[t]) in ('RULE', 'INIT')]; random.Random(0).shuffle(ids)
    keep, heads = set(), set()
    for t in ids:
        s = set(); h = by[t]['clause'].split()[1]
        if h not in heads and closure(t, s): keep |= s; heads.add(h)
        if len(heads) == k: break
    rename, clauses, seen, used = {}, [], set(), collections.Counter()
    for t in sorted(keep, key=int):
        c = by[t]['clause']; h = c.split()[1]
        if h in seen: continue
        seen.add(h)
        m = re.fullmatch(r'\(DET (&f\d+) (\w+)\)', c)
        if m:
            names = re.findall(r'\(DET(?:_OR_RULE)? (&\S+) ' + m[2] + r'\b', g0)
            used[m[2]] += 1
            if len(names) >= used[m[2]]: rename[m[1]] = names[used[m[2]] - 1]; continue
        clauses.append(re.sub(r'\(:(\w+) (\*?\^?)\1\)', r'\2\1', c))
    text = '\n'.join(clauses)
    for a in sorted(rename, key=len, reverse=True): text = re.sub(re.escape(a) + r'(?![\w])', rename[a], text)
    return text, heads

def one(T, k):
    t0 = time.time(); d = f'{W}/{T}'; os.makedirs(f'{d}/prog', exist_ok=True); os.makedirs(f'{d}/tasks', exist_ok=True)
    g = open(f'{GOLD}/{T}.arclog').read(); j = json.load(open(f'{ROOT}/data/tasks/{T}.json'))
    c, data = concept(g, open(f'{GOLD}/{T}.arcdata').read())
    text, heads = extras(T, re.sub(r'\(ALTS .*', '', g, flags=re.S), g, k); i = c.rindex('(OUT')
    open(f'{d}/prog/{T}.arclog', 'w').write(c[:i] + text + '\n\n' + c[i:])
    open(f'{d}/prog/{T}.arcdata', 'w').write(data)
    json.dump({'train': j['train'], 'test': [{'input': p['output'], 'output': p['output']} for p in j['train']]}, open(f'{d}/tasks/{T}.json', 'w'))
    tb, amb = tables(f'{d}/prog', f'{d}/tasks', T); n = len(j['train'])
    res = {'gold': {}, 'node': {}}; dropped = collections.Counter(); goldrows = set()
    gold_names = [x for x in tb if not re.match(r'&f\d+', x)]
    for x in gold_names: goldrows.add(tuple(tb[x].get((1, e), frozenset()) for e in range(n)))
    for x, v in tb.items():
        head = x.split('.')[0]; side = 'node' if re.match(r'&f\d+', x) else 'gold'
        if side == 'node' and head not in heads: continue
        if x in amb: dropped['ambiguous'] += 1; continue
        a = [v.get((1, e), frozenset()) for e in range(n)]; b = [v.get((2, e), frozenset()) for e in range(n)]
        if not any(a): dropped['empty'] += 1; continue
        if side == 'node' and tuple(a) in goldrows: dropped['equals gold'] += 1; continue
        if n > 1 and all(a[e] == b[(e + 1) % n] for e in range(n)): dropped['grid-independent'] += 1; continue
        res[side].setdefault(head, []).append(all(a[e] == b[e] for e in range(n)))
    score = lambda s: {f: sum(v) / len(v) for f, v in res[s].items()}
    return {'task': T, 'gold': score('gold'), 'node': score('node'), 'dropped': dropped, 'seconds': round(time.time() - t0, 1)}

if sys.argv[1] == 'one': print(json.dumps(one(sys.argv[2], int(sys.argv[3]))))
else:
    ts = open(sys.argv[2]).read().split(); k = sys.argv[3]; out = sys.argv[4]
    done = {json.loads(l)['task'] for l in open(out)} if os.path.exists(out) else set()
    for n, T in enumerate(ts):
        if T in done: continue
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, '-B', __file__, 'one', T, k], capture_output=True, text=True, timeout=120)
            line = p.stdout.strip().splitlines()[-1] if p.returncode == 0 and p.stdout.strip() else json.dumps({'task': T, 'error': p.stderr.strip()[-200:]})
        except subprocess.TimeoutExpired: line = json.dumps({'task': T, 'error': 'timeout'})
        open(out, 'a').write(line + '\n'); print(n + 1, len(ts), T, round(time.time() - t0, 1), line[:120], flush=True)
