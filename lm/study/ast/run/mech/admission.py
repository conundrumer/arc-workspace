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
                           if k in ('complete','fits_train','fits_test','refused','receipt_ref')},
                  kind=evidence.get('kind'),
                  search={k:v for k,v in evidence.get('search',{}).items()
                          if k in ('status','complete','settled_space','unvisited','receipt_ref')},
                  target_scope='main G; same-case tables strictly after point; all tables every other case',
                  judge_test_rows='never included')
    result['receipt_sha256']=digest(result)
    return result


def load_admission(reference, record):
    """Validate a durable mech-base receipt for the renderer.

    `reference`: {database: ABSOLUTE_SQLITE, pair_id: MECH_ID} (table grades).
    A mech-admission-v1 object with grade_ref is also accepted. Returns explicit
    unavailable on missing/stale/unqualified evidence; never executes native code.
    This validates the trusted owned producer's receipt chain, not arbitrary
    receipt_ref strings or caller booleans. Native row comparisons stay in tool.
    """
    import hashlib
    import json
    from pathlib import Path
    import sqlite3
    from run import pair_key
    from base_pass import code_manifest,STUDY
    unavailable=dict(schema='mech-admission-validation-v1',status='unavailable',
                     receipt_authenticated=False,eligible=False)
    db=None
    try:
        if isinstance(reference,(str,Path)):
            reference=json.loads(Path(reference).read_text())
        if reference.get('schema')=='mech-admission-v1':
            supplied=dict(reference);saved_hash=supplied.pop('receipt_sha256',None)
            if digest(supplied)!=saved_hash:raise ValueError('admission payload digest differs')
            ref=reference['grade_ref']
        else:ref=reference
        if ref.get('table','grades')!='grades':raise ValueError('expected grades reference')
        database=Path(ref['database']).resolve()
        owned=DATA_ROOT/'ast/run/mech'
        if not database.is_relative_to(owned):raise ValueError('grade database outside owned area')
        pair_id=digest(pair_key(record));source=digest(record)
        if ref.get('pair_id')!=pair_id:raise ValueError('mechanical pair key differs')
        db=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True);db.execute('BEGIN')
        row=db.execute('SELECT evidence_sha256,code_sha256,config_sha256,result_sha256,record_json FROM grades WHERE pair_id=?',(pair_id,)).fetchone()
        if not row:raise ValueError('grade record unavailable')
        result=json.loads(row[4])
        if digest(result)!=row[3] or result.get('source_sha256')!=source:raise ValueError('grade/source digest differs')
        codes=code_manifest()
        if result.get('code_manifest')!=codes or row[1]!=digest(codes):raise ValueError('grade producer code changed or is not native base producer')
        cfg=result['config']
        if digest(cfg)!=row[2] or cfg.get('schema')!='mech-base-config-v1':raise ValueError('base producer config differs')
        spec=STUDY/'codex-adm/briefs/judge-decisions.md'
        if cfg.get('spec_sha256')!=hashlib.sha256(spec.read_bytes()).hexdigest():raise ValueError('specification changed')
        proofrow=db.execute('SELECT source,code,config,metadata,result_sha256,payload FROM evidence WHERE pair_id=?',(pair_id,)).fetchone()
        if not proofrow:raise ValueError('native evidence unavailable')
        evidence=json.loads(proofrow[5])
        if (digest(evidence)!=proofrow[4] or row[0]!=proofrow[4] or evidence.get('source_sha256')!=source
                or tuple(proofrow[:3])!=(source,row[1],row[2])):raise ValueError('native evidence binding differs')
        metadata=evidence['source_metadata'];mref=metadata['manifest_ref'];mpath=Path(mref['path']).resolve()
        if hashlib.sha256(mpath.read_bytes()).hexdigest()!=mref['sha256']:raise ValueError('source layout manifest changed')
        manifest=json.loads(mpath.read_text());binding=manifest['adapter']['comparison_target']['binding']
        gold=evidence['native_receipts'].get('G',{})
        # Eligibility must be backed by the actual complete fresh observer. A
        # legacy train snapshot reference or copied assertion is insufficient.
        if (gold.get('original_source_sha256')!=source or gold.get('train_complete') is not True or gold.get('test_complete') is not True
                or gold.get('layout_sha256')!=digest(binding['projected_schema'])
                or gold.get('gold_program_sha256')!=digest(record['gold_sexp'])
                or gold.get('kept_context_sha256')!=digest(record['evaluation']['kept_assignments'])):
            raise ValueError('complete fresh gold target receipt unavailable')
        for artifact in (gold.get('artifact'),evidence['native_receipts'].get('program',{}).get('replay',{}).get('artifact')):
            if not artifact:raise ValueError('required native replay artifact unavailable')
            folder=Path(artifact).resolve()
            if not folder.is_relative_to(DATA_ROOT / 'judgetool/replays'):raise ValueError('native replay artifact outside shared store')
            receipt=json.loads((folder/'receipt.json').read_text());engine=json.loads((folder/'engine-0.json').read_text())
            if receipt.get('settings')!=cfg['evaluator'] or engine.get('status')!='complete':raise ValueError('native replay settings/completeness differs')
            if not (folder/'entries-0.jsonl.gz').is_file():raise ValueError('native replay entries unavailable')
        policy=reduce_grade(evidence)
        if policy['grade']!=result['grade'] or policy['attributes']!=result['attributes']:raise ValueError('stored grade disagrees with current reducer')
        eligible=judge_eligible(evidence)
        exported=admission(evidence,dict(database=str(database),table='grades',pair_id=pair_id),inputs_authenticated=True)
        return dict(schema='mech-admission-validation-v1',status='eligible' if eligible else 'not_eligible',
                    receipt_authenticated=True,eligible=eligible,admission=exported,
                    grade_result_sha256=row[3],evidence_sha256=row[0])
    except Exception as error:
        return dict(unavailable,reason=str(error),error_type=type(error).__name__)
    finally:
        if db is not None:db.close()
