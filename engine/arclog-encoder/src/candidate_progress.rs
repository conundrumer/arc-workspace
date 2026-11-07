//! What a candidate's table adds to the tables before it, and how its rows stand to the relations upstream of it. A relation or an instance is one step, so
//! the tables of one instance do not count as before one another.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

use crate::catalog_lists::{Claims, NamedShape};
use crate::native::{Cell, FastMap, Table};
use crate::stored::Stored;

/// The tries of one match of columns per pair of tables, past which no match stands, so that the answer does not depend on the order of the columns.
const MOST_MATCHES: usize = 5000;

const FIXES_OUTPUT: &str = "C,C determines the output color";
const WHICH_CHANGE: &str = "C,C determines which cells change";
const AGREES_OUTPUT: &str = "C,C agrees with the output colors, proportion";

/// What the candidate holds at each example, against the union of what the tables before it hold.
pub fn progress_shapes(own: &[Option<Claims>], before: &[&[Option<Claims>]], train: usize, changed: &[Option<usize>]) -> Vec<NamedShape> {
    let examples = own.len();
    let mut shapes: BTreeMap<&'static str, Vec<Option<f64>>> = BTreeMap::new();
    let mut put = |name: &'static str, at: usize, value: f64| shapes.entry(name).or_insert_with(|| vec![None; examples])[at] = Some(value);
    let flag = |held: bool| f64::from(u8::from(held));
    for (at, claims) in own.iter().enumerate() {
        let Some(claims) = claims else { continue };
        let earlier: Vec<&Claims> = before.iter().filter_map(|table| table.get(at).and_then(Option::as_ref)).collect();
        let new_input = claims.ins.iter().filter(|kind| !earlier.iter().any(|other| other.ins.contains(*kind))).count();
        put("input claims held", at, claims.ins.len() as f64);
        put("input claims that no earlier table holds", at, new_input as f64);
        if at < train {
            let first = |kind: &str| claims.outs.contains(kind) && !earlier.iter().any(|other| other.outs.contains(kind));
            let new_output = claims.outs.iter().filter(|kind| !earlier.iter().any(|other| other.outs.contains(*kind))).count();
            put("output claims held", at, claims.outs.len() as f64);
            put("output claims that no earlier table holds", at, new_output as f64);
            put("first table where a column determines the output color", at, flag(first(FIXES_OUTPUT)));
            put("first table where every cell agrees with the output colors", at, flag(first(AGREES_OUTPUT)));
            if let Some(changed) = changed[at] {
                put("first table where a column determines which cells change", at, flag(first(WHICH_CHANGE)));
                if changed > 0 && claims.cells {
                    let new_covers = claims.covers.iter().filter(|place| !earlier.iter().any(|other| other.covers.contains(*place))).count();
                    let new_states = claims.states.iter().filter(|place| !earlier.iter().any(|other| other.states.contains(*place))).count();
                    put("changed cells that no earlier table covers, proportion", at, new_covers as f64 / changed as f64);
                    put("changed cells whose output color no earlier table states, proportion", at, new_states as f64 / changed as f64);
                }
            }
        }
    }
    shapes.into_iter().map(|(name, at)| NamedShape { name: name.to_string(), at }).collect()
}

/// The sorted distinct values of each column of a table, held by the table's identity.
#[derive(Default)]
pub struct ValueSets(FastMap<u64, Arc<Vec<Vec<Cell>>>>);

impl ValueSets {
    fn of(&mut self, table: &Table) -> Arc<Vec<Vec<Cell>>> {
        self.0.entry(table.id).or_insert_with(|| {
            Arc::new((0..table.arity).map(|column| {
                let mut held: Vec<Cell> = table.rows().map(|row| row[column]).collect();
                held.sort_unstable();
                held.dedup();
                held
            }).collect())
        }).clone()
    }
}

/// The choices of one candidate per place, each candidate used once, or none where they number more than the bound.
fn column_matches(candidates: &[Vec<usize>]) -> Vec<Vec<usize>> {
    fn walk(candidates: &[Vec<usize>], chosen: &mut Vec<usize>, out: &mut Vec<Vec<usize>>) {
        if chosen.len() == candidates.len() {
            out.push(chosen.clone());
            return;
        }
        for choice in &candidates[chosen.len()] {
            if out.len() > MOST_MATCHES {
                return;
            }
            if !chosen.contains(choice) {
                chosen.push(*choice);
                walk(candidates, chosen, out);
                chosen.pop();
            }
        }
    }
    let mut out = Vec::new();
    walk(candidates, &mut Vec::new(), &mut out);
    if out.len() <= MOST_MATCHES {
        out
    } else {
        Vec::new()
    }
}

fn sorted_rows(table: &Table) -> Vec<Vec<Cell>> {
    let mut rows: Vec<Vec<Cell>> = table.rows().map(<[Cell]>::to_vec).collect();
    rows.sort_unstable();
    rows.dedup();
    rows
}

/// Whether some match of the columns of `narrow` into those of `wide` that have its values takes `wide`'s rows to `narrow`'s.
fn projects_onto(wide: &Table, wide_sets: &[Vec<Cell>], narrow: &Table, narrow_sets: &[Vec<Cell>]) -> bool {
    let candidates: Vec<Vec<usize>> = narrow_sets.iter().map(|set| (0..wide_sets.len()).filter(|at| wide_sets[*at] == *set).collect()).collect();
    if candidates.iter().any(Vec::is_empty) {
        return false;
    }
    let rows = sorted_rows(narrow);
    column_matches(&candidates).iter().any(|choice| {
        let mut projected: Vec<Vec<Cell>> = wide.rows().map(|row| choice.iter().map(|at| row[*at]).collect()).collect();
        projected.sort_unstable();
        projected.dedup();
        projected == rows
    })
}

/// How a table's rows stand to another's.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Restructuring {
    Duplicate,
    Projection,
    Extension,
}

fn restructuring(own: &Table, other: &Table, sets: &mut ValueSets) -> Option<Restructuring> {
    let (own_sets, other_sets) = (sets.of(own), sets.of(other));
    if own.arity <= other.arity {
        projects_onto(other, &other_sets, own, &own_sets).then_some(if own.arity == other.arity { Restructuring::Duplicate } else { Restructuring::Projection })
    } else if own.len == other.len {
        projects_onto(own, &own_sets, other, &other_sets).then_some(Restructuring::Extension)
    } else {
        None
    }
}

/// Whether a table's columns split into two groups, each with two or more distinct rows, whose product it is. Only splits between groups of columns that depend on each other are tried.
fn cartesian(table: &Table) -> bool {
    let k = table.arity;
    if !(2..=10).contains(&k) {
        return false;
    }
    let distinct = |columns: &[usize]| -> usize {
        let mut rows: Vec<Vec<Cell>> = table.rows().map(|row| columns.iter().map(|at| row[*at]).collect()).collect();
        rows.sort_unstable();
        rows.dedup();
        rows.len()
    };
    let counts: Vec<usize> = (0..k).map(|column| distinct(&[column])).collect();
    let varying: Vec<usize> = (0..k).filter(|column| counts[*column] >= 2).collect();
    let mut group: Vec<usize> = (0..k).collect();
    fn root(group: &[usize], mut at: usize) -> usize {
        while group[at] != at {
            at = group[at];
        }
        at
    }
    for (place, i) in varying.iter().enumerate() {
        for j in &varying[place + 1..] {
            if root(&group, *i) != root(&group, *j) && distinct(&[*i, *j]) < counts[*i] * counts[*j] {
                let top = root(&group, *j);
                let own = root(&group, *i);
                group[own] = top;
            }
        }
    }
    let mut groups: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
    for column in &varying {
        groups.entry(root(&group, *column)).or_default().push(*column);
    }
    let groups: Vec<Vec<usize>> = groups.into_values().collect();
    if groups.len() < 2 || groups.len() > 16 {
        return false;
    }
    (1u32..1 << (groups.len() - 1)).any(|mask| {
        let side = |set: bool| -> Vec<usize> { groups.iter().enumerate().filter(|(at, _)| (mask >> at & 1 == 1) == set).flat_map(|(_, held)| held.iter().copied()).collect() };
        let (first, second) = (distinct(&side(true)), distinct(&side(false)));
        first >= 2 && second >= 2 && first * second == table.len
    })
}

/// How a candidate's rows stand at each example to the tables upstream of it and the input grid, and its rows over the most rows of what it reads.
pub fn structure_shapes(own: &Stored, upstream: &[&Stored], direct: &[&Stored], input: &Stored, reads_input: bool, sets: &mut ValueSets) -> Vec<NamedShape> {
    let examples = own.rows.len();
    let mut shapes: BTreeMap<&'static str, Vec<Option<f64>>> = BTreeMap::new();
    let first_of = |table: &Stored, at: usize| table.rows.get(at).and_then(|models| models.first()).cloned();
    for at in 0..examples {
        let Some(rows) = first_of(own, at) else { continue };
        let mut put = |name: &'static str, value: f64| shapes.entry(name).or_insert_with(|| vec![None; examples])[at] = Some(value);
        let mut kinds = BTreeSet::new();
        if rows.len > 0 && rows.arity > 0 {
            for other in upstream.iter().chain([&input]) {
                if let Some(other) = first_of(other, at).filter(|other| other.len > 0 && other.arity > 0) {
                    if let Some(kind) = restructuring(&rows, &other, sets) {
                        kinds.insert(kind as u8);
                    }
                }
            }
        }
        let (duplicate, projection, extension) = (kinds.contains(&(Restructuring::Duplicate as u8)), kinds.contains(&(Restructuring::Projection as u8)), kinds.contains(&(Restructuring::Extension as u8)));
        let flag = |held: bool| f64::from(u8::from(held));
        put("duplicate of a relation it reads", flag(duplicate));
        put("projection of a relation it reads", flag(projection));
        put("functional extension of a relation it reads", flag(extension));
        put("degenerate", flag(rows.len == 0 || duplicate || projection || cartesian(&rows)));
        let largest = direct.iter().filter_map(|other| first_of(other, at)).map(|other| other.len).chain(reads_input.then(|| first_of(input, at).map_or(0, |grid| grid.len))).max().unwrap_or(0);
        if largest > 0 {
            put("selectivity", rows.len as f64 / largest as f64);
        }
    }
    shapes.into_iter().map(|(name, at)| NamedShape { name: name.to_string(), at }).collect()
}
