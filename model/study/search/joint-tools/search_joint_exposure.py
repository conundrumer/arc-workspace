"""The two measures that the joint read adds: forms covered by the gold form's read count, and the live exposure by read count.

Both follow set-pick/design.md and r1-forms/read.md (job.py and analyze.py of that folder).

Reads of a gold form: gold_info(gold_sexp)['reads'][g], the gold forms that form g reads. A form with 0 reads reads no other gold form.

Forms covered: the gold forms with a cover line. Split by the read count: 0, 1, and 2 or more. At 60 s, the forms whose first cover line is within 60 s of the job's start file.

Live exposure, as analyze.py counts right-scope openings:
  - An opening is a line of the picks file that has picked nodes. The openings are in the order of their time.
  - A cover line is kept where the bank's lineage holds its process and the line's node is in the node range of that process.
  - A gold form g with reads can be exposed where each of its reads has a kept cover line (at any time).
  - At an opening, g is exposed where g has no cover line before the opening, and for each read of g a kept cover line of that read has a time before the opening and a node
    that is among the opening's picked nodes.
  - The exposure of an opening is its list of exposed forms. The opening counts for `any` where the list is not empty, for `reads1` where a form in it has 1 read, and for
    `reads2` where a form in it has 2 or more reads.
  - The share is the count over the openings. At 60 s, only the openings within 60 s of the start file count.
The bank is needed for its lineage only. Covers after the last bank save are not kept, so the exposures are lower bounds.
"""
import collections
import os

SECONDS = 60
INF = float('inf')


def read_class(n):
    """The read-count class of a gold form: 0, 1 or 2 (two or more)."""
    return min(n, 2)


def covered_by_reads(covered, cover_t, reads, seconds=None):
    """{'0': n, '1': n, '2+': n} of the gold forms in covered (all of them where seconds is None, else those with cover_t at most seconds)."""
    got = collections.Counter()
    for g in covered:
        if g >= len(reads):
            continue
        if seconds is not None and not (g in cover_t and cover_t[g] <= seconds):
            continue
        got[read_class(len(reads[g]))] += 1
    return {'0': got[0], '1': got[1], '2+': got[2]}


def start_of(folder, picks):
    """The time of the job's start file, else the time of its first picks line, else None."""
    try:
        return float(open(folder + '/start').read().split()[0])
    except (OSError, ValueError, IndexError):
        return min((p['time'] for p in picks), default=None)


def exposure(picks, covers, lineage, reads, start, seconds=(None, SECONDS)):
    """{str(seconds): {'openings': n, 'any': n, 'reads1': n, 'reads2': n}} for each horizon in seconds (None: the whole job; the key is 'all').
    picks: the picks lines. covers: the cover lines. lineage: the bank's lineage entries. reads: the gold form's reads lists. start: the start time or None."""
    ops = sorted((p for p in picks if p.get('picks')), key=lambda p: p['time'])
    lin = {e['proc']: e for e in lineage}
    first = {}
    kept = collections.defaultdict(list)
    for c in covers:
        first[c['gold']] = min(first.get(c['gold'], INF), c['time'])
        e = lin.get(c.get('proc'))
        if e is not None and e['nodes0'] <= c['node'] < e['nodes1']:
            kept[c['gold']].append((c['time'], c['node']))
    forms = [g for g, rd in enumerate(reads) if rd and all(kept.get(q) for q in rd)]
    out = {('all' if s is None else str(s)): collections.Counter() for s in seconds}
    for o in ops:
        ps = set(o['picks'])
        hit = [g for g in forms if first.get(g, INF) >= o['time'] and all(any(t < o['time'] and n in ps for t, n in kept[q]) for q in reads[g])]
        for s in seconds:
            if s is not None and (start is None or o['time'] - start > s):
                continue
            c = out['all' if s is None else str(s)]
            c['openings'] += 1
            c['any'] += bool(hit)
            c['reads1'] += any(len(reads[g]) == 1 for g in hit)
            c['reads2'] += any(len(reads[g]) >= 2 for g in hit)
    return {k: {m: v[m] for m in ('openings', 'any', 'reads1', 'reads2')} for k, v in out.items()}


def job_measures(PA, folder, task, reads, covered, cover_t, bank):
    """The record of one job for the read: forms covered by reads and exposure, at the whole job and at 60 s. bank: the loaded bank (PA.load_bank) or None."""
    work = '%s/work/%s' % (folder, task)
    picks = PA.read_lines(work + '.out.jsonl.picks')
    rec = dict(by_reads={'all': covered_by_reads(covered, cover_t, reads), str(SECONDS): covered_by_reads(covered, cover_t, reads, SECONDS)}, exposure=None)
    if bank is not None and bank.get('lineage') is not None:
        rec['exposure'] = exposure(picks, PA.read_lines(work + '.out.jsonl.cover'), bank['lineage'], reads, start_of(folder, picks))
    return rec


def share(c, key):
    return 100.0 * c[key] / c['openings'] if c and c['openings'] else float('nan')


def add_counts(a, b):
    return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}


def table(rows):
    """Markdown-ish lines of rows: a list of lists of cells, the first row the header."""
    out = ['| ' + ' | '.join(rows[0]) + ' |', '|' + ' --- |' * len(rows[0])]
    out += ['| ' + ' | '.join(r) + ' |' for r in rows[1:]]
    return out
