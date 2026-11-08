//! A hit of the result cache gives the value stored under its key, with the
//! parts of its relation in the columns and the order that they were stored
//! in, whichever other value with the same rows the cache holds under another
//! key.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::cache::{self, EntryContent, EntryRequest};
use arclog::eval::{Cancellation, Caps, Cost, Limits, RelationValue};
use arclog::program::path::{NodePath, PathStep};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::relations::{ColumnIndex, Relation, RelationPart, RowSet};
use arclog::resolver::resolve;
use arclog::session::{same_rows, SessionBound, TaskSession};
use arclog::terms::TermId;
use arclog::types::ValueType;

/// A program with one clause.
fn checked() -> CheckedProgram {
    let text = "(RULE &body\n  (input *P))\n";
    let solver = read_solver("layout", text, "", &|_| None).unwrap_or_else(|error| panic!("{text}: {error:?}")).value;
    let registry = Registry::get();
    let case = solver.concept_case();
    let program = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes")
}

fn session() -> TaskSession {
    TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS)
}

fn cells(values: &[u32]) -> Vec<TermId> {
    values.iter().map(|&value| TermId::from_encoding(value)).collect()
}

fn part(columns: &[u16], arity: u16, values: &[u32]) -> RelationPart {
    RelationPart { columns: columns.iter().map(|&column| ColumnIndex(column)).collect(), rows: RowSet::of_distinct(arity, cells(values)) }
}

/// The relation of the rows (1 2 3) and (1 2 4), in three layouts: one part,
/// two parts of the columns 2 and 0, 1, and the same two parts in the other
/// order.
fn layouts() -> Vec<Arc<Relation>> {
    let joint = Relation::from_parts(3, Box::new([part(&[0, 1, 2], 3, &[1, 2, 3, 1, 2, 4])]));
    let split = Relation::from_parts(3, Box::new([part(&[2], 1, &[3, 4]), part(&[0, 1], 2, &[1, 2])]));
    let swapped = Relation::from_parts(3, Box::new([part(&[0, 1], 2, &[1, 2]), part(&[2], 1, &[3, 4])]));
    vec![Arc::new(joint), Arc::new(split), Arc::new(swapped)]
}

fn columns_of(relation: &Relation) -> Vec<Vec<u16>> {
    relation.parts().iter().map(|part| part.columns.iter().map(|column| column.0).collect()).collect()
}

fn rows_of(value: RelationValue) -> Arc<Relation> {
    match value {
        RelationValue::Rows(relation) => relation,
        other => panic!("a relation, not {other:?}"),
    }
}

/// The column types of the key of the entry number `number`: one type each.
fn types_of(number: usize) -> Vec<ValueType> {
    let ty = [ValueType::Nat, ValueType::Int, ValueType::Position][number].clone();
    vec![ty; 3]
}

#[test]
fn a_hit_gives_the_layout_that_was_stored_under_its_key() {
    let program = checked();
    let form = NodePath(Box::new([PathStep(program.program.program.value().forms.len() as u32 - 1)]));
    let content = program.content(&form).expect("the content of the clause");
    let layouts = layouts();
    assert!(layouts.iter().all(|layout| same_rows(layout, &layouts[0])), "the layouts hold the same rows");
    let limits = Limits::new(None, Cancellation::default());
    let orders: [[usize; 3]; 4] = [[0, 1, 2], [2, 1, 0], [1, 2, 0], [1, 0, 2]];
    for order in orders {
        let session = session();
        let types: Vec<Vec<ValueType>> = (0..layouts.len()).map(types_of).collect();
        let request = |number: usize| EntryRequest { clause: EntryContent::Typed(&content, &types[number]), reads: &[], example: None, parameters: &[] };
        for number in order {
            cache::store(&session, &request(number), &RelationValue::Rows(Arc::clone(&layouts[number])), Cost::default());
        }
        for number in 0..layouts.len() {
            let found = cache::lookup(&session, &limits, &request(number), &form).expect("the entry of the key");
            let relation = rows_of(found.value);
            assert_eq!(columns_of(&relation), columns_of(&layouts[number]), "the layout of the entry {number}, stored in the order {order:?}");
            assert!(same_rows(&relation, &layouts[number]));
        }
    }
}

#[test]
fn a_hit_gives_the_stored_layout_whichever_layout_a_relation_that_the_key_reads_has() {
    let program = checked();
    let form = NodePath(Box::new([PathStep(program.program.program.value().forms.len() as u32 - 1)]));
    let content = program.content(&form).expect("the content of the clause");
    let layouts = layouts();
    let limits = Limits::new(None, Cancellation::default());
    let types = types_of(0);
    let session = session();
    let stored = &layouts[1];
    let storing = EntryRequest { clause: EntryContent::Typed(&content, &types), reads: std::slice::from_ref(&layouts[0]), example: None, parameters: &[] };
    cache::store(&session, &storing, &RelationValue::Rows(Arc::clone(stored)), Cost::default());
    for read in &layouts {
        let request = EntryRequest { clause: EntryContent::Typed(&content, &types), reads: std::slice::from_ref(read), example: None, parameters: &[] };
        let found = cache::lookup(&session, &limits, &request, &form).expect("the entry of the key, whatever layout the relation it reads has");
        assert_eq!(columns_of(&rows_of(found.value)), columns_of(stored));
    }
}
