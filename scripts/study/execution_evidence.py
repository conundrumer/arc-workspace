"""Validate native execution evidence without recomputing candidate-set FITS.

This pure module is archived into immutable runtime checks. Renderers and
loaders must load that pinned copy, not a mutable engine checkout.
"""

SCHEMA = "study-execution-evidence-v1"
_STATUSES = {"complete", "stopped", "fault"}


def validate_train_example(example, context="train example"):
    """Return the same dict, unchanged; raise ValueError on invalid evidence.

    A present empty model list is valid. Missing/None FITS is unavailable,
    never inferred from GIVEN diagnostics or from the number of models.
    Stopped/fault schema is valid evidence, not complete render admission.
    """
    def fail(message):
        raise ValueError(f"{context}: {message}")

    def count(value, label, minimum=0):
        if type(value) is not int or value < minimum:
            fail(f"{label} must be an integer >= {minimum}")

    if not isinstance(example, dict):
        fail("expected an object")
    count(example.get("example"), "example")
    if "status" in example and (type(example["status"]) is not str or example["status"] not in _STATUSES):
        fail("invalid example status")
    models = example.get("models")
    if not isinstance(models, list):
        fail("models must be a present list")
    complete = example.get("status", "complete") == "complete"
    for index, model in enumerate(models):
        label = f"model {index}"
        if not isinstance(model, dict):
            fail(f"{label} must be an object")
        status = model.get("status")
        if type(status) is not str or status not in _STATUSES:
            fail(f"{label} has invalid or missing status")
        complete = complete and status == "complete"
        if status == "complete" or "equals" in model:
            if type(model.get("equals")) is not bool:
                fail(f"{label} equals must be boolean")
        if status == "complete" or "differing_cells" in model:
            count(model.get("differing_cells"), f"{label} differing_cells")
        if "equals" in model and "differing_cells" in model:
            if model["equals"] != (model["differing_cells"] == 0):
                fail(f"{label} GIVEN equality and cell count disagree")
        if "grid_defined" in model and type(model["grid_defined"]) is not bool:
            fail(f"{label} grid_defined must be boolean")
    fit = example.get("fits")
    if fit is not None:
        if type(fit) is not bool:
            fail("fits must be boolean or unavailable")
        if not complete:
            fail("completed FITS supplied for stopped/fault evidence")
    if "fit_comparison" in example:
        if example["fit_comparison"] != "native_closed_candidate_set":
            fail("unsupported fit_comparison")
    if "distinct_output_grids" in example:
        count(example["distinct_output_grids"], "distinct_output_grids")
        if example["distinct_output_grids"] > len(models):
            fail("distinct_output_grids exceeds model count")
    if "output_set_defined" in example:
        defined = example["output_set_defined"]
        if type(defined) is not bool:
            fail("output_set_defined must be boolean")
        if defined and (not complete or example.get("distinct_output_grids") == 0):
            fail("defined output set lacks complete nonempty grid evidence")
        if not defined and fit is True:
            fail("FITS true with an undefined output set")
    if fit is True and example.get("distinct_output_grids") == 0:
        fail("FITS true with zero distinct output grids")
    if "accepted_candidate_sizes" in example:
        sizes = example["accepted_candidate_sizes"]
        if not isinstance(sizes, list) or not sizes:
            fail("accepted_candidate_sizes must be a nonempty list")
        for size in sizes:
            count(size, "accepted candidate size", minimum=1)
    return example


def example_fit(example, context="train example"):
    """Return the native boolean FITS, or None when unavailable."""
    return validate_train_example(example, context).get("fits")
