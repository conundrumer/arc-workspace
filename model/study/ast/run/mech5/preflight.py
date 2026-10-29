"""Fail before any corpus replay when required shared repairs are absent."""
import inspect

# Owner confirmed the ordinary checker retains the judge DET exclusion. Flip
# only after an additive actual-mutant-BODY/public-header route is integrated.
DET_SHARED_ROUTE_QUALIFIED = False
from ._paths import CODE_ROOT


def require_shared():
    required=('judge3/det_metadata.py','ast/run/mech3/det_receipt.py')
    missing=[name for name in required if not (CODE_ROOT/name).is_file()]
    if missing:raise RuntimeError('shared sources not merged: '+', '.join(missing))
    import tables
    for name in ('decode_kept','compatible_kept','comparison_type'):
        if not callable(getattr(tables,name,None)):
            missing.append('judgetool.tables.'+name)
    from case_collector import evaluate_cached
    # Exact-axis cached_gold repair must be merged. The owner must expose the
    # mechanical DET route separately; a judge-path kind exception is unsafe.
    source=inspect.getsource(evaluate_cached)
    if 'required' not in source:missing.append('case_collector cached_gold exact-axis repair')
    if not DET_SHARED_ROUTE_QUALIFIED:
        missing.append('mechanical DET public-header case collection and actual mutant BODY clause checking (owner capability pending)')
    if missing:raise RuntimeError('target pass deployment blocked: '+', '.join(missing))
