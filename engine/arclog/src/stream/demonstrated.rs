//! What the writer and the decoder share of the stream of a `DEMONSTRATED`
//! form, as `docs/engine/arclog-stream.md#token-stream` gives it: the inputs
//! the engine names, with the columns of each, and the columns that the
//! language model fills after a `PREDICT` clause's body.

use std::sync::OnceLock;

use crate::program::{ColumnName, Demonstrated, InstanceInput, PortName};
use crate::registry::{Column, ColumnType, Component, ComponentKind, InputPort, Port, TypeParameter};
use crate::resolver::columns::projection;
use crate::resolver::form_columns::demonstrated_value;
use crate::types::{each_site_label, use_label};

/// The inputs of a `DEMONSTRATED` form, as the stream names them: `value`,
/// with the columns `o`, `i` and `v`, then `demonstration`, with the columns
/// `o` and `o2`, each a type parameter. The form has no output.
pub(crate) fn ports() -> &'static Component {
    static PORTS: OnceLock<Component> = OnceLock::new();
    PORTS.get_or_init(|| {
        let column = |name: &str| Column { name: ColumnName::Written(name.into()), ty: ColumnType::Parameter(TypeParameter { name: name.to_uppercase().into(), bound: None }) };
        let input = |name: &str, columns: &[&str]| InputPort {
            port: Port { name: PortName(name.into()), columns: columns.iter().map(|name| column(name)).collect(), copies: Box::new([]), frames: Box::new([]) },
            default: None,
            reads_outputs: false,
            from_key: false,
        };
        Component {
            kind: ComponentKind::TaskStructure,
            type_parameters: Box::new([]),
            inputs: Box::new([input("value", &["o", "i", "v"]), input("demonstration", &["o", "o2"])]),
            outputs: Box::new([]),
        }
    })
}

/// The names of the columns that a `&prediction` clause of a rule of
/// `demonstrated` fills, in the order the stream fills them: each column of
/// the key, then each column of the head of the `value` input, as the
/// evaluation names them (`crate::eval`'s `DEMONSTRATED` form): a site of
/// one label by the label's name, and a site of a record by each field.
/// `None` for a column that no name names.
pub(crate) fn prediction_targets(demonstrated: &Demonstrated) -> Vec<Option<ColumnName>> {
    let key = demonstrated.key.iter().flat_map(|key| key.value().key.columns.iter().map(|column| Some(column.name.clone())));
    let value = demonstrated_value(demonstrated).map(head_names).unwrap_or_default();
    key.chain(value).collect()
}

/// The name of each column of the head of `input`, in the order of its
/// sites, as the evaluation of a `DEMONSTRATED` form names them.
fn head_names(input: &InstanceInput) -> Vec<Option<ColumnName>> {
    let mut names = Vec::new();
    for site in input.head.iter() {
        match projection(site) {
            Some(fields) => names.extend(fields.iter().cloned().map(Some)),
            None => each_site_label(site, &mut Vec::new(), &mut |use_, path| {
                if use_label(use_).is_some() {
                    names.push((path.len() > 1).then(|| path.last().cloned()).flatten());
                }
            }),
        }
    }
    names
}
