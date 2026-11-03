"""Tables of a case by relation at the stored assignment, and the swapped task: train inputs replaced by train outputs."""
import array, json, re, sys, collections, arclog

def ints(c, part, k):
    a = array.array({'uint8':'B','uint32':'I','int32':'i','uint64':'Q'}[c.dtypes[f'{part}.{k}']])
    a.frombytes(getattr(c, part)[k]); return a

def widths(types): return [4 if t in ('Position','Box','Offset') else 1 for t in types]

def fmt(t, v): return tuple(v) if t in ('Position','Box','Offset') else v[0]

CODE = {n: c for c, n in arclog.orientation_names()}

def params(corpus, task):
    """The stored one-row one-column params of the arcdata file, by relation."""
    out = {}
    for n, v in re.findall(r'\(param (&\S+) \S+ \((\S+)\)\)', open(f'{corpus}/{task}.arcdata').read()):
        out[n] = (CODE[v] if v in CODE else int(v),)
    return out

def tables(corpus, tasks, task):
    cases, lines = arclog.corpus_tables(corpus, tasks, task_ids=[task], all_cases=False)
    if not cases: raise SystemExit(lines)
    c = cases[0]
    if lines: print('lines:', lines, file=sys.stderr)
    t = c.tables
    vals = array.array('i'); vals.frombytes(c.values)
    et, kind, ei, model, nrows, off = (ints(c,'entries',k) for k in ('table','example_kind','example_index','model','rows','offset'))
    ae, ad, ar, ao = (ints(c,'assigned',k) for k in ('entry','det','rows','offset'))
    assigned = collections.defaultdict(dict)
    for a in range(len(ae)):
        e = ae[a]; d = t['det_relations'][et[e]]
        assigned[e][d[ad[a]]] = tuple(vals[ao[a]:ao[a]+ar[a]].tolist())
    def rows_of(i):
        ti = et[i]; names, types = t['column_names'][ti], t['column_types'][ti]
        w = widths(types); W = sum(w); rows = set(); o = off[i]
        for r in range(nrows[i]):
            cells = vals[o+r*W:o+(r+1)*W]; p = 0; row = []
            for n, ty, wi in zip(names, types, w):
                row.append((n, fmt(ty, list(cells[p:p+wi])))); p += wi
            rows.add(tuple(row))
        return rows
    # the assignment whose &output is the train output at every train example
    truth = {}
    for i in range(len(et)):
        if t['relation_name'][et[i]] == 'ex_output':
            for r in rows_of(i):
                d = dict(r); truth.setdefault(d['E'], set()).add(frozenset((d['P'], d['Col'])))
    n_ex = len(truth); fits = collections.Counter()
    for i in range(len(et)):
        if t['relation_name'][et[i]] == '&output' and kind[i] == 1 and model[i] == 0:
            if {frozenset(v for _, v in r) for r in rows_of(i)} == truth.get(ei[i]):
                fits[tuple(sorted(assigned[i].items()))] += 1
    full = [a for a, n in fits.items() if n == n_ex]
    if not full: print('no assignment fits', file=sys.stderr); return {}
    slot = {}
    for i, n in enumerate(t['relation_name']):
        if n and len(t['det_relations'][i]) == 1 and n not in slot: slot[n] = t['det_relations'][i][0]
    stored = {slot[n]: v for n, v in params(corpus, task).items() if n in slot}
    full = [a for a in full if all(stored.get(s, v) == v for s, v in a)]
    if not full: print('no fit at the stored values', file=sys.stderr); return {}
    want = {s: v for s, v in full[0] if s in stored}
    want = dict(stored) if not want else {**stored, **want}
    out = {}
    for i in range(len(et)):
        ti = et[i]; name = t['relation_name'][ti]
        if name is None or kind[i] != 1 or model[i] != 0: continue
        if t['fault'][ti]: print('fault', name, t['fault'][ti], file=sys.stderr); continue
        if any(s in want and v != want[s] for s, v in assigned[i].items()): continue
        rows = rows_of(i)
        if ei[i] in out.get(name, {}) and out[name][ei[i]] != rows: print('two assignments left for', name, ei[i], file=sys.stderr)
        out.setdefault(name, {})[ei[i]] = rows
    return out

def swap(task_path, out_path):
    d = json.load(open(task_path))
    tr = [{'input': p['output'], 'output': p['output']} for p in d['train']]
    json.dump({'train': tr, 'test': [tr[0]]}, open(out_path, 'w'))
