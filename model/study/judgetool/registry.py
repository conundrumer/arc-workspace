"""Canonical native lib metadata for mechanical candidate generation.

No predicate is executed here. All candidate execution uses ReplayEvaluator.
"""
import json
from evaluator import sha


def registry_interfaces(ev,record):
    program=ev.arclog.StudyProgram.from_sexp(record['mutant_sexp'],ev.settings)
    exported=json.loads(ev.arclog.study_program_export_json(program))
    registry=exported['definitions']['registry']
    return dict(schema='judgetool-registry-interfaces-v1',source_sha256=sha(record),
                program_sha256=sha(record['mutant_sexp']),runtime=ev.runtime,
                registry_sha256=sha(registry),registry=registry,
                entries=registry['entries'],
                typed_sites=exported.get('typed_sites'),
                readers=exported['definitions'].get('readers'),
                semantics='native registry metadata only; candidates must be checked by evaluate')
