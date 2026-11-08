//! `QueryVector`: the features of one query, from the tables it uses, the tables it computes, the
//! relation between them and the base tables, as the contract gives it. A relation feature is
//! computed at each assignment of the query, against each used table at that assignment restricted
//! to the `DET`s it depends on, and enters as its `:min`, `:mean` and `:max` over the assignments.
//! Program text reads the program relations, and a form's counts its own body.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

use arclog::layout::SourceFile;
use arclog::read::{read_sexprs, SExpr};

use crate::gen_constants::margins_of;
use crate::generate::{Generated, Generators, Walker};
use crate::program_relations::{ProgramFacts, QueryFacts};
use crate::run::{stored_tables, Host, StoredTable};
use crate::stored::Stored;
use crate::table_vector::{table_vector, Grids, TableVector};

type Assignment = Vec<(String, Vec<Vec<u32>>)>;

/// A query's vector.
#[derive(Clone, Debug, Default)]
pub struct QueryVector {
    pub identity: String,
    pub names: Vec<String>,
    pub values: Vec<f64>,
    pub use_names: Vec<String>,
    /// Each used parameterized table, by identity or a base table's name, and its features.
    pub per_use: Vec<(String, Vec<f64>)>,
    /// For each `Name`, each column's type and the used tables it is carried over from.
    pub column_origin: Vec<(String, Vec<(String, Vec<String>)>)>,
}

/// What a query's table at an assignment gives against the train outputs, as the contract's paint
/// and fill read it. A cell is (example, row, column).
#[derive(Default, Clone)]
struct Paint {
    gain: Option<f64>,
    fixed: BTreeSet<(usize, i32, i32)>,
    cells: BTreeSet<(usize, i32, i32)>,
}

/// A pair's grids as the paint reads them: whether the input stands under the output, and the colors
/// a blank grid holds where it does not.
struct PairView {
    input: BTreeMap<(i32, i32), u32>,
    output: BTreeMap<(i32, i32), u32>,
    same: bool,
    blank: BTreeSet<u32>,
}

impl PairView {
    fn of(input: &crate::native::Table, output: &crate::native::Table) -> PairView {
        let read = |table: &crate::native::Table| -> BTreeMap<(i32, i32), u32> {
            table.rows().map(|row| {
                let m = margins_of(row[0]);
                ((m[0], m[2]), row[1])
            }).collect()
        };
        let (input, output) = (read(input), read(output));
        let extent = |grid: &BTreeMap<(i32, i32), u32>| (grid.keys().map(|at| at.0).max(), grid.keys().map(|at| at.1).max());
        let same = extent(&input) == extent(&output);
        let mut counts: BTreeMap<u32, usize> = BTreeMap::new();
        for color in output.values() {
            *counts.entry(*color).or_insert(0) += 1;
        }
        let most = counts.values().copied().max().unwrap_or(0);
        PairView { input, output, same, blank: counts.iter().filter(|(_, count)| **count == most).map(|(color, _)| *color).collect() }
    }

    /// Whether the grid under the paint already holds the output's color at a cell.
    fn right(&self, at: (i32, i32)) -> bool {
        let want = self.output[&at];
        if self.same { self.input.get(&at) == Some(&want) } else { self.blank.contains(&want) }
    }

    fn wrong_cells(&self) -> usize {
        self.output.keys().filter(|at| !self.right(**at)).count()
    }
}

fn paint_of(table: &Stored, views: &[PairView]) -> Paint {
    let position: Vec<usize> = (0..table.types.len()).filter(|at| table.types[*at] == arclog::types::ValueType::Position).collect();
    let color: Vec<usize> = (0..table.types.len()).filter(|at| table.types[*at] == arclog::types::ValueType::Color).collect();
    let base: usize = views.iter().map(PairView::wrong_cells).sum::<usize>().max(1);
    let mut out = Paint::default();
    let mut best: Option<(i64, BTreeSet<(usize, i32, i32)>)> = None;
    let whole = 1024.0;
    for p in &position {
        for c in &color {
            let (mut fixed, mut fixed_count, mut broke) = (BTreeSet::new(), 0f64, 0f64);
            for (example, view) in views.iter().enumerate() {
                let share = 1.0 / table.rows[example].len().max(1) as f64;
                for model in &table.rows[example] {
                    let mut cells: BTreeMap<(i32, i32), BTreeSet<u32>> = BTreeMap::new();
                    for row in model.rows() {
                        let m = margins_of(row[*p]);
                        cells.entry((m[0], m[2])).or_default().insert(row[*c]);
                    }
                    for (at, colors) in &cells {
                        let Some(want) = view.output.get(at) else { continue };
                        let value = if colors.len() == 1 { colors.iter().next().copied() } else { None };
                        if value == Some(*want) {
                            if !view.right(*at) {
                                fixed.insert((example, at.0, at.1));
                                fixed_count += share;
                            }
                        } else if view.right(*at) {
                            broke += share;
                        }
                    }
                }
            }
            let err = ((base as f64 - fixed_count + broke) * 1024.0).round() as i64;
            // The least error, and over equal errors the fixed cells of each, so no order of the
            // columns enters.
            match &mut best {
                Some((held, cells)) if *held == err => cells.extend(fixed),
                Some((held, _)) if *held < err => {}
                _ => best = Some((err, fixed)),
            }
        }
    }
    if let Some((err, fixed)) = best {
        out.gain = Some(1.0 - err as f64 / whole / base as f64);
        out.fixed = fixed;
    }
    // A Position column with no paint color: how close one fill color comes.
    let mut best_fill: Option<(f64, BTreeSet<(usize, i32, i32)>)> = None;
    for p in &position {
        let (mut got, mut own) = (0f64, 0f64);
        let mut cells = BTreeSet::new();
        for (example, view) in views.iter().enumerate() {
            let share = 1.0 / table.rows[example].len().max(1) as f64;
            for model in &table.rows[example] {
                let held: BTreeSet<(i32, i32)> = model.rows().map(|row| {
                    let m = margins_of(row[*p]);
                    (m[0], m[2])
                }).filter(|at| view.output.contains_key(at)).collect();
                cells.extend(held.iter().map(|at| (example, at.0, at.1)));
                let mut counts: BTreeMap<u32, i64> = BTreeMap::new();
                for at in &held {
                    *counts.entry(view.output[at]).or_insert(0) += 1;
                }
                let most = counts.values().copied().max().unwrap_or(0);
                // Under a tie of fill colors, the mean over them.
                let tied: Vec<u32> = counts.iter().filter(|(_, count)| **count == most).map(|(color, _)| *color).collect();
                let weight = share / tied.len().max(1) as f64;
                for fill in &tied {
                    for at in &held {
                        let want = view.output[at];
                        if want == *fill && !view.right(*at) {
                            got += weight;
                        } else if want != *fill && view.right(*at) {
                            own += weight;
                        }
                    }
                }
            }
        }
        let gain = (got - own) / base as f64;
        if best_fill.as_ref().is_none_or(|held| gain > held.0) {
            best_fill = Some((gain, cells));
        }
    }
    if let Some((gain, cells)) = best_fill {
        out.cells = cells;
        if out.gain.is_none() {
            out.gain = Some(gain);
        }
    }
    out
}

fn total_rows(table: &Stored) -> f64 {
    table.rows.iter().map(|models| {
        if models.is_empty() { 0.0 } else { models.iter().map(|model| model.len as f64).sum::<f64>() / models.len() as f64 }
    }).sum()
}

/// Whether two assignments agree on each `DET` that both name.
pub(crate) fn agrees(a: &Assignment, b: &Assignment) -> bool {
    a.iter().all(|(name, rows)| b.iter().find(|(own, _)| own == name).is_none_or(|(_, own)| own == rows))
}

/// The features of a query against its used tables, in the contract's families. A list of one schema
/// version, so each vector has these names, with no value where a feature has none.
const RELATION_FEATURES: [&str; 10] = ["rows_over_greatest_use", "cells_subset_of_use", "cells_superset_of_use", "cells_disjoint_from_uses", "use_gain", "gain_less_use_gain", "gain_above_use_gain", "new_cells_share", "new_cells_count", "union_share_added"];
const USE_FEATURES: [&str; 5] = ["rows_over_use", "type_share", "same_entries_share", "gain_less_use", "fixed_not_in_use"];

/// Each feature at each assignment of a query: the greatest over its Names.
#[derive(Clone, Default)]
struct AtAssignments(BTreeMap<String, BTreeMap<&'static str, f64>>);

impl AtAssignments {
    fn put(&mut self, assignment: &str, name: &'static str, value: f64) {
        let held = self.0.entry(assignment.to_string()).or_default().entry(name).or_insert(value);
        *held = held.max(value);
    }

    /// The min, the mean and the max of `name` over the assignments, with no value where it has none.
    fn pooled(&self, name: &str) -> [f64; 3] {
        let seen: Vec<f64> = self.0.values().filter_map(|at| at.get(name).copied()).collect();
        if seen.is_empty() {
            return [f64::NAN; 3];
        }
        [seen.iter().copied().fold(f64::INFINITY, f64::min), seen.iter().sum::<f64>() / seen.len() as f64, seen.iter().copied().fold(f64::NEG_INFINITY, f64::max)]
    }
}

fn pooled_names(features: &[&str]) -> Vec<String> {
    features.iter().flat_map(|name| ["min", "mean", "max"].map(|suffix| format!("{name}:{suffix}"))).collect()
}

/// The mean over examples of a value's mean over the pairs of TableRows of two tables at the example,
/// over the examples where the value has one.
fn over_pairs(a: &Stored, b: &Stored, value: &dyn Fn(&crate::native::Table, &crate::native::Table) -> Option<f64>) -> Option<f64> {
    let mut means = Vec::new();
    for example in 0..a.rows.len().min(b.rows.len()) {
        let seen: Vec<f64> = a.rows[example].iter().flat_map(|one| b.rows[example].iter().filter_map(|two| value(one, two))).collect();
        if !seen.is_empty() {
            means.push(seen.iter().sum::<f64>() / seen.len() as f64);
        }
    }
    (!means.is_empty()).then(|| means.iter().sum::<f64>() / means.len() as f64)
}

/// The cells of a TableRows' Position columns.
fn cells_of(table: &crate::native::Table, types: &[arclog::types::ValueType]) -> BTreeSet<[i32; 4]> {
    let places: Vec<usize> = (0..types.len()).filter(|at| types[*at] == arclog::types::ValueType::Position).collect();
    table.rows().flat_map(|row| places.iter().map(|at| margins_of(row[*at])).collect::<Vec<_>>()).collect()
}

/// The counts of a form's body, by the contract's family from the query's body.
#[derive(Default)]
struct Body {
    counts: BTreeMap<String, f64>,
    labels: BTreeMap<String, u32>,
}

impl Body {
    fn add(&mut self, name: &str) {
        *self.counts.entry(name.to_string()).or_insert(0.0) += 1.0;
    }

    fn site(&mut self, node: &SExpr) {
        match node {
            SExpr::Symbol { text, .. } => {
                let text: &str = text;
                if text == "0" || text.starts_with(':') {
                    return;
                }
                *self.labels.entry(text.trim_start_matches(['*', '^']).to_string()).or_insert(0) += 1;
            }
            SExpr::List { items, .. } => {
                let skip = usize::from(matches!(items.first(), Some(SExpr::Symbol { text, .. }) if text.starts_with(':')));
                for item in &items[skip..] {
                    self.site(item);
                }
            }
            SExpr::String { .. } => {}
        }
    }

    fn atom(&mut self, node: &SExpr, negated: bool) {
        let SExpr::List { items, .. } = node else { return };
        let Some(head) = items.first() else { return };
        let SExpr::Symbol { text, .. } = head else {
            for item in items {
                self.atom(item, negated);
            }
            return;
        };
        let head: &str = text;
        match head {
            "NOT" => {
                for item in &items[1..] {
                    self.atom(item, true);
                }
            }
            "OR" => {
                self.add("ors");
                for branch in &items[1..] {
                    self.add("or_branches");
                    self.atom(branch, negated);
                }
            }
            "IF" | "ALL" => {
                self.add(if head == "IF" { "ifs" } else { "alls" });
                for item in &items[1..] {
                    self.atom(item, negated);
                }
            }
            "=" | "!=" | "<" | "<=" | ">" | ">=" => {
                self.add("comparisons");
                for item in &items[1..] {
                    self.site(item);
                }
            }
            _ => {
                self.add("atoms");
                if negated {
                    self.add("not_atoms");
                }
                if head == "input" || head == "ex_input" || head == "ex_output" {
                    self.add(&format!("uses:{head}"));
                } else if head.starts_with('&') {
                    self.add("uses:tables");
                } else {
                    self.add(&format!("atom:{head}"));
                }
                for item in &items[1..] {
                    self.site(item);
                }
            }
        }
    }

    fn form(&mut self, form: &SExpr) {
        let SExpr::List { items, .. } = form else { return };
        let Some(SExpr::Symbol { text, .. }) = items.first() else { return };
        if &**text == "INIT" {
            if let Some(SExpr::Symbol { text, .. }) = items.get(2) {
                self.add(&format!("component:{text}"));
            }
            for clause in items.iter().skip(3) {
                let SExpr::List { items: inner, .. } = clause else { continue };
                let is_key = matches!(inner.first(), Some(SExpr::Symbol { text, .. }) if &**text == "key");
                if is_key {
                    if let Some(SExpr::List { items: body, .. }) = inner.get(1) {
                        for atom in body {
                            self.atom(atom, false);
                        }
                    }
                    for held in inner.iter().skip(2) {
                        self.input_clause(held);
                    }
                } else {
                    self.input_clause(clause);
                }
            }
            return;
        }
        for part in items.iter().skip(2) {
            match part {
                SExpr::Symbol { text, .. } => self.add(&format!("component:{text}")),
                other => self.atom(other, false),
            }
        }
    }

    fn input_clause(&mut self, clause: &SExpr) {
        let SExpr::List { items, .. } = clause else { return };
        if let Some(sites) = items.get(1) {
            self.site(sites);
        }
        for atom in items.iter().skip(2) {
            self.atom(atom, false);
        }
    }
}

/// A `Name` of a query, by the tail of its table's name, which is its port.
fn name_of(table: &str) -> String {
    table.split_once('.').map_or(String::new(), |(_, port)| port.to_string())
}

/// The depth of a query over the state's own use edges.
fn depth_of(query: &QueryFacts, facts: &ProgramFacts, memo: &mut BTreeMap<String, usize>) -> usize {
    if let Some(found) = memo.get(&query.identity) {
        return *found;
    }
    let mut depth = 0;
    for read in &query.reads {
        if let Some(parent) = facts.queries.iter().find(|other| other.computes.contains(read)) {
            depth = depth.max(1 + depth_of(parent, facts, memo));
        }
    }
    memo.insert(query.identity.clone(), depth);
    depth
}

/// A vector of each query of a state. `d` is the size of the shapes that the share over a used table
/// reads, and 0 leaves that share out.
pub fn query_vectors(host: &Host, grids: &Grids, families: &Generators, d: usize) -> Result<Vec<QueryVector>, String> {
    let facts = host.program_facts();
    let mut tables: BTreeMap<String, StoredTable> = BTreeMap::new();
    for (identity, spelled) in &facts.table_names {
        if let Ok(table) = stored_tables(host, spelled) {
            tables.insert(identity.clone(), table);
        }
    }
    let base_table = |name: &str| -> Option<Stored> {
        match name {
            "input" | "ex_input" => Some(Stored::of_grids(&grids.inputs)),
            "ex_output" => {
                let mut stored = Stored::of_grids(&grids.outputs);
                stored.rows.resize(grids.inputs.len(), Vec::new());
                Some(stored)
            }
            _ => None,
        }
    };
    let views: Vec<PairView> = (0..grids.train).map(|at| PairView::of(&grids.inputs[at], &grids.outputs[at])).collect();
    let forms = read_sexprs(host.state_text(), SourceFile::Arclog).map(|(forms, _)| forms).unwrap_or_default();
    // A query's form, by the name it defines.
    let mut texts: BTreeMap<String, &SExpr> = BTreeMap::new();
    for form in &forms {
        let SExpr::List { items, .. } = form else { continue };
        let (Some(SExpr::Symbol { text: head, .. }), Some(SExpr::Symbol { text: name, .. })) = (items.first(), items.get(1)) else { continue };
        if matches!(&**head, "OUT" | "INPUT" | "OUTPUT" | "ALTS") {
            continue;
        }
        if texts.insert(name.to_string(), form).is_some() {
            return Err(format!("two forms define {name}"));
        }
    }
    let mut walkers: BTreeMap<String, (Arc<Generated>, BTreeMap<u128, Arc<TableVector>>)> = BTreeMap::new();
    let mut vector_of = |table: &Stored| -> Arc<TableVector> {
        let entry = walkers.entry(table.key.clone()).or_insert_with(|| (families.get(table, d.max(1)), BTreeMap::new()));
        let content = table.content();
        if let Some(found) = entry.1.get(&content) {
            return found.clone();
        }
        let family = entry.0.clone();
        let mut walker = Walker::new(&family);
        let found = Arc::new(table_vector(&mut walker, table, grids, grids.inputs.len(), false));
        entry.1.insert(content, found.clone());
        found
    };
    let mut depths = BTreeMap::new();
    let mut out = Vec::with_capacity(facts.queries.len());
    for query in &facts.queries {
        let depth = depth_of(query, &facts, &mut depths);
        let members: Vec<&String> = query.reads.iter().filter(|read| facts.table_names.contains_key(*read)).collect();
        // Used tables: the base tables first, then the members' by the query's hash and the Name.
        let mut used: Vec<String> = query.reads.iter().filter(|read| !facts.table_names.contains_key(*read)).cloned().collect();
        used.sort();
        let mut member_order: Vec<(String, String, String)> = members.iter().map(|read| {
            let owner = facts.queries.iter().find(|other| other.computes.contains(*read)).map_or(String::new(), |other| other.identity.clone());
            (owner, name_of(&facts.table_names[*read]), (*read).clone())
        }).collect();
        member_order.sort();
        used.extend(member_order.into_iter().map(|held| held.2));

        let mut values = AtAssignments::default();
        let mut per_use_values: Vec<AtAssignments> = vec![AtAssignments::default(); used.len()];
        for computed in &query.computes {
            let Some(own) = tables.get(computed) else { continue };
            for (assignment, table) in &own.at {
                let at = format!("{assignment:?}");
                let own_paint = paint_of(table, &views);
                let rows = total_rows(table);
                let own_vector = (d > 0).then(|| vector_of(table));
                let (mut greatest_rows, mut parent_gains) = (f64::NEG_INFINITY, Vec::new());
                let mut parent_fixed: BTreeSet<(usize, i32, i32)> = BTreeSet::new();
                let mut pair_union = f64::NEG_INFINITY;
                let (mut subset, mut superset, mut disjoint): (Option<f64>, Option<f64>, Option<f64>) = (None, None, None);
                let base_cells = |paint: &Paint| if paint.fixed.is_empty() { paint.cells.clone() } else { paint.fixed.clone() };
                let own_base = base_cells(&own_paint);
                for (place, read) in used.iter().enumerate() {
                    let held: Option<Stored> = match tables.get(read) {
                        Some(found) => found.at.iter().find(|(other, _)| agrees(other, assignment)).map(|(_, stored)| stored.clone()),
                        None => base_table(read),
                    };
                    let Some(other) = held else { continue };
                    let bucket = &mut per_use_values[place];
                    if let Some(ratio) = over_pairs(table, &other, &|one, two| (two.len > 0).then(|| one.len as f64 / two.len as f64)) {
                        bucket.put(&at, "rows_over_use", ratio);
                    }
                    let mut types: Vec<String> = other.types.iter().map(|ty| format!("{:?}", ty.without_source())).collect();
                    let shared = table.types.iter().filter(|ty| {
                        let text = format!("{:?}", ty.without_source());
                        match types.iter().position(|own| *own == text) {
                            Some(at) => {
                                types.remove(at);
                                true
                            }
                            None => false,
                        }
                    }).count();
                    bucket.put(&at, "type_share", shared as f64 / table.types.len().max(1) as f64);
                    if let Some(own_vector) = &own_vector {
                        let their = vector_of(&other);
                        let active: Vec<usize> = (0..own_vector.shapes.len()).filter(|shape| own_vector.at(*shape).iter().any(|slot| slot.state != crate::generate::SlotState::Default)).collect();
                        let same = active.iter().filter(|shape| own_vector.same_at_each_example(**shape, &their)).count();
                        bucket.put(&at, "same_entries_share", same as f64 / active.len().max(1) as f64);
                    }
                    let paint = paint_of(&other, &views);
                    if let (Some(a), Some(b)) = (own_paint.gain, paint.gain) {
                        bucket.put(&at, "gain_less_use", a - b);
                    }
                    if !own_paint.fixed.is_empty() {
                        let new = own_paint.fixed.difference(&paint.fixed).count();
                        bucket.put(&at, "fixed_not_in_use", new as f64 / own_paint.fixed.len() as f64);
                    }
                    if facts.table_names.contains_key(read) {
                        greatest_rows = greatest_rows.max(total_rows(&other));
                        if let Some(gain) = paint.gain {
                            parent_gains.push(gain);
                            let theirs = base_cells(&paint);
                            parent_fixed.extend(theirs.iter().copied());
                            let union = own_base.union(&theirs).count();
                            pair_union = pair_union.max((union as f64 - own_base.len().max(theirs.len()) as f64) / union.max(1) as f64);
                        }
                        // At an example where both have cells, over the pairs of TableRows there.
                        let relation = |test: &dyn Fn(&BTreeSet<[i32; 4]>, &BTreeSet<[i32; 4]>) -> bool| over_pairs(table, &other, &|one, two| {
                            let (a, b) = (cells_of(one, &table.types), cells_of(two, &other.types));
                            (!a.is_empty() && !b.is_empty()).then(|| f64::from(u8::from(test(&a, &b))))
                        });
                        let most = |held: Option<f64>, new: Option<f64>| match (held, new) {
                            (Some(a), Some(b)) => Some(a.max(b)),
                            (a, b) => a.or(b),
                        };
                        subset = most(subset, relation(&|a, b| a.is_subset(b) && a.len() < b.len()));
                        superset = most(superset, relation(&|a, b| b.is_subset(a) && a.len() > b.len()));
                        // Disjoint from each used table: the least over them.
                        let apart = relation(&|a, b| a.is_disjoint(b));
                        disjoint = match (disjoint, apart) {
                            (Some(a), Some(b)) => Some(a.min(b)),
                            (a, b) => a.or(b),
                        };
                    }
                }
                let mut put = |name: &'static str, value: f64| values.put(&at, name, value);
                if greatest_rows.is_finite() {
                    put("rows_over_greatest_use", (rows + 1.0) / (greatest_rows + 1.0));
                }
                if let (Some(a), Some(b), Some(c)) = (subset, superset, disjoint) {
                    put("cells_subset_of_use", a);
                    put("cells_superset_of_use", b);
                    put("cells_disjoint_from_uses", c);
                }
                if let Some(top) = parent_gains.iter().copied().reduce(f64::max) {
                    put("use_gain", top);
                    if let Some(gain) = own_paint.gain {
                        put("gain_less_use_gain", gain - top);
                        put("gain_above_use_gain", f64::from(u8::from(gain > top)));
                        let new = own_base.difference(&parent_fixed).count();
                        put("new_cells_share", new as f64 / own_base.len().max(1) as f64);
                        put("new_cells_count", new as f64);
                        put("union_share_added", pair_union);
                    }
                }
            }
        }
        let mut names = vec!["depth".to_string(), "used_members".to_string(), "names".to_string()];
        let mut number_values = vec![depth as f64, members.len() as f64, query.computes.len() as f64];
        names.extend(pooled_names(&RELATION_FEATURES));
        number_values.extend(RELATION_FEATURES.iter().flat_map(|name| values.pooled(name)));

        // Column origin, from the lineage of each column.
        let empty = BTreeSet::new();
        let lineage = facts.rows.get(arclog::program::ProgramFact::ColumnLineage.name()).unwrap_or(&empty);
        let types = facts.rows.get(arclog::program::ProgramFact::ColumnType.name()).unwrap_or(&empty);
        let mut column_origin = Vec::new();
        let (mut carried, mut new_columns) = (0.0, 0.0);
        let mut carried_from: BTreeSet<String> = BTreeSet::new();
        for computed in &query.computes {
            let mut columns: BTreeMap<String, (String, BTreeSet<String>)> = BTreeMap::new();
            for row in types.iter().filter(|row| row[0] == *computed) {
                columns.insert(row[1].clone(), (row[2].clone(), BTreeSet::new()));
            }
            for row in lineage.iter().filter(|row| row[0] == *computed && row[2] == "Copy") {
                let mut source = row[3].split(['/', '.']).next().unwrap_or("").to_string();
                // A read of `input` has `ex_input` as its lineage, so a column carried from it is
                // written by the base table the query uses.
                if source == "ex_input" && !used.contains(&source) {
                    source = "input".to_string();
                }
                if used.contains(&source) {
                    if let Some(column) = columns.get_mut(&row[1]) {
                        column.1.insert(source.clone());
                    }
                }
            }
            let mut inner: Vec<(String, Vec<String>)> = columns.into_values().map(|(ty, from)| {
                if from.is_empty() { new_columns += 1.0 } else { carried += 1.0 }
                carried_from.extend(from.iter().cloned());
                (ty, from.into_iter().collect())
            }).collect();
            inner.sort();
            let name = facts.table_names.get(computed).map_or(String::new(), |spelled| name_of(spelled));
            column_origin.push((name, inner));
        }
        column_origin.sort();
        names.extend(["columns_carried".to_string(), "columns_new".to_string(), "uses_with_no_column_carried".to_string()]);
        number_values.extend([carried, new_columns, used.iter().filter(|read| !carried_from.contains(*read)).count() as f64]);

        // The query's body.
        names.push(format!("kind:{}", query.kind));
        number_values.push(1.0);
        let defined: BTreeSet<&str> = query.computes.iter().filter_map(|computed| facts.table_names.get(computed)).map(|spelled| spelled.split('.').next().unwrap_or("")).collect();
        let [name] = defined.iter().copied().collect::<Vec<_>>()[..] else {
            return Err(format!("the query {} defines {} names", query.identity, defined.len()));
        };
        let form = texts.get(name).ok_or_else(|| format!("no form of the state's text defines {name}"))?;
        let mut body = Body::default();
        body.form(form);
        let labels = body.labels.len() as f64;
        let joined = body.labels.values().filter(|count| **count >= 2).count() as f64;
        for (name, count) in &body.counts {
            names.push(name.clone());
            number_values.push(*count);
        }
        names.extend(["labels".to_string(), "labels_two_or_more_sites".to_string()]);
        number_values.extend([labels, joined]);

        let use_names = pooled_names(&USE_FEATURES);
        let per_use = used.iter().zip(&per_use_values).map(|(read, bucket)| {
            (read.clone(), USE_FEATURES.iter().flat_map(|name| bucket.pooled(name)).collect())
        }).collect();
        out.push(QueryVector { identity: query.identity.clone(), names, values: number_values, use_names, per_use, column_origin });
    }
    Ok(out)
}
