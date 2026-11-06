//! The columns of a table of a checked program, as an expansion addresses
//! them: each by a name, with the path that a site on it writes.
//!
//! A column of a declared relation has its label's name. An instance's output
//! has the fields of its key and of its records as columns, and a read writes
//! them in the `:key` site and in the site of the record's column
//! (`work/feature-spec/feature-spec.md#column-names`).

use std::sync::Arc;

use arclog::check::CheckedProgram;
use arclog::eval::relation_of;
use arclog::program::path::{node_at, NodeRef};
use arclog::program::{ColumnName, DeclaredName, InstanceName, OutputName, OutputOwner, OutputStep, PortName, ProgramRelation, RelationName};
use arclog::resolver::{DependencyKind, Side};
use arclog::types::{GraphRelation, ValueType};

/// A column of a table.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TableColumn {
    /// The name by which an expression addresses the column, unique in the
    /// table.
    pub name: String,
    /// The steps of a site on the column: `P`, or `key` then `Col`.
    pub path: Vec<String>,
    /// The column's type, where the checked program gives it one.
    pub ty: Option<ValueType>,
}

/// The relations that hold a table given as stored rows, each as an atom's head
/// writes it: the table, and its lifted form, whose first column is `E`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StoredReads {
    pub plain: String,
    pub lifted: Option<String>,
}

/// What an expansion reads of a table.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TableSchema {
    pub columns: Vec<TableColumn>,
    /// Where the table is given as stored rows, the relations that hold them.
    pub stored: Option<StoredReads>,
    /// Whether a task-wide form reads the table in its lifted form.
    pub per_input: bool,
    /// Whether a column holds an Example, which makes an expression over the
    /// table task-wide.
    pub has_example: bool,
}

/// The tables of a state that an expansion reads.
pub trait Tables {
    fn table(&self, name: &str) -> Option<TableSchema>;
}

/// The value type that a type's name in a table's description gives.
pub fn type_of_name(name: &str) -> Option<ValueType> {
    Some(match name {
        "Int" => ValueType::Int,
        "Nat" => ValueType::Nat,
        "Color" => ValueType::Color,
        "Example" => ValueType::Example,
        "Unit" => ValueType::Unit,
        "LibName" => ValueType::LibName,
        "Box" => ValueType::Box,
        "Position" => ValueType::Position,
        "Offset" => ValueType::Offset,
        "Ident" => ValueType::OPEN_IDENT,
        "C4" => ValueType::C4,
        "D4" => ValueType::D4,
        "Dir" => ValueType::Dir,
        "DiagDir" => ValueType::DiagDir,
        "Dir8" => ValueType::Dir8,
        "Axis" => ValueType::Axis,
        "DiagAxis" => ValueType::DiagAxis,
        "Axis4" => ValueType::Axis4,
        "Sym" => ValueType::Sym,
        "Sense" => ValueType::Sense,
        _ => return None,
    })
}

/// The relation that a program's text names `name`: `&ink`, or `&rays.ray`.
pub fn program_relation(name: &str) -> ProgramRelation {
    match name.split_once('.') {
        None => ProgramRelation::Declared(RelationName(DeclaredName::Written(name.into()))),
        Some((owner, port)) => ProgramRelation::Output(OutputName {
            of: OutputOwner::Instance(InstanceName(DeclaredName::Written(owner.into()))),
            path: Arc::from([OutputStep::Port(PortName(port.into()))]),
        }),
    }
}

/// The graph relation of the table `name` in `program`.
pub fn graph_relation(program: &CheckedProgram, name: &str) -> Option<GraphRelation> {
    relation_of(program, &program_relation(name))
}

fn written(name: &ColumnName) -> Option<&str> {
    match name {
        ColumnName::Written(text) => Some(text),
        ColumnName::Slot(_) => None,
    }
}

/// The names that a read of a `DET` by clauses may name: every label its
/// clause keeps. A later read can name a column that no read of the state
/// names, as `docs/arclog/arclog.md#sites` gives a `DET`'s columns.
fn det_labels(program: &CheckedProgram, relation: &GraphRelation) -> Option<Vec<String>> {
    let resolved = &program.program;
    if !matches!(resolved.graph.nodes[relation.node.0 as usize].kind, DependencyKind::Parameter(_) | DependencyKind::Chosen(_)) {
        return None;
    }
    let root = NodeRef::Program(resolved.program.value());
    let form = resolved.form_of(relation.node);
    let Some(NodeRef::Clause(clause)) = node_at(root, form) else { return None };
    let names: Option<Vec<String>> = clause.columns.iter().map(|column| written(&column.name).map(str::to_string)).collect();
    names.filter(|names| !names.is_empty())
}

/// The schema of the table `name` of `program`, or `None` where it has no such
/// table.
pub fn table_schema(program: &CheckedProgram, name: &str) -> Option<TableSchema> {
    let relation = graph_relation(program, name)?;
    let resolved = &program.program;
    let types = program.types.columns(&relation);
    let row_names = resolved.column_names(relation.node)?;
    let mut names = row_names.clone();
    let mut typed: Vec<Option<ValueType>> = match types {
        Some(types) if types.len() == row_names.len() => types.iter().cloned().map(Some).collect(),
        _ => vec![None; row_names.len()],
    };
    // A `DET` keeps the columns that a read names, so a column no read of the
    // state names has no type until a feature's read names it.
    if let Some(labels) = det_labels(program, &relation) {
        for label in labels {
            if !names.contains(&label) {
                names.push(label);
                typed.push(None);
            }
        }
    }
    let mut columns: Vec<TableColumn> = Vec::new();
    for (name, ty) in names.iter().zip(typed) {
        let path: Vec<String> = name.split('.').map(str::to_string).collect();
        let mut short = path.last().expect("a split gives a part").clone();
        let base = short.clone();
        let mut suffix = 2;
        while columns.iter().any(|column| column.name == short) {
            short = format!("{base}_{suffix}");
            suffix += 1;
        }
        columns.push(TableColumn { name: short, path, ty });
    }
    Some(TableSchema {
        columns,
        stored: None,
        per_input: resolved.side(relation.node) == Side::PerInput,
        has_example: program.types.has_example_column(&relation),
    })
}

/// The label that a site on a column writes: its name, with its first letter in upper case.
pub fn label_name(name: &str) -> String {
    crate::expand::label_of(name)
}
