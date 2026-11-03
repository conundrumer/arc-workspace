"""Builds revision gold-v3-cheapest-round50 from the helper view as it stands and the covering clause rows: corpus-view/, points-eval.json, helpers.json, view-stems.jsonl, kind-mix.json, census-bits.json and the views entry of manifest.json. The view is built beside the old one, stem by stem, and swapped in by rename, so the script can run again at any time. It reads no engine.

  python3 gold_cover_view.py [--dry]

A stem takes its row's program when the row read, its `swapped` is not empty, and the text the row started from is gen-v3's current text. Every other stem takes what the helper view holds. Rows: pod-out/rows-<k>.jsonl, then pod-out/rows-pass2-<k>.jsonl, then round-out/rows-<round>.jsonl by time; a later row of a stem replaces an earlier one. Current text: current-text.json.
Three sources apply after that, in order: a taken row of round-out/hand-rewrites.jsonl (source hand-rewrite), a taken row of round-out/case-choice.jsonl (source case-choice), and a taken row of round-out/prune-rows.jsonl (`pruned` in view-stems.jsonl), which applies only to the text it read. A stem with no folder takes them in points-eval.json. A stem whose first row stands keeps its bytes from the view it replaces. round-out/rebuild-stems.txt lists the stems whose text changed.
"""
import collections, ctypes, glob, gzip, hashlib, json, os, re, shutil, statistics, sys, time

ROOT = '/Users/davidlu/code/arc-workspace/'
D = ROOT + 'work/lm/data-study/'
HERE = D + 'gold/gold-v3-cover-forms-a036da074/'
HELP = D + 'gold/gold-v3-helper-forms-a036da074/'
GEN = D + 'gold/gen-v3-11f6a212c/'
HANDS = D + 'gold/gold-or-rewrite-heldout7/final/golds.json'
HELD = D + 'sampler/sampler-worker/held/tasks.txt'
LEAVE_OUT = D + 'sampler/sampler-worker/held/leave_out.txt'
EVAL = D + 'features-worker/arm/eval-tasks.txt'
REVISION = 'gold-v3-cheapest-round50'
BASE_ROUND = 48  # the round of lines.json
KIND_STEP, KIND_TOP = 2, 12  # the clause count buckets of the priors' next-kind counts
NAME = re.compile(r'&[A-Za-z_0-9]+')
os.chdir(HERE)


RENAME_SWAP = 2  # renamex_np of macOS


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def later_rows():
    """The taken rows of the hand rewrite, case choice and prune steps, each by stem."""
    def take(name):
        p = 'round-out/' + name
        return [json.loads(l) for l in open(p)] if os.path.exists(p) else []
    return ({r['stem']: r for r in take('hand-rewrites.jsonl') if r['taken']}, {r['stem']: r for r in take('case-choice.jsonl') if r['taken']}, {t: r for t, r in {r['stem']: r for r in take('prune-rows.jsonl') if r.get('dropped') or r.get('taken')}.items() if r['taken']})


def later_helpers(t, r):
    """helpers.json rows of a hand rewrite or case choice row, on the rule of helper_rows. None where `cuts` doesn't fit the crossing list."""
    cuts = r.get('cuts') or []
    if not cuts:
        return []
    cross = sorted(r['crossing_list'] if 'crossing_list' in r else r['crossing'], key=lambda c: c['line'])
    if len(cross) != len(cuts):
        return None
    out, shift = [], 0
    for c, at in zip(cross, cuts):
        n = len(c['cuts'])
        out += [dict(task=t, line=at + shift + k, source_line=c['line'], last=k == n - 1) for k in range(n)]
        shift += n - 1
    return out


def align(old, new):
    """{line of old: line of new} of program new, a program old with forms dropped, on masked text in order."""
    out, k = {}, 0
    for i, x in enumerate(old):
        if k < len(new) and masked(x) == masked(new[k]):
            out[i] = k
            k += 1
    return out


def masked(form):
    """The form with relation names masked: a form keeps its text under the renames of a normal form."""
    return NAME.sub('&_', form)


def name_of(x):
    m = re.match(r'\(\w+ (&[A-Za-z_0-9]+)', x)
    return m[1] if m else None


def prune(ls):
    """ls without the forms that no later form reads. The items are (gold line or None, text). Same rule as gold_cover_one.py."""
    ls = list(ls)
    while True:
        text = '\n'.join(x for _, x in ls)
        dead = [k for k, (_, x) in enumerate(ls) if name_of(x) and len(re.findall(re.escape(name_of(x)) + r'(?=[ .)])', text)) == 1]
        if not dead:
            return ls
        ls.pop(dead[-1])


def joint_items(base, covers):
    """The items of the program with every candidate in at once, as gold_cover_one.py builds it."""
    joint = list(enumerate(base))
    for line in sorted({c['line'] for c in covers}, reverse=True):
        c = min((c for c in covers if c['line'] == line), key=lambda c: len(c['forms']))
        at = next(k for k, (o, _) in enumerate(joint) if o == line)
        joint = joint[:at] + [(None, f) for f in c['forms']] + joint[at + 1:]
    return prune(joint)


def load_rows():
    """{stem: (row, base lines, covers, crossing, round)}, the last row of each stem. A line that doesn't parse is skipped and counted."""
    lines = json.load(open('lines.json'))
    covers = json.load(open('covers.json'))
    crossing = json.load(open('crossing.json'))
    got, torn = {}, 0
    files = [(f, None) for f in sorted(glob.glob('pod-out/rows-[0-9]*.jsonl'))] + [(f, None) for f in sorted(glob.glob('pod-out/rows-pass2-*.jsonl'))]
    files += [(f, re.search(r'rows-(\d+)\.jsonl', f)[1]) for f in sorted(glob.glob('round-out/rows-*.jsonl'), key=os.path.getmtime)]
    for f, n in files:
        if n:
            round_lines = json.load(open('round-out/lines-%s.json' % n))
            round_covers = json.load(open('round-out/covers-%s.json' % n))
            round_cross = json.load(open('round-out/crossing-%s.json' % n))
        for l in open(f):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                torn += 1
                continue
            t = r['task']
            if n:
                got[t] = (r, round_lines[t], round_covers.get(t, []), round_cross.get(t, []), int(n))
            else:
                got[t] = (r, lines[t], covers.get(t, []), crossing.get(t, []), BASE_ROUND)
    return got, torn


def changed_rounds():
    """{stem: the last round after BASE_ROUND that regolded it}."""
    got = {}
    for f in glob.glob(GEN + 'changed-gold-round*.txt'):
        n = int(re.search(r'round(\d+)\.txt', f)[1])
        if n > BASE_ROUND:
            for t in open(f).read().split():
                got[t] = max(got.get(t, 0), n)
    return got


def first_row(path):
    with gzip.open(path, 'rt') as f:
        return json.loads(f.readline())


def program_lines(sexp):
    return [x for x in sexp.splitlines() if x.strip()]


def choose(t, row, regold, current):
    """The stem's source and the reason."""
    if row is None:
        return 'helper', 'no covering clause row'
    r, base, _, _, n = row
    if 'error' in r:
        return 'helper', 'row has an error: ' + ('set aside at the cap' if r['error'] in ('time', 'memory') else 'stopped at the table work cap')
    if not r.get('swapped'):
        return 'helper', 'row made no swap'
    if regold.get(t, 0) > n or base != current:
        return 'helper', 'regolded after the row; its swaps are on old text'
    return 'cover', 'row with swaps on current text' + (', rerun in round %d' % n if n > BASE_ROUND else '')


def form_changes(t, program, current, cands, hands, cover=False, chains=()):
    """The forms of the program with no equal form in current, as dicts of stem, line, form and label. On a cover stem a form outside the cut chains comes from a pick: a form of a candidate, or a reader whose text the pick's normal form changed, flagged `reader`."""
    left = collections.Counter(map(masked, current))
    out = []
    for i, x in enumerate(program):
        m = masked(x)
        if i in chains:
            out.append(dict(stem=t, line=i, form=x, label='helper-cut'))
        elif left[m] > 0:
            left[m] -= 1
        elif not x.startswith('(OUT'):
            c = dict(stem=t, line=i, form=x, label='helper-cut')
            if cover:
                c['label'] = 'pool-picked'
                if m not in cands:
                    c['reader'] = True
            elif m in hands:
                c['label'] = 'hand-rewrite'
            out.append(c)
    return out


def picks(t, r, base, covers, program):
    """The swaps of a row as groups of gold forms and the forms in their place, with the bits the row gives."""
    have = set(map(masked, program))
    out = []
    for s in r['swapped']:
        if s['line'] == -1:
            items = joint_items(base, covers)
            kept = {o for o, _ in items if o is not None}
            new = [k for k, (o, _) in enumerate(items) if o is None]
            gone = [o for o in range(len(base) - 1) if o not in kept]
            out.append(dict(stem=t, source='joint', gold_lines=gone, gold_forms=[base[o] for o in gone], gold_bits=[s['before'][o] for o in gone], view_forms=[items[k][1] for k in new], view_bits=[s['after'][k] for k in new]))
        else:
            stood = [[f for f in c['forms'] if masked(f) in have] for c in covers if c['line'] == s['line']]  # a form no later form reads comes out, so a swap can leave none
            forms = next((f for f in stood if len(f) == len(s['after'])), None)
            if forms is None:
                sys.exit('no candidate of %s line %d stands in its program' % (t, s['line']))
            gone = [s['line']] + s.get('removed', [])
            out.append(dict(stem=t, source=s['source'], gold_lines=gone, gold_forms=[base[o] for o in gone], gold_bits=s['before'], view_forms=forms, view_bits=s['after']))
    return out


def helper_rows(t, r, base, covers, cross):
    """helpers.json rows of a cover stem, on the rule of gold_helper_view.py: `cuts` holds each cut clause's line after the swaps, so its forms stand at that line plus the forms that earlier cuts added. source_line is the gold line. None where `cuts` doesn't fit the crossing list."""
    touched = set()
    for s in r['swapped']:
        if s['line'] == -1:
            touched |= set(range(len(base))) - {o for o, _ in joint_items(base, covers) if o is not None}
        else:
            touched |= {s['line'], *s.get('removed', [])}
    kept = [c for c in sorted(cross, key=lambda c: c['line']) if c['line'] not in touched]
    if len(kept) != len(r['cuts']):
        return None
    out, shift = [], 0
    for c, at in zip(kept, r['cuts']):
        n = len(c['cuts'])
        out += [dict(task=t, line=at + shift + k, source_line=c['line'], last=k == n - 1) for k in range(n)]
        shift += n - 1
    return out


def mix(sexps):
    """Form and clause counts over programs."""
    kinds, pairs, stems, clauses = collections.Counter(), collections.Counter(), collections.Counter(), []
    for s in sexps:
        heads = [x.split()[0].lstrip('(') for x in program_lines(s)]
        n = sum(h != 'OUT' for h in heads)
        b = min(n // KIND_STEP * KIND_STEP, KIND_TOP)
        clauses.append(n)
        stems[b] += 1
        for h in heads:
            if h != 'OUT':
                kinds[h] += 1
                pairs['%s clauses %d' % (h, b)] += 1
    return dict(stems=len(clauses), clauses=sum(clauses), clauses_per_stem_median=statistics.median(clauses) if clauses else None, clauses_per_stem_mean=round(sum(clauses) / len(clauses), 3) if clauses else None, forms_by_kind=dict(sorted(kinds.items())), forms_by_kind_and_clause_bucket=dict(sorted(pairs.items())), stems_by_clause_bucket={str(k): v for k, v in sorted(stems.items())})


def main():
    view = HELP + 'corpus-view'
    stamp = os.stat(view).st_mtime_ns
    text = json.load(open('current-text.json'))
    rows, torn = load_rows()
    regold = changed_rounds()
    held = set(open(HELD).read().split())
    ev = open(EVAL).read().split()
    evs = set(ev)
    hands = {g['task']: set(map(masked, program_lines(g['gold_sexp']))) for g in json.load(open(HANDS))}
    helpers_in = collections.defaultdict(list)
    for h in json.load(open(HELP + 'helpers.json')):
        helpers_in[h['task']].append(h)
    hand_rows, case_rows, prune_rows = later_rows()
    late, stale, rebuilt, dropped_kinds = {}, [], [], collections.Counter()
    tmp = 'corpus-view.new'
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    helpers, pool_held, bits, counts, sums, lost = [], [], [], collections.Counter(), collections.Counter(), []
    sides = collections.defaultdict(lambda: ([], []))
    stems = sorted(os.listdir(view))
    with open('view-stems.jsonl.new', 'w') as out:
        for t in stems:
            src, entry = os.path.join(view, t), os.path.join(tmp, t)
            if t not in text or 'error' in text[t]:
                sys.exit('no current text for ' + t)
            current = text[t]['lines']
            row = rows.get(t)
            source, why = choose(t, row, regold, current)
            first = first_row(src + '/pairs.jsonl.gz')
            old = 'corpus-view/' + t
            old_first = first_row(old + '/pairs.jsonl.gz') if os.path.exists(old + '/pairs.jsonl.gz') else None
            base_sexp = row[0]['program'] if source == 'cover' else first['gold_sexp']
            over = case_rows.get(t) or hand_rows.get(t)  # the later row that replaces the text
            pre = over['program'] if over else base_sexp
            cut = prune_rows.get(t)
            if cut and cut['base'] != sha(pre):
                stale.append(t)
                cut = None
            sexp = cut['program'] if cut else pre
            prog = program_lines(sexp)
            if source == 'cover':
                r, base, covers, cross, n = row
                cands = {masked(x) for c in covers for x in c['forms']}
                got = helper_rows(t, r, base, covers, cross)
            else:
                cands, got = (), helpers_in.get(t, [])
            if over:
                got = later_helpers(t, over)
            if cut and got:
                place = align(program_lines(pre), prog)
                got = [dict(h, line=place[h['line']]) for h in got if h['line'] in place]
            chains = {h['line'] for h in got or []}
            real = source == 'cover' or not os.path.islink(src) or sexp != first['gold_sexp']
            changes = []
            if real:
                changes = form_changes(t, prog, current, cands, hands.get(t, ()), source == 'cover' and not over, chains)
                for c in changes:
                    if over and c['line'] not in chains:
                        c['label'] = 'case-choice' if t in case_rows else 'hand-rewrite'
            if t in case_rows:
                case_name, source, why = case_rows[t]['taken'], 'case-choice', 'cheapest case that holds'
            elif over:
                case_name, source, why = over['case'] or over['view_case'], 'hand-rewrite', 'hand rewrite: ' + over['why']
            else:
                case_name = text[t]['case'] if source == 'cover' else first.get('case')
            flags = dict(first, gold_sexp=sexp, case=case_name)
            if source == 'cover':
                flags.update(cover_forms=True, helper_forms=bool(row[0]['cuts']))
            elif over:
                flags.pop('cover_forms', None)
                flags['helper_forms'] = bool(over.get('cuts'))
                flags['hand_rewrite' if source == 'hand-rewrite' else 'case_choice'] = True
            if cut:
                flags['pruned'] = True
            if sexp != (old_first or {}).get('gold_sexp'):
                rebuilt.append(t)
            if not real:
                os.symlink(os.readlink(src), entry)
            else:
                os.makedirs(entry)
                if old_first == flags or (old_first and not over and not cut and source != 'cover' and old_first == first):
                    shutil.copyfile(old + '/pairs.jsonl.gz', entry + '/pairs.jsonl.gz')  # the first row stands, so the bytes do
                elif sexp == first['gold_sexp'] and flags == first:
                    shutil.copyfile(src + '/pairs.jsonl.gz', entry + '/pairs.jsonl.gz')
                else:
                    with gzip.open(src + '/pairs.jsonl.gz', 'rt') as f, open(entry + '/pairs.jsonl.gz', 'wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as dst:
                        f.readline()
                        dst.write((json.dumps(flags) + '\n').encode())
                        dst.write(f.read().encode())
            if got is None:
                lost.append(t)
            else:
                helpers += got
            if source == 'cover' and t in held:
                bits += picks(t, row[0], row[1], row[2], program_lines(row[0]['program']))
            group = 'held_out' if t in held else 'evaluation_other' if t in evs else 'training'
            counts[source, group] += 1
            for c in changes:
                sums[c['label'], group] += 1
                if c['label'] == 'pool-picked' and t in held:
                    pool_held.append(c)
            sides[group][0].append(first['gold_sexp'])
            sides[group][1].append(sexp)
            extra = {}
            if cut:
                extra = dict(pruned=True, forms_dropped=[dict(form=x, kind=x.split()[0][1:], label='pruned') for x in cut['dropped']])
                sums['pruned', group] += len(cut['dropped'])
                dropped_kinds.update(x.split()[0][1:] for x in cut['dropped'])
                counts['pruned, stems', group] += 1
            out.write(json.dumps(dict(stem=t, source=source, why=why, held_out=t in held, evaluation=t in evs, forms_changed=[{k: v for k, v in c.items() if k != 'stem'} for c in changes], **extra)) + '\n')
        for t in sorted(set(text) - set(stems)):  # stems of gen-v3 that no corpus view holds
            group = 'held_out' if t in held else 'evaluation_other' if t in evs else 'training'
            extra, over = {}, case_rows.get(t) or hand_rows.get(t)
            if t in evs:  # the census reads these stems from points-eval.json
                base_sexp = next(p for p in json.load(open(HELP + 'points-eval.json')) if p['task'] == t)['gold_sexp']
                pre = over['program'] if over else base_sexp
                cut = prune_rows.get(t)
                if cut and cut['base'] != sha(pre):
                    stale.append(t)
                    cut = None
                sexp = cut['program'] if cut else pre
                if sexp != base_sexp:
                    late[t] = sexp
                if over:
                    extra['later'] = 'case-choice' if t in case_rows else 'hand-rewrite'
                    counts[extra['later'] + ', stems with no folder', group] += 1
                if cut:
                    extra.update(pruned=True, forms_dropped=[dict(form=x, kind=x.split()[0][1:], label='pruned') for x in cut['dropped']])
                    sums['pruned', group] += len(cut['dropped'])
                    dropped_kinds.update(x.split()[0][1:] for x in cut['dropped'])
                    counts['pruned, stems', group] += 1
                if sexp != next((p['gold_sexp'] for p in json.load(open('points-eval.json')) if p['task'] == t), None):
                    rebuilt.append(t)
            out.write(json.dumps(dict(stem=t, source='absent', why='no folder in the helper view', held_out=t in held, evaluation=t in evs, forms_changed=[], **extra)) + '\n')
            counts['absent', group] += 1
    if os.stat(view).st_mtime_ns != stamp:
        sys.exit('the helper view was rebuilt during the read; run again')
    if '--dry' in sys.argv:  # builds and counts, swaps nothing
        print('dry:', len(rebuilt), 'stems would change', sorted(rebuilt)[:20], 'stale', stale, 'not mapped', lost, dict(sums), dict(counts))
        shutil.rmtree(tmp)
        os.remove('view-stems.jsonl.new')
        return
    swap_in(tmp, ev, rows, helpers, pool_held, bits, counts, sums, lost, sides, stamp, torn, late, stale, rebuilt, dropped_kinds, hand_rows, case_rows)


def swap_folders(new, cur):
    """Swaps two folders in one atomic rename, then removes the old one. A reader sees one view or the other, and an open file stays whole."""
    if not os.path.exists(cur):
        os.rename(new, cur)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.renamex_np(new.encode(), cur.encode(), RENAME_SWAP):
        raise OSError(ctypes.get_errno(), 'renamex_np')
    shutil.rmtree(new)


def swap_in(tmp, ev, rows, helpers, pool_held, bits, counts, sums, lost, sides, stamp, torn, late, stale, rebuilt, dropped_kinds, hand_rows, case_rows):
    points = {p['task']: p for p in json.load(open(HELP + 'points-eval.json'))}
    pts = []
    for t in ev:
        p = points[t]
        if os.path.isdir(tmp + '/' + t):
            p = dict(task=t, gold_sexp=first_row(tmp + '/' + t + '/pairs.jsonl.gz')['gold_sexp'])
        elif t in late:
            p = dict(task=t, gold_sexp=late[t])
        pts.append(p)
    for name, value in (('points-eval.json', pts), ('helpers.json', helpers)):
        with open(name + '.new', 'w') as f:
            json.dump(value, f)
        os.replace(name + '.new', name)
    os.replace('view-stems.jsonl.new', 'view-stems.jsonl')
    with open('kind-mix.json.new', 'w') as f:
        json.dump(dict(note='Forms by head kind, stems by clause count, and forms by both, in the buckets of the priors next-kind counts (clause count without OUT, step %d, top bucket %d). A group is the stems of the view in it.' % (KIND_STEP, KIND_TOP), training={'helper view': mix(sides['training'][0]), 'this view': mix(sides['training'][1])}, held_out={'helper view': mix(sides['held_out'][0]), 'this view': mix(sides['held_out'][1])}, evaluation_other={'helper view': mix(sides['evaluation_other'][0]), 'this view': mix(sides['evaluation_other'][1])}), f, indent=1)
    os.replace('kind-mix.json.new', 'kind-mix.json')
    with open('census-bits.json.new', 'w') as f:
        json.dump(dict(note='Forms of held-out stems that this revision takes from a pool, with gold text bits and this view bits, as the rows give them. The view column falls by selection, since the pool picked these clauses on those tasks. Census horizon figures stay on round 50 text.', priors='sampler-priors-refit-heldout-8a5ffec60', columns=dict(gold_bits='bits of each gold form taken out', view_bits='bits of each form in their place'), rows=bits, gold_sum=round(sum(sum(b['gold_bits']) for b in bits), 2), view_sum=round(sum(sum(b['view_bits']) for b in bits), 2)), f, indent=1)
    os.replace('census-bits.json.new', 'census-bits.json')
    with open('round-out/rebuild-stems.txt.new', 'w') as f:
        f.write(''.join(t + '\n' for t in sorted(rebuilt)))
    os.replace('round-out/rebuild-stems.txt.new', 'round-out/rebuild-stems.txt')
    swap_folders(tmp, 'corpus-view')
    date = time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime(stamp / 1e9))
    source_counts = collections.Counter()
    for (s, _), v in counts.items():
        if ', stems' not in s:
            source_counts[s] += v
    entry = dict(
        revision=REVISION,
        scope='every stem of the helper view, the 37 held-out and the 99 evaluation tasks included; a stem of gen-v3 with no folder in the helper view is listed in view-stems.jsonl as absent',
        rule='A stem takes its row program when the row read, swapped is not empty, and the text the row started from is gen-v3 current text. Every other stem takes what the helper view holds. A later row replaces an earlier row of its stem.',
        later_sources='In order, after the rule: hand-rewrite (round-out/hand-rewrites.jsonl), case-choice (round-out/case-choice.jsonl), pruned (round-out/prune-rows.jsonl). Cheapest: fewer undrawable forms, then the lower worst form, then the lower sum, in the all-earlier-forms context.',
        stems=dict(total=sum(source_counts.values()), by_source=dict(source_counts), by_source_and_group={'%s, %s' % k: v for k, v in sorted(counts.items())}, hand_rewrite=sorted(hand_rows), hand_rewrite_count=len(hand_rows), case_choice_count=len(case_rows), pruned_count=sum(v for k, v in counts.items() if k[0] == 'pruned, stems'), prune_rows_stale=stale),
        forms_dropped_by_kind=dict(sorted(dropped_kinds.items())),
        base=dict(text='gold-v3-rigid-round50, concept case of each stem, in current-text.json', rows='gold-v3-size-faults-round48 in pod-out, current text in round-out'),
        runtime=dict(pod_rows='pod 2kjovy8e83mje6, venv with wheel_engine', mac_rows='runtime-ba0754492', current_text='runtime-ba0754492'),
        wheel_engine=dict(commit='c87cf482a', file='arclog-0.1.0-cp312-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl', sha256='eeebf281685646614e0935a8ac976aa6099c6b1dc1f4e1bb3499df0aabaef57d'),
        wheel_engine_mac=dict(commit='ba0754492', runtime='runtime-ba0754492', sha256='a3278497561b3fabbb5d90edb1f2c3845dbe54091d29d95f055fd299e64900d8', so_sha256='4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371'),
        helper_view=dict(path=HELP + 'corpus-view', date=date),
        fit=dict(reads=['corpus-view/<stem>/pairs.jsonl.gz, first row, gold_sexp'], command='SAMPLER_CORPUS=<revision>/corpus-view/ live_priors.py --out <file> --leave-out <leave_out>', leave_out=LEAVE_OUT, rule='held-out and evaluation rows stay out of any fit; the list is the helper arm list, unchanged'),
        census_reads=['points-eval.json', 'helpers.json', 'lines.json'],
        forms_changed=dict(meaning='forms with no equal form in gen-v3 once relation names are masked', by_label_and_group={'%s, %s' % k: v for k, v in sorted(sums.items())}, forms='view-stems.jsonl, forms_changed'),
        pool_picked_heldout=pool_held,
        helpers_not_mapped=lost,
        torn_row_lines=torn,
    )
    m = json.load(open('manifest.json'))
    old = m.get('views', {}).get('corpus-view', {})
    for k in ('census_heldout', 'census_heldout_before_rebuild', 'bands', 'cover_worst'):
        if k in old:
            entry[k] = old[k]
    m.update(revision=REVISION, gen_v3_comparison='gold-v3-rigid-round50')
    m.setdefault('views', {})['corpus-view'] = entry
    with open('manifest.json.new', 'w') as f:
        json.dump(m, f, indent=1)
    os.replace('manifest.json.new', 'manifest.json')
    print(len(rebuilt), 'stems changed;', len(rows), 'rows;', dict(source_counts), {'%s, %s' % k: v for k, v in sums.items()}, 'helpers not mapped', len(lost), 'helper view', date)


if __name__ == '__main__':
    main()
