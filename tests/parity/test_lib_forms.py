"""Each component of `lib-forms.dl` declares the relations of its signature component, with their widths."""

from arclog_convert import libmap
from arclog_convert.lib import Lib, SIGNATURE
from arclog_convert.parity_text import FORM_PREFIX, forms


def test_a_form_declares_the_width_of_each_relation_its_signature_component_declares() -> None:
    sig = Lib(SIGNATURE)
    for name, relations in forms().items():
        comp = name.removeprefix(FORM_PREFIX)
        renames = libmap.COMP.get(comp)
        if comp == "Gaps":   # the base of the forms that read gaps, no component of the signature
            continue
        target = sig.comps[renames.name if renames else comp]
        declared = {r.name: len(r.cols) for r in sig.relations(target.name)[1]}
        parts = renames.parts if renames else {}
        for relation, width in relations.items():
            assert declared.get(parts.get(relation, relation)) == width, (name, relation)
        assert {parts.get(r, r) for r in relations} >= declared.keys(), name


