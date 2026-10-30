"""Startup contract for the loaded study stack; no task/session or replay.

Keep required features here when adding a native call. Entry masks are optional:
19cbc68c's full-row API remains supported by the evaluator's existing fallback.
Report schemas remain checked at consumption; the render schema is available
at startup through a fixed, task-free metadata export.
"""
from functools import lru_cache
import inspect
import importlib
import json
from pathlib import Path
import sys


NATIVE_CALLS = {
    'StudyTaskEvaluator.gold_tables': ('full_rows',),
    'StudyTaskEvaluator.gold_kept': ('program',),
    'StudyTaskEvaluator.gold_body': ('program', 'body_path', 'expected_kept_json'),
    'StudyProgram.from_sexp': (),
    'StudyProgram.decode_source': (),
    'StudyProgram.decode_rows_json': (),
    'StudyProgram.construct_identity': (),
    'StudyProgram.out_bindings_json': (),
    'study_program_export_json': ('relation_source_names_json', 'source_program'),
}
RENDER_SCHEMA = {
    'schema': 'arclog-study-render-v1',
    'correspondence.schema': 'arclog-study-correspondence-v1',
    'parts.body_views': 'complete',
    'parts.definitions_readers': 'complete',
    'parts.types_frames': 'complete',
}
DOCUMENT_METHODS = ('schema', 'target_projection', 'callable_atom',
                    'dependency_scope', 'definition_node')
# This helper existed briefly without being included in extracted Document.
DOCUMENT_HELPERS = ('body_view',)


class CompatibilityError(RuntimeError):
    """An incompatible code/runtime deployment, not a per-pair unknown."""


def _fail(native, missing):
    raise CompatibilityError('Incompatible study stack: runtime '+str(Path(sys.prefix))+
        ' ('+str(getattr(native, '__file__', '<unknown arclog>'))+'); missing '+
        '; '.join(missing))


def _call_missing(function, name, keywords):
    if not callable(function):
        return [name+' method']
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return [name+' inspectable call signature']
    return [name+' keyword '+repr(k) for k in keywords if k not in parameters
            or parameters[k].kind == inspect.Parameter.POSITIONAL_ONLY]


@lru_cache(maxsize=1)
def _require_native(native):
    missing = []
    for path, keywords in NATIVE_CALLS.items():
        value = native
        for part in path.split('.'):
            value = getattr(value, part, None)
        missing.extend(_call_missing(value, path, keywords))
    if missing:
        _fail(native, missing)
    # Compile/export metadata only: no StudyTaskEvaluator is constructed and
    # neither gold_tables nor any FITS/search/body operation is invoked.
    try:
        program = native.StudyProgram.from_sexp(
            '(RULE &Probe (input (:P *P) (:Col *Col))) (OUT (&Probe ^P ^Col))',
            native.DecodeSettings())
        report = json.loads(native.study_program_export_json(program))
    except Exception as error:
        _fail(native, ['native render schema probe: '+str(error)])
    for path, expected in RENDER_SCHEMA.items():
        value = report
        for part in path.split('.'):
            value = value.get(part) if isinstance(value, dict) else None
        if value != expected:
            missing.append('native render '+path+'='+repr(expected)+' (got '+repr(value)+')')
    if missing:
        _fail(native, missing)


def require_evaluator(native):
    """Check actual loaded native and Python call signatures before work."""
    _require_native(native)
    from tables import kept_entries
    missing = _call_missing(kept_entries, 'Python tables.kept_entries', ('held_entries',))
    if missing:
        _fail(native, missing)


def require_exporter(native):
    """Also check the actual extracted renderer used by ReceiptDocument."""
    require_evaluator(native)
    from judge3 import det_metadata
    try:
        # The exporter and mechanical DET adapter use these two existing
        # import namespaces. Check their actual cached classes, not a newly
        # imported renderer that could hide a stale extracted Document.
        providers = (importlib.import_module('nonrender_metadata'), det_metadata.base)
        produce = det_metadata._receipt_produce(Path(det_metadata.base.__file__).read_bytes())
        documents = [provider._policy()[0]['Document'] for provider in providers]
    except Exception as error:
        _fail(native, ['Python extracted metadata contract: '+str(error)])
    missing = []
    for document in documents:
        missing.extend(f'Python extracted Document.{name} method' for name in DOCUMENT_METHODS
                       if not callable(getattr(document, name, None)))
        callers = [produce] + [getattr(document, name, None) for name in DOCUMENT_METHODS]
        for helper in DOCUMENT_HELPERS:
            if (any(helper in getattr(getattr(f, '__code__', None), 'co_names', ()) for f in callers)
                    and not callable(getattr(document, helper, None))):
                missing.append('Python extracted Document.'+helper+' method required by loaded producer')
    if missing:
        _fail(native, sorted(set(missing)))
