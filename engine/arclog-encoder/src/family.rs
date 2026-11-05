//! The relational shapes that read a table and `output`, up to size 2, computed in
//! one pass per table: a plain function of a table's types and rows and the task's
//! grids. A shape's terms are `project`, `select`, `join`, `antijoin` and `union`,
//! with the grids `input` and `output` as the other leaves. It enumerates what the
//! grammar writes on the types alone, so it reads no checker. It leaves out what
//! repeats a term: a `join` in its other order, and a table joined with itself. A
//! `project` reads at most `MAX_PROJECTED` columns, and a `union` stands at size 1.

use std::collections::HashSet;
use std::sync::{Arc, Mutex};

use arclog::decode::corpus::corpus_session;
use arclog::types::ValueType;

use crate::expression::Op;
use crate::native::{hash_words, CompInstance, CompShape, Evaluator, FastMap, LibRelation, Step, Table, Val};
use crate::tablewalk::{active_entry, shape_text, stored_of, Entry2, ShapeMap, StableRule, Stored};

const READS_INPUT: u8 = 1;
const READS_OUTPUT: u8 = 2;
const READS_TABLE: u8 = 4;
const REQUIRED: u8 = READS_TABLE | READS_OUTPUT;
const NO_TERM: u32 = u32::MAX;
/// The most columns of a `project` in the family.
const MAX_PROJECTED: u32 = 3;
const PAYLOAD: u64 = (1 << 62) - 1;

/// A term: its step over its children, its text, its columns, and the hash of each
/// of its roots where it is a root.
struct Term {
    step: Option<Step>,
    a: u32,
    b: u32,
    text: String,
    names: Vec<String>,
    types: Vec<ValueType>,
    flags: u8,
    size: u8,
    invariant: Vec<u16>,
    roots: Vec<u128>,
}

/// The terms over a table of one schema: the leaves, then size 1, then size 2.
pub struct Family {
    terms: Vec<Term>,
}

fn unique(name: &str, taken: &mut Vec<String>) -> String {
    let mut held = name.to_string();
    let mut suffix = 2;
    while taken.contains(&held) {
        held = format!("{name}_{suffix}");
        suffix += 1;
    }
    taken.push(held.clone());
    held
}

fn is_number(ty: &ValueType) -> bool {
    matches!(ty, ValueType::Int | ValueType::Nat)
}

/// The pair sets of a binary operator: each right column pairs with at most one
/// left column whose type it can meet.
fn pair_sets(left: &[ValueType], right: &[ValueType]) -> Vec<Vec<(u16, u16)>> {
    let mut sets: Vec<Vec<(u16, u16)>> = vec![Vec::new()];
    for (r, right_ty) in right.iter().enumerate() {
        let mut next = Vec::new();
        for set in &sets {
            next.push(set.clone());
            for (l, left_ty) in left.iter().enumerate() {
                if left_ty.meets(right_ty) {
                    let mut with = set.clone();
                    with.push((l as u16, r as u16));
                    next.push(with);
                }
            }
        }
        sets = next;
    }
    sets
}

/// Each way that a `union`'s pairs name every column of both relations: each left
/// column pairs with a right column, or with `0` where its type has one.
fn matchings(left: &[ValueType], right: &[ValueType]) -> Vec<Vec<Option<u16>>> {
    fn walk(left: &[ValueType], right: &[ValueType], at: usize, used: &mut Vec<bool>, held: &mut Vec<Option<u16>>, out: &mut Vec<Vec<Option<u16>>>) {
        if at == left.len() {
            if used.iter().all(|used| *used) {
                out.push(held.clone());
            }
            return;
        }
        for (other, ty) in right.iter().enumerate() {
            if used[other] || !left[at].meets(ty) {
                continue;
            }
            used[other] = true;
            held.push(Some(other as u16));
            walk(left, right, at + 1, used, held, out);
            held.pop();
            used[other] = false;
        }
        if left[at].has_zero() {
            held.push(None);
            walk(left, right, at + 1, used, held, out);
            held.pop();
        }
    }
    let mut out = Vec::new();
    walk(left, right, 0, &mut vec![false; right.len()], &mut Vec::new(), &mut out);
    out
}

impl Family {
    /// The family over a table of the column types `types`.
    pub fn of(types: &[ValueType], d: usize, names: &Mutex<FastMap<u128, String>>) -> Family {
        let mut family = Family { terms: Vec::new() };
        let t_names: Vec<String> = (0..types.len()).map(|at| format!("T{at}")).collect();
        family.leaf("T", t_names, types.to_vec(), READS_TABLE);
        let grid_types = vec![ValueType::Position, ValueType::Color];
        let grid_names = vec!["P".to_string(), "Col".to_string()];
        family.leaf("output", grid_names.clone(), grid_types.clone(), READS_OUTPUT);
        family.leaf("input", grid_names, grid_types, READS_INPUT);
        // Size 1. A `join` gives the same rows in either order, so the table or the
        // output stands on its left alone; so does a `union` of two equal arities.
        let same_arity = types.len() == 2;
        family.binary(0, 1, 1, true, true);
        family.binary(1, 0, 1, false, !same_arity);
        family.binary(0, 2, 1, true, false);
        family.binary(2, 0, 1, false, false);
        family.binary(1, 2, 1, true, false);
        family.binary(2, 1, 1, false, false);
        family.unary(0, 1);
        family.unary(1, 1);
        if d >= 2 {
            let small: Vec<u32> = (3..family.terms.len() as u32).collect();
            for at in &small {
                match family.terms[*at as usize].flags & REQUIRED {
                    REQUIRED => {
                        family.unary(*at, 2);
                        family.binary(*at, 2, 2, true, false);
                        family.binary(2, *at, 2, false, false);
                    }
                    READS_TABLE => {
                        family.binary(*at, 1, 2, true, false);
                        family.binary(1, *at, 2, false, false);
                    }
                    READS_OUTPUT => {
                        family.binary(0, *at, 2, true, false);
                        family.binary(*at, 0, 2, false, false);
                    }
                    _ => {}
                }
            }
        }
        // The hash of each root, and its name.
        let invariant_type = |ty: &ValueType| matches!(ty, ValueType::Int | ValueType::Nat | ValueType::Unit | ValueType::LibName);
        for term in &mut family.terms {
            term.invariant = term.types.iter().enumerate().filter(|(_, ty)| invariant_type(ty)).map(|(at, _)| at as u16).take(12).collect();
            if term.flags & REQUIRED != REQUIRED {
                continue;
            }
            let mut texts = vec![format!("(nonempty {})", term.text), format!("(cardinality {})", term.text)];
            for mask in 1u32..(1 << term.invariant.len()) {
                let columns: Vec<&str> = term.invariant.iter().enumerate().filter(|(at, _)| mask & (1 << at) != 0).map(|(_, at)| term.names[usize::from(*at)].as_str()).collect();
                texts.push(format!("(value-set {} {})", term.text, columns.join(" ")));
            }
            let mut held = names.lock().expect("no panic");
            term.roots = texts.iter().map(|text| {
                let shape = shape_text(text, "T", types);
                let hash = hash_words(shape.bytes().map(u64::from));
                held.entry(hash).or_insert(shape);
                hash
            }).collect();
        }
        family
    }

    fn leaf(&mut self, text: &str, names: Vec<String>, types: Vec<ValueType>, flags: u8) {
        self.terms.push(Term { step: None, a: NO_TERM, b: NO_TERM, text: text.to_string(), names, types, flags, size: 0, invariant: Vec::new(), roots: Vec::new() });
    }

    /// The terms of `project` and `select` over the term at `at`.
    fn unary(&mut self, at: u32, size: u8) {
        let (names, types, text, flags) = {
            let term = &self.terms[at as usize];
            (term.names.clone(), term.types.clone(), term.text.clone(), term.flags)
        };
        let count = names.len();
        if count <= 14 {
            for mask in 1u32..(1 << count) - 1 {
                // A count of distinct rows reads few columns.
                if mask.count_ones() > MAX_PROJECTED {
                    continue;
                }
                let places: Vec<u16> = (0..count as u16).filter(|place| mask & (1 << place) != 0).collect();
                let columns: Vec<&str> = places.iter().map(|place| names[usize::from(*place)].as_str()).collect();
                self.terms.push(Term {
                    step: Some(Step::Project { columns: places.iter().copied().collect() }),
                    a: at,
                    b: NO_TERM,
                    text: format!("(project {text} {})", columns.join(" ")),
                    names: places.iter().map(|place| names[usize::from(*place)].clone()).collect(),
                    types: places.iter().map(|place| types[usize::from(*place)].clone()).collect(),
                    flags,
                    size,
                    invariant: Vec::new(),
                    roots: Vec::new(),
                });
            }
        }
        let without = |dropped: Option<usize>| -> (Vec<String>, Vec<ValueType>) {
            (
                names.iter().enumerate().filter(|(place, _)| Some(*place) != dropped).map(|(_, name)| name.clone()).collect(),
                types.iter().enumerate().filter(|(place, _)| Some(*place) != dropped).map(|(_, ty)| ty.clone()).collect(),
            )
        };
        let mut pushes: Vec<Term> = Vec::new();
        for a in 0..count {
            for b in a + 1..count {
                if !types[a].meets(&types[b]) {
                    continue;
                }
                for op in Op::ALL {
                    if matches!(op, Op::Eq | Op::Ne) || (is_number(&types[a]) && is_number(&types[b])) {
                        let dropped = (op == Op::Eq).then_some(b);
                        let (kept_names, kept_types) = without(dropped);
                        pushes.push(Term {
                            step: Some(Step::Select { at: a as u16, op, other: Some(b as u16), drop: dropped.map(|at| at as u16) }),
                            a: at,
                            b: NO_TERM,
                            text: format!("(select {text} {} {} {})", names[a], op.text(), names[b]),
                            names: kept_names,
                            types: kept_types,
                            flags,
                            size,
                            invariant: Vec::new(),
                            roots: Vec::new(),
                        });
                    }
                }
            }
            if types[a].has_zero() {
                for op in Op::ALL {
                    if matches!(op, Op::Eq | Op::Ne) || is_number(&types[a]) {
                        let dropped = (op == Op::Eq).then_some(a);
                        let (kept_names, kept_types) = without(dropped);
                        pushes.push(Term {
                            step: Some(Step::Select { at: a as u16, op, other: None, drop: dropped.map(|at| at as u16) }),
                            a: at,
                            b: NO_TERM,
                            text: format!("(select {text} {} {} 0)", names[a], op.text()),
                            names: kept_names,
                            types: kept_types,
                            flags,
                            size,
                            invariant: Vec::new(),
                            roots: Vec::new(),
                        });
                    }
                }
            }
        }
        self.terms.extend(pushes);
    }

    /// The terms of `antijoin` with `l` on the left, and of `join` and `union` where
    /// the caller asks for them.
    fn binary(&mut self, l: u32, r: u32, size: u8, joins: bool, unions: bool) {
        let (left, right) = (&self.terms[l as usize], &self.terms[r as usize]);
        let flags = left.flags | right.flags;
        let left_arity = left.types.len() as u16;
        let mut pushes: Vec<Term> = Vec::new();
        for pairs in pair_sets(&left.types, &right.types) {
            let pair_text: Vec<String> = pairs.iter().map(|(a, b)| format!("({} {})", left.names[usize::from(*a)], right.names[usize::from(*b)])).collect();
            let pair_text = if pair_text.is_empty() { String::new() } else { format!(" {}", pair_text.join(" ")) };
            let left_at: Box<[u16]> = pairs.iter().map(|(a, _)| *a).collect();
            let right_at: Box<[u16]> = pairs.iter().map(|(_, b)| *b).collect();
            let kept: Box<[u16]> = (0..right.types.len() as u16).filter(|at| !right_at.contains(at)).collect();
            let mut taken = left.names.clone();
            let mut names = left.names.clone();
            let mut types = left.types.clone();
            for at in kept.iter() {
                names.push(unique(&right.names[usize::from(*at)], &mut taken));
                types.push(right.types[usize::from(*at)].clone());
            }
            if joins {
            pushes.push(Term {
                step: Some(Step::Join { left: left_at.clone(), right: right_at.clone(), kept, left_arity }),
                a: l,
                b: r,
                text: format!("(join {} {}{pair_text})", left.text, right.text),
                names,
                types,
                flags,
                size,
                invariant: Vec::new(),
                roots: Vec::new(),
            });
            }
            pushes.push(Term {
                step: Some(Step::Antijoin { left: left_at, right: right_at }),
                a: l,
                b: r,
                text: format!("(antijoin {} {}{pair_text})", left.text, right.text),
                names: left.names.clone(),
                types: left.types.clone(),
                flags,
                size,
                invariant: Vec::new(),
                roots: Vec::new(),
            });
        }
        if unions && !left.types.is_empty() && left.types.len() >= right.types.len() {
            for map in matchings(&left.types, &right.types) {
                let pair_text: Vec<String> = map.iter().enumerate().map(|(at, other)| format!("({} {})", left.names[at], other.map_or("0", |other| right.names[usize::from(other)].as_str()))).collect();
                pushes.push(Term {
                    step: Some(Step::Union { map: map.into_boxed_slice() }),
                    a: l,
                    b: r,
                    text: format!("(union {} {} {})", left.text, right.text, pair_text.join(" ")),
                    names: left.names.clone(),
                    types: left.types.clone(),
                    flags,
                    size,
                    invariant: Vec::new(),
                    roots: Vec::new(),
                });
            }
        }
        self.terms.extend(pushes);
    }
}

/// What one schema's walk holds on one task.
struct Eval<'a> {
    family: &'a Family,
    eval: Evaluator<'a>,
    values: Vec<Val>,
    value_index: FastMap<u128, u32>,
    memo: FastMap<(u32, u32, u32), u32>,
    top_memo: FastMap<(u32, u32, u32), u32>,
    arena: Vec<u64>,
}

static NO_SHAPES: [CompShape; 0] = [];
static NO_INSTANCES: [CompInstance; 0] = [];
static NO_LIBS: [LibRelation; 0] = [];

impl<'a> Eval<'a> {
    fn new(family: &'a Family) -> Self {
        Eval { family, eval: Evaluator::new(&NO_SHAPES, &NO_INSTANCES, &NO_LIBS, corpus_session()), values: vec![Val::None, Val::Empty], value_index: FastMap::default(), memo: FastMap::default(), top_memo: FastMap::default(), arena: Vec::new() }
    }

    fn value_id(&mut self, value: Val) -> u32 {
        match value {
            Val::None => 0,
            Val::Empty => 1,
            Val::Rows(_) => {
                let hash = value.hash();
                if let Some(found) = self.value_index.get(&hash) {
                    return *found;
                }
                let at = self.values.len() as u32;
                self.values.push(value);
                self.value_index.insert(hash, at);
                at
            }
        }
    }

    fn apply(&mut self, step: &Step, a: u32, b: u32) -> Val {
        let first = self.values[a as usize].clone();
        if b == NO_TERM {
            self.eval.apply(step, &[&first])
        } else {
            let second = self.values[b as usize].clone();
            self.eval.apply(step, &[&first, &second])
        }
    }

    /// The words of a term's value on the values `a` and `b`: a count where the term
    /// has only the two roots that count.
    fn word_offset(&mut self, at: u32, a: u32, b: u32) -> u32 {
        let key = (at, a, b);
        if let Some(found) = self.top_memo.get(&key) {
            return *found;
        }
        let family = self.family;
        let term = &family.terms[at as usize];
        let step = term.step.as_ref().expect("a term of size 1 or 2 has a step");
        let offset = self.arena.len() as u32;
        let counted = if term.roots.len() == 2 {
            let first = self.values[a as usize].clone();
            if b == NO_TERM {
                self.eval.count(step, &[&first])
            } else {
                let second = self.values[b as usize].clone();
                self.eval.count(step, &[&first, &second])
            }
        } else {
            None
        };
        match counted {
            Some(Some(rows)) => {
                self.arena.push(crate::native::WORD_NONEMPTY | u64::from(rows > 0));
                self.arena.push(crate::native::WORD_COUNT | rows.min(PAYLOAD));
            }
            Some(None) => self.arena.extend_from_slice(&[0, 0]),
            None => {
                let value = self.apply(step, a, b);
                self.eval.words(&value, &term.invariant, &[], &mut self.arena);
            }
        }
        self.top_memo.insert(key, offset);
        offset
    }

    fn accumulate(&self, map: &mut ShapeMap, term: &Term, offsets: &[u32], allow: Option<&HashSet<u128>>) {
        for (root, hash) in term.roots.iter().enumerate() {
            if allow.is_some_and(|allow| !allow.contains(hash)) {
                continue;
            }
            let words = offsets.iter().map(|offset| self.arena[*offset as usize + root]);
            if !words.clone().any(|word| word == 0 || word & PAYLOAD != 0) {
                continue;
            }
            let entry = map.entry(*hash).or_insert(Entry2 { sums: [0; 12], none: 0, size: term.size });
            for (pair, word) in words.enumerate().take(12) {
                if word == 0 {
                    entry.none |= 1 << pair;
                } else if word & PAYLOAD != 0 {
                    entry.sums[pair] = entry.sums[pair].wrapping_add(crate::tablewalk::mix_word(word));
                }
            }
        }
    }

    /// The sparse map from a root's shape to its value, on one table.
    fn walk(&mut self, rows: &[Option<Arc<Table>>], inputs: &[Arc<Table>], outputs: &[Arc<Table>], allow: Option<&HashSet<u128>>) -> ShapeMap {
        let family = self.family;
        let pairs = rows.len();
        let mut values: Vec<Vec<u32>> = Vec::with_capacity(family.terms.len());
        let leaves = [
            rows.iter().map(|table| table.clone().map_or(Val::None, Val::of_table)).collect::<Vec<_>>(),
            outputs.iter().map(|table| Val::of_table(table.clone())).collect(),
            inputs.iter().map(|table| Val::of_table(table.clone())).collect(),
        ];
        for leaf in leaves {
            let ids: Vec<u32> = leaf.into_iter().map(|value| self.value_id(value)).collect();
            values.push(ids);
        }
        let mut map: ShapeMap = FastMap::default();
        let empty = vec![1u32; pairs];
        for (at, term) in family.terms.iter().enumerate().skip(3) {
            let at = at as u32;
            let first = values[term.a as usize].clone();
            let second = (term.b != NO_TERM).then(|| values[term.b as usize].clone());
            let step = term.step.as_ref().expect("a term of size 1 or 2 has a step");
            let root = term.flags & REQUIRED == REQUIRED;
            // A term of size 2 is only a root: nothing extends it.
            if term.size < 2 {
                let mut ids = Vec::with_capacity(pairs);
                for pair in 0..pairs {
                    let b = second.as_ref().map_or(NO_TERM, |second| second[pair]);
                    let key = (at, first[pair], b);
                    let id = match self.memo.get(&key) {
                        Some(found) => *found,
                        None => {
                            let value = self.apply(step, first[pair], b);
                            let id = self.value_id(value);
                            self.memo.insert(key, id);
                            id
                        }
                    };
                    ids.push(id);
                }
                values.push(ids);
            } else {
                values.push(Vec::new());
            }
            if !root {
                continue;
            }
            if allow.is_some_and(|allow| !term.roots.iter().any(|hash| allow.contains(hash))) {
                continue;
            }
            // An operator that is empty on an empty relation is at its default.
            if step.empty_on_empty() && first == empty {
                continue;
            }
            if matches!(step, Step::Join { .. }) && second.as_ref() == Some(&empty) {
                continue;
            }
            let offsets: Vec<u32> = (0..pairs).map(|pair| {
                let b = second.as_ref().map_or(NO_TERM, |second| second[pair]);
                self.word_offset(at, first[pair], b)
            }).collect();
            self.accumulate(&mut map, term, &offsets, allow);
        }
        map
    }
}

/// How a shape stood on an item's tables: gold's stable and not the mutant's, the
/// reverse, and the comparisons it was contingent in; the same under the null.
#[derive(Default, Clone, Copy)]
pub struct Tally {
    pub gold_only: u32,
    pub mutant_only: u32,
    pub compared: u32,
    pub null_gold_only: u32,
    pub null_mutant_only: u32,
    pub null_compared: u32,
}

/// The families of each schema, built once, and the name of each root.
#[derive(Default)]
pub struct Families {
    held: Mutex<FastMap<u128, Arc<Family>>>,
    pub names: Mutex<FastMap<u128, String>>,
}

impl Families {
    fn get(&self, stored: &Stored, d: usize) -> Arc<Family> {
        let hash = hash_words(stored.key.bytes().map(u64::from));
        if let Some(found) = self.held.lock().expect("no panic").get(&hash) {
            return found.clone();
        }
        let family = Arc::new(Family::of(&stored.types, d, &self.names));
        self.held.lock().expect("no panic").insert(hash, family.clone());
        family
    }
}

fn auc_of(scores: &[(usize, f64, Vec<f64>)]) -> Option<f64> {
    let mut sum = 0.0;
    let mut count = 0usize;
    for (_, gold, mutants) in scores {
        for mutant in mutants {
            sum += if gold > mutant { 1.0 } else if gold == mutant { 0.5 } else { 0.0 };
            count += 1;
        }
    }
    (count > 0).then(|| sum / count as f64)
}

fn holds(rule: StableRule, map: &ShapeMap, rows_everywhere: bool, name: &u128, pairs: usize) -> bool {
    let entry = map.get(name);
    match rule {
        StableRule::Active => active_entry(entry, pairs),
        StableRule::NonVacuous => {
            rows_everywhere
                && match entry {
                    None => true,
                    Some(entry) => entry.none == 0 && entry.sums[..pairs].iter().all(|sum| *sum == entry.sums[0]),
                }
        }
    }
}

type Held<'m> = (&'m ShapeMap, bool);

/// An item's scores at size `d`, with each comparison added to `tallies` where given.
#[allow(clippy::too_many_arguments)]
fn scores(rule: StableRule, bases: &[Held<'_>], gold: Held<'_>, mutants: &[Held<'_>], pairs: usize, d: u8, tallies: Option<(&mut FastMap<u128, Tally>, bool)>) -> (usize, f64, Vec<f64>, usize) {
    let every: Vec<Held<'_>> = bases.iter().copied().chain(std::iter::once(gold)).chain(mutants.iter().copied()).collect();
    let mut names: FastMap<u128, ()> = FastMap::default();
    for (map, _) in &every {
        for (name, entry) in map.iter() {
            if entry.size <= d && !names.contains_key(name) && !bases.iter().all(|(base, rows)| holds(rule, base, *rows, name, pairs)) {
                names.insert(*name, ());
            }
        }
    }
    if let Some((tallies, null)) = tallies {
        for name in names.keys() {
            let on_gold = holds(rule, gold.0, gold.1, name, pairs);
            let tally = tallies.entry(*name).or_default();
            for (map, rows) in mutants {
                let on_mutant = holds(rule, map, *rows, name, pairs);
                let (only_gold, only_mutant) = (on_gold && !on_mutant, on_mutant && !on_gold);
                if null {
                    tally.null_compared += 1;
                    tally.null_gold_only += u32::from(only_gold);
                    tally.null_mutant_only += u32::from(only_mutant);
                } else {
                    tally.compared += 1;
                    tally.gold_only += u32::from(only_gold);
                    tally.mutant_only += u32::from(only_mutant);
                }
            }
        }
    }
    let mut classes: FastMap<u128, u128> = FastMap::default();
    for name in names.keys() {
        let mut words: Vec<u64> = Vec::with_capacity(every.len() * (pairs + 2));
        for (map, rows) in &every {
            match map.get(name) {
                Some(entry) => {
                    words.extend_from_slice(&entry.sums[..pairs]);
                    words.push(u64::from(entry.none));
                }
                None => words.extend(std::iter::repeat_n(0, pairs + 1)),
            }
            words.push(u64::from(*rows));
        }
        classes.entry(hash_words(words)).or_insert(*name);
    }
    let contingent: Vec<u128> = classes.values().copied().collect();
    if contingent.is_empty() {
        return (0, 0.0, vec![0.0; mutants.len()], names.len());
    }
    let score = |held: Held<'_>| contingent.iter().filter(|name| holds(rule, held.0, held.1, name, pairs)).count() as f64 / contingent.len() as f64;
    (contingent.len(), score(gold), mutants.iter().map(|held| score(*held)).collect(), names.len())
}

/// A task's result: per size, the family's AUC and null, each shape's tally, and the
/// seconds per table of its one pass over the family.
#[allow(clippy::too_many_arguments)]
pub fn family_task(path: &str, task_dir: &std::path::Path, families: &Families, d: usize, nulls: usize, rule: StableRule, allow: Option<&HashSet<u128>>, max_table_columns: usize) -> Result<serde_json::Value, String> {
    let data: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
    let train = data["train"].as_u64().ok_or("a file's train")? as usize;
    let last_query = data["last_query"].as_str().unwrap_or("").to_string();
    let task = arclog::task::read_task(&task_dir.join(format!("{task_name}.json"))).map_err(|error| format!("the task does not read: {error:?}"))?;
    let grid = |fact: arclog::program::FactRelation, at: usize| {
        let relation = task.fact_rows(fact, Some(arclog::terms::Example::at(at as u16)));
        let mut cells = Vec::new();
        arclog::eval::join::each_row(&relation, &mut |row| cells.extend(row.iter().map(|cell| cell.encoding())));
        Table::new(2, cells)
    };
    let inputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Input, at)).collect();
    let outputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Output, at)).collect();
    let input_table = {
        let rows: Vec<Option<Arc<Table>>> = inputs.iter().map(|table| {
            let mut cells = Vec::with_capacity(table.cells.len());
            for row in table.rows() {
                cells.push(row[1]);
                cells.push(row[0]);
            }
            Some(Table::new(2, cells))
        }).collect();
        let types = vec![ValueType::Color, ValueType::Position];
        Stored { key: format!("{types:?}"), types, rows }
    };
    struct Parsed {
        query: String,
        reads: Vec<Stored>,
        gold: Stored,
        mutants: Vec<Stored>,
    }
    let mut parsed: Vec<Parsed> = Vec::new();
    let mut left_out: Vec<String> = Vec::new();
    for item in data["items"].as_array().ok_or("a file's items")? {
        let query = item["query"].as_str().unwrap_or("").to_string();
        let gold = stored_of(&item["gold"], train);
        let reads: Option<Vec<Stored>> = item["reads"].as_object().map_or(Some(Vec::new()), |reads| reads.values().map(|table| stored_of(table, train)).collect());
        let mutants: Option<Vec<Stored>> = item["mutants"].as_array().and_then(|mutants| mutants.iter().map(|mutant| stored_of(&mutant["table"], train)).collect());
        match (gold, reads, mutants) {
            (Some(gold), Some(reads), Some(mutants)) if gold.types.len() <= max_table_columns && reads.iter().all(|table| table.types.len() <= max_table_columns) && mutants.iter().all(|table| table.types.len() <= max_table_columns) => parsed.push(Parsed { query, reads, gold, mutants }),
            _ => left_out.push(query),
        }
    }
    let everywhere = |stored: &Stored| stored.rows.iter().all(|rows| rows.as_ref().is_some_and(|table| table.len > 0));
    // Each schema's family, and one evaluation of it for the task.
    let mut tables: Vec<&Stored> = vec![&input_table];
    for item in &parsed {
        tables.extend(item.reads.iter());
        tables.push(&item.gold);
        tables.extend(item.mutants.iter());
    }
    let mut held: Vec<(String, Arc<Family>)> = Vec::new();
    for table in &tables {
        if !held.iter().any(|(key, _)| *key == table.key) {
            held.push((table.key.clone(), families.get(table, d)));
        }
    }
    let mut evals: Vec<(String, Eval<'_>)> = held.iter().map(|(key, family)| (key.clone(), Eval::new(family))).collect();
    let mut tallies: FastMap<u128, Tally> = FastMap::default();
    let mut walks = 0u64;
    let mut walk_seconds = 0f64;
    let mut run = |moved: &[Arc<Table>], null: bool, tallies: &mut FastMap<u128, Tally>| -> Vec<Vec<(usize, f64, Vec<f64>, usize)>> {
        let mut done: FastMap<u128, Arc<ShapeMap>> = FastMap::default();
        let mut map_of = |stored: &Stored| -> Arc<ShapeMap> {
            let content = hash_words(stored.key.bytes().map(u64::from).chain(stored.rows.iter().flat_map(|rows| rows.as_ref().map_or([0, 0], |table| [table.hash as u64, (table.hash >> 64) as u64]))));
            if let Some(found) = done.get(&content) {
                return found.clone();
            }
            let eval = &mut evals.iter_mut().find(|(key, _)| *key == stored.key).expect("a schema's evaluation").1;
            let started = std::time::Instant::now();
            let map = Arc::new(eval.walk(&stored.rows, &inputs, moved, allow));
            walks += 1;
            walk_seconds += started.elapsed().as_secs_f64();
            done.insert(content, map.clone());
            map
        };
        let input_map = map_of(&input_table);
        parsed.iter().map(|item| {
            let reads: Vec<(Arc<ShapeMap>, bool)> = item.reads.iter().map(|table| (map_of(table), everywhere(table))).collect();
            let gold_map = map_of(&item.gold);
            let mutants: Vec<(Arc<ShapeMap>, bool)> = item.mutants.iter().map(|table| (map_of(table), everywhere(table))).collect();
            let mut bases: Vec<Held<'_>> = vec![(&input_map, true)];
            bases.extend(reads.iter().map(|(map, rows)| (map.as_ref(), *rows)));
            let mutant_refs: Vec<Held<'_>> = mutants.iter().map(|(map, rows)| (map.as_ref(), *rows)).collect();
            let gold = (gold_map.as_ref(), everywhere(&item.gold));
            let is_last = item.query == last_query;
            (1..=d).map(|size| {
                // Each shape's tally reads the primary queries, at the top size.
                let tally = (size == d && !is_last).then_some((&mut *tallies, null));
                scores(rule, &bases, gold, &mutant_refs, train, size as u8, tally)
            }).collect()
        }).collect()
    };
    let started = std::time::Instant::now();
    let results = run(&outputs, false, &mut tallies);
    let is_last = |at: usize| parsed[at].query == last_query;
    let per_size = |results: &[Vec<(usize, f64, Vec<f64>, usize)>], size: usize, last: bool| -> Vec<(usize, f64, Vec<f64>)> {
        results.iter().enumerate().filter(|(at, _)| is_last(*at) == last).map(|(_, item)| (item[size].0, item[size].1, item[size].2.clone())).collect()
    };
    let distinct_outputs = outputs.iter().map(|table| table.hash).collect::<std::collections::BTreeSet<_>>().len() > 1;
    let mut null_aucs: Vec<Vec<f64>> = vec![Vec::new(); d];
    if distinct_outputs && train > 1 {
        let mut state = 0x2545_f491_4f6c_dd1du64 ^ hash_words(task_name.bytes().map(u64::from)) as u64;
        for _ in 0..nulls {
            let mut order: Vec<usize> = (0..train).collect();
            loop {
                for at in (1..train).rev() {
                    state ^= state << 13;
                    state ^= state >> 7;
                    state ^= state << 17;
                    order.swap(at, (state % (at as u64 + 1)) as usize);
                }
                if order.iter().enumerate().all(|(at, own)| at != *own) {
                    break;
                }
            }
            let moved: Vec<Arc<Table>> = order.iter().map(|at| outputs[*at].clone()).collect();
            let found = run(&moved, true, &mut tallies);
            for (size, aucs) in null_aucs.iter_mut().enumerate() {
                if let Some(auc) = auc_of(&per_size(&found, size, false)) {
                    aucs.push(auc);
                }
            }
        }
    }
    let draws = null_aucs.first().map_or(0, Vec::len);
    let mean = |values: &[f64]| (!values.is_empty()).then(|| values.iter().sum::<f64>() / values.len() as f64);
    let sizes: Vec<serde_json::Value> = (0..d).map(|size| {
        let rest = per_size(&results, size, false);
        let last = per_size(&results, size, true);
        serde_json::json!({
            "d": size + 1,
            "auc": auc_of(&rest),
            "auc_last": auc_of(&last),
            "null": mean(&null_aucs[size]),
            "contingent": mean(&rest.iter().map(|found| found.0 as f64).collect::<Vec<_>>()),
            "items": rest.iter().map(|found| found.2.len()).sum::<usize>(),
        })
    }).collect();
    let terms: Vec<usize> = held.iter().map(|(_, family)| family.terms.len()).collect();
    let names = families.names.lock().expect("no panic");
    // A shape stands in the result where a comparison told gold from a mutant, either
    // under the task's outputs or under the null.
    let mut shapes: Vec<serde_json::Value> = Vec::new();
    for (hash, tally) in &tallies {
        if tally.gold_only + tally.mutant_only + tally.null_gold_only + tally.null_mutant_only == 0 {
            continue;
        }
        shapes.push(serde_json::json!([names.get(hash).map_or("", String::as_str), tally.gold_only, tally.mutant_only, tally.compared, tally.null_gold_only, tally.null_mutant_only, tally.null_compared]));
    }
    Ok(serde_json::json!({
        "task": task_name, "rule": format!("{rule:?}"), "sizes": sizes, "left_out": left_out, "draws": draws, "shapes": shapes,
        "terms_per_schema": terms, "walks": walks, "walk_seconds": walk_seconds, "seconds": started.elapsed().as_secs_f64(),
    }))
}
