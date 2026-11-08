//! The identity of each table, column and flow atom of a case program,
//! free of every name and every order that the program's author chose.
//!
//! - A table of a relation form has the hash of the resolved content of the
//!   form's query ([`arclog::resolver::ResolvedProgram::query_identity`]),
//!   written as 32 hexadecimal digits: two tables of any two case programs
//!   have one identity where the contents of their queries are equal. A port
//!   of an instance (or a part of a `RIGID_DET` form) has the hash of its
//!   form's identity and the port's name in the lib. A table of a fact
//!   relation has the hash of the relation's name.
//! - A column the lib declares has the lib's column name. A field of a record
//!   column of the lib has the lib column's name, `.#` and the canonical
//!   position of its label in the labeling of the form's label scope under
//!   the resolver's writer (the least of the positions where the heads of
//!   several inputs write the column with several labels). Any other column
//!   has `#` and that position. A rigid part column that
//!   repeats a key's label prefixes its identity with `part.` to distinguish
//!   the two roles.
//! - A flow's atom has the identity of its form, and its canonical path in
//!   the form (the path of the atom with each sorted list in canonical
//!   order), under the resolver's writer.

use std::hash::Hasher;
use std::sync::Arc;

use arclog::check::CheckedProgram;
use arclog::hash::{StableHash, StableHashMap, StableHasher};
use arclog::program::path::NodePath;
use arclog::program::{Form, ProgramRelation};
use arclog::read::spelling::{spelling, FACT_RELATIONS};
use arclog::registry::Registry;
use arclog::resolver::QueryIdentity;

use crate::columns::CaseColumns;
use crate::structure::Structure;
use crate::tables::{Contents, Point, Table, TableRelation};

/// The identities of the tables of a case, the first of them the first
/// evidence table, and of the atoms of their flows.
#[derive(Clone, Debug, Default)]
pub struct Identities {
    /// The identity of each table, as 32 hexadecimal digits, and the empty
    /// string for a table that has none: a table that faulted or stands at a
    /// body in progress, and a `DEMONSTRATED` form's.
    pub tables: Vec<String>,
    /// The identity of each column of each table, in the order of its
    /// columns.
    pub columns: Vec<Vec<String>>,
    /// For each flow of each table, in the order of the flows of the
    /// columns, the identity of the form of the flow's atom, and the empty
    /// string for a flow with no atom.
    pub atom_forms: Vec<String>,
    /// For each flow, the canonical path of its atom in its form, as the
    /// steps joined by `.`, and the empty string for a flow with no atom or
    /// the atom of the empty path.
    pub atom_paths: Vec<String>,
    /// The structure of each table's bodies, the instance of each table that
    /// an instance's output gives and the symmetries of each table's
    /// columns, as [`crate::structure`] gives them.
    pub structure: Structure,
}

/// The query identity of each top-level form of `checked` that a table
/// stands at, made on its first use.
pub(crate) struct Forms<'a> {
    checked: &'a CheckedProgram,
    registry: &'a Registry,
    held: StableHashMap<usize, Option<Arc<(QueryIdentity, String)>>>,
}

impl<'a> Forms<'a> {
    pub(crate) fn new(checked: &'a CheckedProgram, registry: &'a Registry) -> Self {
        Forms { checked, registry, held: StableHashMap::default() }
    }

    pub(crate) fn of(&mut self, top: usize) -> Option<Arc<(QueryIdentity, String)>> {
        let (checked, registry) = (self.checked, self.registry);
        self.held
            .entry(top)
            .or_insert_with(|| {
                let identity = checked.program.query_identity(top, registry)?;
                let hex = hex(identity.content.content_hash());
                Some(Arc::new((identity, hex)))
            })
            .clone()
    }

    fn form(&self, top: usize) -> Option<&Form> {
        self.checked.program.program.value().forms.get(top)
    }
}

fn hex(hash: StableHash) -> String {
    format!("{:032x}", hash.0)
}

/// The identity of the table of the fact relation `name`.
fn fact_ident(name: &str) -> String {
    let mut hasher = StableHasher::new();
    hasher.write(b"arclog.identity.fact");
    hasher.write(name.as_bytes());
    hex(hasher.finish128())
}

/// The identity of the table that stands for the port `port` of the form
/// whose identity is `form`.
fn port_ident(form: StableHash, port: &str) -> String {
    let mut hasher = StableHasher::new();
    hasher.write(b"arclog.identity.port");
    hasher.write_u128(form.0);
    hasher.write(port.as_bytes());
    hex(hasher.finish128())
}

/// The part of the relation `spelled` after the owner's name: `size` for
/// `&body_count.size`, and the empty string for a relation of no port.
fn port_of(spelled: &str) -> &str {
    spelled.split_once('.').map_or("", |(_, port)| port)
}

/// The identities of `evidence`, then of `tables`, each with its token, in a
/// case of `checked`, whose program declares at each slot the relation in
/// `relations`.
pub fn identify(checked: &CheckedProgram, registry: &Registry, relations: &[ProgramRelation], evidence: &[Table], tables: &[(usize, Table)]) -> Identities {
    let mut forms = Forms { checked, registry, held: StableHashMap::default() };
    let mut out = Identities::default();
    let all: Vec<&Table> = evidence.iter().chain(tables.iter().map(|(_, table)| table)).collect();
    for &table in &all {
        let (ident, columns) = table_identity(&mut forms, table);
        out.tables.push(ident);
        out.columns.push(columns);
        if let Ok(contents) = &table.contents {
            for sources in contents.flows.iter() {
                for source in sources {
                    let (form, path) = atom_identity(&mut forms, &source.atom);
                    out.atom_forms.push(form);
                    out.atom_paths.push(path);
                }
            }
        }
    }
    let graphs = crate::structure::graph_relations(checked, registry, relations, &all);
    out.structure = crate::structure::describe(checked, registry, &mut forms, all, graphs, &out);
    out
}

/// The contents of the table of `relation` with no rows, whose form stands at
/// `form` and whose name is `name`: its columns and their flows.
pub fn relation_contents(checked: &CheckedProgram, registry: &Registry, relation: &arclog::types::GraphRelation, form: &NodePath, name: &str) -> arclog::eval::Outcome<Contents> {
    let contents = crate::tables::relation_metadata(registry, checked, form, relation, 0, &[], Vec::new())?;
    Ok(Contents { name: name.to_string(), ..contents })
}

/// The identity of the table of `relation`, whose form stands at `form`, and of
/// each of its columns, in row order: those that [`identify`] gives that table.
pub fn relation_identity(checked: &CheckedProgram, registry: &Registry, relation: &arclog::types::GraphRelation, form: &NodePath, name: &str) -> Option<(String, Vec<String>)> {
    let contents = relation_contents(checked, registry, relation, form, name).ok()?;
    let table = Table { form: form.clone(), point: Point::Relation, contents: Ok(contents) };
    let mut forms = Forms { checked, registry, held: StableHashMap::default() };
    Some(table_identity(&mut forms, &table))
}

/// The identity of the form of the atom at `atom` and the atom's canonical
/// path in it, both empty for the empty path.
pub(crate) fn atom_identity(forms: &mut Forms, atom: &NodePath) -> (String, String) {
    let Some((top, rest)) = atom.0.split_first() else { return (String::new(), String::new()) };
    let top = top.0 as usize;
    let Some(identity) = forms.of(top) else { return (String::new(), format!("?{}", spelled(atom))) };
    let (query, hex) = &*identity;
    let relative = NodePath(rest.into());
    match query.order.try_canonical_path(&relative) {
        Some(path) => (hex.clone(), spelled(&path)),
        None => (hex.clone(), format!("?{}", spelled(&relative))),
    }
}

pub(crate) fn spelled(path: &NodePath) -> String {
    path.0.iter().map(|step| step.0.to_string()).collect::<Vec<_>>().join(".")
}

/// The identity of `table` and of each of its columns.
pub(crate) fn table_identity(forms: &mut Forms, table: &Table) -> (String, Vec<String>) {
    let Ok(contents) = &table.contents else { return (String::new(), Vec::new()) };
    if let TableRelation::Fact(fact) = contents.relation {
        return (fact_ident(spelling(FACT_RELATIONS, &fact)), contents.columns.iter().map(|column| column.name.clone()).collect());
    }
    if !matches!(table.point, Point::Relation) {
        return (String::new(), contents.columns.iter().map(|column| column.name.clone()).collect());
    }
    let Some(top) = table.form.0.first().map(|step| step.0 as usize) else { return (String::new(), Vec::new()) };
    let Some(identity) = forms.of(top) else {
        return (String::new(), contents.columns.iter().map(|column| format!("?{}", column.name)).collect());
    };
    let (query, _) = &*identity;
    let form = query.content.content_hash();
    let ported = matches!(forms.form(top), Some(Form::Instance(_) | Form::RigidDet(_)));
    let ident = if ported {
        let port = match forms.form(top) {
            Some(Form::RigidDet(_)) => contents.output_name.as_str(),
            _ => port_of(&contents.name),
        };
        port_ident(form, port)
    } else {
        hex(form)
    };
    let instance = matches!(forms.form(top), Some(Form::Instance(_)));
    let mut columns: Vec<String> = contents
        .columns
        .iter()
        .enumerate()
        .map(|(at, column)| {
            let position = column_position(query, contents, at);
            match (column.name.split_once('.'), position) {
                // A field of a record below a lib column: the lib column and the position of its label.
                (Some((lib, _)), Some(position)) => format!("{lib}.#{position}"),
                (Some(_), None) => column.name.clone(),
                // A column of an instance's port that has no field is the lib's own.
                (None, _) if instance => column.name.clone(),
                (None, Some(position)) => format!("#{position}"),
                (None, None) => column.name.clone(),
            }
        })
        .collect();
    let rigid = matches!(forms.form(top), Some(Form::RigidDet(rigid)) if rigid.value().key.is_some())
        && contents.output_name != arclog::read::spelling::POSE;
    if rigid {
        rigid_key_aliases(&mut columns, &contents.columns.iter().map(|column| column.slot).collect::<Vec<_>>());
    }
    distinct(&mut columns, contents);
    (ident, columns)
}

/// The least canonical position among a column's bound labels. Selection
/// of one header label depends on head order; the set of labels does not.
fn column_position(query: &QueryIdentity, contents: &Contents, at: usize) -> Option<u32> {
    let bound = contents.bound_labels.get(at).map(|labels| &labels[..]).unwrap_or_default();
    contents.columns[at].label_id.iter().chain(bound)
        .filter_map(|label| query.order.label_position(&NodePath::default(), *label)).min()
}

/// A rigid output's key precedes its pose and part columns by the language's
/// schema. A part may read the same label as the key; its role distinguishes
/// that occurrence without using its authored name or its site's order.
fn rigid_key_aliases(columns: &mut [String], slots: &[Option<u32>]) {
    let keys: Vec<String> = columns.iter().zip(slots).filter(|(_, slot)| **slot == Some(0)).map(|(column, _)| column.clone()).collect();
    for (column, slot) in columns.iter_mut().zip(slots) {
        if slot.is_some_and(|slot| slot > 1) && keys.contains(column) {
            *column = format!("part.{column}");
        }
    }
}

/// Makes the identities of `columns` differ where two label positions or
/// two lib names coincide, by the column's name after a `~`.
fn distinct(columns: &mut [String], contents: &Contents) {
    for at in 0..columns.len() {
        if columns[..at].contains(&columns[at]) {
            columns[at] = format!("{}~{}", columns[at], contents.columns[at].name);
        }
    }
}

impl CaseColumns {
    /// These columns with the identities of the tables, columns and flow atoms
    /// in `identities`, for the tables and flows that the columns hold.
    pub fn with_identities(mut self, identities: Identities) -> CaseColumns {
        let tables = self.tables.form.len();
        let flows = self.flows.table.len();
        self.tables.ident = identities.tables.into_iter().take(tables).collect();
        self.tables.column_idents = identities.columns.into_iter().take(tables).collect();
        self.flows.atom_form = identities.atom_forms.into_iter().take(flows).collect();
        self.flows.atom_path = identities.atom_paths.into_iter().take(flows).collect();
        self.tables.body_ir = identities.structure.bodies.into_iter().take(tables).collect();
        self.tables.instance = identities.structure.instances.into_iter().take(tables).collect();
        self.tables.column_symmetries = identities.structure.column_symmetries.into_iter().take(tables).collect();
        debug_assert_eq!(self.flows.atom_form.len(), flows);
        self.identified = true;
        self
    }
}
