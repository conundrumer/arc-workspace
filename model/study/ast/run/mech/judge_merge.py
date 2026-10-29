"""Merge a checked judge final into source-bound mechanical evidence.

Call with the shared tool's checked final, not the judge answer. Reasons/prose
never affect policy. Receipt storage/authentication belongs to the caller.
"""
import copy
from clause_evidence import clause_evidence,digest
from run import pair_key


def merge_final(record, manifest, target, evidence, final, receipt_ref):
    if (evidence.get('pair_id') != digest(pair_key(record))
            or evidence.get('source_sha256') != digest(record)):
        raise ValueError('mechanical evidence source binding differs')
    if (final.get('schema') != 'judge-tool-final-v3'
            or final.get('pair_id') != manifest['pair_id']
            or final.get('render_version') != manifest['render_version']
            or final.get('source_sha256') != digest(record)
            or final.get('adapter_sha256') != digest(target['adapter'])):
        raise ValueError('expected checked final with matching pair/render version')
    outcomes = final.get('outcomes')
    if not isinstance(outcomes,list) or final.get('no_clause_found') != (not outcomes):
        raise ValueError('checked final outcomes inconsistent')
    out = copy.deepcopy(evidence)
    answers = []
    for index, result in enumerate(outcomes):
        role = 'continuation' if result.get('kind') == 'alternative' else 'recovery'
        ref = dict(receipt_ref, outcome_index=index, tool_result_sha256=digest(result))
        answer = clause_evidence(result,record,ref,purpose='answer',role=role,
                                 ntrain=target['ntrain'],ntest=target['ntest'])
        if not result.get('kind') and result.get('outcome') != 'continuation passed':
            answer['role'] = 'unspecified'
        if not (final.get('judge_run',{}).get('completed') is True
                and final.get('judge_run',{}).get('admission_authenticated') is True):
            answer['judgment_complete'] = False
        answers.append(answer)
    # Keep earlier checked answers; strongest evidence across judge sessions wins.
    out['clauses'] = list(out.get('clauses',[])) + answers
    out['judge_run'] = dict(complete=(final.get('judge_run',{}).get('completed') is True
                                      and final.get('judge_run',{}).get('admission_authenticated') is True
                                      and not final.get('judge_run',{}).get('no_kept_entry')
                                      and (not outcomes or all(a['judgment_complete'] for a in answers))),
                            answered=True,receipt_ref=receipt_ref,
                            no_clause_found=not outcomes)
    return out
