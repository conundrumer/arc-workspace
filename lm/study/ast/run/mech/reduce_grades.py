#!/usr/bin/env python3
"""Durably reduce authenticated mech-grade-evidence-v1 JSONL; no engine runs."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
from grades import reduce_grade, judge_eligible
from admission import admission
from outcomes import canonical

HERE = Path(__file__).resolve().parent
SPEC = HERE.parents[2] / 'codex-adm/briefs/judge-decisions.md'


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('evidence', type=Path)
    ap.add_argument('--output', type=Path, default=DATA_ROOT / 'ast/run/mech/grades.sqlite3')
    a = ap.parse_args()
    if a.evidence.resolve() == a.output.resolve():
        ap.error('evidence and output must differ')
    code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).resolve(), HERE/'grades.py', HERE/'outcomes.py',
                      HERE/'admission.py', HERE/'clause_evidence.py', HERE/'grade_store.py')}
    code_hash = sha(code)
    config = dict(schema='mech-grade-reduction-v1', spec_path=str(SPEC),
                  spec_sha256=hashlib.sha256(SPEC.read_bytes()).hexdigest())
    config_hash = sha(config)
    from grade_store import GradeStore
    store = GradeStore(a.output, code, config)
    start = time.monotonic(); last = 0; done = 0; written = 0; skipped = 0
    with a.evidence.open() as src:
        total = sum(1 for line in src if line.strip())
    def progress():
        elapsed = time.monotonic()-start
        rate = done/max(elapsed, .001)
        print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.2f}/s '
              f'ETA={(total-done)/max(rate,.001):.1f}s write={written} skip={skipped}',
              file=sys.stderr, flush=True)
    with a.evidence.open() as src:
        for lineno, line in enumerate(src, 1):
            if not line.strip():
                continue
            try:
                evidence = json.loads(line)
                _, was_skip = store.save(evidence, inputs_authenticated=False)
                skipped += was_skip
                written += not was_skip
            except Exception as error:
                raise RuntimeError(f'{a.evidence}:{lineno}: {error}') from error
            done += 1
            if time.monotonic()-last-start >= 5:
                progress(); last = time.monotonic()-start
    progress(); store.close()


if __name__ == '__main__':
    main()
