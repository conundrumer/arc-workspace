//! Read-only metadata through the actual INIT argument binding machinery.
use super::*;

pub(crate) fn input_projection(
    program: &CheckedProgram,
    form: &NodePath,
    input: &InstanceInput,
    registry: &crate::registry::Registry,
) -> Result<(Vec<Option<LabelId>>, Box<[ValueType]>, Vec<LabelId>), String> {
    let Some(NodeRef::Instance(instance)) =
        node_at(NodeRef::Program(program.program.program.value()), form)
    else {
        return Err("input projection owner is not INIT".into());
    };
    let Some(LibEntry::Component(component)) = registry.entry(&instance.component) else {
        return Err("INIT component is absent".into());
    };
    let port = component
        .inputs
        .iter()
        .find(|i| i.port.name == input.name)
        .ok_or_else(|| "INIT input port is absent".to_string())?;
    let shape = InstanceShape::of(program, form, instance, component);
    let labels = shape.head_labels(input, &port.port.columns)?;
    let types = shape.port_types(&port.port.columns)?;
    if labels.len() != types.len() {
        return Err("native INIT head/type widths differ".into());
    }
    Ok((labels, types, shape.key_labels()))
}
