//! The program relations of `docs/feature-spec/feature-spec.md#program-relations`:
//! the state's program as data, for the QueryVector. A value is a lib name: a name of the lib, or the engine's identity of a query,
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
use arclog_tables::structure::{relation_bodies, RelationBodies};

use crate::body_features::{self, TableBody};

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
        DependencyKind::InstanceInput { instance, input } => Some(format!("{}.{}", relation_spelled(&ProgramRelation::Declared(arclog::program::RelationName(instance.0.clone()))), input.0)),
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
    /// What the lineage and the bodies of each table say of its columns, by the table's identity. [`add_table_columns`] fills it.
    pub columns: BTreeMap<String, TableColumns>,
}

/// What the lineage and the bodies of a table say of one column.
#[derive(Clone, Debug, Default)]
pub struct ColumnFacts {
    /// The column's type, as the program relations give it, with no arguments; empty for a column that has none.
    pub ty: String,
    /// The kinds of the lib and grid columns that its values come from: grid, proposer, lib, component, constant and recursive.
    pub kinds: BTreeSet<&'static str>,
    pub copy_steps: usize,
    pub input: bool,
    pub output: bool,
    pub parameter: bool,
    /// Whether each flow that gives the column a value copies one.
    pub copies_only: bool,
    pub body: Option<body_features::ColumnBody>,
}

/// What the lineage and the bodies of a table say of its columns, in the order of the columns.
#[derive(Clone, Debug, Default)]
pub struct TableColumns {
    pub columns: Vec<ColumnFacts>,
    pub body: Option<TableBody>,
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
    ProgramFacts { queries, table_names, rows: rows.0, columns: BTreeMap::new() }
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

/// What one column's values come from, as `model/contracts/features/provenance.py` traces it.
#[derive(Clone, Default)]
struct Traced {
    kinds: BTreeSet<&'static str>,
    steps: usize,
    input: bool,
    output: bool,
    parameter: bool,
}

/// What the trace of a column reads.
struct TraceEnv<'a> {
    program: &'a CheckedProgram,
    registry: &'a Registry,
    held: &'a BTreeMap<u32, RelationBodies>,
    /// The tables of a `DET` form, of a `RULE_OR_DET` form and of a `RIGID_DET` form.
    parameters: BTreeSet<u32>,
    /// The tables of an instance's output ports.
    outputs: BTreeSet<u32>,
}

/// The kind of origin of a column of the lib name `name`.
fn lib_kind(registry: &Registry, name: &LibName) -> &'static str {
    match registry.entry(name) {
        Some(LibEntry::Proposer(_)) => "proposer",
        Some(LibEntry::Component(_)) => "component",
        _ => "lib",
    }
}

impl TraceEnv<'_> {
    /// The table that a source reads, and the column of it, where the case holds that table.
    fn table_read(&self, source: &ColumnSource) -> Option<(u32, Option<usize>)> {
        let relation = source.relation.as_ref()?;
        if matches!(relation, RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_)) {
            return None;
        }
        let node = self.program.program.program_read(relation)?.0;
        self.held.contains_key(&node).then_some((node, match source.column {
            SourceColumn::Position(at) => Some(usize::from(at)),
            _ => None,
        }))
    }

    fn trace(&self, node: u32, column: usize, stack: &mut Vec<(u32, usize)>, memo: &mut BTreeMap<(u32, usize), Traced>) -> Traced {
        if let Some(held) = memo.get(&(node, column)) {
            return held.clone();
        }
        if stack.contains(&(node, column)) {
            return Traced { kinds: BTreeSet::from(["recursive"]), ..Traced::default() };
        }
        stack.push((node, column));
        let mut out = Traced { parameter: self.parameters.contains(&node), ..Traced::default() };
        let fact_reach = |out: &mut Traced, relation: &Option<RelationRef>| -> bool {
            match relation {
                Some(RelationRef::Fact(FactRelation::Input | FactRelation::ExInput)) => out.input = true,
                Some(RelationRef::Fact(FactRelation::ExOutput | FactRelation::Output)) => out.output = true,
                _ => return false,
            }
            true
        };
        for source in self.held[&node].contents.flows.get(column).into_iter().flatten() {
            match source.kind {
                SourceKind::Copy => {
                    if fact_reach(&mut out, &source.relation) {
                        out.kinds.insert("grid");
                    } else if let Some((from, at)) = self.table_read(source) {
                        // A column the source's table has no place for gives no origin and one more step.
                        let above = at.map(|at| self.trace(from, at, stack, memo)).unwrap_or_default();
                        out.kinds.extend(above.kinds);
                        out.steps = out.steps.max(above.steps + 1);
                        out.input |= above.input;
                        out.output |= above.output;
                        out.parameter |= above.parameter;
                    } else {
                        out.kinds.insert(match &source.relation {
                            Some(RelationRef::Lib(name)) => lib_kind(self.registry, name),
                            _ => "lib",
                        });
                    }
                }
                SourceKind::Computed => {
                    out.kinds.insert(if self.outputs.contains(&node) { "component" } else { "lib" });
                    if !fact_reach(&mut out, &source.relation) {
                        if let Some((from, Some(at))) = self.table_read(source) {
                            let above = self.trace(from, at, stack, memo);
                            out.input |= above.input;
                            out.output |= above.output;
                            out.parameter |= above.parameter;
                        }
                    }
                }
                SourceKind::Constant => {
                    out.kinds.insert("constant");
                }
                SourceKind::LibName => match &source.relation {
                    Some(RelationRef::Lib(name)) => {
                        let kind = lib_kind(self.registry, name);
                        out.kinds.insert(kind);
                        out.parameter |= kind == "proposer";
                    }
                    _ => {
                        out.kinds.insert("lib");
                    }
                },
            }
        }
        stack.pop();
        memo.insert((node, column), out.clone());
        out
    }
}

/// Gives `facts` what the lineage and the bodies of each table say of its columns: the values of `provenance.py`'s column and table features
/// and of `dependence.py`'s, as `table_numbers` reads them.
pub fn add_table_columns(facts: &mut ProgramFacts, program: &CheckedProgram, registry: &Registry) {
    let resolved = &program.program;
    let mut nodes: Vec<u32> = Vec::new();
    let mut relations = Vec::new();
    for node in 0..resolved.graph.nodes.len() as u32 {
        let Some(spelled) = table_name(&resolved.graph.nodes[node as usize].kind) else { continue };
        nodes.push(node);
        relations.push((GraphRelation { node: GraphNodeIndex(node), output: None }, resolved.form_of(GraphNodeIndex(node)).clone(), spelled));
    }
    let held: BTreeMap<u32, RelationBodies> = nodes.iter().copied().zip(relation_bodies(program, registry, &relations)).filter_map(|(node, found)| Some((node, found?))).collect();
    let forms = &resolved.program.value().forms[..];
    let parameters = held
        .keys()
        .copied()
        .filter(|node| match resolved.form_of(GraphNodeIndex(*node)).0.first().and_then(|top| forms.get(top.0 as usize)) {
            Some(Form::Clause(clause)) => !matches!(clause.value().keyword, arclog::program::ClauseKeyword::Rule),
            Some(Form::RigidDet(_)) => true,
            _ => false,
        })
        .collect();
    let outputs = held.keys().copied().filter(|node| matches!(resolved.graph.nodes[*node as usize].kind, DependencyKind::InstanceOutput { .. })).collect();
    let env = TraceEnv { program, registry, held: &held, parameters, outputs };
    let mut memo = BTreeMap::new();
    for (node, table) in &held {
        let types = program.types.columns(&GraphRelation { node: GraphNodeIndex(*node), output: None }).unwrap_or_default();
        let body = body_features::features(&table.bodies, &table.columns);
        let mut columns = Vec::new();
        for column in 0..table.contents.columns.len() {
            let traced = env.trace(*node, column, &mut Vec::new(), &mut memo);
            columns.push(ColumnFacts {
                ty: types.get(column).map(|ty| type_text(ty).split('(').next().unwrap_or("").to_string()).unwrap_or_default(),
                kinds: traced.kinds,
                copy_steps: traced.steps,
                input: traced.input,
                output: traced.output,
                parameter: traced.parameter,
                copies_only: table.contents.flows.get(column).into_iter().flatten().all(|source| source.kind == SourceKind::Copy),
                body: body.as_ref().and_then(|(columns, _)| columns.get(column).copied()),
            });
        }
        facts.columns.insert(table.identity.clone(), TableColumns { columns, body: body.map(|(_, table)| table) });
    }
}

/// Where one column's values come from, over a program's lineage rows.
#[derive(Clone, Default)]
struct Lineage {
    roots: BTreeSet<String>,
    copy_steps: usize,
    reach: BTreeSet<&'static str>,
}

fn reach_of(upstream: &str) -> Option<&'static str> {
    let head = upstream.split('.').next().unwrap_or("");
    match head {
        "input" | "ex_input" => Some("input"),
        "output" | "ex_output" => Some("output"),
        _ => None,
    }
}

/// The lineage of a column: its roots along `Copy` rows, and what its values depend on along every row.
fn lineage_of<'f>(table: &'f str, column: &'f str, rows: &BTreeMap<(&'f str, &'f str), Vec<(&'f str, &'f str)>>, parameters: &BTreeSet<&str>, memo: &mut BTreeMap<(&'f str, &'f str), Lineage>) -> Lineage {
    if let Some(held) = memo.get(&(table, column)) {
        return held.clone();
    }
    // A column that reaches itself, as an `Unfold`'s does, adds nothing on the way round.
    memo.insert((table, column), Lineage::default());
    let mut out = Lineage::default();
    if parameters.contains(table) {
        out.reach.insert("parameter");
    }
    for (kind, upstream) in rows.get(&(table, column)).into_iter().flatten() {
        let above = upstream.split_once('/').filter(|(from, at)| rows.contains_key(&(*from, *at)));
        match *kind {
            "Copy" => match above {
                Some((from, at)) => {
                    let held = lineage_of(from, at, rows, parameters, memo);
                    out.roots.extend(held.roots);
                    out.copy_steps = out.copy_steps.max(held.copy_steps + 1);
                    out.reach.extend(held.reach);
                }
                None => {
                    out.roots.insert((*upstream).to_string());
                    out.reach.extend(reach_of(upstream));
                }
            },
            "Computed" => {
                out.roots.insert("computed".to_string());
                match above {
                    Some((from, at)) => out.reach.extend(lineage_of(from, at, rows, parameters, memo).reach),
                    None => out.reach.extend(reach_of(upstream)),
                }
            }
            "Constant" => {
                out.roots.insert("0".to_string());
            }
            _ => {
                out.roots.insert((*upstream).to_string());
                out.reach.insert("parameter");
            }
        }
    }
    memo.insert((table, column), out.clone());
    out
}

/// What the program relations say of one table: for each type of its columns, how many hold each lineage kind and each lineage root, their greatest
/// count of copy steps, and what they depend on; which columns its query carries over; and its query's joins, by whether the two sides have one root.
pub fn table_numbers(facts: &ProgramFacts, name: &str, form: Option<usize>) -> Vec<(String, f64)> {
    let empty = BTreeSet::new();
    let rows_of = |fact: ProgramFact| facts.rows.get(fact.name()).unwrap_or(&empty);
    // Two tables of one name, an instance's input and the `DET` of that input, stand in two forms: the table is the one that the form computes.
    let named: Vec<&str> = facts.table_names.iter().filter(|(_, spelled)| spelled.as_str() == name).map(|(identity, _)| identity.as_str()).collect();
    let of_form = form.and_then(|form| facts.queries.iter().find(|query| query.form == form)).and_then(|query| named.iter().find(|identity| query.computes.iter().any(|computed| computed.as_str() == **identity)));
    let Some(identity) = of_form.or(named.first()).copied() else { return Vec::new() };
    let mut rows: BTreeMap<(&str, &str), Vec<(&str, &str)>> = BTreeMap::new();
    for row in rows_of(ProgramFact::ColumnLineage) {
        rows.entry((row[0].as_str(), row[1].as_str())).or_default().push((row[2].as_str(), row[3].as_str()));
    }
    let parameters: BTreeSet<&str> = facts.queries.iter().filter(|query| query.kind == "DET").flat_map(|query| query.computes.iter().map(String::as_str)).collect();
    let mut memo = BTreeMap::new();
    let mut out: BTreeMap<String, f64> = BTreeMap::new();
    let query = facts.queries.iter().find(|query| query.computes.iter().any(|computed| computed == identity));
    let used: BTreeSet<&str> = query.map_or_else(BTreeSet::new, |query| query.reads.iter().map(String::as_str).collect());
    let mut carried_from: BTreeSet<String> = BTreeSet::new();
    let (mut carried, mut fresh) = (0.0, 0.0);
    let mut copies_only = true;
    for row in rows_of(ProgramFact::ColumnType).iter().filter(|row| row[0] == identity) {
        let column = row[1].as_str();
        let ty = row[2].split('(').next().unwrap_or("");
        let own = rows.get(&(identity, column)).cloned().unwrap_or_default();
        for (kind, _) in &own {
            *out.entry(format!("?{ty} lineage {kind}")).or_insert(0.0) += 1.0;
            copies_only &= *kind == "Copy";
        }
        let held = lineage_of(identity, column, &rows, &parameters, &mut memo);
        for root in &held.roots {
            *out.entry(format!("?{ty} root {root}")).or_insert(0.0) += 1.0;
        }
        for word in &held.reach {
            out.insert(format!("?{ty} reaches {word}"), 1.0);
        }
        let steps = out.entry(format!("?{ty} copy steps")).or_insert(0.0);
        *steps = steps.max(held.copy_steps as f64);
        let mut from_a_use = false;
        for (kind, upstream) in &own {
            if *kind == "Copy" {
                let source = upstream.split(['/', '.']).next().unwrap_or("");
                let source = if source == "ex_input" && !used.contains(source) { "input" } else { source };
                if used.contains(source) {
                    carried_from.insert(source.to_string());
                    from_a_use = true;
                }
            }
        }
        if from_a_use { carried += 1.0 } else { fresh += 1.0 }
    }
    out.insert("columns carried".to_string(), carried);
    out.insert("columns new".to_string(), fresh);
    out.insert("uses with no column carried".to_string(), used.iter().filter(|read| !carried_from.contains(**read)).count() as f64);
    out.insert("every column is a copy".to_string(), f64::from(u8::from(copies_only && !rows.is_empty())));
    if let Some(detail) = facts.columns.get(identity) {
        add_column_numbers(&mut out, detail, facts, name);
    }
    if let Some(query) = query {
        let mut sites: BTreeMap<&str, Vec<(&str, &str)>> = BTreeMap::new();
        for row in rows_of(ProgramFact::LabelSite).iter().filter(|row| row[0] == query.identity) {
            sites.entry(row[1].as_str()).or_default().push((row[2].as_str(), row[3].as_str()));
        }
        let roots_at = |site: &(&'_ str, &'_ str), memo: &mut BTreeMap<_, _>| -> BTreeSet<String> {
            if rows.contains_key(&(site.0, site.1)) {
                lineage_of(facts_key(&rows, site.0, site.1).0, facts_key(&rows, site.0, site.1).1, &rows, &parameters, memo).roots
            } else {
                // A read of `input` has `ex_input` as its lineage.
                BTreeSet::from([site.1.strip_prefix("input.").map_or_else(|| site.1.to_string(), |rest| format!("ex_input.{rest}"))])
            }
        };
        let (mut same, mut different) = (0.0, 0.0);
        for held in sites.values().filter(|held| held.len() >= 2) {
            let first = roots_at(&held[0], &mut memo);
            if held[1..].iter().all(|site| !first.is_disjoint(&roots_at(site, &mut memo))) {
                same += 1.0;
            } else {
                different += 1.0;
            }
        }
        out.insert("joins of one root".to_string(), same);
        out.insert("joins of different roots".to_string(), different);
    }
    out.into_iter().filter(|(_, value)| *value != 0.0).collect()
}

/// The values of the provenance and dependence features of a table, over its columns. Where several columns have one type, a count is the
/// greatest or the sum as the lineage numbers above give it, and a flag holds where it holds for one of them.
fn add_column_numbers(out: &mut BTreeMap<String, f64>, detail: &TableColumns, facts: &ProgramFacts, name: &str) {
    const KINDS: [&str; 5] = ["grid", "proposer", "lib", "component", "constant"];
    for kind in KINDS {
        out.insert(format!("columns of {kind} origin"), detail.columns.iter().filter(|column| column.kinds.contains(kind)).count() as f64);
    }
    out.insert("every column is a copy".to_string(), f64::from(u8::from(!detail.columns.is_empty() && detail.columns.iter().all(|column| column.copies_only))));
    out.insert("some column from the train outputs".to_string(), f64::from(u8::from(detail.columns.iter().any(|column| column.output))));
    out.insert("some column from a task parameter".to_string(), f64::from(u8::from(detail.columns.iter().any(|column| column.parameter))));
    // Its place in the program, where a relation or an instance is one step.
    let head = |spelled: &'_ str| -> String { spelled.split('.').next().unwrap_or(spelled).to_string() };
    let spelled = |identity: &String| -> String { head(facts.table_names.get(identity).unwrap_or(identity)) };
    let mut graph: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for query in &facts.queries {
        for computed in &query.computes {
            let own = spelled(computed);
            let reads: Vec<String> = query.reads.iter().map(&spelled).filter(|read| *read != own).collect();
            graph.entry(own).or_default().extend(reads);
        }
    }
    fn steps(graph: &BTreeMap<String, BTreeSet<String>>, node: &str, memo: &mut BTreeMap<String, i64>) -> i64 {
        if let Some(found) = memo.get(node) {
            return *found;
        }
        memo.insert(node.to_string(), 0);
        let deepest = graph.get(node).map_or(-1, |reads| reads.iter().filter(|read| read.as_str() != node).map(|read| steps(graph, read, memo)).max().unwrap_or(-1));
        memo.insert(node.to_string(), 1 + deepest);
        1 + deepest
    }
    let own = head(name);
    out.insert("steps from the input grid".to_string(), steps(&graph, &own, &mut BTreeMap::new()) as f64);
    let mut before: BTreeSet<&str> = BTreeSet::new();
    let mut stack: Vec<&str> = graph.get(&own).map_or_else(Vec::new, |reads| reads.iter().map(String::as_str).collect());
    while let Some(next) = stack.pop() {
        if before.insert(next) {
            if let Some(reads) = graph.get(next) {
                stack.extend(reads.iter().map(String::as_str));
            }
        }
    }
    let facts_read = ["input", "ex_input", "ex_output"];
    out.insert("tables before it".to_string(), before.iter().filter(|name| !facts_read.contains(*name) && **name != own).count() as f64);
    out.insert("reads the input grid".to_string(), f64::from(u8::from(graph.get(&own).is_some_and(|reads| reads.contains("input")))));
    if let Some(body) = &detail.body {
        out.insert("reads one table twice".to_string(), f64::from(u8::from(body.reads_one_table_twice)));
        for (word, count) in [("relation atoms", body.relation_atoms), ("lib atoms", body.lib_atoms), ("comparisons", body.comparisons), ("NOTs", body.nots), ("ALLs", body.alls), ("ORs", body.ors), ("joined variables", body.joined_variables), ("variables not at a column", body.variables_not_at_a_column)] {
            out.insert(word.to_string(), count as f64);
        }
    }
    for column in detail.columns.iter().filter(|column| !column.ty.is_empty()) {
        let ty = &column.ty;
        let word = ["grid", "proposer", "lib", "component", "constant", "recursive"].into_iter().filter(|kind| column.kinds.contains(kind)).collect::<Vec<_>>().join("+");
        *out.entry(format!("?{ty} origin kinds {}", if word.is_empty() { "none" } else { &word })).or_insert(0.0) += 1.0;
        for (what, held) in [("from the input", column.input), ("from the train outputs", column.output), ("from a task parameter", column.parameter)] {
            if held {
                out.insert(format!("?{ty} {what}"), 1.0);
            }
        }
        if let Some(body) = &column.body {
            let mut greatest = |name: String, value: usize| {
                let held = out.entry(name).or_insert(0.0);
                *held = held.max(value as f64);
            };
            greatest(format!("?{ty} relation atoms"), body.relation_atoms);
            greatest(format!("?{ty} joins"), usize::from(body.joins));
            greatest(format!("?{ty} alternatives"), body.alternatives);
            greatest(format!("?{ty} alternatives bind it from different sources"), usize::from(body.alternatives_differ));
        }
    }
    if let Some(body) = &detail.body {
        for (i, j) in &body.shared {
            let (Some(a), Some(b)) = (detail.columns.get(*i), detail.columns.get(*j)) else { continue };
            if !a.ty.is_empty() && !b.ty.is_empty() {
                out.insert(format!("?{} shares an atom with ?{}", a.ty, b.ty), 1.0);
            }
        }
    }
}

/// A lineage row's own key, which lives as long as the rows.
fn facts_key<'f>(rows: &BTreeMap<(&'f str, &'f str), Vec<(&'f str, &'f str)>>, table: &str, column: &str) -> (&'f str, &'f str) {
    *rows.keys().find(|(own, at)| *own == table && *at == column).expect("a key the caller found")
}
