//! The columns of a table of a checked program, as an expansion addresses
//! them: each by a name, with the path that a site on it writes.
//!
//! A column of a declared relation has its label's name. An instance's output
//! has the fields of its key and of its records as columns, and a read writes
//! them in the `:key` site and in the site of the record's column
//! (`docs/feature-spec/feature-spec.md#column-names`).

use std::sync::Arc;

use arclog::check::CheckedProgram;
use arclog::eval::relation_of;
use arclog::program::path::{node_at, NodePath, NodeRef};
use arclog::program::LabelId;
use arclog::program::{ColumnName, DeclaredName, InstanceName, OutputName, OutputOwner, OutputStep, PortName, ProgramRelation, RelationName};
use arclog::resolver::{output_of, DependencyKind, Resolution, ResolvedProgram, Side};
use arclog::types::{each_site_label, use_label, GraphRelation, ValueType};

use crate::lookup::LookupSet;

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

/// The name that `type_of_name` reads back to `ty`, none for a type that a table's description does not name (a Pose or a Record).
pub fn name_of_type(ty: &ValueType) -> Option<String> {
    use arclog::types::IdentSource;
    Some(match ty {
        ValueType::Int => "Int".to_string(),
        ValueType::Nat => "Nat".to_string(),
        ValueType::Color => "Color".to_string(),
        ValueType::Example => "Example".to_string(),
        ValueType::Unit => "Unit".to_string(),
        ValueType::LibName => "LibName".to_string(),
        ValueType::Box => "Box".to_string(),
        ValueType::Position => "Position".to_string(),
        ValueType::Offset => "Offset".to_string(),
        ValueType::Ident(IdentSource::Open) => "Ident".to_string(),
        ValueType::Ident(IdentSource::Form(source)) => format!("Ident@{:x}", source.0 .0),
        ValueType::C4 => "C4".to_string(),
        ValueType::D4 => "D4".to_string(),
        ValueType::Dir => "Dir".to_string(),
        ValueType::DiagDir => "DiagDir".to_string(),
        ValueType::Dir8 => "Dir8".to_string(),
        ValueType::Axis => "Axis".to_string(),
        ValueType::DiagAxis => "DiagAxis".to_string(),
        ValueType::Axis4 => "Axis4".to_string(),
        ValueType::Sym => "Sym".to_string(),
        ValueType::Sense => "Sense".to_string(),
        ValueType::Pose(_) | ValueType::Record(_) => return None,
    })
}

/// The value type that a type's name in a table's description gives.
pub fn type_of_name(name: &str) -> Option<ValueType> {
    // An Ident column of one source, as a tables file writes it.
    if let Some(source) = name.strip_prefix("Ident@") {
        let identity = u128::from_str_radix(source, 16).ok()?;
        return Some(ValueType::Ident(arclog::types::IdentSource::Form(arclog::types::SourceId(arclog::hash::StableHash(identity)))));
    }
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
    let mut examples = LookupSet::new();
    example_labels(NodeRef::Clause(clause), form.clone(), resolved, &mut examples);
    let names: Option<Vec<String>> = clause.columns.iter().filter(|column| !examples.contains(&column.label)).map(|column| written(&column.name).map(str::to_string)).collect();
    names.filter(|names| !names.is_empty())
}

/// The labels under `node` that a read holds at a column of an Example. A read of the relation at such a label would
/// make it a column, and a per-input read of it is refused, so a table's schema has it only where a read of the state names it.
fn example_labels(node: NodeRef<'_>, at: NodePath, resolved: &ResolvedProgram, out: &mut LookupSet<LabelId>) {
    if let Some(atom) = node.atom() {
        if let Some(Resolution::Node(read)) = resolved.resolution(&at) {
            let columns = resolved.example_columns(*read, output_of(&atom.relation));
            // A clause reads a per-input relation in its lifted form, and `ex_input` and `ex_output` have one too, with `E` first.
            let lifted = resolved.side(*read) == Side::PerInput || matches!(resolved.graph.nodes[read.0 as usize].kind, DependencyKind::Fact(_));
            for site in atom.sites.iter() {
                each_site_label(site, &mut Vec::new(), &mut |use_, path| {
                    let at_lifted = lifted && path.first().and_then(written) == Some("E");
                    if at_lifted || columns.iter().any(|column| path.starts_with(column)) {
                        out.extend(use_label(use_));
                    }
                });
            }
        }
        return;
    }
    for (child, index) in node.children().into_iter().zip(0u32..) {
        example_labels(child, at.child(index), resolved, out);
    }
}

/// Whether a column of this name and type is a table's own column named `E`: one that is not an Example.
pub fn is_own_e(name: &str, ty: Option<&ValueType>) -> bool {
    name == "E" && !matches!(ty, Some(ValueType::Example))
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
        // A read labels a column by its name with the first letter in upper case, so a name whose label an earlier column has
        // takes the suffix `_2`, then `_3`, on its label, which is the name that the engine gives the column. The name `E` is
        // the Example column's, so a column of another type that a table names `E` is addressed as `E_2`.
        let clashes = |name: &str| is_own_e(name, ty.as_ref()) || columns.iter().any(|column| label_name(&column.name) == label_name(name));
        if clashes(&short) {
            let base = label_name(&short);
            let mut suffix = 2;
            short = base.clone();
            while clashes(&short) {
                short = format!("{base}_{suffix}");
                suffix += 1;
            }
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

/// The labels that a read of a table gives its columns, in the order of `columns`: each name with its first letter in upper
/// case, and the suffix `_2`, then `_3`, where a label is taken.
pub fn read_labels(columns: &[TableColumn]) -> Vec<String> {
    let mut taken = Vec::new();
    columns.iter().map(|column| crate::expand::unique(&label_name(&column.name), &mut taken)).collect()
}

/// The label that a site on a column writes: its name, with its first letter in upper case.
pub fn label_name(name: &str) -> String {
    crate::expand::label_of(name)
}
