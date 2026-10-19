//! The inputs file of each lib element, generated from its columns.
//!
//! # An inputs file
//!
//! A JSON object: `element`, the element's arclog name; `kind`, `relation`
//! or `component`; `constants`, the name of each orientation constant of
//! the registry; and by kind:
//!
//! - a relation: `columns`, each column's name and the kind of its values;
//!   `domains`, the constants of each column of an orientation type;
//!   `modes`, for each mode, `mode`, the names of its columns, and `rows`,
//!   the rows of those columns. A relation with no mode has one mode of no
//!   column and one empty row.
//! - a component: `type_arguments`, the type each type parameter takes;
//!   `inputs`, each input's `port`, `columns` and `rows`; `outputs`, each
//!   output's `port` and `columns`.
//!
//! A value is a number, a Box as its margins `[t, b, l, r]`, or the name
//! of an orientation constant. The kind of a column's values is `number`,
//! `box` or `constant`.
//!
//! An element of the Souffle lib that declares no input of the element's
//! has a second inputs file, `<element>.souffle.json`, in which each such
//! input holds no row.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

use arclog::algebra::geometry::Geometry;
use arclog::program::ColumnName;
use arclog::registry::{AlgebraRelation, Column, ColumnType, Component, LibEntry, LibName, Macro, Registry};
use arclog::terms::{Constant, Term, TermId};
use arclog::types::ValueType;
use serde_json::{json, Value};

use super::sources::fnv1a;

/// The seed of the inputs, so that a run gives the same inputs each time.
pub(super) const SEED: u64 = 0x9e37_79b9_7f4a_7c15;

/// The rows of each mode of a relation's inputs, and of each input of a
/// component's.
pub(super) const ROWS: usize = 12;

/// The values of one type that a component's inputs draw from, few so that
/// the rows of two inputs meet.
pub(super) const POOL: usize = 4;

/// The height and width of the one frame that every generated Box lies
/// in, so that the Positions of one inputs file are cells of one grid.
pub(super) const FRAME: (usize, usize) = (4, 5);

/// The type each type parameter of a component takes in its inputs, and
/// its name as arclog and Souffle write it.
pub(super) const PARAMETER_TYPE: (ValueType, &str) = (ValueType::Box, "Box");

/// A lib element the registry declares: a relation or a relation macro,
/// or a component.
pub(super) enum Element<'r> {
    Relation { name: Box<str>, relation: &'r AlgebraRelation },
    Component { name: Box<str>, component: &'r Component },
}

/// Each relation, relation macro and component of the registry, in the
/// order of their names.
pub(super) fn elements() -> Vec<Element<'static>> {
    let registry = Registry::get();
    let mut names: Vec<&LibName> = registry.names().collect();
    names.sort_by(|a, b| a.0.cmp(&b.0));
    names
        .into_iter()
        .filter_map(|name| {
            let name_text = name.0.clone();
            match registry.entry(name)? {
                LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => {
                    Some(Element::Relation { name: name_text, relation })
                }
                LibEntry::Component(component) => Some(Element::Component { name: name_text, component }),
                LibEntry::Proposer(_) => None,
            }
        })
        .collect()
}

impl Element<'_> {
    pub(super) fn name(&self) -> &str {
        match self {
            Element::Relation { name, .. } | Element::Component { name, .. } => name,
        }
    }

    /// The element's inputs file, generated from its columns.
    pub(super) fn inputs(&self) -> Value {
        let mut random = Random::of(self.name());
        let constants: BTreeSet<&str> = Geometry::get()
            .domain(&ValueType::Dir8)
            .iter()
            .chain(Geometry::get().domain(&ValueType::Axis4))
            .chain(Geometry::get().domain(&ValueType::D4))
            .chain(Geometry::get().domain(&ValueType::Sym))
            .chain(Geometry::get().domain(&ValueType::Sense))
            .map(|&id| constant_name(id))
            .collect();
        let mut out = json!({ "element": self.name(), "constants": constants.into_iter().collect::<Vec<_>>() });
        match self {
            Element::Relation { relation, .. } => {
                let modes: Vec<Vec<usize>> = if relation.modes.is_empty() {
                    vec![Vec::new()]
                } else {
                    relation.modes.iter().map(|mode| mode.grounded.iter().map(|c| column_index(relation, c)).collect()).collect()
                };
                let modes: Vec<Value> = modes
                    .iter()
                    .map(|mode| {
                        let count = if mode.is_empty() { 1 } else { ROWS };
                        let rows: Vec<Value> =
                            (0..count).map(|_| Value::from(mode.iter().map(|&i| random.value(&relation_type(&relation.columns[i]))).collect::<Vec<_>>())).collect();
                        let names: Vec<String> = mode.iter().map(|&i| column_text(&relation.columns[i].name)).collect();
                        json!({ "mode": names, "rows": rows })
                    })
                    .collect();
                let domains: BTreeMap<String, Vec<&str>> = relation
                    .columns
                    .iter()
                    .filter(|c| is_orientation(&relation_type(c)))
                    .map(|c| (column_text(&c.name), constant_names(&relation_type(c))))
                    .collect();
                out["kind"] = json!("relation");
                out["columns"] = columns_json(&relation.columns, &|c| relation_type(c));
                out["domains"] = json!(domains);
                out["modes"] = Value::from(modes);
            }
            Element::Component { component, .. } => {
                let ty = |column: &Column| component_type(column);
                let mut pools: Vec<(ValueType, Vec<Value>)> = Vec::new();
                let mut pooled = |ty: &ValueType| -> Value {
                    let at = match pools.iter().position(|(t, _)| t == ty) {
                        Some(at) => at,
                        None => {
                            let pool = (0..POOL).map(|_| random.value(ty)).collect();
                            pools.push((ty.clone(), pool));
                            pools.len() - 1
                        }
                    };
                    let index = random.below(POOL);
                    pools[at].1[index].clone()
                };
                let inputs: Vec<Value> = component
                    .inputs
                    .iter()
                    .map(|input| {
                        let rows: BTreeSet<String> = (0..ROWS)
                            .map(|_| Value::from(input.port.columns.iter().map(|c| pooled(&ty(c))).collect::<Vec<_>>()).to_string())
                            .collect();
                        let rows: Vec<Value> = rows.iter().map(|row| serde_json::from_str(row).expect("a row as JSON")).collect();
                        json!({ "port": &*input.port.name.0, "columns": columns_json(&input.port.columns, &ty), "rows": rows })
                    })
                    .collect();
                let outputs: Vec<Value> = component
                    .outputs
                    .iter()
                    .map(|output| json!({ "port": &*output.name.0, "columns": columns_json(&output.columns, &ty) }))
                    .collect();
                out["kind"] = json!("component");
                out["type_arguments"] = Value::from(vec![PARAMETER_TYPE.1; component.type_parameters.len()]);
                out["inputs"] = Value::from(inputs);
                out["outputs"] = Value::from(outputs);
            }
        }
        out
    }
}

/// The type of a relation's column: a Pose column takes D4's constants.
pub(super) fn relation_type(column: &Column) -> ValueType {
    match &column.ty {
        ColumnType::Fixed(ty) | ColumnType::PoseOr(ty) => ty.clone(),
        ColumnType::Pose | ColumnType::SharedPose => ValueType::D4,
        ColumnType::Parameter(_) => panic!("a relation's column is of no type parameter"),
    }
}

/// The type of a component's column, a type parameter taking
/// [`PARAMETER_TYPE`].
pub(super) fn component_type(column: &Column) -> ValueType {
    match &column.ty {
        ColumnType::Parameter(_) => PARAMETER_TYPE.0,
        _ => relation_type(column),
    }
}

pub(super) fn column_index(relation: &AlgebraRelation, name: &ColumnName) -> usize {
    relation.columns.iter().position(|c| c.name == *name).expect("a mode's column is a column of its relation")
}

pub(super) fn column_text(name: &ColumnName) -> String {
    match name {
        ColumnName::Written(text) => text.to_string(),
        ColumnName::Slot(slot) => format!("#{slot}"),
    }
}

/// Each column's name and the kind of its values.
pub(super) fn columns_json(columns: &[Column], ty: &dyn Fn(&Column) -> ValueType) -> Value {
    Value::from(columns.iter().map(|c| json!([column_text(&c.name), value_kind(&ty(c))])).collect::<Vec<_>>())
}

/// The kind of the values of `ty` in an inputs file.
pub(super) fn value_kind(ty: &ValueType) -> &'static str {
    if is_orientation(ty) {
        "constant"
    } else if *ty == ValueType::Box {
        "box"
    } else {
        "number"
    }
}

pub(super) fn is_orientation(ty: &ValueType) -> bool {
    !matches!(ty, ValueType::Number | ValueType::Color | ValueType::Example | ValueType::Unit | ValueType::Box | ValueType::Ident | ValueType::Record(_))
}

pub(super) fn constant_name(id: TermId) -> &'static str {
    let registry = Registry::get();
    for ty in [ValueType::Dir8, ValueType::Axis4, ValueType::D4, ValueType::Sym, ValueType::Sense] {
        if Geometry::get().domain(&ty).contains(&id) {
            if let Term::Constant(Constant::Orientation(c)) = Term::decode(id, &ty) {
                return registry.constant_name(c);
            }
        }
    }
    panic!("an orientation constant's term id")
}

/// The names of the constants of the orientation type `ty`, in their
/// order.
pub(super) fn constant_names(ty: &ValueType) -> Vec<&'static str> {
    let names: BTreeSet<&str> = Geometry::get().domain(ty).iter().map(|&id| constant_name(id)).collect();
    names.into_iter().collect()
}

/// A fixed generator of the inputs: SplitMix64 from a seed and the
/// element's name, so that an element's inputs do not change when another
/// element is added.
pub(super) struct Random(u64);

impl Random {
    pub(super) fn of(name: &str) -> Random {
        Random(fnv1a(SEED, name.bytes()))
    }

    pub(super) fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    }

    pub(super) fn below(&mut self, n: usize) -> usize {
        (self.next() % n as u64) as usize
    }

    /// A value of `ty`: a number from 0 to 5, a Box of [`FRAME`], half of
    /// them a cell, a color, or a constant of an orientation type, picked
    /// from its constants in the order of their names.
    pub(super) fn value(&mut self, ty: &ValueType) -> Value {
        match ty {
            ValueType::Box => {
                let cell = self.below(2) == 0;
                let mut span = |extent: usize| {
                    let near = self.below(extent);
                    let far = if cell { extent - 1 - near } else { self.below(extent - near) };
                    (near, far)
                };
                let ((top, bottom), (left, right)) = (span(FRAME.0), span(FRAME.1));
                json!([top, bottom, left, right])
            }
            ValueType::Color => Value::from(self.below(10)),
            _ if is_orientation(ty) => {
                let names = constant_names(ty);
                Value::from(names[self.below(names.len())])
            }
            _ => Value::from(self.below(6)),
        }
    }
}

pub(super) fn inputs_path(snapshot: &Path, element: &str, suffix: &str) -> PathBuf {
    snapshot.join("inputs").join(format!("{element}{suffix}.json"))
}

pub(super) fn write_json(path: &Path, value: &Value) -> Result<(), String> {
    let text = serde_json::to_string(value).expect("JSON prints");
    std::fs::write(path, text + "\n").map_err(|error| format!("{} cannot be written: {error}", path.display()))
}

/// The inputs with each input of `ports` holding no row.
pub(super) fn emptied_inputs(inputs: &Value, ports: &[String]) -> Value {
    let mut out = inputs.clone();
    for input in out["inputs"].as_array_mut().into_iter().flatten() {
        if input["port"].as_str().is_some_and(|port| ports.iter().any(|p| p == port)) {
            input["rows"] = json!([]);
        }
    }
    out
}
