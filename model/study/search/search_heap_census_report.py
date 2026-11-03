#!/usr/bin/env python3
"""What the Python heap of a search worker holds, from one out folder, streamed or finished. It reads the `census` and `sites` lines of the worker logs.

  python3 search_heap_census_report_fixed.py OUT_FOLDER

OUT_FOLDER holds <arm>/<task>/work/<task>.log, or holds out/ with those folders. A log with no census line is left out.

A renewal is three censuses: before_renewal in generation g, then after_load and later in generation g + 1. Each table uses a renewal that has all three, the one whose RSS at before_renewal is nearest 2,000 MiB. Under tracemalloc, where RSS doesn't compare, it uses the first that has all three. With no such renewal it uses the first, and a census it lacks has `-` in those columns. A run with no before_renewal census prints its last census and sites, with no renewal columns.

Columns:
  MiB, objects    at before_renewal
  share           of all the census's bytes, or of all the bytes that tracemalloc lists for a site table, and not of the rows that the line lists
  load MiB        at after_load, in the next process
  load freed      1 less load MiB over MiB: the share a renewal frees at once
  later MiB       at the later census, about 60 s after the load
  later freed     1 less later MiB over MiB: the share still free then; a negative share means more bytes than before the renewal

A census line lists its top 60 types, its top 60 sites and its top 30 holders. A row that the next census doesn't list has that census's smallest listed value as its bound, marked `<`, and its share has `>`.

The group table adds the holders of hot and of given-up runs, because a run that is hot at one census can be given up at the next. A row of the holder table alone doesn't compare across a renewal.

Reached is the census's bytes of 512 or less over pymalloc's live bytes. It is the check on the walk: what is under 100% lies outside the walk, or is sizes that sys.getsizeof leaves out. pymalloc prints nothing under tracemalloc, so the heap-sites arm has none, and the block counts compare the arms in its place.

Row statuses: each _OwnedBytes past the COLUMNS of each CaseTables is one row's extent status, with its own __dict__. The rows column is an estimate from the code of CaseTables, since a census has no row for them. Its MiB uses ROW_CENSUS bytes each, as a census counts them, and ROW_POOL bytes each, as pymalloc allocates them on Python 3.12.

type_sites comes from one object in 16 of the walk, so one large object moves it. The sum of a type's sites can pass the type's bytes. Read it as an order, and not as MiB.
"""
import collections
import glob
import json
import os
import sys

M = 2 ** 20
TARGET_RSS = 2000
ROWS = 20
PHASES = 'before_renewal', 'after_load', 'later'
COLUMNS = 39  # integer columns of a CaseTables, and values
ROW_CENSUS, ROW_POOL = 384, 416
OWNED, CASES = '_arclog_buffer_owner._OwnedBytes', 'arclog.CaseTables'


def say(*a):
    print(*a, flush=True)


def load(path):
    """(census lines, sites lines, lines that a stream cut) of a worker log."""
    out = dict(census=[], sites=[])
    cut = 0
    with open(path, errors='replace') as f:
        for line in f:
            name = line.partition(' ')[0]
            if name in out and line[len(name) + 1:].startswith('{'):
                try:
                    out[name].append(json.loads(line[len(name) + 1:]))
                except ValueError:
                    cut += 1
    return out['census'], out['sites'], cut


def read_folder(folder):
    if os.path.isdir(os.path.join(folder, 'out')):
        folder = os.path.join(folder, 'out')
    runs = {}
    for path in sorted(glob.glob(os.path.join(folder, '*', '*', 'work', '*.log'))):
        parts = path.split(os.sep)
        census, sites, cut = load(path)
        if census or sites:
            runs[parts[-4], parts[-3]] = dict(census=census, sites=sites, cut=cut)
    return runs


def by_key(rows):
    return {(x.get('generation'), x.get('phase')): x for x in rows if 'error' not in x}


def renewals(run):
    """[(census lines of a renewal, sites lines of it)], the one a table uses first."""
    cs, ss = by_key(run['census']), by_key(run['sites'])
    out = []
    for g, phase in sorted(k for k in cs if k[1] == 'before_renewal'):
        out.append(tuple({p: d.get((g + (p != 'before_renewal'), p)) for p in PHASES} for d in (cs, ss)))

    def rank(r):
        c = r[0]['before_renewal']
        whole = all(r[0].values())
        return not whole, 0 if 'traced' in c else abs(c['rss'] - TARGET_RSS), c['generation']
    return sorted(out, key=rank)


def fmt_mib(x):
    return '-' if x is None else '%.0f' % (x / M)


class Later:
    """A value of a row at a later census: its bytes, or its bound where the census doesn't list it."""

    def __init__(self, table, line):
        self.table, self.line = table, line

    def get(self, name):
        """(bytes, whether this is only a bound), or (None, False) with no census."""
        if self.line is None:
            return None, False
        if name in self.table:
            return self.table[name], False
        return (min(self.table.values()) if self.table else 0), True


def rows_of(line, key):
    """{name: (bytes, count)} of a list in a census or sites line."""
    return {x[0]: (x[1], x[2]) for x in (line or {}).get(key, ())}


def cell(base, later):
    """The MiB and share columns of one later census. A bound's share stops at 99%, since a share over a bound never reaches 100%."""
    got, bound = later
    if got is None:
        return ['-', '-']
    share = 100 * (1 - got / base) if base else 0
    return ['%s%.0f' % ('<' if bound else '', got / M), '>%.0f%%' % min(share, 99) if bound else '%.0f%%' % share]


def table(title, base, load_, later, first='name', total=None, rows=ROWS):
    """Prints rows of {name: (bytes, count)} base, by bytes, with the two later censuses. total is the census's bytes, which share divides by."""
    total = total or sum(v[0] for v in base.values())
    say('%s' % title)
    head = [first, 'MiB', 'objects', 'share', 'load MiB', 'load freed', 'later MiB', 'later freed']
    out = [head, ['---'] * len(head)]
    a = Later({k: v[0] for k, v in load_.items()}, load_ if load_ else None)
    b = Later({k: v[0] for k, v in later.items()}, later if later else None)
    for name, (size, n) in sorted(base.items(), key=lambda x: -x[1][0])[:rows]:
        out.append([name, '%.0f' % (size / M), '{:,}'.format(n), '%.1f%%' % (100 * size / total if total else 0)] + cell(size, a.get(name)) + cell(size, b.get(name)))
    for r in out:
        say('| ' + ' | '.join(r) + ' |')
    say('')


def plain_table(title, base, first, total, rows=ROWS):
    say(title)
    say('| %s | MiB | objects | share |' % first)
    say('| --- | --- | --- | --- |')
    for name, (size, n) in sorted(base.items(), key=lambda x: -x[1][0])[:rows]:
        say('| %s | %.1f | %s | %.1f%% |' % (name, size / M, '{:,}'.format(n), 100 * size / total))
    say('')


def group_of(name):
    """The row of the group table that a holder adds to."""
    for mark, group in (('SearchRun given up.memo[table]', 'memo[table], given-up runs'), ('SearchRun.memo[table]', 'memo[table], hot runs'), ('SearchRun given up', 'other holders of given-up runs'), ('SearchRun', 'other holders of hot runs')):
        if name.startswith(mark):
            return group
    return {'rest': 'rest', 'Policy.nodes': 'Policy.nodes', 'module sample2_col.DROWS': 'module sample2_col.DROWS'}.get(name, 'other named holders')


def groups(line):
    """{group: bytes} of a census line."""
    out = collections.Counter()
    for x in (line or {}).get('holders', ()):
        out[group_of(x[0])] += x[1]
    return out


GROUPS = 'memo[table], given-up runs', 'memo[table], hot runs', 'other holders of given-up runs', 'other holders of hot runs', 'rest', 'Policy.nodes', 'module sample2_col.DROWS', 'other named holders'


def renewal_row(r):
    """The cells of one renewal for the group table."""
    b, l, n = lists(r, 0)
    gb, gl, gn = groups(b), groups(l), groups(n)
    cells = []
    for g in GROUPS:
        cells.append('%.0f, %.0f, %s' % (gb[g] / M, gl[g] / M, '%.0f' % (gn[g] / M) if n else '-'))
    runs = (b['retained'].get('runs', 0))
    return [str(b['generation']), '%s, %s, %s' % (b['rss'], l['rss'] if l else '-', n['rss'] if n else '-'), '%s, %s, %s' % (fmt_mib(b.get('bytes')), fmt_mib(l and l.get('bytes')), fmt_mib(n and n.get('bytes'))), str(runs)] + cells


def row_statuses(c):
    """(rows, CaseTables): an estimate of the row statuses of a census line, or None where the line doesn't list CaseTables."""
    t = rows_of(c, 'types')
    if CASES not in t or OWNED not in t:
        return None
    return t[OWNED][1] - COLUMNS * t[CASES][1], t[CASES][1]


def lists(r, which):
    """The three lines of a renewal for a table: which is 0 for census lines, 1 for sites lines."""
    return [r[which][p] for p in PHASES]


def task_tables(arm, task, r, others):
    (cb, cl, cn), (sb, sl, sn) = lists(r, 0), lists(r, 1)
    say('## %s %s: renewal after generation %s' % (arm, task, cb['generation']))
    say('RSS MiB at before_renewal %s, after_load %s, later %s; census bytes MiB %s, %s, %s.' % (cb['rss'], cl['rss'] if cl else '-', cn['rss'] if cn else '-', fmt_mib(cb.get('bytes')), fmt_mib(cl and cl.get('bytes')), fmt_mib(cn and cn.get('bytes'))))
    if others:
        say('Other renewals, RSS and census MiB at before_renewal, after_load, later: ' + '; '.join(
            'generation %s: %s' % (o[0]['before_renewal']['generation'], ', '.join('%s %s' % (x['rss'], fmt_mib(x.get('bytes'))) if x else '-' for x in lists(o, 0))) for o in others))
    say('')
    table('Top types', rows_of(cb, 'types'), rows_of(cl, 'types'), rows_of(cn, 'types'), 'type', cb['bytes'])
    table('Top holders: the attribute that first reaches the bytes', rows_of(cb, 'holders'), rows_of(cl, 'holders'), rows_of(cn, 'holders'), 'holder', cb['bytes'])
    if sb:
        table('Top sites', rows_of(sb, 'sites'), rows_of(sl, 'sites'), rows_of(sn, 'sites'), 'site', sb['bytes'])
    type_sites(cb)
    say('Largest objects: ' + '; '.join('%s of %s entries, %s MiB, %s' % (name, n, fmt_mib(b), holder) for b, name, n, holder in cb.get('big', ())[:5]))
    say('Given-up runs: %s' % json.dumps(cb.get('retained', {})))
    say('')


def type_sites(c):
    if c.get('type_sites'):
        say('Sites of the top types, from one object in 16 of the walk: an order, and not MiB. The first number after a type is what its listed sites sum to, over its bytes in the census')
        t = rows_of(c, 'types')
        for name, sites in c['type_sites'].items():
            say('- %s (%.2f): %s' % (name, sum(b for _, b in sites) / t[name][0] if name in t else 0, ', '.join('%s %.0f' % (s, b / M) for s, b in sites)))
        say('')


def last_tables(arm, task, run):
    """The tables of a run with no before_renewal census: its last census and sites."""
    good = [c for c in run['census'] if 'error' not in c]
    if not good:
        return
    c = good[-1]
    say('## %s %s: no before_renewal census; the last census is %s of generation %s at %s s, RSS %s' % (arm, task, c['phase'], c['generation'], c['t'], c['rss']))
    say('')
    plain_table('Top types', rows_of(c, 'types'), 'type', c['bytes'])
    plain_table('Top holders', rows_of(c, 'holders'), 'holder', c['bytes'])
    s = by_key(run['sites']).get((c['generation'], c['phase']))
    if s:
        plain_table('Top sites, of %s MiB that tracemalloc lists' % fmt_mib(s['bytes']), rows_of(s, 'sites'), 'site', s['bytes'])
    type_sites(c)
    say('Given-up runs: %s' % json.dumps(c.get('retained', {})))
    say('')


def pooled(chosen, which, key):
    """Sums over tasks: {name: (bytes, count)} per phase. A row that one task's census doesn't list adds nothing for that task, so its freed share can read a little high."""
    out = [collections.Counter(), collections.Counter(), collections.Counter()]
    counts = collections.Counter()
    for r in chosen:
        for i, line in enumerate(lists(r, which)):
            for name, (size, n) in rows_of(line, key).items():
                out[i][name] += size
                counts[name] += n if i == 0 else 0
    return [{k: (v, counts[k]) for k, v in c.items()} for c in out]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    runs = read_folder(sys.argv[1])
    if not runs:
        sys.exit('no census line under %s' % sys.argv[1])
    say('# Censuses')
    rows = [['arm', 'task', 'generation', 'phase', 't s', 'RSS', 'py alloc', 'py total', 'blocks M', 'traced', 'tracer', 'census MiB', 'objects M', 'reached', 'census s', 'sites s']]
    rows.append(['---'] * len(rows[0]))
    for (arm, task), run in sorted(runs.items()):
        sites = by_key(run['sites'])
        for c in run['census']:
            if 'error' in c:
                rows.append([arm, task, str(c.get('generation')), str(c.get('phase')), str(c.get('t')), 'failed: %s' % c['error'][:80]] + [''] * 10)
                continue
            py, s = c.get('py_alloc'), sites.get((c['generation'], c['phase']))
            rows.append([arm, task, str(c['generation']), c['phase'], str(c['t']), str(c['rss']), fmt_mib(py), fmt_mib(c.get('py_total')), '%.1f' % (c['blocks'] / 1e6) if 'blocks' in c else '-', fmt_mib(c.get('traced')), fmt_mib(c.get('trace_memory')),
                         fmt_mib(c.get('bytes')), '%.1f' % (c.get('objects', 0) / 1e6), '%.0f%%' % (100 * c['small'] / py) if py and 'small' in c else '-', str(c.get('seconds', '-')), str(s['seconds']) if s else '-'])
        for s in run['sites']:
            if 'error' in s:
                rows.append([arm, task, str(s.get('generation')), str(s.get('phase')), str(s.get('t')), 'sites failed: %s' % s['error'][:80]] + [''] * 10)
    for r in rows:
        say('| ' + ' | '.join(r) + ' |')
    say('')
    if any(run['cut'] for run in runs.values()):
        say('Lines that a stream cut: %d' % sum(run['cut'] for run in runs.values()))
        say('')
    say('# Each renewal, by group of holders: MiB before the renewal, after the load, about 60 s later')
    head = ['arm', 'task', 'generation', 'RSS', 'census', 'given-up runs'] + list(GROUPS)
    say('| ' + ' | '.join(head) + ' |')
    say('| ' + ' | '.join(['---'] * len(head)) + ' |')
    for (arm, task), run in sorted(runs.items()):
        for r in sorted(renewals(run), key=lambda r: r[0]['before_renewal']['generation']):
            say('| ' + ' | '.join([arm, task] + renewal_row(r)) + ' |')
    say('')
    say('# Row statuses at before_renewal: an estimate')
    say('| arm | task | generation | CaseTables | row statuses | MiB as a census counts them | share of the census | MiB in pymalloc | share of py alloc |')
    say('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    for (arm, task), run in sorted(runs.items()):
        for r in sorted(renewals(run), key=lambda r: r[0]['before_renewal']['generation']):
            c = r[0]['before_renewal']
            got = row_statuses(c)
            if got:
                n, cases = got
                py = c.get('py_alloc')
                say('| %s | %s | %s | %s | %s | %.0f | %.1f%% | %.0f | %s |' % (arm, task, c['generation'], '{:,}'.format(cases), '{:,}'.format(n), n * ROW_CENSUS / M, 100 * n * ROW_CENSUS / c['bytes'], n * ROW_POOL / M, '%.1f%%' % (100 * n * ROW_POOL / py) if py else '-'))
    say('')
    chosen = collections.defaultdict(list)
    for (arm, task), run in sorted(runs.items()):
        found = renewals(run)
        if not found:
            last_tables(arm, task, run)
            continue
        task_tables(arm, task, found[0], found[1:])
        chosen[arm].append(found[0])
    for arm, picked in sorted(chosen.items()):
        if len(picked) > 1:
            say('## %s: %d tasks together' % (arm, len(picked)))
            say('')
            total = sum(r[0]['before_renewal']['bytes'] for r in picked)
            b, l, n = pooled(picked, 0, 'types')
            table('Top types', b, l, n, 'type', total)
            b, l, n = pooled(picked, 0, 'holders')
            table('Top holders', b, l, n, 'holder', total)
            if any(r[1]['before_renewal'] for r in picked):
                b, l, n = pooled(picked, 1, 'sites')
                table('Top sites', b, l, n, 'site', sum(r[1]['before_renewal']['bytes'] for r in picked))
    tasks = sorted({t for _, t in runs})
    arms = sorted({a for a, _ in runs})
    if len(arms) > 1:
        say('# Do the arms compare? Blocks at before_renewal, millions, by generation')
        for t in tasks:
            got = {a: ['g%d %.1f' % (r[0]['before_renewal']['generation'], r[0]['before_renewal'].get('blocks', 0) / 1e6) for (x, y), v in runs.items() if x == a and y == t for r in sorted(renewals(v), key=lambda r: r[0]['before_renewal']['generation'])] for a in arms}
            say('- %s: %s' % (t, ', '.join('%s %s' % (a, ' '.join(v) or '-') for a, v in got.items())))


if __name__ == '__main__':
    main()
