"""Stable fault classes for streamed mutation-study observations."""
import re


def fault_group(reason):
    if "does not compile: Untyped" in reason:
        return "branch_local_storage_type"
    if reason in ("undefined clause table","undefined table at an assignment absent from the other domain"):
        return "undefined_body_result"
    if "per-input form reads" in reason and ("Example column" in reason or "ex_input" in reason or "ex_output" in reason):
        return "synthetic_body_scope_loss"
    if "makes the label, so the site names its partner" in reason:
        return "synthetic_body_column_contract"
    if "column of the relation has no label that the widened body makes" in reason:
        return "widened_branch_interface"
    if "from two branches, which have no join" in reason and "Pose(" in reason:
        return "synthetic_body_nominal_type_context"
    if "column is `0` in every clause" in reason:
        return "synthetic_body_zero_column"
    if "matching example scope" in reason:
        return "mutation_changes_evaluation_scope"
    if "does not assign every DET" in reason:
        return "gold_assignment_incomplete_for_body"
    checks = sorted(set(re.findall(r"Check\(([^)]+)\)", reason)))
    if checks:
        return "check:" + "+".join(checks)
    return re.sub(r" at \d+$", "", reason)[:180]


def normalized_reason(reason):
    reason = re.sub(r" at \d+$", "", reason)
    if "CanonicalForm" in reason:
        return fault_group(reason)
    return reason
