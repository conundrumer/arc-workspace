//! The columns of a table of a checked program, as an expansion addresses
//! them: each by a name, with the path that a site on it writes.
//!
//! A column of a declared relation has its label's name. An instance's output
//! has the fields of its key and of its records as columns, and a read writes
//! them in the `:key` site and in the site of the record's column
//! (`work/feature-spec/feature-spec.md#column-names`).

use std::sync::Arc;

use arclog::check::CheckedProgram;
use arclog::eval::determinations::relation_spelled;
use arclog::eval::relation_of;
use arclog::program::path::{node_at, NodeRef};
use arclog::program::{ColumnName, DeclaredName, FactRelation, InstanceName, OutputName, OutputOwner, OutputStep, PortName, ProgramFact, ProgramRelation, RelationName, RelationRef};
use arclog::registry::{Column as LibColumn, LibEntry, LibName, Macro, Registry};
use arclog::resolver::{DependencyKind, Side};
use arclog::types::{GraphRelation, ValueType};
use arclog_tables::flows::{ColumnSource, SourceColumn, SourceKind};
use arclog_tables::identity::{relation_contents, relation_identity};

use crate::expand::Rows;

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

/// What a pool reads of a column of a relation.
#[derive(Clone, Debug)]
pub struct ColumnFacts {
    /// The steps of a site on the column.
    pub path: Vec<String>,
    pub ty: ValueType,
    /// The column's identity in the engine, free of the labels of its program.
    pub identity: String,
    /// The roots of the column's lineage, each as `<relation>.<column>`.
    pub roots: Vec<String>,
}

/// The tables of a state that an expansion reads.
pub trait Tables {
    fn table(&self, name: &str) -> Option<TableSchema>;
    /// Whether the checker accepts the state's forms with `forms` after them,
    /// or why it refuses them.
    fn accepts(&self, forms: &[String]) -> Result<(), String>;
    /// The columns of `rows`, a relation that the state's forms with `forms`
    /// after them can read.
    fn columns_of(&self, forms: &[String], rows: &crate::expand::Rows) -> Result<Vec<ColumnFacts>, String>;
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

/// The columns of `rows`, a relation of `program`: a fact relation, a lib
/// relation or a relation of the program. A lifted read's `E` holds an Example.
pub fn column_facts(program: &CheckedProgram, registry: &Registry, rows: &Rows) -> Result<Vec<ColumnFacts>, String> {
    let example = || ColumnFacts { path: vec!["E".to_string()], ty: ValueType::Example, identity: "E".to_string(), roots: vec!["ex_input.E".to_string()] };
    let declared = |prefix: &str, columns: &[LibColumn]| -> Vec<ColumnFacts> {
        columns
            .iter()
            .filter_map(|column| {
                let name = written(&column.name)?.to_string();
                let ty = column.ty.fixed()?.clone();
                Some(ColumnFacts { path: vec![name.clone()], ty, identity: format!("{prefix}.{name}"), roots: vec![format!("{prefix}.{name}")] })
            })
            .collect()
    };
    let relation = rows.relation.as_str();
    if let Some(fact) = fact_of(relation) {
        let mut facts = declared(relation, registry.fact_columns(fact));
        // A read of `input` has the columns and the lineage of `ex_input`.
        for column in &mut facts {
            column.roots = vec![column.roots[0].replace("output.", "ex_output.").replacen("ex_ex_", "ex_", 1).replacen("input.", "ex_input.", usize::from(relation == "input"))];
        }
        return Ok(facts);
    }
    if !relation.starts_with('&') {
        let Some(columns) = lib_columns(registry, relation) else { return Err(format!("`{relation}` is no relation")) };
        return Ok(declared(relation, columns));
    }
    let Some(graph) = graph_relation(program, relation) else { return Err(format!("the program has no relation `{relation}`")) };
    let resolved = &program.program;
    let form = resolved.form_of(graph.node).clone();
    let Some(names) = resolved.column_names(graph.node) else { return Err(format!("the columns of `{relation}` are not known")) };
    let types = program.types.columns(&graph).ok_or_else(|| format!("the columns of `{relation}` have no types"))?;
    if names.len() != types.len() {
        return Err(format!("`{relation}` has {} columns and {} types", names.len(), types.len()));
    }
    let (table, identities) = relation_identity(program, registry, &graph, &form, relation).ok_or_else(|| format!("`{relation}` has no identity"))?;
    let contents = relation_contents(program, registry, &graph, &form, relation).map_err(|fault| fault.message.to_string())?;
    let mut facts = vec![example()];
    for (at, (name, ty)) in names.iter().zip(types).enumerate() {
        let path: Vec<String> = name.split('.').map(str::to_string).collect();
        let identity = identities.get(at).map_or_else(|| format!("{table}/?{at}"), |column| format!("{table}/{column}"));
        let roots = contents.flows.get(at).map(|sources| lineage_roots(program, registry, sources, &mut Vec::new())).unwrap_or_default();
        facts.push(ColumnFacts { path, ty: ty.clone(), identity, roots });
    }
    Ok(facts)
}

fn fact_of(name: &str) -> Option<FactRelation> {
    match name {
        "input" => Some(FactRelation::Input),
        "output" => Some(FactRelation::Output),
        "ex_input" => Some(FactRelation::ExInput),
        "ex_output" => Some(FactRelation::ExOutput),
        other => ProgramFact::of_name(other).map(FactRelation::Program),
    }
}

fn lib_columns<'r>(registry: &'r Registry, name: &str) -> Option<&'r [LibColumn]> {
    match registry.entry(&LibName(name.into()))? {
        LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(&relation.columns),
        LibEntry::Proposer(proposer) => Some(&proposer.columns),
        LibEntry::Component(_) => None,
    }
}

/// The lineage roots that `sources` reach: following each copy back to a fact
/// relation, a proposer or a lib column.
fn lineage_roots(program: &CheckedProgram, registry: &Registry, sources: &[ColumnSource], visiting: &mut Vec<(String, u16)>) -> Vec<String> {
    let mut roots: Vec<String> = Vec::new();
    for source in sources {
        let found: Vec<String> = match (&source.relation, source.column) {
            (None, _) => vec!["0".to_string()],
            (Some(RelationRef::Fact(fact)), column) => {
                // A read of `input` is a read of `ex_input`, as a source gives it.
                let fact = match *fact {
                    FactRelation::Input => FactRelation::ExInput,
                    FactRelation::Output => FactRelation::ExOutput,
                    other => other,
                };
                vec![format!("{}.{}", fact.spelled(), column_at(registry.fact_columns(fact), column))]
            }
            (Some(RelationRef::Lib(name)), column) => match lib_columns(registry, &name.0) {
                Some(columns) if !matches!(column, SourceColumn::None) => vec![format!("{}.{}", name.0, column_at(columns, column))],
                _ => vec![name.0.to_string()],
            },
            (Some(RelationRef::DefinedPort(port)), _) => vec![port.0.to_string()],
            (Some(relation @ (RelationRef::Declared(_) | RelationRef::Output(_))), SourceColumn::Position(at)) if source.kind == SourceKind::Copy => {
                let spelled = match relation {
                    RelationRef::Declared(name) => relation_spelled(&ProgramRelation::Declared(name.clone())),
                    RelationRef::Output(name) => relation_spelled(&ProgramRelation::Output(name.clone())),
                    _ => unreachable!("the arm's relations"),
                };
                let key = (spelled.clone(), at);
                if visiting.contains(&key) {
                    Vec::new()
                } else {
                    visiting.push(key);
                    let found = upstream_roots(program, registry, &spelled, usize::from(at), visiting);
                    visiting.pop();
                    found
                }
            }
            (Some(_), SourceColumn::Example) => vec!["ex_input.E".to_string()],
            (Some(_), _) => Vec::new(),
        };
        for root in found {
            if !roots.contains(&root) {
                roots.push(root);
            }
        }
    }
    roots
}

/// The name of `column` among `columns`.
fn column_at(columns: &[LibColumn], column: SourceColumn) -> String {
    match column {
        SourceColumn::Position(at) => columns.get(usize::from(at)).and_then(|own| written(&own.name)).unwrap_or_default().to_string(),
        SourceColumn::Example => "E".to_string(),
        SourceColumn::None => String::new(),
    }
}

fn upstream_roots(program: &CheckedProgram, registry: &Registry, name: &str, at: usize, visiting: &mut Vec<(String, u16)>) -> Vec<String> {
    let Some(graph) = graph_relation(program, name) else { return Vec::new() };
    let resolved = &program.program;
    let form = resolved.form_of(graph.node).clone();
    let Ok(contents) = relation_contents(program, registry, &graph, &form, name) else { return Vec::new() };
    contents.flows.get(at).map(|sources| lineage_roots(program, registry, sources, visiting)).unwrap_or_default()
}
