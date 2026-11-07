//! The summary of the table of each of many candidate atoms at a state of a
//! decode: the body in progress with that atom added, at each assignment.

use std::collections::HashMap;

use super::*;
use crate::summary::{summarize_body, DetFulls, TableSummary};
use arclog::decode::{AtomRows, BaseRows};
use arclog::terms::Example;
use arclog::eval::join::Materializer;

/// The most bindings that the rows of one atom may count, a multiple of the
/// settings' table work cap.
const ATOM_WORK_SCALE: u64 = 16;

/// What [`atom_tables`] gives.
pub struct AtomTables {
    /// For each atom, the place of its table's summary in `summaries`, none
    /// where the atom has no table.
    pub index: Vec<Option<u32>>,
    pub summaries: Vec<TableSummary>,
    /// The atoms whose rows came from a program made for the atom.
    pub by_program: usize,
    /// The place in the list of atoms of each atom whose work passed the cap.
    pub over_cap: Vec<u32>,
}

/// A hash of what a summary tells a reader, so that atoms with equal tables share one.
fn summary_key(summary: &TableSummary) -> (bool, Vec<u32>, Vec<Option<u128>>) {
    let hashes = summary.assignments.iter().map(|at| at.hash.map(|hash| hash.0)).collect();
    let bits = summary.assignments.iter().flat_map(|at| at.features.iter().map(|value| value.to_bits())).collect();
    (summary.capped, bits, hashes)
}

/// The summary of the table of the atom `tokens` with a program made for it.
fn summary_by_program(decoder: &Decoder<'_>, tokens: &[u32], materializer: &Materializer<'_>, train: &[arclog_features::Pair], fulls: &DetFulls<'_>) -> Option<TableSummary> {
    let mut walk = decoder.fork();
    let vocabulary = decoder.vocabulary();
    for id in tokens {
        walk.step_untested(vocabulary.token(*id)?.clone()).ok()?;
    }
    let form = NodePath::top(walk.program().value().forms.len() as u32);
    let sub = match walk.closed_sub_body()? {
        Some(Ok(sub)) => sub,
        _ => return None,
    };
    let relation = derived_at(&sub.program, &sub.form);
    let slot = walk.state().open_slot();
    let work = walk.query_work();
    let examples = walk.examples_of(sub.scope).into_iter().zip(walk.values_of(&sub, Some(&work)).into_vec()).map(|(example, rows)| ExampleRows { example, rows: rows.map(|rows| models_of_body(&rows)) }).collect();
    let contents = relation_metadata(walk.registry(), &sub.program, &form, &relation, slot, &walked_dets(&sub.program, relation.node), examples).ok()?;
    summarize_body(materializer, &contents, train, fulls).ok()
}

/// The summary of the table of each atom of `atoms`, ids of the tokens of each,
/// as [`Decoder::candidate_atoms`] gives them, at the state of `decoder`, whose
/// limits hold no deadline where the caller wants the tables to depend on no
/// clock. `fulls` holds the tables of the stream, which the summaries read for
/// the `DET`s of an assignment. With `by_program` each atom's rows come from a
/// program made for the atom, which reads every kind of atom.
pub fn atom_tables(decoder: &Decoder<'_>, atoms: &[Box<[u32]>], materializer: &Materializer<'_>, train: &[arclog_features::Pair], fulls: &DetFulls<'_>, by_program: bool) -> AtomTables {
    let mut out = AtomTables { index: Vec::with_capacity(atoms.len()), summaries: Vec::new(), by_program: 0, over_cap: Vec::new() };
    let mut distinct: HashMap<(bool, Vec<u32>, Vec<Option<u128>>), u32> = HashMap::new();
    // The summary of each table by its types and its rows, before a summary is made.
    let mut by_rows: HashMap<u128, Option<u32>> = HashMap::new();
    let cap = decoder.settings().table_work_cap.saturating_mul(ATOM_WORK_SCALE);
    let closed = decoder.closed_sub_body();
    // Where no clause is in progress, no body has a table.
    if closed.is_none() {
        out.index = vec![None; atoms.len()];
        return out;
    }
    let base = if by_program { None } else { base_of(decoder, closed.as_ref()) };
    let rows: Vec<AtomRows> = match &base {
        Some((_, rows, sub)) => decoder.atom_rows(*sub, rows, decoder.state().label_count(), atoms, cap),
        None => atoms.iter().map(|_| AtomRows::ByProgram).collect(),
    };
    for (at, (tokens, rows)) in atoms.iter().zip(rows).enumerate() {
        let mut key = None;
        let summary = match rows {
            AtomRows::Rows { types, examples } => {
                let hash = rows_key(&types, &examples);
                if let Some(held) = by_rows.get(&hash) {
                    out.index.push(*held);
                    continue;
                }
                key = Some(hash);
                let (contents, _, _) = base.as_ref().expect("a base where the join gave rows");
                summary_of_rows(contents, types, examples, materializer, train, fulls)
            }
            AtomRows::NoTable => None,
            AtomRows::OverCap => {
                out.over_cap.push(at as u32);
                None
            }
            AtomRows::ByProgram => {
                out.by_program += 1;
                summary_by_program(decoder, tokens, materializer, train, fulls)
            }
        };
        let place = summary.map(|summary| *distinct.entry(summary_key(&summary)).or_insert_with(|| {
            out.summaries.push(summary);
            out.summaries.len() as u32 - 1
        }));
        if let Some(key) = key {
            by_rows.insert(key, place);
        }
        out.index.push(place);
    }
    out
}

/// A hash of the types of a table's columns and of its value at each assignment of each example.
fn rows_key(types: &[ValueType], examples: &[(Option<Example>, Outcome<Assigned<Vec<RelationValue>>>)]) -> u128 {
    use std::hash::{Hash, Hasher};
    let mut hasher = arclog::hash::StableHasher::new();
    types.hash(&mut hasher);
    for (example, rows) in examples {
        example.hash(&mut hasher);
        match rows {
            Err(fault) => fault.message.hash(&mut hasher),
            Ok(assigned) => {
                assigned.stop.as_ref().map(|stop| format!("{:?}", stop.bound)).hash(&mut hasher);
                for (_, models) in &assigned.at {
                    hasher.write_usize(models.len());
                    for model in models {
                        match model {
                            RelationValue::Rows(rows) => hasher.write_u128(rows.rows_hash().0),
                            RelationValue::Undefined => hasher.write_u8(1),
                            RelationValue::Stopped(stop) => format!("{:?}", stop.bound).hash(&mut hasher),
                        }
                    }
                }
            }
        }
    }
    hasher.finish128().0
}

/// The body at the state of `decoder`, closed: its contents with no rows, its rows, and its sub-body.
fn base_of<'s>(decoder: &Decoder<'_>, closed: Option<&'s Option<Outcome<arclog::decode::SubBody>>>) -> Option<(Contents, BaseRows, Option<&'s arclog::decode::SubBody>)> {
    let work = decoder.query_work();
    let empty = || Contents { assignment_layout: AssignmentLayout::Search, relation: TableRelation::Slot(decoder.state().open_slot()), columns: Box::default(), dets: Box::default(), examples: Box::default(), projections: None, name: String::new(), output_name: String::new(), flows: Box::default(), rows: None, bound_labels: Box::default(), depth: 0, keys: Vec::new(), selected: SelectedColumns::default(), frames: Vec::new(), extents: None };
    match closed? {
        None => Some((empty(), decoder.base_rows(None, Vec::new(), Vec::new(), &work), None)),
        Some(Err(_)) => None,
        Some(Ok(sub)) => {
            let form = NodePath::top(decoder.program().value().forms.len() as u32);
            let relation = derived_at(&sub.program, &sub.form);
            let dets = walked_dets(&sub.program, relation.node);
            let contents = relation_metadata(decoder.registry(), &sub.program, &form, &relation, decoder.state().open_slot(), &dets, Vec::new()).ok()?;
            let columns = contents.columns.iter().map(|column| column.label_id.map(|label| (label, column.ty.clone()))).collect::<Option<Vec<_>>>()?;
            let names = dets.iter().map(|det| det.relation.clone()).collect();
            let rows = decoder.base_rows(Some(sub), columns, names, &work);
            Some((contents, rows, Some(sub)))
        }
    }
}

/// The summary of the table of the columns of `types` that holds `examples`.
fn summary_of_rows(base: &Contents, types: Vec<ValueType>, examples: Vec<(Option<Example>, Outcome<Assigned<Vec<RelationValue>>>)>, materializer: &Materializer<'_>, train: &[arclog_features::Pair], fulls: &DetFulls<'_>) -> Option<TableSummary> {
    let columns: Box<[TableColumn]> = types.into_iter().enumerate().map(|(at, ty)| TableColumn { name: format!("c{at}"), ty, slot: None, label_id: None, label: None }).collect();
    let examples: Box<[ExampleRows]> = examples.into_iter().map(|(example, rows)| ExampleRows { example, rows }).collect();
    let contents = Contents { assignment_layout: AssignmentLayout::Search, relation: base.relation, columns, dets: base.dets.clone(), examples, projections: None, name: String::new(), output_name: String::new(), flows: Box::default(), rows: None, bound_labels: Box::default(), depth: 0, keys: Vec::new(), selected: SelectedColumns::default(), frames: Vec::new(), extents: None };
    summarize_body(materializer, &contents, train, fulls).ok()
}
