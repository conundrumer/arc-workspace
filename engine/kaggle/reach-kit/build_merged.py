#!/usr/bin/env python3
"""Union records for the reach measurement kit from the merged union files (gold/gold-union/union-<set>.jsonl and union-<set>-addendum.jsonl), one task a line, streamed to records-<set>.jsonl next to this script; a restart skips tasks it has. A task whose merged line has no tables is set aside and gets no record. A task with no merged line takes the text-level record of union-identity-<set>.jsonl through build.py's union_record, and gets its merged record on a later run once one exists.

  SAMPLER_CODE=<kit>/model/study/sampler PYTHONPATH=<repo>/model/study/gold/cover_forms:<arclog site> <runtime python> build_merged.py [--jobs N] [--merged-only] SET...

Each kept program of a task is put in normal form as gold_union.py does (Bar.normal), so its forms' identities are those of the merged file; each form's union key is the key of the table whose forms hold that identity.
"""
import json, multiprocessing, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('UNION_REACH_OUT', '/Users/davidlu/code/arc-workspace/work/synth-kaggle/kit-union-read')  # the kit, its records and its maps; the scripts live in the repo
UNION = os.environ.get('GOLD_UNION_DIR', '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union').rstrip('/') + '/'  # the union files' folder
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/model/study/gold/reads/union')
sys.path.insert(0, HERE)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../../model/study'))  # study_zst.py
import study_zst as Z  # noqa: E402  the union files and the records are zstd streams or plain files, whichever is on disk
import gold_union as U  # noqa: E402
import build as B  # noqa: E402


def merged_record(rec, pubs, ex):
    t = rec['task']
    bar = U.Bar(t)
    key = {f['ident']: x['key'] for x in rec['tables'] for f in x['forms']}
    texts = {'pinned': U.G.pinned(t)}
    for c in (pubs[t][1]['cases'] if t in pubs else []):
        texts.setdefault(c['case'], c.get('filtered_program') or c.get('original_program') or '')
    by_prog = {}
    for case, pid in rec['cases'].items():
        by_prog.setdefault(pid, []).append(case)
    programs, missing = [], 0
    for pid, cases in by_prog.items():
        if pid in rec['left_out'] or pid not in rec['programs']:
            continue
        norm, _ = bar.normal(texts[cases[0]])
        assert norm is not None and U.sha(norm) == pid, (t, cases[0])
        fs, _ = U.forms_of(U.program_lines(norm))
        fk = [key.get(f['ident']) for f in fs]
        missing += sum(k is None for k in fk)
        programs.append(dict(cases=cases, sexp=norm, form_keys=fk))
    tables = [dict(key=x['key'], kind=x['kind'], component=x['component'], depth=x['depth'], depths=x['depths'],
                   reads=sorted({k for v in x['reads'].values() for k in v}), pinned=x['pinned'], cases=x['cases'], form=x['forms'][0]['text']) for x in rec['tables']]
    return dict(task=t, set=rec['set'], merged=rec['merged'], src=rec['src'], programs=programs, tables=tables, forms_unkeyed=missing, left_out=rec['left_out'])


def init():
    global PUBS
    PUBS = U.G.publications(), U.G.excluded()
    B.PUBS = PUBS


def one(job):
    t, rec, want = job
    try:
        return merged_record(rec, *PUBS) if rec is not None else dict(B.union_record(t, want), merged='text', src='text')
    except Exception as e:  # noqa: BLE001
        return dict(task=t, error='%s: %s' % (type(e).__name__, str(e)[:300]))


def main():
    args = sys.argv[1:]
    jobs = int(args.pop(args.index('--jobs') + 1)) if '--jobs' in args else 1
    args = [a for a in args if a != '--jobs']
    merged_only = '--merged-only' in args  # no text-level record for a task with no merged line
    for want in [a for a in args if a != '--merged-only']:
        out = OUT + '/records-%s.jsonl' % want
        done = {r['task']: r.get('src', 'text' if r['merged'] == 'text' else None) for r in map(json.loads, Z.open_text(out))} if Z.exists(out) else {}
        merged, _, aside = B.merged_rows(want)
        order = B.task_order(want)
        todo = [(t, merged.get(t), want) for t in order if t not in aside and (
            (t in merged and done.get(t) != merged[t]['src']) or (t not in merged and t not in done and not merged_only))]
        t0, n = time.time(), 0
        print('%s: %d tasks to build, %d jobs' % (want, len(todo), jobs), flush=True)
        with open(out, 'a') as f, multiprocessing.get_context('spawn').Pool(jobs, initializer=init) as pool:
            for r in pool.imap_unordered(one, todo):  # a task's later record, from a changed line, follows its earlier one; build.py takes the last
                n += 1
                if 'error' in r:
                    print('%s %s FAILED %s' % (want, r['task'], r['error']), flush=True)
                    continue
                f.write(json.dumps(r) + '\n')
                f.flush()
                el = time.time() - t0
                print('%s %s %d/%d: %d programs, %d tables, %d forms unkeyed, merged %s, %.0f s, ETA %.0f s' % (
                    want, r['task'], n, len(todo), len(r['programs']), len(r['tables']), r.get('forms_unkeyed', 0), r.get('merged'), el, el / n * (len(todo) - n)), flush=True)


if __name__ == '__main__':
    main()
