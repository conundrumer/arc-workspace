"""Export mechanical judge routing, with explicit evidence authority.

The receiver validates this record against the referenced durable grade and
source/evidence receipts. A JSON hash on its own never authenticates data.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
from grades import judge_eligible,reduce_grade
from clause_evidence import digest


def admission(evidence, grade_ref, *, inputs_authenticated=False):
    eligible = judge_eligible(evidence)
    result = dict(schema='mech-admission-v1',pair_id=evidence['pair_id'],
                  source_sha256=evidence['source_sha256'],evidence_sha256=digest(evidence),
                  grade=reduce_grade(evidence)['grade'],grade_ref=grade_ref,
                  status='eligible' if eligible and inputs_authenticated else
                         'not_eligible' if not eligible and inputs_authenticated else 'unavailable',
                  policy_eligible=eligible,receipt_authenticated=bool(inputs_authenticated),
                  containment={k:v for k,v in evidence.get('comparisons',{}).get('point',{}).items()
                               if k in ('complete','lossy','X_holds_every_gold_row','receipt_ref')},
                  program={k:v for k,v in evidence.get('program',{}).items()
                           if k in ('complete','fits_train','fits_test','refused','receipt_ref',
                                    'train_nonfit_complete','train_nonfit_receipt')},
                  kind=evidence.get('kind'),
                  search={k:v for k,v in evidence.get('search',{}).items()
                          if k in ('status','complete','settled_space','unvisited','receipt_ref')},
                  target_scope='main G; same-case tables strictly after point; all tables every other case',
                  judge_test_rows='never included')
    result['receipt_sha256']=digest(result)
    return result


def load_admission(reference,record):
    """Authenticate admission through the read-time join, never a grades table."""
    from pathlib import Path
    import json
    from run import pair_key
    from read_grades import read_pair
    unavailable=dict(schema='mech-admission-validation-v1',status='unavailable',receipt_authenticated=False,eligible=False)
    try:
        if isinstance(reference,(str,Path)):reference=json.loads(Path(reference).read_text())
        ref=reference.get('grade_ref',reference)
        pair_id=digest(pair_key(record))
        if ref.get('pair_id')!=pair_id:raise ValueError('mechanical pair key differs')
        joined=read_pair(pair_id,source_record=record)
        if not joined.get('valid'):raise ValueError(joined.get('reason','joined results unavailable'))
        evidence=joined['evidence'];eligible=judge_eligible(evidence)
        exported=admission(evidence,dict(pair_id=pair_id,view='read_grades.read_pair'),inputs_authenticated=True)
        return dict(schema='mech-admission-validation-v1',status='eligible' if eligible else 'not_eligible',
            receipt_authenticated=True,eligible=eligible,admission=exported,
            evidence_sha256=joined['evidence_sha256'],grade_result_sha256=joined['result_sha256'])
    except Exception as error:return dict(unavailable,reason=str(error),error_type=type(error).__name__)
