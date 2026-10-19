//! What of the engine's rows of an element the comparison with its Souffle
//! record covers: the parts the record gives rows of, and of those, the
//! rows inside the domain of the Souffle form. A relation's row lies
//! inside it where each value at a column of an orientation type is a
//! constant of the type the Souffle form declares there; a row of Frame,
//! where it lies at a key whose `extent` rows give each axis.

use arclog::program::TypeName;
use arclog::registry::Component;
use arclog::types::ValueType;
use serde_json::Value;

use arclog::registry::is_key;
use super::evaluation::{Cell, Compared, Rows, Subject};
use super::inputs::{component_type, constant_names, is_orientation};

/// The Souffle side of an element that its record gives rows of.
pub(super) struct Souffle {
    /// The rows of each part the record gives, by the part's index, in the
    /// order of the indices.
    pub(super) parts: Vec<(usize, Rows)>,
    /// Each output of a component that the record leaves out, by its
    /// index, with the width of the Souffle form's relation of it where
    /// the Souffle form holds one.
    pub(super) left_out: Vec<(usize, Option<usize>)>,
    /// The type of each column of a relation's Souffle form that is an
    /// orientation type of the registry, by the column's index.
    pub(super) column_types: Vec<(usize, ValueType)>,
}

/// The orientation type that the Souffle type `name` names, where it
/// names one: the Souffle lib writes each type by its arclog name.
pub(super) fn orientation_type(name: &str) -> Option<ValueType> {
    TypeName::named(name).map(TypeName::value_type).filter(is_orientation)
}

/// The component whose rows lie inside the domain of its Souffle form at
/// the keys whose rows of the input [`FRAME_EXTENT`] give each axis. At a
/// key with an `extent` row on one axis alone, the row of Frame in
/// `docs/lib-spec.md` gives the other axis extent 1, and the Souffle form
/// `Frame2D` gives no cell: the Souffle form of that case is `AxisFrame`,
/// which `src/arclog_convert/libmap/division.py` `axis_frame` expands onto Frame
/// with one `extent` row per key.
const FRAME: &str = "Frame";
const FRAME_EXTENT: &str = "extent";

/// The rows of each part that the comparison of the engine's rows
/// `engine` of `subject` on `inputs` with `souffle` covers, by part: at a
/// part the record gives, the engine's rows inside the domain of the
/// Souffle form and the record's rows; at another, no row on either side.
/// With the line on the engine's rows of the parts the record gives that
/// lie outside that domain, where there are any.
pub(super) fn covered(subject: &Subject<'_>, inputs: &Value, engine: &[Rows], souffle: &Souffle) -> (Compared, Option<String>) {
    let domain = Domain::of(subject, inputs, souffle);
    let mut outside = 0;
    let mut compared: Compared = (vec![Rows::new(); engine.len()], vec![Rows::new(); engine.len()]);
    for (at, rows) in &souffle.parts {
        let (kept, left): (Rows, Rows) = engine[*at].iter().cloned().partition(|row| domain.holds(*at, row));
        outside += left.len();
        compared.0[*at] = kept;
        compared.1[*at] = rows.clone();
    }
    let line = (outside > 0).then(|| {
        let place = match domain {
            Domain::Columns(_) => "outside the column types of its Souffle form",
            Domain::Keys { .. } => "at keys whose `extent` rows leave an axis out, where its Souffle form gives no row",
            Domain::Whole => unreachable!("no row lies outside the whole domain"),
        };
        format!("{}: against Souffle: {outside} of the engine's rows lie {place}", subject.name())
    });
    (compared, line)
}

/// Each line on an output of a component that `souffle` leaves out, with
/// why.
pub(super) fn left_out_lines(subject: &Subject<'_>, souffle: &Souffle) -> Vec<String> {
    let (Subject::Component { component, .. } | Subject::Unfold { component, .. }) = subject else { return Vec::new() };
    souffle
        .left_out
        .iter()
        .map(|&(at, width)| {
            let reason = match width {
                None => "its Souffle form has no relation of it".to_owned(),
                Some(width) => format!("its Souffle form holds it at {width} columns, the engine at {}", component.outputs[at].columns.len()),
            };
            format!("{}, {}: against Souffle: {reason}", subject.name(), subject.part(at))
        })
        .collect()
}

/// The domain of an element's Souffle form, as it reaches the engine's
/// rows.
enum Domain {
    /// Each column of a relation that the Souffle form declares at an
    /// orientation type, by its index, with the names of that type's
    /// constants.
    Columns(Vec<(usize, Vec<&'static str>)>),
    /// The keys of Frame's inputs whose `extent` rows give each axis, and
    /// the index of the key column of each output.
    Keys { keys: Vec<Value>, columns: Vec<usize> },
    Whole,
}

impl Domain {
    fn of(subject: &Subject<'_>, inputs: &Value, souffle: &Souffle) -> Domain {
        match subject {
            Subject::Relation { .. } => Domain::Columns(souffle.column_types.iter().map(|(at, ty)| (*at, constant_names(ty))).collect()),
            Subject::Component { name, component, .. } if *name == FRAME => Domain::Keys {
                keys: frame_keys(component, inputs),
                columns: component.outputs.iter().map(|o| o.columns.iter().position(is_key).expect("each output of Frame has a key column")).collect(),
            },
            Subject::Component { .. } | Subject::Unfold { .. } => Domain::Whole,
        }
    }

    /// Whether `row` of the part at `part` lies inside the domain.
    fn holds(&self, part: usize, row: &[Cell]) -> bool {
        match self {
            Domain::Columns(columns) => columns.iter().all(|(at, names)| matches!(&row[*at], Cell::Value(Value::String(name)) if names.contains(&name.as_str()))),
            Domain::Keys { keys, columns } => match &row[columns[part]] {
                Cell::Value(key) => keys.contains(key),
                Cell::Ident(_) => false,
            },
            Domain::Whole => true,
        }
    }
}

/// The keys of Frame's `inputs` whose `extent` rows give each constant of
/// the type of their axis column.
fn frame_keys(component: &Component, inputs: &Value) -> Vec<Value> {
    let at = component.inputs.iter().position(|input| &*input.port.name.0 == FRAME_EXTENT).expect("Frame has an input `extent`");
    let columns = &component.inputs[at].port.columns;
    let key = columns.iter().position(is_key).expect("Frame's `extent` has a key column");
    let axis = columns.iter().position(|c| is_orientation(&component_type(c))).expect("Frame's `extent` has an axis column");
    let axes = constant_names(&component_type(&columns[axis]));
    let rows = inputs["inputs"][at]["rows"].as_array().map_or(&[][..], Vec::as_slice);
    let mut keys: Vec<Value> = Vec::new();
    for row in rows {
        let given = |a: &str| rows.iter().any(|r| r[key] == row[key] && r[axis] == a);
        if !keys.contains(&row[key]) && axes.iter().all(|a| given(a)) {
            keys.push(row[key].clone());
        }
    }
    keys
}
