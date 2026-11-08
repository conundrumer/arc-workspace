//! The summary of the table of each of many candidate atoms at a state of a
//! decode: the body in progress with that atom added, at each assignment.

use arclog::hash::StableHashMap;

use super::*;
use crate::summary::{summarize_body, DetFulls, TableSummary};
use arclog::decode::{AtomRows, BaseRows};
use arclog::program::LabelId;
use arclog::stream::{Control, Token};
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

/// The most bytes of results that a [`AtomTablesMemo`] holds.
const MEMO_BYTES: usize = 1 << 28;

/// The results of [`atom_tables`] at the states of one task session, by the
/// state and its list of atoms: a search reaches a state of a shared prefix many
/// times. It holds at most [`MEMO_BYTES`], and is emptied when it would pass that.
#[derive(Default)]
pub struct AtomTablesMemo(std::sync::Mutex<(StableHashMap<u128, std::sync::Arc<AtomTables>>, usize)>);

impl AtomTablesMemo {
    /// The key of the list `atoms` at the state of `decoder`, where the state has one.
    pub fn key(decoder: &Decoder<'_>, atoms: &[Box<[u32]>]) -> Option<u128> {
        use std::hash::Hasher;
        let mut hasher = arclog::hash::StableHasher::new();
        hasher.write_u128(decoder.state_key()?);
        for atom in atoms {
            hasher.write_usize(atom.len());
            atom.iter().for_each(|id| hasher.write_u32(*id));
        }
        Some(hasher.finish128().0)
    }

    pub fn get(&self, key: u128) -> Option<std::sync::Arc<AtomTables>> {
        self.0.lock().expect("the memo is not poisoned").0.get(&key).cloned()
    }

    pub fn keep(&self, key: u128, tables: std::sync::Arc<AtomTables>) {
        let bytes = 64 + tables.index.len() * 8 + tables.summaries.iter().flat_map(|summary| summary.assignments.iter()).map(|at| 256 + at.features.len() * 4).sum::<usize>();
        let mut held = self.0.lock().expect("the memo is not poisoned");
        if held.1 + bytes > MEMO_BYTES {
            *held = Default::default();
        }
        held.0.insert(key, tables);
        held.1 += bytes;
    }
}

/// A hash of what a summary tells a reader, so that atoms with equal tables share one.
fn summary_key(summary: &TableSummary) -> (bool, Vec<u32>, Vec<Option<u128>>) {
    let hashes = summary.assignments.iter().map(|at| at.hash.map(|hash| hash.0)).collect();
    let bits = summary.assignments.iter().flat_map(|at| at.features.iter().map(|value| value.to_bits())).collect();
    (summary.capped, bits, hashes)
}

/// `contents`, the table of the atom `tokens` from a program made for it, with
/// its columns in the order that a table of the join holds them: the columns of
/// the body, `base`, then each label that the atom adds, in the order of its sites.
/// A program holds them in the canonical order of its body, and a feature can
/// read a column by its place among the columns of its type.
fn in_atom_order(contents: Contents, base: &[LabelId], tokens: &[u32], decoder: &Decoder<'_>) -> Contents {
    let labels = decoder.state().label_count();
    let mut wanted: Vec<LabelId> = base.to_vec();
    let mut made = 0;
    for id in tokens {
        match decoder.vocabulary().token(*id) {
            Some(Token::Label(label)) if !wanted.contains(&LabelId(*label)) => wanted.push(LabelId(*label)),
            Some(Token::Control(Control::Fresh | Control::Key)) => {
                wanted.push(LabelId(labels + made));
                made += 1;
            }
            _ => {}
        }
    }
    let mut order: Vec<usize> = wanted.iter().filter_map(|label| contents.columns.iter().position(|column| column.label_id == Some(*label))).collect();
    order.extend((0..contents.columns.len()).filter(|at| contents.columns[*at].label_id.is_none_or(|label| !wanted.contains(&label))));
    if order.iter().enumerate().all(|(at, old)| at == *old) {
        return contents;
    }
    let mut new_place = vec![0u16; order.len()];
    for (new, old) in order.iter().enumerate() {
        new_place[*old] = new as u16;
    }
    let reordered = |value: RelationValue| match value {
        RelationValue::Rows(rows) => {
            let parts = rows.parts().iter().map(|part| arclog::relations::RelationPart { columns: part.columns.iter().map(|column| arclog::relations::ColumnIndex(new_place[usize::from(column.0)])).collect(), rows: part.rows.clone() }).collect();
            RelationValue::Rows(std::sync::Arc::new(arclog::relations::Relation::from_parts(rows.arity(), parts)))
        }
        other => other,
    };
    let columns: Box<[TableColumn]> = order.iter().map(|old| contents.columns[*old].clone()).collect();
    let examples: Box<[ExampleRows]> = contents.examples.into_vec().into_iter().map(|example| ExampleRows {
        example: example.example,
        rows: example.rows.map(|assigned| Assigned {
            at: assigned.at.into_iter().map(|(values, models)| (values, models.into_iter().map(reordered).collect())).collect(),
            stop: assigned.stop,
        }),
    }).collect();
    Contents { columns, examples, ..contents }
}

/// The summary of the table of the atom `tokens` with a program made for it,
/// where `base` holds the labels of the body's columns.
fn summary_by_program(decoder: &Decoder<'_>, tokens: &[u32], base: &[LabelId], materializer: &Materializer<'_>, train: &[arclog_features::Pair], fulls: &DetFulls<'_>) -> Option<TableSummary> {
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
    let contents = body_metadata(walk.registry(), &sub.program, &form, &relation, slot, &walked_dets(&sub.program, relation.node), examples).ok()?;
    summarize_body(materializer, &in_atom_order(contents, base, tokens, decoder), train, fulls).ok()
}

/// The summary of the table of each atom of `atoms`, ids of the tokens of each,
/// as [`Decoder::candidate_atoms`] gives them, at the state of `decoder`, whose
/// limits count the work of one request, so the tables depend on no clock. `fulls` holds the tables of the stream, which the summaries read for
/// the `DET`s of an assignment. With `by_program` each atom's rows come from a
/// program made for the atom, which reads every kind of atom.
pub fn atom_tables(decoder: &Decoder<'_>, atoms: &[Box<[u32]>], materializer: &Materializer<'_>, train: &[arclog_features::Pair], fulls: &DetFulls<'_>, by_program: bool) -> AtomTables {
    let mut out = AtomTables { index: Vec::with_capacity(atoms.len()), summaries: Vec::new(), by_program: 0, over_cap: Vec::new() };
    let mut distinct: StableHashMap<(bool, Vec<u32>, Vec<Option<u128>>), u32> = StableHashMap::default();
    // The summary of each table by its types and its rows, before a summary is made.
    let mut by_rows: StableHashMap<u128, Option<u32>> = StableHashMap::default();
    let cap = decoder.settings().table_work_cap.saturating_mul(ATOM_WORK_SCALE);
    let closed = decoder.closed_sub_body();
    // Where no clause is in progress, no body has a table.
    if closed.is_none() {
        out.index = vec![None; atoms.len()];
        return out;
    }
    let contents = base_contents(decoder, closed.as_ref());
    let base_labels: Vec<LabelId> = contents.as_ref().map_or_else(Vec::new, |(contents, _)| contents.columns.iter().filter_map(|column| column.label_id).collect());
    let base = if by_program { None } else { contents.and_then(|(contents, dets)| base_of(decoder, closed.as_ref(), contents, dets)) };
    let mut visit = |at: usize, rows: AtomRows| {
        let mut key = None;
        let summary = match rows {
            AtomRows::Rows(atom) => {
                let hash = atom.key();
                if let Some(held) = by_rows.get(&hash) {
                    out.index.push(*held);
                    return;
                }
                key = Some(hash);
                let (types, examples) = atom.table();
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
                summary_by_program(decoder, &atoms[at], &base_labels, materializer, train, fulls)
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
    };
    match &base {
        Some((_, rows, sub)) => decoder.each_atom_rows(*sub, rows, decoder.state().label_count(), atoms, cap, &mut visit),
        None => (0..atoms.len()).for_each(|at| visit(at, AtomRows::ByProgram)),
    }
    out
}

/// The columns of the body at the state of `decoder`, closed, with no rows, and the `DET`s that it reads.
fn base_contents(decoder: &Decoder<'_>, closed: Option<&Option<Outcome<arclog::decode::SubBody>>>) -> Option<(Contents, Vec<Det>)> {
    match closed? {
        None => Some((Contents { assignment_layout: AssignmentLayout::Search, relation: TableRelation::Slot(decoder.state().open_slot()), columns: Box::default(), dets: Box::default(), examples: Box::default(), projections: None, name: String::new(), output_name: String::new(), flows: Box::default(), rows: None, bound_labels: Box::default(), depth: 0, keys: Vec::new(), selected: SelectedColumns::default(), frames: Vec::new(), extents: None }, Vec::new())),
        Some(Err(_)) => None,
        Some(Ok(sub)) => {
            let form = NodePath::top(decoder.program().value().forms.len() as u32);
            let relation = derived_at(&sub.program, &sub.form);
            let dets = walked_dets(&sub.program, relation.node);
            let contents = body_metadata(decoder.registry(), &sub.program, &form, &relation, decoder.state().open_slot(), &dets, Vec::new()).ok()?;
            Some((contents, dets))
        }
    }
}

/// The body at the state of `decoder`, closed: its contents with no rows, its rows, and its sub-body.
fn base_of<'s>(decoder: &Decoder<'_>, closed: Option<&'s Option<Outcome<arclog::decode::SubBody>>>, contents: Contents, dets: Vec<Det>) -> Option<(Contents, BaseRows, Option<&'s arclog::decode::SubBody>)> {
    let work = decoder.query_work();
    match closed? {
        None => Some((contents, decoder.base_rows(None, Vec::new(), Vec::new(), &work), None)),
        Some(Err(_)) => None,
        Some(Ok(sub)) => {
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
