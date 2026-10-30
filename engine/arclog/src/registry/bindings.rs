//! The rule by which an `INIT` form binds the type parameters of its
//! component: the places of the form that project onto each parameter
//! (`docs/arclog/arclog.md#instance`).

use super::*;

/// A place of an `INIT` form that projects onto a type parameter of its
/// component: the key clause, which gives the parameter of the `key` column
/// a record of its `^` labels, or a head site of an input.
#[derive(Clone, Copy, Debug)]
pub(crate) enum ParameterSite<'a> {
    Key(&'a crate::program::KeyClause),
    Head { input: &'a crate::program::InstanceInput, site: &'a crate::program::Site },
}

/// The places of an `INIT` form that project onto one type parameter of
/// its component: the place that binds it, and each later head site onto
/// it, in the order of the form.
#[derive(Clone, Debug)]
pub(crate) struct ParameterSites<'a> {
    pub(crate) parameter: &'a TypeParameter,
    pub(crate) binding: ParameterSite<'a>,
    pub(crate) later: Vec<(&'a crate::program::InstanceInput, &'a crate::program::Site)>,
}

/// The places of the `INIT` form `init` that project onto each type parameter
/// of a component whose inputs are `inputs`, in the order of the first place
/// onto each. The places, in the order of the form, are the key clause, where
/// the component has a `key` column of a type parameter, then each head site
/// on a column of a type parameter, of each input of the form that the
/// component has, the keyed inputs first (`docs/arclog/arclog.md#instance`).
pub(crate) fn binding_sites<'a>(init: &'a crate::program::Instance, inputs: &'a [InputPort]) -> Vec<ParameterSites<'a>> {
    let mut sites: Vec<ParameterSites> = Vec::new();
    if let (Some(key), Some(parameter)) = (&init.key, key_parameter(inputs)) {
        sites.push(ParameterSites { parameter, binding: ParameterSite::Key(key.value()), later: Vec::new() });
    }
    for input in crate::program::written_inputs(init.key.as_ref(), &init.inputs) {
        let Some(port) = inputs.iter().find(|i| i.port.name == input.name) else { continue };
        for site in input.head.iter() {
            let Some(parameter) = parameter_column(port, &site.column) else { continue };
            match sites.iter_mut().find(|s| s.parameter == parameter) {
                Some(bound) => bound.later.push((input, site)),
                None => sites.push(ParameterSites { parameter, binding: ParameterSite::Head { input, site }, later: Vec::new() }),
            }
        }
    }
    sites
}

/// Each of `parameters` onto which none of `sites` projects, which is its
/// bound, or an empty record where it has none (`docs/arclog/arclog.md#instance`).
pub(crate) fn unbound<'p>(parameters: &'p [TypeParameter], sites: &[ParameterSites<'_>]) -> Vec<&'p TypeParameter> {
    parameters.iter().filter(|parameter| sites.iter().all(|sites| sites.parameter != *parameter)).collect()
}

/// The type parameter of the `key` column of a component whose inputs are
/// `inputs`, the column that the key clause binds, where it has one.
pub(crate) fn key_parameter(inputs: &[InputPort]) -> Option<&TypeParameter> {
    inputs.iter().find_map(|input| {
        let column = input.port.columns.iter().find(|c| is_key(c))?;
        match &column.ty {
            ColumnType::Parameter(parameter) => Some(parameter),
            _ => None,
        }
    })
}

/// The type parameter of the column `column` of the input `port`, where
/// the column has one.
fn parameter_column<'p>(port: &'p InputPort, column: &ColumnName) -> Option<&'p TypeParameter> {
    match &port.port.columns.iter().find(|c| c.name == *column)?.ty {
        ColumnType::Parameter(parameter) => Some(parameter),
        _ => None,
    }
}


/// The key position of each row field of the logical non-key `columns`
/// of a `from-key` input. Each field needs exactly one key label of its
/// type. A logical column with no fields has no key label to supply it,
/// and cannot be filled. This differs from a declared input with no
/// non-key columns, whose successful fill is the empty tuple.
///
/// Keep column boundaries until matching: flattening first confuses an
/// unbound parameter `[[]]` with a zero-column input `[]` and invents rows.
pub fn key_fill<'a>(key_types: &[ValueType], columns: impl IntoIterator<Item=&'a [ValueType]>) -> Option<Vec<usize>> {
    let mut positions = Vec::new();
    for fields in columns {
        let (first, rest) = fields.split_first()?;
        for ty in std::iter::once(first).chain(rest) {
            let mut matching = key_types.iter().enumerate().filter(|(_, key)| *key == ty).map(|(position, _)| position);
            match (matching.next(), matching.next()) {
                (Some(position), None) => positions.push(position),
                _ => return None,
            }
        }
    }
    Some(positions)
}
