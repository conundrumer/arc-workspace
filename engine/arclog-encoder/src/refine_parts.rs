//! A part's refinements, read from its fragment's expansion: the clauses of plain arclog that its call
//! writes, with the declarations of the lib elements they read. So a part writes none of its own.
//!
//! A clause's keys come from the keys of its atoms, by closure over its labels. A column's subset
//! relations come from the atoms that hold its label, and through the `copies` rows of a component. A
//! clause whose other atoms keep each row of its first relation has that relation's rows.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, Mutex, OnceLock};

use arclog::algebra::algebra;
use arclog::layout::SourceFile;
use arclog::program::ColumnName;
use arclog::read::{read_sexprs, SExpr};
use arclog::registry::{is_key, Column as LibColumn, ColumnType, Component, LibEntry, LibName, Macro, Registry};
use arclog::types::ValueType;

use crate::lookup::LookupMap;
use crate::refine::{bit, Mask, Refined};
use crate::schema::{TableColumn, TableSchema, Tables};

/// The tuple of a relation's columns that stands within the columns `at` of a base relation.
#[derive(Clone, Debug, PartialEq, Eq)]
struct Origin {
    columns: Vec<u16>,
    source: String,
    at: Vec<String>,
}

/// A relation's rows against a base relation: over the columns of `at`, it holds exactly what the base
/// holds over theirs, with `fan_out` rows per such value where that is known.
#[derive(Clone, Debug)]
struct Like {
    base: String,
    at: Vec<(u16, String)>,
    fan_out: Option<u32>,
}

/// For each value of the columns `lhs`, `fan_out` rows, where that is known.
#[derive(Clone, Debug)]
struct Each {
    lhs: Mask,
    fan_out: Option<u32>,
}

/// What the fragment's reader knows of a relation.
#[derive(Clone, Debug, Default)]
struct Facts {
    columns: Vec<String>,
    keys: Vec<Mask>,
    low: Vec<Option<i32>>,
    high: Vec<Option<i32>>,
    /// The columns of one value over its rows.
    constant: Mask,
    origin: Vec<Origin>,
    like: Option<Like>,
    each: Vec<Each>,
    empty: bool,
    nonempty: bool,
    /// Whether its value is true on every nonempty domain: an `ALL` whose body each row of its domain meets.
    holds_on_domain: bool,
    /// Whether a read of it reads only the columns that its labels use.
    alias: bool,
    /// The base relations it reads.
    deps: BTreeSet<String>,
    /// Where each of its rows depends on one row of this base relation, and on no other row of it.
    rowwise_on: Option<String>,
    /// The columns of `&r` that its value depends on.
    reads: BTreeSet<String>,
}

impl Facts {
    fn index(&self, column: &str) -> Option<usize> {
        self.columns.iter().position(|own| own == column)
    }

    fn with_columns(columns: Vec<String>) -> Facts {
        let arity = columns.len();
        Facts { columns, low: vec![None; arity], high: vec![None; arity], ..Facts::default() }
    }

    fn is_key(&self, mask: Mask) -> bool {
        self.keys.iter().any(|key| key & !mask == 0)
    }

    fn add_key(&mut self, key: Mask) {
        if !self.is_key(key) {
            self.keys.retain(|held| held & !key != 0);
            self.keys.push(key);
        }
    }
}

fn symbol(expr: &SExpr) -> Option<&str> {
    match expr {
        SExpr::Symbol { text, .. } => Some(text),
        _ => None,
    }
}

fn items(expr: &SExpr) -> Option<&[SExpr]> {
    match expr {
        SExpr::List { items, .. } => Some(items),
        _ => None,
    }
}

fn head(expr: &SExpr) -> Option<&str> {
    items(expr).and_then(|list| list.first()).and_then(symbol)
}

fn written(name: &ColumnName) -> String {
    match name {
        ColumnName::Written(text) => text.to_string(),
        ColumnName::Slot(slot) => format!("c{slot}"),
    }
}

fn split_mark(text: &str) -> (char, &str) {
    match text.as_bytes().first() {
        Some(b'*') => ('*', &text[1..]),
        Some(b'^') => ('^', &text[1..]),
        _ => (' ', text),
    }
}

fn is_constraint(name: &str) -> bool {
    matches!(name, "=" | "!=" | "<" | "<=" | ">" | ">=")
}

/// The relation of each orientation type's values.
fn elem_relation(ty: &ValueType) -> Option<&'static str> {
    Some(match ty {
        ValueType::Dir => "dir_elem",
        ValueType::DiagDir => "diag_dir_elem",
        ValueType::Dir8 => "dir8_elem",
        ValueType::Axis => "axis_elem",
        ValueType::DiagAxis => "diag_axis_elem",
        ValueType::Axis4 => "axis4_elem",
        ValueType::D4 => "d4_elem",
        ValueType::C4 => "c4_elem",
        ValueType::Sense => "sense_elem",
        ValueType::Sym => "sym_elem",
        _ => return None,
    })
}

/// The rows of a lib relation over a finite domain.
fn finite_rows(name: &str, arity: usize, registry: &Registry) -> Option<Vec<Vec<u32>>> {
    let relation = algebra(&LibName(name.into()))?;
    let bound: Vec<Option<arclog::terms::TermId>> = vec![None; arity];
    let mut rows = Vec::new();
    relation.evaluate(&bound, registry, &mut |row| rows.push(row.iter().map(|cell| cell.encoding()).collect())).ok()?;
    Some(rows)
}

fn column_value_type(column: &LibColumn) -> Option<ValueType> {
    match &column.ty {
        ColumnType::Fixed(ty) | ColumnType::PoseOr(ty) => Some(ty.clone()),
        _ => None,
    }
}

fn number_low(ty: Option<&ValueType>) -> Option<i32> {
    (ty == Some(&ValueType::Nat)).then_some(0)
}

/// Applies the items of a lib relation's `refines` form that need no instance.
fn apply_relation_items(facts: &mut Facts, name: &str, registry: &Registry) {
    for item in registry.refines(name) {
        let Some(list) = items(item) else { continue };
        let names: Vec<&str> = list.iter().skip(1).filter_map(symbol).collect();
        match list.first().and_then(symbol) {
            Some("key") => {
                let mask = names.iter().filter_map(|column| facts.index(column)).fold(0, |held, at| held | bit(at as u16));
                facts.add_key(mask);
            }
            Some("at-least") => {
                if let (Some(column), Some(Ok(low))) = (names.first().and_then(|column| facts.index(column)), names.get(1).map(|text| text.parse::<i32>())) {
                    facts.low[column] = Some(low);
                }
            }
            Some("each") => {
                let lhs = list.get(1).and_then(items).unwrap_or_default().iter().filter_map(symbol).filter_map(|column| facts.index(column)).fold(0, |held, at| held | bit(at as u16));
                let fan_out = list.get(2).and_then(symbol).and_then(|text| text.parse().ok());
                facts.each.push(Each { lhs, fan_out });
            }
            _ => {}
        }
    }
}

/// What a lib relation declares, and what its rows give where its domain is finite.
fn lib_facts(name: &str) -> Option<Arc<Facts>> {
    static HELD: OnceLock<Mutex<LookupMap<String, Option<Arc<Facts>>>>> = OnceLock::new();
    let held = HELD.get_or_init(Default::default);
    if let Some(found) = held.lock().expect("no panic").get(name) {
        return found.clone();
    }
    let registry = Registry::get();
    let lib_name = LibName(name.into());
    let relation = match registry.entry(&lib_name) {
        Some(LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. })) => Some(relation),
        _ => None,
    };
    let found = relation.map(|relation| {
        let columns: Vec<String> = relation.columns.iter().map(|column| written(&column.name)).collect();
        let mut facts = Facts::with_columns(columns);
        for (at, column) in relation.columns.iter().enumerate() {
            facts.low[at] = number_low(column_value_type(column).as_ref());
        }
        facts.deps = BTreeSet::new();
        facts.alias = false;
        if relation.modes.is_empty() {
            if let Some(rows) = finite_rows(name, relation.columns.len(), registry) {
                facts.nonempty = !rows.is_empty();
                let arity = relation.columns.len();
                for mask in 0u32..(1 << arity) {
                    let mut seen: Vec<Vec<u32>> = rows.iter().map(|row| (0..arity).filter(|at| mask & (1 << at) != 0).map(|at| row[at]).collect()).collect();
                    seen.sort_unstable();
                    if seen.windows(2).all(|pair| pair[0] != pair[1]) {
                        facts.add_key(mask);
                    }
                }
                for (at, column) in relation.columns.iter().enumerate() {
                    let domain = column_value_type(column).and_then(|ty| elem_relation(&ty).and_then(|elem| finite_rows(elem, 1, registry).map(|rows| rows.len())));
                    let mut counts: BTreeMap<u32, u32> = BTreeMap::new();
                    for row in &rows {
                        *counts.entry(row[at]).or_insert(0) += 1;
                    }
                    if domain == Some(counts.len()) {
                        let mut values = counts.values();
                        let first = values.next().copied();
                        let fan_out = first.filter(|one| values.all(|other| other == one));
                        facts.each.push(Each { lhs: bit(at as u16), fan_out });
                    }
                }
            }
        }
        apply_relation_items(&mut facts, name, registry);
        Arc::new(facts)
    });
    held.lock().expect("no panic").insert(name.to_string(), found.clone());
    found
}

fn grid_facts(name: &str) -> Facts {
    let mut facts = Facts::with_columns(vec!["P".to_string(), "Col".to_string()]);
    facts.keys = vec![bit(0)];
    facts.origin = vec![Origin { columns: vec![0, 1], source: name.to_string(), at: vec!["P".to_string(), "Col".to_string()] }];
    facts.like = Some(Like { base: name.to_string(), at: vec![(0, "P".to_string()), (1, "Col".to_string())], fan_out: Some(1) });
    facts.alias = true;
    facts.nonempty = true;
    facts.deps.insert(name.to_string());
    facts.rowwise_on = Some(name.to_string());
    facts
}

/// What a relation hole holds at a call.
#[derive(Clone, Debug, Default, PartialEq, Eq, Hash)]
pub struct RelationInput {
    pub columns: Vec<String>,
    pub keys: Vec<Mask>,
    pub low: Vec<Option<i32>>,
    pub high: Vec<Option<i32>>,
    /// The columns that stand within a base relation's column: (column, source, its column).
    pub within: Vec<(String, String, String)>,
}

impl RelationInput {
    fn facts(&self, name: &str) -> Facts {
        let mut facts = Facts::with_columns(self.columns.clone());
        facts.keys.clone_from(&self.keys);
        facts.low.clone_from(&self.low);
        facts.high.clone_from(&self.high);
        let all: Vec<u16> = (0..self.columns.len() as u16).collect();
        facts.origin = vec![Origin { columns: all.clone(), source: name.to_string(), at: self.columns.clone() }];
        for (column, source, at) in &self.within {
            if let Some(place) = self.columns.iter().position(|own| own == column) {
                facts.origin.push(Origin { columns: vec![place as u16], source: source.clone(), at: vec![at.clone()] });
            }
        }
        facts.like = Some(Like { base: name.to_string(), at: self.columns.iter().enumerate().map(|(at, column)| (at as u16, column.clone())).collect(), fan_out: Some(1) });
        facts.alias = true;
        facts.deps.insert(name.to_string());
        facts.rowwise_on = Some(name.to_string());
        facts
    }
}

/// An `INIT` form.
struct Instance {
    component: String,
    key_fields: Vec<String>,
    key: Option<Facts>,
    inputs: LookupMap<String, Facts>,
    /// Each column of a type parameter that a binding writes as a record: its fields.
    shapes: LookupMap<String, Vec<String>>,
}

/// A site of an atom: the column it stands at, and its label or a zero.
#[derive(Clone, Debug)]
enum Value {
    Label(String),
    Zero,
}

fn value_of(expr: &SExpr) -> Option<Value> {
    let text = symbol(expr)?;
    let (_, name) = split_mark(text);
    Some(if name == "0" { Value::Zero } else { Value::Label(name.to_string()) })
}

/// The sites of an atom of the relation `facts`, by column.
fn atom_sites(facts: &Facts, sites: &[SExpr]) -> Vec<(usize, Value)> {
    let mut out = Vec::new();
    for site in sites {
        match site {
            SExpr::Symbol { text, .. } => {
                let (_, name) = split_mark(text);
                if let Some(at) = facts.index(name) {
                    if name != "0" {
                        out.push((at, Value::Label(name.to_string())));
                    }
                }
            }
            SExpr::List { items: list, .. } => {
                let Some(column) = list.first().and_then(symbol).and_then(|text| text.strip_prefix(':')) else { continue };
                if let (Some(at), Some(value)) = (facts.index(column), list.get(1).and_then(value_of)) {
                    out.push((at, value));
                    continue;
                }
                for arg in &list[1..] {
                    match arg {
                        SExpr::Symbol { text, .. } => {
                            let (_, name) = split_mark(text);
                            if let Some(at) = facts.index(&format!("{column}.{name}")) {
                                out.push((at, Value::Label(name.to_string())));
                            }
                        }
                        SExpr::List { items: field, .. } => {
                            if let (Some(name), Some(value)) = (field.first().and_then(symbol).and_then(|text| text.strip_prefix(':')), field.get(1).and_then(value_of)) {
                                if let Some(at) = facts.index(&format!("{column}.{name}")) {
                                    out.push((at, value));
                                }
                            }
                        }
                        SExpr::String { .. } => {}
                    }
                }
            }
            SExpr::String { .. } => {}
        }
    }
    out
}

/// The columns and labels that an input's head writes.
fn head_sites(sites: &[SExpr]) -> Vec<(String, String)> {
    let mut out = Vec::new();
    for site in sites {
        match site {
            SExpr::Symbol { text, .. } => {
                let (_, name) = split_mark(text);
                out.push((name.to_string(), name.to_string()));
            }
            SExpr::List { items: list, .. } => {
                let Some(column) = list.first().and_then(symbol).and_then(|text| text.strip_prefix(':')) else { continue };
                let args = &list[1..];
                if let [SExpr::Symbol { text, .. }] = args {
                    out.push((column.to_string(), split_mark(text).1.to_string()));
                    continue;
                }
                for arg in args {
                    match arg {
                        SExpr::Symbol { text, .. } => {
                            let (_, name) = split_mark(text);
                            out.push((format!("{column}.{name}"), name.to_string()));
                        }
                        SExpr::List { items: field, .. } => {
                            if let (Some(name), Some(label)) = (field.first().and_then(symbol).and_then(|text| text.strip_prefix(':')), field.get(1).and_then(symbol)) {
                                out.push((format!("{column}.{name}"), split_mark(label).1.to_string()));
                            }
                        }
                        SExpr::String { .. } => {}
                    }
                }
            }
            SExpr::String { .. } => {}
        }
    }
    out
}

/// The labels marked `^` in a key clause's body, in order.
fn key_labels(expr: &SExpr, out: &mut Vec<String>) {
    match expr {
        SExpr::Symbol { text, .. } => {
            if let Some(name) = text.strip_prefix('^') {
                if !out.iter().any(|held| held == name) {
                    out.push(name.to_string());
                }
            }
        }
        SExpr::List { items: list, .. } => {
            for item in list {
                key_labels(item, out);
            }
        }
        SExpr::String { .. } => {}
    }
}

/// Counts each label that `expr` writes.
fn count_labels(expr: &SExpr, skip_columns: bool, counts: &mut BTreeMap<String, u32>) {
    match expr {
        SExpr::Symbol { text, .. } => {
            let (_, name) = split_mark(text);
            if !name.starts_with(':') && !name.starts_with('&') && name != "0" {
                *counts.entry(name.to_string()).or_insert(0) += 1;
            }
        }
        SExpr::List { items: list, .. } => {
            let start = usize::from(list.first().and_then(symbol).is_some_and(|text| text.starts_with(':') || (skip_columns && !text.starts_with('(') && !is_constraint(text))));
            for item in &list[start..] {
                count_labels(item, false, counts);
            }
        }
        SExpr::String { .. } => {}
    }
}

/// Each relation head that the atoms under `expr` read.
fn nested_heads(expr: &SExpr, out: &mut Vec<String>) {
    let Some(list) = items(expr) else { return };
    if let Some(name) = list.first().and_then(symbol) {
        if !name.starts_with(':') && !is_constraint(name) && !matches!(name, "NOT" | "OR" | "IF" | "ALL") {
            out.push(name.to_string());
            return;
        }
    }
    for item in list {
        nested_heads(item, out);
    }
}

/// One read of the state of a fragment's forms.
struct Reader<'a> {
    registry: &'static Registry,
    relations: BTreeMap<String, RelationInput>,
    rules: LookupMap<String, Facts>,
    instances: LookupMap<String, Instance>,
    _marker: std::marker::PhantomData<&'a ()>,
}

impl Reader<'_> {
    fn facts_of(&self, name: &str) -> Option<Facts> {
        if let Some(input) = self.relations.get(name) {
            return Some(input.facts(name));
        }
        if matches!(name, "input" | "output") {
            return Some(grid_facts(name));
        }
        if let Some(found) = self.rules.get(name) {
            return Some(found.clone());
        }
        if let Some((owner, port)) = name.split_once('.') {
            return self.port_facts(owner, port);
        }
        lib_facts(name).map(|found| (*found).clone())
    }

    /// The clause of `atoms`, with the head `head`: each column and the label at it.
    fn body(&self, atoms: &[SExpr], head_columns: &[(String, String)]) -> Facts {
        // Each label's place in the masks of the clause.
        let mut labels: Vec<String> = head_columns.iter().map(|(_, label)| label.clone()).collect();
        labels.dedup();
        let mut place = |name: &str, labels: &mut Vec<String>| -> usize {
            match labels.iter().position(|own| own == name) {
                Some(at) => at,
                None => {
                    labels.push(name.to_string());
                    labels.len() - 1
                }
            }
        };
        let mut fds: Vec<(u64, u64)> = Vec::new();
        let mut low: BTreeMap<String, i32> = BTreeMap::new();
        let mut high: BTreeMap<String, i32> = BTreeMap::new();
        let mut plain = true;
        let mut empty = false;
        let mut holds_on_domain = false;
        let mut deps: BTreeSet<String> = BTreeSet::new();
        let mut positive: Vec<(Facts, Vec<(usize, Value)>)> = Vec::new();
        let mut nested_reads: BTreeSet<String> = BTreeSet::new();
        let mut nested_deps: BTreeSet<String> = BTreeSet::new();
        for atom in atoms {
            let Some(name) = head(atom) else { continue };
            let list = items(atom).unwrap_or_default();
            match name {
                "NOT" | "OR" | "IF" | "ALL" => {
                    plain = false;
                    let mut heads = Vec::new();
                    nested_heads(atom, &mut heads);
                    for held in heads {
                        if let Some(facts) = self.facts_of(&held) {
                            nested_deps.extend(facts.deps.iter().cloned());
                            nested_reads.extend(facts.reads.iter().cloned());
                            if facts.alias {
                                let mut counts = BTreeMap::new();
                                count_labels(atom, false, &mut counts);
                                if let Some(like) = &facts.like {
                                    // A nested read of a base relation reads each column it labels.
                                    let at_columns: BTreeSet<&String> = like.at.iter().map(|(_, column)| column).collect();
                                    for column in at_columns {
                                        if like.base == "&r" {
                                            nested_reads.insert(column.clone());
                                        }
                                    }
                                }
                            }
                        }
                    }
                    if name == "ALL" {
                        // `(ALL (domain) (body))`: every row of the domain meets the body.
                        if let (Some(domain), Some(meets)) = (list.get(1).and_then(items), list.get(2).and_then(items)) {
                            holds_on_domain = holds_on_domain || self.all_holds(domain, meets);
                        }
                    }
                }
                constraint if is_constraint(constraint) => {
                    let a = list.get(1).and_then(symbol).map(|text| split_mark(text).1.to_string());
                    let b = list.get(2).and_then(symbol).map(|text| split_mark(text).1.to_string());
                    if let (Some(a), Some(b)) = (a, b) {
                        if b == "0" {
                            match constraint {
                                "=" => {
                                    low.insert(a.clone(), 0);
                                    high.insert(a.clone(), 0);
                                    let at = place(&a, &mut labels);
                                    fds.push((0, 1 << at));
                                }
                                ">" => {
                                    let held = low.entry(a).or_insert(1);
                                    *held = (*held).max(1);
                                    plain = false;
                                }
                                ">=" => {
                                    let held = low.entry(a).or_insert(0);
                                    *held = (*held).max(0);
                                    plain = false;
                                }
                                "<" => {
                                    let held = high.entry(a).or_insert(-1);
                                    *held = (*held).min(-1);
                                    plain = false;
                                }
                                "<=" => {
                                    let held = high.entry(a).or_insert(0);
                                    *held = (*held).min(0);
                                    plain = false;
                                }
                                _ => plain = false,
                            }
                            if constraint == "=" {
                                plain = false;
                            }
                        } else if constraint == "=" {
                            let (one, two) = (place(&a, &mut labels), place(&b, &mut labels));
                            fds.push((1 << one, 1 << two));
                            fds.push((1 << two, 1 << one));
                            plain = false;
                        } else {
                            plain = false;
                        }
                    }
                }
                relation => {
                    let Some(facts) = self.facts_of(relation) else {
                        plain = false;
                        continue;
                    };
                    let sites = atom_sites(&facts, &list[1..]);
                    let mut mask = 0u64;
                    for (_, value) in &sites {
                        if let Value::Label(label) = value {
                            mask |= 1 << place(label, &mut labels);
                        }
                    }
                    for key in &facts.keys {
                        let mut lhs = 0u64;
                        let mut known = true;
                        for column in 0..facts.columns.len() {
                            if key & bit(column as u16) != 0 && facts.constant & bit(column as u16) == 0 {
                                match sites.iter().find(|(at, _)| *at == column) {
                                    Some((_, Value::Label(label))) => lhs |= 1 << place(label, &mut labels),
                                    Some((_, Value::Zero)) => {}
                                    None => known = false,
                                }
                            }
                        }
                        if known {
                            fds.push((lhs, mask));
                        }
                    }
                    for (at, value) in &sites {
                        if let Value::Label(label) = value {
                            if facts.constant & bit(*at as u16) != 0 {
                                fds.push((0, 1 << place(label, &mut labels)));
                            }
                            if let Some(bound) = facts.low[*at] {
                                let held = low.entry(label.clone()).or_insert(bound);
                                *held = (*held).max(bound);
                            }
                            if let Some(bound) = facts.high[*at] {
                                let held = high.entry(label.clone()).or_insert(bound);
                                *held = (*held).min(bound);
                            }
                        } else if facts.low[*at].is_some_and(|low| low > 0) {
                            empty = true;
                        }
                    }
                    empty |= facts.empty;
                    deps.extend(facts.deps.iter().cloned());
                    positive.push((facts, sites));
                }
            }
        }
        // The relation's rows, against its first atom on a base relation.
        let driver = positive.iter().position(|(facts, sites)| facts.like.is_some() && !sites.iter().any(|(_, value)| matches!(value, Value::Zero)));
        let mut like: Option<Like> = None;
        let mut rowwise = None;
        if let Some(driver_at) = driver {
            let (facts, sites) = &positive[driver_at];
            let held = facts.like.as_ref().expect("the driver has rows");
            // Each label of the driver, with the base column under it.
            let mut read: BTreeMap<String, String> = BTreeMap::new();
            let mut covers_all = true;
            for (column, base_column) in &held.at {
                match sites.iter().find(|(at, _)| *at == usize::from(*column)) {
                    Some((_, Value::Label(label))) => {
                        read.insert(label.clone(), base_column.clone());
                    }
                    _ => covers_all = false,
                }
            }
            let mut bound: BTreeSet<String> = sites.iter().filter_map(|(_, value)| if let Value::Label(label) = value { Some(label.clone()) } else { None }).collect();
            let mut fan_out = if covers_all { held.fan_out } else { None };
            let mut rowwise_holds = facts.rowwise_on.as_deref() == Some(held.base.as_str());
            let base = held.base.clone();
            for (at, (other, other_sites)) in positive.iter().enumerate() {
                if at == driver_at {
                    continue;
                }
                if other.deps.contains(&base) && !(other.rowwise_on.as_deref() == Some(base.as_str())) {
                    rowwise_holds = false;
                }
                let labeled: Vec<(usize, &str)> = other_sites.iter().filter_map(|(column, value)| if let Value::Label(label) = value { Some((*column, label.as_str())) } else { None }).collect();
                let has_zero = other_sites.iter().any(|(_, value)| matches!(value, Value::Zero));
                let mut keeps_each_row = false;
                let mut other_fan_out = None;
                if !has_zero {
                    // A relation of one row that binds only labels of its own.
                    if other.nonempty && (labeled.is_empty() || (other.is_key(0) && labeled.iter().all(|(_, label)| !bound.contains(*label)))) {
                        keeps_each_row = true;
                        other_fan_out = Some(1);
                    }
                    // The same rows of the driver's base.
                    if let Some(other_like) = other.like.as_ref().filter(|other_like| other_like.base == base) {
                        let same = labeled.iter().all(|(column, label)| match other_like.at.iter().find(|(own, _)| usize::from(*own) == *column) {
                            Some((_, base_column)) => read.get(*label).is_some_and(|held| held == base_column),
                            None => !bound.contains(*label),
                        });
                        if same {
                            keeps_each_row = true;
                            let all_labeled = other.columns.iter().enumerate().all(|(column, _)| other.constant & bit(column as u16) != 0 || labeled.iter().any(|(own, _)| *own == column));
                            other_fan_out = if all_labeled { other_like.fan_out } else { None };
                        }
                    }
                    // A relation with a row for each value of the columns the clause has bound.
                    for each in &other.each {
                        let bound_lhs = (0..other.columns.len()).filter(|column| each.lhs & bit(*column as u16) != 0).all(|column| labeled.iter().any(|(own, label)| *own == column && bound.contains(*label)) || other.constant & bit(column as u16) != 0);
                        let rest_new = labeled.iter().all(|(column, label)| each.lhs & bit(*column as u16) != 0 || !bound.contains(*label));
                        if bound_lhs && rest_new {
                            keeps_each_row = true;
                            let all_labeled = (0..other.columns.len()).all(|column| labeled.iter().any(|(own, _)| *own == column) || other.constant & bit(column as u16) != 0);
                            other_fan_out = if all_labeled { each.fan_out } else { None };
                            break;
                        }
                    }
                    // A column that stands within this relation already.
                    if !keeps_each_row && labeled.iter().all(|(_, label)| bound.contains(*label)) {
                        let name = other.like.as_ref().map(|other_like| other_like.base.clone());
                        if let Some(name) = name {
                            let within = labeled.iter().all(|(column, label)| {
                                let other_column = other.columns[*column].clone();
                                facts.origin.iter().any(|origin| origin.source == name && origin.columns.iter().zip(&origin.at).any(|(own, target)| *target == other_column && sites.iter().any(|(site, value)| *site == usize::from(*own) && matches!(value, Value::Label(held) if held == *label))))
                            });
                            if within {
                                keeps_each_row = true;
                                other_fan_out = Some(1);
                            }
                        }
                    }
                }
                if !keeps_each_row {
                    plain = false;
                }
                fan_out = match (fan_out, other_fan_out) {
                    (Some(a), Some(b)) => Some(a * b),
                    _ => None,
                };
                for (_, label) in &labeled {
                    bound.insert((*label).to_string());
                }
            }
            if nested_deps.contains(&base) {
                rowwise_holds = false;
            }
            if plain {
                let at: Vec<(u16, String)> = head_columns.iter().enumerate().filter_map(|(column, (_, label))| read.get(label).map(|base_column| (column as u16, base_column.clone()))).collect();
                let head_labels: BTreeSet<&String> = head_columns.iter().map(|(_, label)| label).collect();
                let whole = bound.iter().all(|label| head_labels.contains(label));
                like = Some(Like { base: base.clone(), at, fan_out: if whole { fan_out } else { None } });
            }
            if rowwise_holds {
                rowwise = Some(base);
            }
        }
        // Keys, by closure over the head's labels.
        let closure = |start: u64| -> u64 {
            let mut held = start;
            loop {
                let before = held;
                for (lhs, rhs) in &fds {
                    if lhs & !held == 0 {
                        held |= rhs;
                    }
                }
                if held == before {
                    return held;
                }
            }
        };
        let head_places: Vec<u64> = head_columns.iter().map(|(_, label)| labels.iter().position(|own| own == label).map_or(0, |at| 1u64 << at)).collect();
        let head_mask = head_places.iter().fold(0, |held, one| held | one);
        let mut out = Facts::with_columns(head_columns.iter().map(|(column, _)| column.clone()).collect());
        let column_mask = |subset: u32| -> u64 { (0..head_places.len()).filter(|at| subset & (1 << at) != 0).fold(0, |held, at| held | head_places[at]) };
        let n = head_places.len().min(16);
        let mut sets: Vec<u32> = vec![0];
        for one in 0..n {
            sets.push(1 << one);
            for two in one + 1..n {
                sets.push(1 << one | 1 << two);
                for three in two + 1..n {
                    sets.push(1 << one | 1 << two | 1 << three);
                }
            }
        }
        for subset in sets {
            if closure(column_mask(subset)) & head_mask == head_mask {
                out.add_key(subset);
            }
        }
        // One least key by removing columns, for a key of many columns.
        if n > 0 {
            let mut greedy: u32 = if n >= 32 { u32::MAX } else { (1 << n) - 1 };
            for one in 0..n {
                let less = greedy & !(1 << one);
                if closure(column_mask(less)) & head_mask == head_mask {
                    greedy = less;
                }
            }
            out.add_key(greedy);
        }
        let constant_labels = closure(0);
        for (column, (_, label)) in head_columns.iter().enumerate() {
            if let Some(found) = low.get(label) {
                out.low[column] = Some(*found);
            }
            if let Some(found) = high.get(label) {
                out.high[column] = Some(*found);
            }
            if head_places[column] & constant_labels != 0 || (out.low[column].is_some() && out.low[column] == out.high[column]) {
                out.constant |= bit(column as u16);
            }
        }
        // What each head column stands within.
        for (facts, sites) in &positive {
            for origin in &facts.origin {
                let mut columns = Vec::new();
                let mut at = Vec::new();
                for (own, target) in origin.columns.iter().zip(&origin.at) {
                    if let Some((_, Value::Label(label))) = sites.iter().find(|(site, _)| *site == usize::from(*own)) {
                        for (column, (_, head_label)) in head_columns.iter().enumerate() {
                            if head_label == label && !columns.contains(&(column as u16)) {
                                columns.push(column as u16);
                                at.push(target.clone());
                            }
                        }
                    }
                }
                if !columns.is_empty() {
                    let found = Origin { columns, source: origin.source.clone(), at };
                    if !out.origin.contains(&found) {
                        out.origin.push(found);
                    }
                }
            }
        }
        // What the value depends on of `&r`.
        let mut counts: BTreeMap<String, u32> = BTreeMap::new();
        for atom in atoms {
            count_labels(atom, true, &mut counts);
        }
        for (_, label) in head_columns {
            *counts.entry(label.clone()).or_insert(0) += 2;
        }
        let used = |label: &str| counts.get(label).is_some_and(|count| *count >= 2);
        let mut reads = nested_reads;
        for (facts, sites) in &positive {
            if facts.alias {
                if let Some(held) = facts.like.as_ref().filter(|held| held.base == "&r") {
                    for (column, base_column) in &held.at {
                        if let Some((_, Value::Label(label))) = sites.iter().find(|(site, _)| *site == usize::from(*column)) {
                            if used(label) {
                                reads.insert(base_column.clone());
                            }
                        }
                    }
                }
            } else {
                reads.extend(facts.reads.iter().cloned());
            }
        }
        deps.extend(nested_deps);
        out.like = like;
        // A clause with a column that an instance computes from other columns reads those too.
        out.alias = plain && out.like.is_some() && positive.iter().all(|(facts, _)| facts.alias || facts.reads.is_empty());
        out.empty = empty;
        out.nonempty = positive.iter().all(|(facts, sites)| facts.nonempty && sites.iter().all(|(_, value)| matches!(value, Value::Label(_)))) && plain && !positive.is_empty();
        out.holds_on_domain = holds_on_domain;
        out.deps = deps;
        out.rowwise_on = rowwise;
        out.reads = reads;
        out
    }

    /// Whether each row of an `ALL` form's domain meets its body, by the body's relations.
    fn all_holds(&self, domain: &[SExpr], meets: &[SExpr]) -> bool {
        let Some(first) = domain.first() else { return false };
        let Some(facts) = head(first).and_then(|name| self.facts_of(name)) else { return false };
        let Some(base) = facts.like.as_ref().map(|like| like.base.clone()) else { return false };
        meets.iter().all(|atom| {
            let Some(name) = head(atom) else { return false };
            if matches!(name, "NOT" | "OR" | "IF" | "ALL") || is_constraint(name) {
                return false;
            }
            self.facts_of(name).is_some_and(|other| other.like.as_ref().is_some_and(|like| like.base == base))
        })
    }

    /// An `INIT` form's clauses.
    fn instance(&mut self, name: &str, component: &str, clauses: &[SExpr]) {
        let mut out = Instance { component: component.to_string(), key_fields: Vec::new(), key: None, inputs: LookupMap::new(), shapes: LookupMap::new() };
        let mut bound_inputs: Vec<&SExpr> = Vec::new();
        for clause in clauses {
            if head(clause) == Some("key") {
                let list = items(clause).unwrap_or_default();
                let body = list.get(1).and_then(items).unwrap_or_default();
                for atom in body {
                    key_labels(atom, &mut out.key_fields);
                }
                let columns: Vec<(String, String)> = out.key_fields.iter().map(|field| (format!("key.{field}"), field.clone())).collect();
                out.key = Some(self.body(body, &columns));
                bound_inputs.extend(list.iter().skip(2));
            } else {
                bound_inputs.push(clause);
            }
        }
        for clause in bound_inputs {
            let list = items(clause).unwrap_or_default();
            let Some(input) = list.first().and_then(symbol) else { continue };
            let sites = list.get(1).and_then(items).unwrap_or_default();
            let written_head = head_sites(sites);
            for (column, _) in &written_head {
                if let Some((param, field)) = column.split_once('.') {
                    let fields = out.shapes.entry(param.to_string()).or_default();
                    if !fields.iter().any(|held| held == field) {
                        fields.push(field.to_string());
                    }
                }
            }
            let mut columns: Vec<(String, String)> = out.key_fields.iter().map(|field| (format!("key.{field}"), field.clone())).collect();
            columns.extend(written_head);
            let facts = self.body(&list[2..], &columns);
            out.inputs.insert(input.to_string(), facts);
        }
        self.instances.insert(name.to_string(), out);
    }

    /// Whether each key of an instance has one row of the input.
    fn single(instance: &Instance, input: &str) -> bool {
        let Some(facts) = instance.inputs.get(input) else { return false };
        let key_mask = facts.columns.iter().enumerate().filter(|(_, column)| column.starts_with("key.")).fold(0, |held, (at, _)| held | bit(at as u16));
        facts.is_key(key_mask)
    }

    /// Whether each key of an instance has a row of the input.
    fn covered(instance: &Instance, input: &str) -> bool {
        let Some(facts) = instance.inputs.get(input) else { return false };
        let Some(input_like) = &facts.like else { return false };
        let Some(key) = &instance.key else { return facts.nonempty };
        let Some(key_like) = &key.like else { return false };
        if key_like.base != input_like.base {
            return false;
        }
        instance.key_fields.iter().all(|field| {
            let name = format!("key.{field}");
            let in_key = key.index(&name).and_then(|at| key_like.at.iter().find(|(own, _)| usize::from(*own) == at)).map(|(_, base)| base);
            match in_key {
                Some(base) => facts.index(&name).and_then(|at| input_like.at.iter().find(|(own, _)| usize::from(*own) == at)).is_some_and(|(_, other)| other == base),
                None => key.index(&name).is_some_and(|at| key.constant & bit(at as u16) != 0),
            }
        })
    }

    /// An output of an instance.
    fn port_facts(&self, owner: &str, port: &str) -> Option<Facts> {
        let instance = self.instances.get(owner)?;
        let Some(LibEntry::Component(component)) = self.registry.entry(&LibName(instance.component.as_str().into())) else { return None };
        let out_port = component.outputs.iter().find(|held| written_port(&held.name) == port)?;
        let mut columns: Vec<String> = Vec::new();
        for column in out_port.columns.iter() {
            if is_key(column) {
                columns.extend(instance.key_fields.iter().map(|field| format!("key.{field}")));
            } else {
                let name = written(&column.name);
                match instance.shapes.get(&name) {
                    Some(fields) => columns.extend(fields.iter().map(|field| format!("{name}.{field}"))),
                    None => columns.push(name),
                }
            }
        }
        let mut facts = Facts::with_columns(columns);
        for column in out_port.columns.iter() {
            if !is_key(column) {
                if let Some(at) = facts.index(&written(&column.name)) {
                    facts.low[at] = number_low(column_value_type(column).as_ref());
                }
            }
        }
        // A key's constant fields.
        if let Some(key) = &instance.key {
            for field in &instance.key_fields {
                let name = format!("key.{field}");
                if let (Some(at), Some(own)) = (facts.index(&name), key.index(&name)) {
                    if key.constant & bit(own as u16) != 0 {
                        facts.constant |= bit(at as u16);
                    }
                }
            }
        }
        for source in instance.inputs.sorted_values().into_iter().chain(instance.key.iter()) {
            facts.deps.extend(source.deps.iter().cloned());
            facts.reads.extend(source.reads.iter().cloned());
        }
        // What the rows copy.
        for row in out_port.copies.iter() {
            let [alternative] = &row.alternatives[..] else { continue };
            let input_port = &component.inputs[alternative.input].port;
            let Some(input) = instance.inputs.get(&written_port(&input_port.name)) else { continue };
            for origin in &input.origin {
                let mut own = Vec::new();
                let mut at = Vec::new();
                for (column, target) in origin.columns.iter().zip(&origin.at) {
                    let name = &input.columns[usize::from(*column)];
                    let mapped = if name.starts_with("key.") {
                        Some(name.clone())
                    } else {
                        let (param, field) = name.split_once('.').map_or((name.as_str(), None), |(param, field)| (param, Some(field)));
                        alternative.columns.iter().find(|(input_at, _)| written(&input_port.columns[*input_at].name) == param).map(|(_, output_at)| {
                            let output_name = written(&out_port.columns[*output_at].name);
                            field.map_or(output_name.clone(), |field| format!("{output_name}.{field}"))
                        })
                    };
                    if let Some(place) = mapped.and_then(|mapped| facts.index(&mapped)) {
                        own.push(place as u16);
                        at.push(target.clone());
                    }
                }
                if !own.is_empty() {
                    facts.origin.push(Origin { columns: own, source: origin.source.clone(), at });
                }
            }
        }
        let name = format!("{}.{port}", instance.component);
        apply_port_items(&mut facts, self.registry.refines(&name), instance, component);
        Some(facts)
    }
}

fn written_port(name: &arclog::program::PortName) -> String {
    name.0.to_string()
}

/// The mask of the columns of `facts` under the column names `names`, `key` for each key field.
fn port_mask(facts: &Facts, names: &[&str]) -> Mask {
    let mut mask = 0;
    for (at, column) in facts.columns.iter().enumerate() {
        let param = column.split_once('.').map_or(column.as_str(), |(param, _)| param);
        if names.contains(&param) {
            mask |= bit(at as u16);
        }
    }
    mask
}

/// `same-as`: the output's rows are the input's, over the columns of one name.
fn same_as(facts: &mut Facts, input: &Facts) {
    let place = |name: &str| facts.columns.iter().position(|own| own == name);
    let map: Vec<Option<usize>> = input.columns.iter().map(|column| place(column)).collect();
    let mut keys = Vec::new();
    for key in &input.keys {
        let mut mapped = Some(0);
        for column in 0..input.columns.len() {
            if key & bit(column as u16) != 0 {
                mapped = match (mapped, map[column]) {
                    (Some(held), Some(at)) => Some(held | bit(at as u16)),
                    _ => None,
                };
            }
        }
        if let Some(mapped) = mapped {
            keys.push(mapped);
        }
    }
    for key in keys {
        facts.add_key(key);
    }
    for (column, at) in map.iter().enumerate() {
        if let Some(at) = at {
            facts.low[*at] = input.low[column];
            facts.high[*at] = input.high[column];
            if input.constant & bit(column as u16) != 0 {
                facts.constant |= bit(*at as u16);
            }
        }
    }
    facts.origin = input.origin.iter().filter_map(|origin| {
        let mut own = Vec::new();
        let mut at = Vec::new();
        for (column, target) in origin.columns.iter().zip(&origin.at) {
            if let Some(place) = map[usize::from(*column)] {
                own.push(place as u16);
                at.push(target.clone());
            }
        }
        (!own.is_empty()).then(|| Origin { columns: own, source: origin.source.clone(), at })
    }).collect();
    facts.like = input.like.as_ref().map(|like| Like {
        base: like.base.clone(),
        at: like.at.iter().filter_map(|(column, base)| map[usize::from(*column)].map(|place| (place as u16, base.clone()))).collect(),
        fan_out: like.fan_out,
    });
    facts.alias = input.alias;
    facts.nonempty = input.nonempty;
    facts.reads.clone_from(&input.reads);
    facts.deps.clone_from(&input.deps);
    facts.rowwise_on.clone_from(&input.rowwise_on);
}

fn apply_claim(facts: &mut Facts, claim: &SExpr, instance: &Instance) {
    if symbol(claim) == Some("empty") {
        facts.empty = true;
        return;
    }
    let Some(list) = items(claim) else { return };
    let names: Vec<&str> = list.iter().skip(1).filter_map(symbol).collect();
    match list.first().and_then(symbol) {
        Some("at-least") | Some("at-most") => {
            let least = list.first().and_then(symbol) == Some("at-least");
            if let (Some(column), Some(Ok(value))) = (names.first().and_then(|column| facts.index(column)), names.get(1).map(|text| text.parse::<i32>())) {
                if least {
                    facts.low[column] = Some(facts.low[column].map_or(value, |held| held.max(value)));
                } else {
                    facts.high[column] = Some(facts.high[column].map_or(value, |held| held.min(value)));
                }
                if facts.low[column].is_some() && facts.low[column] == facts.high[column] {
                    facts.constant |= bit(column as u16);
                }
            }
        }
        Some("same-as") => {
            if let Some(input) = names.first().and_then(|input| instance.inputs.get(*input)) {
                let input = input.clone();
                same_as(facts, &input);
            }
        }
        _ => {}
    }
}

/// Applies the items of an output's `refines` form.
fn apply_port_items(facts: &mut Facts, refines: &[SExpr], instance: &Instance, component: &Component) {
    let _ = component;
    for item in refines {
        let Some(list) = items(item) else { continue };
        let names: Vec<&str> = list.iter().skip(1).filter_map(symbol).collect();
        match list.first().and_then(symbol) {
            Some("key") => {
                let mask = port_mask(facts, &names);
                facts.add_key(mask);
            }
            Some("at-least") => {
                if let (Some(column), Some(Ok(low))) = (names.first().and_then(|column| facts.index(column)), names.get(1).map(|text| text.parse::<i32>())) {
                    facts.low[column] = Some(low);
                }
            }
            // A row for each key.
            Some("each-key") => {
                if let Some(key) = &instance.key {
                    if let Some(like) = &key.like {
                        let at = like.at.iter().filter_map(|(column, base)| facts.index(&key.columns[usize::from(*column)]).map(|place| (place as u16, base.clone()))).collect();
                        facts.like = Some(Like { base: like.base.clone(), at, fan_out: Some(1) });
                    }
                    facts.nonempty = key.nonempty;
                }
            }
            // A row for each row of an input, over the named columns.
            Some("each-row") => {
                let Some(input) = names.first().and_then(|input| instance.inputs.get(*input)) else { continue };
                let Some(like) = &input.like else { continue };
                let wanted = port_mask(facts, &names[1..]);
                let at: Vec<(u16, String)> = like.at.iter().filter_map(|(column, base)| {
                    let name = &input.columns[usize::from(*column)];
                    facts.index(name).filter(|place| wanted & bit(*place as u16) != 0).map(|place| (place as u16, base.clone()))
                }).collect();
                let covers = (0..facts.columns.len()).filter(|place| wanted & bit(*place as u16) != 0 && facts.constant & bit(*place as u16) == 0).all(|place| at.iter().any(|(own, _)| usize::from(*own) == place));
                if covers && Reader::covered(instance, names[0]) {
                    facts.like = Some(Like { base: like.base.clone(), at, fan_out: Some(1) });
                }
            }
            Some("covered") => {
                if let (Some(input), Some(claim)) = (names.first(), list.get(2)) {
                    if Reader::covered(instance, input) {
                        apply_claim(facts, claim, instance);
                    }
                }
            }
            Some("single") => {
                if let (Some(input), Some(claim)) = (names.first(), list.get(2)) {
                    if Reader::single(instance, input) {
                        apply_claim(facts, claim, instance);
                    }
                }
            }
            Some("unbound") => {
                let inputs: Vec<&str> = list.get(1).and_then(items).unwrap_or_default().iter().filter_map(symbol).collect();
                if let Some(claim) = list.get(2) {
                    if inputs.iter().all(|input| !instance.inputs.contains_key(*input)) {
                        apply_claim(facts, claim, instance);
                    }
                }
            }
            Some("tied") => {
                let held = names.first().and_then(|input| instance.inputs.get(*input));
                if let (Some(held), Some(column), Some(claim)) = (held, names.get(1), list.get(3)) {
                    if held.index(column).is_some_and(|at| held.constant & bit(at as u16) != 0) {
                        apply_claim(facts, claim, instance);
                    }
                }
            }
            _ => {}
        }
    }
}

/// A call's forms, read once.
pub struct PartPlan {
    forms: Vec<SExpr>,
    export: String,
    /// The columns the call gives, by the names of its expansion.
    columns: Vec<String>,
    /// The names of its relation holes' columns, by hole.
    r_arity: usize,
    s_columns: Vec<String>,
    /// For each column of the native term, its place in `columns`.
    out: Vec<Option<usize>>,
    results: Mutex<LookupMap<(RelationInput, Option<RelationInput>), Arc<PartResult>>>,
    /// Whether the part reads only the columns its holes name: a column more changes nothing.
    pub reads_only_holes: bool,
}

/// What a part's fragment gives at a call.
#[derive(Clone, Debug, Default)]
pub struct PartResult {
    pub verdict: Option<crate::refine::Rejected>,
    pub refined: Refined,
    /// Each column it stands within: columns, source, the source's column names.
    pub within: Vec<(Vec<u16>, String, Vec<String>)>,
    /// Where each output row depends on one row of its relation, and the output holds every column of it.
    pub row_wise: bool,
    /// Whether every row of its relation stands in the output.
    pub total: bool,
    /// Whether the output has any column beside its relation's.
    pub adds_columns: bool,
}

struct PlanTables {
    r: Vec<String>,
    s: Vec<String>,
}

impl Tables for PlanTables {
    fn table(&self, name: &str) -> Option<TableSchema> {
        let columns = match name {
            "&r" => &self.r,
            "&s" => &self.s,
            _ => return None,
        };
        Some(TableSchema { columns: columns.iter().map(|column| TableColumn { name: column.clone(), path: vec![column.clone()], ty: None }).collect(), stored: None, per_input: true, has_example: false })
    }
}

fn parse_forms(texts: &[String]) -> Vec<SExpr> {
    read_sexprs(&texts.join("\n"), SourceFile::Arclog).map(|(forms, _)| forms).unwrap_or_default()
}

fn plan_of_text(call: &str, r_arity: usize, s_columns: &[String]) -> Option<(Vec<SExpr>, String, Vec<String>)> {
    let registry = Registry::get();
    let tables = PlanTables { r: (0..r_arity).map(|at| format!("C{at}")).collect(), s: s_columns.to_vec() };
    let library = crate::library::library();
    let reader = crate::expression::Reader { registry, library, program_relations: &crate::program_relations::is_program_relation };
    let rel = reader.rel_text(call).ok()?;
    let expanded = crate::expand::expand_rel(&rel, &tables, registry, false).ok()?;
    Some((parse_forms(&expanded.forms), expanded.export, expanded.columns))
}

/// The plan of the call `call` over a relation `&r` of the columns `C0..`, and a second relation
/// `&s` of the columns `s_columns`. `native` gives the term's columns: for each, the name it has in the
/// expansion where its relation gives it, and the name it has where it is a new column.
pub fn plan(call: &str, r_arity: usize, s_columns: &[String], native: &[(String, String)]) -> Option<Arc<PartPlan>> {
    static HELD: OnceLock<Mutex<LookupMap<String, Option<Arc<PartPlan>>>>> = OnceLock::new();
    let key = format!("{call}|{r_arity}|{s_columns:?}|{native:?}");
    let held = HELD.get_or_init(Default::default);
    if let Some(found) = held.lock().expect("no panic").get(&key) {
        return found.clone();
    }
    let built = plan_of_text(call, r_arity, s_columns).map(|(forms, export, columns)| {
        let out = native.iter().map(|(name, other)| columns.iter().position(|own| own == name).or_else(|| columns.iter().position(|own| own == other))).collect();
        let mut plan = PartPlan { forms, export, columns, r_arity, s_columns: s_columns.to_vec(), out, results: Mutex::new(LookupMap::new()), reads_only_holes: false };
        // A column more, that no hole names.
        if let Some((forms, export, _)) = plan_of_text(call, r_arity + 1, s_columns) {
            let wider = RelationInput { columns: (0..=r_arity).map(|at| format!("C{at}")).collect(), keys: vec![if r_arity + 1 >= 32 { Mask::MAX } else { (1 << (r_arity + 1)) - 1 }], low: vec![None; r_arity + 1], high: vec![None; r_arity + 1], within: Vec::new() };
            let facts = read_forms(&forms, &export, &wider, None, s_columns);
            plan.reads_only_holes = !facts.reads.contains(&format!("C{r_arity}")) && !facts.columns.iter().any(|column| *column == format!("C{r_arity}"));
        }
        Arc::new(plan)
    });
    let mut plans = held.lock().expect("no panic");
    // A long run meets many schemas, and this is a cache.
    if plans.len() >= 20_000 {
        plans.clear();
    }
    plans.insert(key, built.clone());
    built
}

fn read_forms(forms: &[SExpr], export: &str, r: &RelationInput, s: Option<&RelationInput>, s_columns: &[String]) -> Facts {
    let mut relations = BTreeMap::new();
    relations.insert("&r".to_string(), r.clone());
    let s_input = s.cloned().unwrap_or_else(|| {
        let arity = s_columns.len();
        let all = if arity >= 32 { Mask::MAX } else { (1u32 << arity).wrapping_sub(1) };
        RelationInput { columns: s_columns.to_vec(), keys: vec![all], low: vec![None; arity], high: vec![None; arity], within: Vec::new() }
    });
    relations.insert("&s".to_string(), s_input);
    let mut reader = Reader { registry: Registry::get(), relations, rules: LookupMap::new(), instances: LookupMap::new(), _marker: std::marker::PhantomData };
    for form in forms {
        let Some(list) = items(form) else { continue };
        match list.first().and_then(symbol) {
            Some("RULE" | "DET") => {
                let Some(name) = list.get(1).and_then(symbol) else { continue };
                let mut kept = Vec::new();
                for atom in &list[2..] {
                    crate::library::keep(atom, &mut kept);
                }
                let columns: Vec<(String, String)> = kept.into_iter().map(|label| (label.clone(), label)).collect();
                let facts = finite_clause(&list[2..], &columns, reader.registry).unwrap_or_else(|| reader.body(&list[2..], &columns));
                reader.rules.insert(name.to_string(), facts);
            }
            Some("INIT") => {
                let (Some(name), Some(component)) = (list.get(1).and_then(symbol), list.get(2).and_then(symbol)) else { continue };
                reader.instance(name, component, &list[3..]);
            }
            _ => {}
        }
    }
    reader.rules.remove(export).unwrap_or_default()
}

/// A clause that reads only lib relations over finite domains, by its rows.
fn finite_clause(atoms: &[SExpr], columns: &[(String, String)], registry: &'static Registry) -> Option<Facts> {
    let mut rows: Vec<BTreeMap<String, u32>> = vec![BTreeMap::new()];
    for atom in atoms {
        let list = items(atom)?;
        let name = list.first().and_then(symbol)?;
        if name.starts_with('&') || is_constraint(name) || matches!(name, "NOT" | "OR" | "IF" | "ALL" | "input" | "output" | "ex_input" | "ex_output") {
            return None;
        }
        let facts = lib_facts(name)?;
        let relation = registry.algebra_relation(&LibName(name.into()))?;
        if !relation.modes.is_empty() {
            return None;
        }
        let table = finite_rows(name, facts.columns.len(), registry)?;
        let sites = atom_sites(&facts, &list[1..]);
        let mut next = Vec::new();
        for row in &rows {
            'row: for own in &table {
                let mut extended = row.clone();
                for (column, value) in &sites {
                    let Value::Label(label) = value else { return None };
                    match extended.get(label) {
                        Some(held) if *held != own[*column] => continue 'row,
                        _ => {
                            extended.insert(label.clone(), own[*column]);
                        }
                    }
                }
                next.push(extended);
            }
        }
        rows = next;
    }
    let mut facts = Facts::with_columns(columns.iter().map(|(column, _)| column.clone()).collect());
    let mut distinct: Vec<Vec<u32>> = rows.iter().map(|row| columns.iter().map(|(_, label)| row.get(label).copied().unwrap_or(0)).collect()).collect();
    distinct.sort_unstable();
    distinct.dedup();
    facts.nonempty = !distinct.is_empty();
    if distinct.len() <= 1 {
        facts.keys = vec![0];
        facts.constant = if columns.is_empty() { 0 } else { (1 << columns.len()) - 1 };
    } else {
        facts.keys = vec![(1 << columns.len()) - 1];
    }
    Some(facts)
}

impl PartPlan {
    /// What the call gives where its relation holes hold `r` and `s`.
    pub fn result(&self, r: &RelationInput, s: Option<&RelationInput>) -> Arc<PartResult> {
        let key = (r.clone(), s.cloned());
        if let Some(found) = self.results.lock().expect("no panic").get(&key) {
            return found.clone();
        }
        let facts = read_forms(&self.forms, &self.export, r, s, &self.s_columns);
        let result = Arc::new(self.judge(&facts));
        let mut held = self.results.lock().expect("no panic");
        // A long run meets many relations, and this is a cache.
        if held.len() >= 256 {
            held.clear();
        }
        held.insert(key, result.clone());
        result
    }

    fn judge(&self, facts: &Facts) -> PartResult {
        use crate::refine::{Claim, Rejected};
        let arity = self.out.len();
        let mut out = PartResult { refined: Refined::with_arity(arity), ..PartResult::default() };
        // The native term's place of each of the expansion's columns.
        let place_of = |column: usize| -> Option<u16> { self.out.iter().position(|held| *held == Some(column)).map(|at| at as u16) };
        let name_place = |name: &str| -> Option<usize> { self.columns.iter().position(|own| own == name) };
        for key in &facts.keys {
            let mut mapped = Some(0);
            for (column, name) in facts.columns.iter().enumerate() {
                if key & bit(column as u16) != 0 {
                    mapped = match (mapped, name_place(name).and_then(place_of)) {
                        (Some(held), Some(at)) => Some(held | bit(at)),
                        _ => None,
                    };
                }
            }
            if let Some(mapped) = mapped {
                out.refined.add_key(mapped);
            }
        }
        out.refined.add_key(out.refined.all_columns());
        for (column, name) in facts.columns.iter().enumerate() {
            if let Some(at) = name_place(name).and_then(place_of) {
                out.refined.low[usize::from(at)] = facts.low[column];
                out.refined.high[usize::from(at)] = facts.high[column];
            }
        }
        for origin in &facts.origin {
            let mut columns = Vec::new();
            let mut at = Vec::new();
            for (column, target) in origin.columns.iter().zip(&origin.at) {
                if let Some(place) = name_place(&facts.columns[usize::from(*column)]).and_then(place_of) {
                    columns.push(place);
                    at.push(target.clone());
                }
            }
            if !columns.is_empty() {
                out.within.push((columns, origin.source.clone(), at));
            }
        }
        // How the output stands to its relation.
        let r_names: Vec<String> = (0..self.r_arity).map(|at| format!("C{at}")).collect();
        let own_columns = facts.columns.iter().filter(|column| r_names.contains(column)).count();
        let extra_constant = facts.columns.iter().enumerate().filter(|(_, column)| !r_names.contains(column)).all(|(at, _)| facts.constant & bit(at as u16) != 0);
        out.adds_columns = own_columns < facts.columns.len();
        let is_rowwise = facts.rowwise_on.as_deref() == Some("&r");
        let whole_relation = own_columns == self.r_arity && self.r_arity > 0;
        out.row_wise = is_rowwise && whole_relation;
        out.total = false;
        if facts.empty {
            out.verdict = Some(Rejected { rule: "part-empty", claim: Claim::Empty });
            return out;
        }
        if facts.holds_on_domain && facts.columns.is_empty() {
            out.verdict = Some(Rejected { rule: "part-holds-on-domain", claim: Claim::Follows });
            return out;
        }
        if let Some(like) = facts.like.as_ref().filter(|like| like.base == "&r") {
            let at_all = facts.columns.iter().enumerate().all(|(at, column)| !r_names.contains(column) || like.at.iter().any(|(own, base)| usize::from(*own) == at && base == column));
            out.total = like.fan_out.is_some();
            if at_all && extra_constant && like.fan_out == Some(1) {
                out.verdict = Some(if whole_relation {
                    Rejected { rule: "part-no-op", claim: Claim::SameRows }
                } else {
                    Rejected { rule: "part-is-project", claim: Claim::Follows }
                });
                return out;
            }
            if at_all && like.fan_out.is_some() {
                out.refined.count_follows = true;
            }
            // Over no row of a relation but what a `project` of it gives, the count is the `project`'s.
            if like.fan_out == Some(1) {
                out.refined.count_follows = true;
            }
        }
        out
    }
}

/// The refinements of a part with no hole: what its call gives over no table.
pub fn base_part(call: &str, native: &[(String, String)]) -> Option<PartResult> {
    let found = plan(call, 0, &[], native)?;
    let r = RelationInput::default();
    Some((*found.result(&r, None)).clone())
}

/// The refinements of a lib relation as a leaf of a family, by its columns.
pub fn lib_leaf(name: &str, columns: &[String]) -> Option<Refined> {
    let facts = lib_facts(name)?;
    let mut out = Refined::with_arity(columns.len());
    let place = |column: usize| columns.iter().position(|own| *own == facts.columns[column]).map(|at| at as u16);
    for key in &facts.keys {
        let mapped = (0..facts.columns.len()).filter(|column| key & bit(*column as u16) != 0).try_fold(0, |held, column| place(column).map(|at| held | bit(at)));
        if let Some(mapped) = mapped {
            out.add_key(mapped);
        }
    }
    out.add_key(out.all_columns());
    for each in &facts.each {
        for column in 0..facts.columns.len() {
            if each.lhs == bit(column as u16) {
                if let Some(at) = place(column) {
                    out.complete |= bit(at);
                }
            }
        }
    }
    Some(out)
}

/// The fixed names a base relation's own hole cannot give.
pub fn grid_refined(name: &str) -> Refined {
    let facts = grid_facts(name);
    let mut out = Refined::with_arity(2);
    out.keys = facts.keys;
    out
}

/// What the reader finds of a call over a relation of `arity` columns with one key, as text, for a reader of a rule.
pub fn explain(call: &str, arity: usize, key: Mask) -> String {
    let Some((forms, export, columns)) = plan_of_text(call, arity, &[]) else { return format!("no expansion of {call}") };
    let r = RelationInput { columns: (0..arity).map(|at| format!("C{at}")).collect(), keys: vec![key], low: vec![None; arity], high: vec![None; arity], within: Vec::new() };
    let mut relations = BTreeMap::new();
    relations.insert("&r".to_string(), r);
    let mut reader = Reader { registry: Registry::get(), relations, rules: LookupMap::new(), instances: LookupMap::new(), _marker: std::marker::PhantomData };
    let mut out = String::new();
    for form in &forms {
        out.push_str(&format!("{}\n", form_text(form)));
        let Some(list) = items(form) else { continue };
        match list.first().and_then(symbol) {
            Some("RULE" | "DET") => {
                let Some(name) = list.get(1).and_then(symbol) else { continue };
                let mut kept = Vec::new();
                for atom in &list[2..] {
                    crate::library::keep(atom, &mut kept);
                }
                let held: Vec<(String, String)> = kept.into_iter().map(|label| (label.clone(), label)).collect();
                let facts = finite_clause(&list[2..], &held, reader.registry).unwrap_or_else(|| reader.body(&list[2..], &held));
                out.push_str(&format!("  = {facts:?}\n"));
                reader.rules.insert(name.to_string(), facts);
            }
            Some("INIT") => {
                let (Some(name), Some(component)) = (list.get(1).and_then(symbol), list.get(2).and_then(symbol)) else { continue };
                reader.instance(name, component, &list[3..]);
                if let Some(instance) = reader.instances.get(name) {
                    out.push_str(&format!("  key {:?}\n", instance.key));
                    for (input, facts) in instance.inputs.sorted_entries() {
                        out.push_str(&format!("  input {input} {facts:?}\n"));
                    }
                }
            }
            _ => {}
        }
    }
    out.push_str(&format!("gives {export} {columns:?}\n"));
    out
}

fn form_text(form: &SExpr) -> String {
    match form {
        SExpr::Symbol { text, .. } => text.to_string(),
        SExpr::String { text, .. } => format!("{text:?}"),
        SExpr::List { items, .. } => format!("({})", items.iter().map(form_text).collect::<Vec<_>>().join(" ")),
    }
}
