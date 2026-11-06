//! The program relations of `docs/feature-spec/feature-spec.md#program-relations`:
//! the state's program as data, for the QueryVector and the candidate block. A
//! value is a lib name: a name of the lib, or the engine's identity of a query,
//! a table or a column, free of the names of the program's author.

use std::collections::{BTreeMap, BTreeSet};

use arclog::check::reads::form_reads;
use arclog::check::CheckedProgram;
use arclog::eval::determinations::relation_spelled;
use arclog::eval::join::one_part;
use arclog::hash::StableHash;
use arclog::program::path::NodePath;
use arclog::program::{ColumnName, FactRelation, Form, ProgramFact, ProgramRelation, RelationRef};
use arclog::registry::{Column as LibColumn, LibEntry, LibName, Macro, Registry};
use arclog::relations::{Relation, RowSet};
use arclog::resolver::{DependencyKind, GraphNodeIndex, Resolution};
use arclog::terms::{Constant, LibNameId, Term, TermId};
use arclog::types::{each_site_label, use_label, GraphRelation, ValueType};
use arclog_tables::flows::{ColumnSource, SourceColumn, SourceFrame, SourceKind};
use arclog_tables::identity::{relation_contents, relation_identity};

/// Whether `name` is a program relation.
pub fn is_program_relation(name: &str) -> bool {
    ProgramFact::of_name(name).is_some()
}

fn hex(hash: StableHash) -> String {
    format!("{:032x}", hash.0)
}

fn term(text: &str) -> TermId {
    Term::Constant(Constant::LibName(LibNameId::of(text))).encode().expect("a lib name's term id")
}

fn written(name: &ColumnName) -> String {
    match name {
        ColumnName::Written(text) => text.to_string(),
        ColumnName::Slot(slot) => format!("c{slot}"),
    }
}

/// The rows of each program relation, by their text.
#[derive(Default)]
struct Rows(BTreeMap<&'static str, BTreeSet<Vec<String>>>);

impl Rows {
    fn add(&mut self, fact: ProgramFact, row: &[&str]) {
        self.0.entry(fact.name()).or_default().insert(row.iter().map(|cell| cell.to_string()).collect());
    }
}

/// A table of the program: its relation, and its identity and that of each of
/// its columns, in row order.
struct TableOf {
    relation: GraphRelation,
    spelled: String,
    identity: String,
    columns: Vec<String>,
}

/// The relation that a table of `node` reads as, where the node gives a table.
pub(crate) fn table_name(kind: &DependencyKind) -> Option<String> {
    match kind {
        DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => Some(relation_spelled(relation)),
        DependencyKind::Chosen(name) => Some(relation_spelled(&ProgramRelation::Declared(name.clone()))),
        DependencyKind::Demonstrated(name) => Some(relation_spelled(&ProgramRelation::Declared(name.clone()))),
        DependencyKind::InstanceOutput { instance, output } => Some(format!("{}.{}", relation_spelled(&ProgramRelation::Declared(arclog::program::RelationName(instance.0.clone()))), output.0)),
        _ => None,
    }
}

fn table_of(program: &CheckedProgram, registry: &Registry, node: GraphNodeIndex) -> Option<TableOf> {
    let resolved = &program.program;
    let spelled = table_name(&resolved.graph.nodes[node.0 as usize].kind)?;
    let relation = GraphRelation { node, output: None };
    let form = resolved.form_of(node).clone();
    let (identity, columns) = relation_identity(program, registry, &relation, &form, &spelled)?;
    Some(TableOf { relation, spelled, identity, columns })
}

/// The name of a lib column of `columns`.
fn lib_column(columns: &[LibColumn], at: SourceColumn) -> String {
    match at {
        SourceColumn::Position(at) => columns.get(usize::from(at)).map(|column| written(&column.name)).unwrap_or_default(),
        SourceColumn::Example => "E".to_string(),
        SourceColumn::None => String::new(),
    }
}

fn lib_columns<'r>(registry: &'r Registry, name: &str) -> Option<&'r [LibColumn]> {
    match registry.entry(&LibName(name.into()))? {
        LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(&relation.columns),
        LibEntry::Proposer(proposer) => Some(&proposer.columns),
        LibEntry::Component(_) => None,
    }
}

/// The table whose node a read of `relation` at the atom's path resolves to.
fn read_node(program: &CheckedProgram, read: &NodePath) -> Option<GraphNodeIndex> {
    match program.program.resolution(read) {
        Some(Resolution::Node(node)) => Some(*node),
        _ => None,
    }
}

/// The text of the type of a column, without its source.
fn type_text(ty: &ValueType) -> String {
    format!("{:?}", ty.without_source())
}

/// A query of a program, with what the program relations hold of it.
#[derive(Clone, Debug)]
pub struct QueryFacts {
    /// Its place among the program's forms.
    pub form: usize,
    pub identity: String,
    pub kind: String,
    /// Each table it computes, by identity.
    pub computes: Vec<String>,
    /// Each table it reads, by identity or by a base table's name.
    pub reads: Vec<String>,
}

/// A program as the program relations give it, with each table's name in the program, which a
/// reader of its rows needs and no feature reads.
#[derive(Clone, Debug, Default)]
pub struct ProgramFacts {
    pub queries: Vec<QueryFacts>,
    /// A table's identity to its name in the program.
    pub table_names: BTreeMap<String, String>,
    /// Each row of `column_type`, `column_lineage` and the others, by the relation's name.
    pub rows: BTreeMap<&'static str, BTreeSet<Vec<String>>>,
}

/// The program as data: the rows of the program relations, and its queries.
pub fn program_facts(program: &CheckedProgram, registry: &Registry) -> ProgramFacts {
    let rows = program_rows(program, registry);
    let resolved = &program.program;
    let mut table_names = BTreeMap::new();
    for node in 0..resolved.graph.nodes.len() as u32 {
        if let Some(table) = table_of(program, registry, GraphNodeIndex(node)) {
            table_names.insert(table.identity, table.spelled);
        }
    }
    let empty = BTreeSet::new();
    let of_fact = |fact: ProgramFact| rows.0.get(fact.name()).unwrap_or(&empty);
    let mut queries = Vec::new();
    for (top, form) in resolved.program.value().forms.iter().enumerate() {
        if matches!(form, Form::Out(_) | Form::Claim(_) | Form::Alts(_)) {
            continue;
        }
        let Some(identity) = resolved.query_identity(top, registry) else { continue };
        let identity = hex(identity.content.content_hash());
        let kind = of_fact(ProgramFact::QueryKind).iter().find(|row| row[0] == identity).map_or(String::new(), |row| row[1].clone());
        let computes = of_fact(ProgramFact::QueryComputes).iter().filter(|row| row[0] == identity).map(|row| row[1].clone()).collect();
        let reads = of_fact(ProgramFact::QueryReads).iter().filter(|row| row[0] == identity && (table_names.contains_key(&row[1]) || matches!(row[1].as_str(), "input" | "ex_input" | "ex_output"))).map(|row| row[1].clone()).collect();
        queries.push(QueryFacts { form: top, identity, kind, computes, reads });
    }
    ProgramFacts { queries, table_names, rows: rows.0 }
}

/// The rows of each program relation of `program`, as relations.
pub fn program_relations(program: &CheckedProgram, registry: &Registry) -> Vec<(FactRelation, Relation)> {
    let rows = program_rows(program, registry);
    ProgramFact::ALL
        .into_iter()
        .map(|fact| {
            let mut set = RowSet::empty(fact.columns().len() as u16);
            for row in rows.0.get(fact.name()).into_iter().flatten() {
                set.insert(row.iter().map(|cell| term(cell)).collect());
            }
            (FactRelation::Program(fact), one_part(set))
        })
        .collect()
}

fn program_rows(program: &CheckedProgram, registry: &Registry) -> Rows {
    let mut rows = Rows::default();
    let resolved = &program.program;
    // Each table of the program, by its node.
    let mut tables: BTreeMap<u32, TableOf> = BTreeMap::new();
    for node in 0..resolved.graph.nodes.len() as u32 {
        if let Some(table) = table_of(program, registry, GraphNodeIndex(node)) {
            tables.insert(node, table);
        }
    }
    let upstream = |source: &ColumnSource| -> String {
        match (&source.relation, source.column) {
            (None, _) => "0".to_string(),
            (Some(RelationRef::Fact(fact)), column) => format!("{}.{}", fact.spelled(), lib_column(registry.fact_columns(*fact), column)),
            (Some(RelationRef::Lib(name)), SourceColumn::None) => name.0.to_string(),
            (Some(RelationRef::Lib(name)), column) => format!("{}.{}", name.0, lib_columns(registry, &name.0).map(|columns| lib_column(columns, column)).unwrap_or_default()),
            (Some(RelationRef::DefinedPort(port)), _) => port.0.to_string(),
            (Some(relation), column) => {
                let held = program.program.program_read(relation).and_then(|node| tables.get(&node.0));
                match (held, column) {
                    (Some(table), SourceColumn::Position(at)) => format!("{}/{}", table.identity, table.columns.get(usize::from(at)).cloned().unwrap_or_default()),
                    (Some(table), _) => table.identity.clone(),
                    (None, _) => String::new(),
                }
            }
        }
    };
    for table in tables.values() {
        let form = resolved.form_of(table.relation.node).clone();
        let Ok(contents) = relation_contents(program, registry, &table.relation, &form, &table.spelled) else { continue };
        let types = program.types.columns(&table.relation).unwrap_or_default();
        for (at, column) in table.columns.iter().enumerate() {
            if let Some(ty) = types.get(at) {
                rows.add(ProgramFact::ColumnType, &[&table.identity, column, &type_text(ty)]);
                if let ValueType::Ident(arclog::types::IdentSource::Form(source)) = ty {
                    rows.add(ProgramFact::ColumnSource, &[&table.identity, column, &format!("{source:?}")]);
                }
            }
            for source in contents.flows.get(at).into_iter().flatten() {
                let kind = match source.kind {
                    SourceKind::Copy => "Copy",
                    SourceKind::Computed => "Computed",
                    SourceKind::Constant => "Constant",
                    SourceKind::LibName => "LibName",
                };
                rows.add(ProgramFact::ColumnLineage, &[&table.identity, column, kind, &upstream(source)]);
                for frame in &source.frames {
                    match frame {
                        SourceFrame::Read => {
                            let read = match &source.relation {
                                Some(RelationRef::Fact(FactRelation::ExOutput | FactRelation::Output)) => "output".to_string(),
                                Some(RelationRef::Fact(_)) => "input".to_string(),
                                _ => upstream(source),
                            };
                            rows.add(ProgramFact::ColumnFrame, &[&table.identity, column, &read]);
                        }
                        SourceFrame::Made { maker, .. } => rows.add(ProgramFact::ColumnFrame, &[&table.identity, column, &maker.spelled()]),
                        SourceFrame::Unknown => rows.add(ProgramFact::ColumnFrame, &[&table.identity, column, "unknown"]),
                    }
                }
            }
        }
    }
    // Each query, and what it reads and computes.
    for (top, form) in resolved.program.value().forms.iter().enumerate() {
        let kind = match form {
            Form::Clause(clause) => match clause.value().keyword {
                arclog::program::ClauseKeyword::Rule | arclog::program::ClauseKeyword::RuleOrDet => "RULE",
                arclog::program::ClauseKeyword::Det | arclog::program::ClauseKeyword::DetOrRule => "DET",
            },
            Form::Instance(_) => "INIT",
            Form::Choose(_) => "CHOOSE",
            Form::RigidDet(_) => "RIGID_DET",
            Form::Demonstrated(_) => "DEMONSTRATED",
            Form::Out(_) | Form::Claim(_) | Form::Alts(_) => continue,
        };
        let Some(identity) = resolved.query_identity(top, registry) else { continue };
        let query = hex(identity.content.content_hash());
        rows.add(ProgramFact::QueryKind, &[&query, kind]);
        let path = NodePath::top(top as u32);
        if let Form::Instance(instance) = form {
            rows.add(ProgramFact::QueryAtom, &[&query, &instance.value().component.0]);
        }
        for node in resolved.nodes_of(&path) {
            if let Some(table) = tables.get(&node.0) {
                rows.add(ProgramFact::QueryComputes, &[&query, &table.identity]);
            }
        }
        for read in form_reads(form, &path) {
            let at = path.join(&read.at);
            // The table the atom reads, and the name of each column it names.
            let (table, columns): (String, Vec<(String, String)>) = match &read.atom.relation {
                RelationRef::Fact(fact) => {
                    let name = fact.spelled();
                    rows.add(ProgramFact::QueryAtom, &[&query, &name]);
                    (name.clone(), registry.fact_columns(*fact).iter().map(|column| (written(&column.name), format!("{name}.{}", written(&column.name)))).collect())
                }
                RelationRef::Lib(name) => {
                    rows.add(ProgramFact::QueryAtom, &[&query, &name.0]);
                    let columns = lib_columns(registry, &name.0).unwrap_or_default();
                    (name.0.to_string(), columns.iter().map(|column| (written(&column.name), format!("{}.{}", name.0, written(&column.name)))).collect())
                }
                _ => {
                    let Some(node) = read_node(program, &at) else { continue };
                    let Some(table) = tables.get(&node.0) else { continue };
                    let names = resolved.column_names(node).unwrap_or_default();
                    (table.identity.clone(), names.into_iter().zip(table.columns.iter().cloned()).collect())
                }
            };
            rows.add(ProgramFact::QueryReads, &[&query, &table]);
            for site in read.atom.sites.iter() {
                each_site_label(site, &mut Vec::new(), &mut |use_, column_path| {
                    let Some(label) = use_label(use_) else { return };
                    let Some(position) = identity.order.label_position(&NodePath::default(), label) else { return };
                    let spelled: Vec<String> = column_path.iter().map(written).collect();
                    let name = spelled.join(".");
                    // A named label of a type parameter's column is at that column, as a
                    // record's field is where a table names it.
                    let first = spelled.first().cloned().unwrap_or_default();
                    let column = columns.iter().find(|(own, _)| *own == name).or_else(|| columns.iter().find(|(own, _)| *own == first)).map_or(first.as_str(), |(_, column)| column.as_str());
                    rows.add(ProgramFact::LabelSite, &[&query, &format!("#{position}"), &table, column]);
                });
            }
        }
    }
    rows
}
