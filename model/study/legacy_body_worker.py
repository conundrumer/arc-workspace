"""Compile historical BODY correspondence in its serializer runtime; no evaluation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from study_paths import CODE_ROOT
sys.path.insert(0, str(CODE_ROOT / 'ast/run'))
from provenance import load_build

from native_correspondence import _native_stream, certify_stored_representation


def acquire(request):
    import arclog
    record=request['record']
    ready=request['runtime_ready']
    build=load_build(arclog,SimpleNamespace(build_receipt=None,
        engine_commit=ready['revision'],wheel=Path(ready['wheel'])))
    settings = arclog.DecodeSettings(deadline_seconds=None, rule_tests=False)
    gold = arclog.StudyProgram.from_sexp(record['programs']['gold'], settings).decode_source()
    valid = gold.construct_identity(json.dumps(record['identity']))
    mutant = arclog.StudyProgram.from_sexp(record['programs']['mutant'], settings).decode_source()
    constructed = json.loads(arclog.study_mutant_export_json(valid))
    exports = dict(gold=json.loads(arclog.study_program_export_json(gold,source_program=gold)),
                   mutant=json.loads(arclog.study_program_export_json(mutant,source_program=mutant)))
    certificate = certify_stored_representation(valid, mutant,
        requested_text=record['programs']['mutant'], rehydrated_export=constructed,
        stored_export=exports['mutant'], mutation_identity=record['identity'])
    binary = Path(importlib.util.find_spec('arclog.arclog').origin).resolve()
    return dict(schema='legacy-native-body-metadata-v2',
        build=build, runtime=dict(python=sys.executable, binary=str(binary),
                     binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()),
        source_record=record, mutation=certificate,
        sides={side:dict(export=exports[side], stream=_native_stream(handle))
               for side,handle in (('gold',gold),('mutant',mutant))})


if __name__ == '__main__':
    json.dump(acquire(json.load(sys.stdin)), sys.stdout, ensure_ascii=False,
              sort_keys=True, separators=(',', ':'), allow_nan=False)
