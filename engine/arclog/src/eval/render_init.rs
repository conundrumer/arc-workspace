//! Read-only metadata through the actual INIT argument binding machinery.
use super::*;

/// A registry-declared logical column, including those with no row positions.
pub(crate) struct ProjectionColumn {
    pub ordinal: usize,
    pub name: ColumnName,
    pub key: bool,
    pub row_start: usize,
    pub width: usize,
    pub fields: Option<Vec<ColumnName>>,
}

pub(crate) fn input_projection(
    program: &CheckedProgram,
    form: &NodePath,
    input: &InstanceInput,
    registry: &crate::registry::Registry,
) -> Result<(Vec<Option<LabelId>>, Box<[ValueType]>, Vec<LabelId>, Vec<ProjectionColumn>), String> {
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
    let mut columns = Vec::new();
    let mut row_start = 0;
    for (ordinal,column) in port.port.columns.iter().enumerate() {
        let key = is_key(column);
        let width = if key { 0 } else { shape.column_types(column)?.len() };
        columns.push(ProjectionColumn {ordinal,name:column.name.clone(),key,row_start,width,
            fields:shape.fields(column).map(|f|f.to_vec())});
        row_start += width;
    }
    if row_start != types.len() { return Err("native INIT logical/row widths differ".into()); }
    Ok((labels, types, shape.key_labels(), columns))
}
