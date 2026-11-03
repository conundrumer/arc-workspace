"""The covering clause step of a regold round: runs gold_cover_one.py on the current text of the round's stems. A candidate moves to the form of current text with the text of the form it replaces, relation names masked, and drops where that form is gone. A stem runs once, alone, under 15 min and 8 GB, and a stem past a cap keeps the helper text. A stem with no candidate left is skipped. Refreshes each stem in current-text.json.

  <runtime python> gold_cover_round.py ROUND STEM...
Rows go to round-out/rows-<round>.jsonl, and a stem with a row in that file does not run again. Crossing clauses come from the helper revision's latest census of the stem.
"""
import glob, hashlib, json, os, re, subprocess, sys, time
import arclog
from gold_cover_text import concept, save

HELP = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-helper-forms-a036da074/'
SECONDS, BYTES = 900, 8 << 30
RUNTIME = 'runtime-ba0754492'
SO_SHA256 = '4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371'
WHEEL_SHA256 = 'a3278497561b3fabbb5d90edb1f2c3845dbe54091d29d95f055fd299e64900d8'
NAME = re.compile(r'&[A-Za-z_0-9]+')
n, stems = sys.argv[1], sys.argv[2:]


def crossing_of(t, lines):
    """The stem's crossing clauses from the latest helper census that lists it, kept where the clause text is the text that census read."""
    files = [(HELP + 'crossing.json', HELP + 'lines.json')]
    for f in sorted(glob.glob(HELP + 'round-out/crossing-*.json'), key=os.path.getmtime):
        files.append((f, f.replace('crossing-', 'lines-')))
    for cross, read in reversed(files):
        got = json.load(open(cross))
        if t in got:
            text = json.load(open(read)).get(t, lines) if os.path.exists(read) else lines
            return [c for c in got[t] if c['line'] < min(len(lines), len(text)) and lines[c['line']] == text[c['line']]]
    return []


def moved(cands, old, lines):
    """The candidates on current text. A form of the old text pairs with the form of current text that has its text once relation names are masked, in order. A candidate moves to the line of the form it replaces, and its reads of old forms take their current names. It drops where the form it replaces, or a form it reads, is gone. Returns the candidates and the count dropped."""
    free = {}
    for k, x in enumerate(lines):
        free.setdefault(NAME.sub('&_', x), []).append(k)
    place = {i: free[NAME.sub('&_', x)].pop(0) for i, x in enumerate(old) if free.get(NAME.sub('&_', x))}
    heads = {NAME.search(x)[0]: i for i, x in enumerate(old) if NAME.search(x)}
    names = {n: NAME.search(lines[place[i]])[0] for n, i in heads.items() if i in place}
    out, gone = [], 0
    for c in cands:
        reads = {n for f in c['forms'] for n in NAME.findall(f)}
        if c['line'] not in place or any(n in heads and n not in names for n in reads):
            gone += 1
            continue
        out.append(dict(c, line=place[c['line']], forms=[NAME.sub(lambda m: names.get(m[0], m[0]), f) for f in c['forms']]))
    return out, gone


def run(t, lp, cp, vp):
    """One stem under the caps: its row, with its peak and its time."""
    t0, peak = time.time(), 0
    with open(f'round-out/rows-{n}.log', 'a') as err:
        p = subprocess.Popen([sys.executable, '-u', 'gold_cover_one.py', t, lp, cp, vp], stdout=subprocess.PIPE, stderr=err, text=True)
        killed = None
        while p.poll() is None and killed is None:
            time.sleep(1)
            q = subprocess.run(['ps', '-o', 'rss=', '-p', str(p.pid)], capture_output=True, text=True).stdout.strip()
            peak = max(peak, int(q or 0) * 1024)
            killed = 'time' if time.time() - t0 > SECONDS else 'memory' if peak > BYTES else None
        if killed:
            p.kill()
        out = p.communicate()[0]
    rows = [l for l in out.splitlines() if l.startswith('{"task"')]
    row = dict(task=t, error=killed) if killed else json.loads(rows[-1]) if rows else dict(task=t, error='no row, exit %s' % p.returncode)
    row.update(wall=round(time.time() - t0, 1), peak_gib=round(peak / (1 << 30), 2))
    return row


def main():
    so = hashlib.sha256(open(os.path.join(os.path.dirname(arclog.__file__), 'arclog.abi3.so'), 'rb').read()).hexdigest()
    if so != SO_SHA256:
        sys.exit('arclog is not the wheel of the manifest')
    os.makedirs('round-out', exist_ok=True)
    text = json.load(open('current-text.json'))
    base, covers = json.load(open('lines.json')), json.load(open('covers.json'))
    lp, cp, vp = f'round-out/lines-{n}.json', f'round-out/crossing-{n}.json', f'round-out/covers-{n}.json'
    lines, cuts, cands, dropped = {}, {}, {}, {}
    for p, d in ((lp, lines), (cp, cuts), (vp, cands)):
        if os.path.exists(p):
            d.update(json.load(open(p)))
    for t in stems:
        text[t] = concept(t)
        lines[t] = text[t]['lines']
        cuts[t] = crossing_of(t, lines[t])
        cands[t], dropped[t] = moved(covers.get(t, []), base.get(t, []), lines[t])
    save(text)
    for p, d in ((lp, lines), (cp, cuts), (vp, cands)):
        json.dump(d, open(p, 'w'))
    path = f'round-out/rows-{n}.jsonl'
    done = {json.loads(l)['task'] for l in open(path)} if os.path.exists(path) else set()
    with open(path, 'a') as out:
        for t in stems:
            if t in done or not cands[t]:
                print(t, 'no run,', len(cands[t]), 'candidates,', dropped[t], 'dropped', flush=True)
                continue
            row = run(t, lp, cp, vp)
            row.update(dropped=dropped[t], runtime=RUNTIME, wheel_sha256=WHEEL_SHA256)
            out.write(json.dumps(row) + '\n')
            out.flush()
            print({k: v for k, v in row.items() if k != 'program'}, flush=True)
    m = json.load(open('manifest.json'))
    runs = m.setdefault('passes', [])
    entry = dict(rows=path, round=n, stems=sorted(lines), code='gold_cover_round.py', host='Mac', wheel_engine=dict(commit='ba0754492', runtime=RUNTIME, sha256=WHEEL_SHA256), caps='900 s, 8 GiB, no retry', note='A row here replaces the row of its stem in pod-out.')
    runs[:] = [r for r in runs if r.get('rows') != path] + [entry]
    with open('manifest.json.new', 'w') as f:
        json.dump(m, f, indent=1)
    os.replace('manifest.json.new', 'manifest.json')


if __name__ == '__main__':
    main()
