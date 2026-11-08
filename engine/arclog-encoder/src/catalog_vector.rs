//! A table's sparse vector over the train examples, from the catalog's records.
//!
//! A shape is a kind with each hole written by its column's type. At an example, a shape's
//! bindings give two numbers: the greatest and the sum, or the greatest and the least for a
//! fraction. Over the examples, each of the two gives its least, mean and greatest. A shape
//! whose every value is at its default is left out. A binding with no record has no value at
//! that example, and `present` counts the examples where the shape has one.

use crate::catalog::*;
use crate::catalog_facts::*;
use crate::lookup::LookupMap;

/// An exact fraction in lowest terms, with a positive denominator.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Fraction {
    pub n: i64,
    pub d: i64,
}

fn gcd(a: i64, b: i64) -> i64 {
    if b == 0 { a.abs() } else { gcd(b, a % b) }
}

impl Fraction {
    pub fn of(n: i64, d: i64) -> Fraction {
        let shared = gcd(n, d).max(1);
        let sign = if d < 0 { -1 } else { 1 };
        Fraction { n: sign * n / shared, d: sign * d / shared }
    }

    pub const ZERO: Fraction = Fraction { n: 0, d: 1 };

    pub fn value(self) -> f64 {
        self.n as f64 / self.d as f64
    }
}

impl PartialOrd for Fraction {
    fn partial_cmp(&self, other: &Fraction) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Fraction {
    fn cmp(&self, other: &Fraction) -> std::cmp::Ordering {
        (i128::from(self.n) * i128::from(other.d)).cmp(&(i128::from(other.n) * i128::from(self.d)))
    }
}

/// One number of a shape over the examples.
#[derive(Clone, Copy, PartialEq, Debug)]
pub struct Combined {
    pub min: Fraction,
    pub mean: f64,
    pub max: Fraction,
}

/// A shape's entry in a table's vector.
#[derive(Clone, Debug)]
pub struct Entry {
    pub name: String,
    /// Whether its root is a `ratio`, so `second` is the least rather than the sum.
    pub ratio: bool,
    /// The train examples where it has a value.
    pub present: u8,
    pub greatest: Combined,
    pub second: Combined,
}

impl Entry {
    /// Whether the shape has one value at every example.
    pub fn stable(&self, examples: usize) -> bool {
        self.present as usize == examples && self.greatest.min == self.greatest.max && self.second.min == self.second.max
    }
}

/// The words of the kinds that give this word, each a column of its own.
fn words_with(word: &'static str) -> &'static [&'static str] {
    const SETS: &[&str] = &["equal", "subset", "superset", "overlap", "disjoint", "complement"];
    const SIGNS: &[&str] = &["<", "=", ">", "mixed"];
    const TRENDS: &[&str] = &["rises", "falls", "neither"];
    match word {
        "equal" | "subset" | "superset" | "overlap" | "disjoint" | "complement" => SETS,
        "<" | "=" | ">" | "mixed" => SIGNS,
        "rises" | "falls" | "neither" => TRENDS,
        _ => &[],
    }
}

/// A kind's name with each hole written by its column's type.
pub fn shape_name(record: &Record, kinds: &[Kind]) -> String {
    let mut holes = record.holes.iter().filter(|hole| **hole != NONE).map(|hole| format!("?{}", kinds[*hole as usize].name()));
    let words: Vec<String> = record.kind.split(' ').map(|word| {
        if word.split(',').all(|part| part == "C") {
            word.split(',').map(|_| holes.next().unwrap_or_default()).collect::<Vec<_>>().join(",")
        } else if word.split('-').count() > 1 && word.split('-').all(|part| part == "C") {
            word.split('-').map(|_| holes.next().unwrap_or_default()).collect::<Vec<_>>().join("-")
        } else {
            word.to_string()
        }
    }).collect();
    words.join(" ")
}

#[derive(Default)]
struct Per {
    ratio: bool,
    /// Per example, each binding's value.
    values: Vec<Vec<Fraction>>,
}

/// One table's vector, with its records at each train pair, its entries in the order of their names.
pub fn vector_of(records: &[Vec<Record>], kinds: &[Kind]) -> Vec<Entry> {
    let examples = records.len();
    let mut per: LookupMap<String, Per> = LookupMap::new();
    for (example, held) in records.iter().enumerate() {
        for record in held {
            let name = shape_name(record, kinds);
            let mut put = |name: String, ratio: bool, value: Fraction| {
                let entry = per.entry(name).or_insert_with(|| Per { ratio, values: vec![Vec::new(); examples] });
                entry.values[example].push(value);
            };
            match record.value {
                Value::Null => {}
                Value::Bool(flag) => put(name, false, Fraction::of(i64::from(flag), 1)),
                Value::Num(number) => put(name, false, Fraction::of(number, 1)),
                Value::Share(hits, of) => {
                    if of > 0 {
                        put(name, true, Fraction::of(i64::from(hits), i64::from(of)));
                    }
                }
                Value::Word(word) => {
                    for column in words_with(word) {
                        put(format!("{name} :{column}"), false, Fraction::of(i64::from(*column == word), 1));
                    }
                }
            }
        }
    }
    let mut out = Vec::with_capacity(per.len());
    for (name, held) in per.into_sorted_vec() {
        let mut greatest = Vec::with_capacity(examples);
        let mut second = Vec::with_capacity(examples);
        for values in &held.values {
            if values.is_empty() {
                continue;
            }
            let top = values.iter().copied().max().unwrap_or(Fraction::ZERO);
            let other = if held.ratio {
                values.iter().copied().min().unwrap_or(Fraction::ZERO)
            } else {
                Fraction::of(values.iter().map(|value| value.n).sum(), 1)
            };
            greatest.push(top);
            second.push(other);
        }
        if greatest.iter().all(|value| value.n == 0) && second.iter().all(|value| value.n == 0) {
            continue;
        }
        let combined = |list: &[Fraction]| Combined {
            min: list.iter().copied().min().unwrap_or(Fraction::ZERO),
            mean: list.iter().map(|value| value.value()).sum::<f64>() / list.len().max(1) as f64,
            max: list.iter().copied().max().unwrap_or(Fraction::ZERO),
        };
        out.push(Entry { name, ratio: held.ratio, present: greatest.len() as u8, greatest: combined(&greatest), second: combined(&second) });
    }
    out
}

/// One table's vector over the train pairs: the pass at each pair, then the combination.
pub fn table_vector(kinds: &[Kind], keys: &[bool], rows: &[Option<(usize, Vec<Cell>)>], facts: &[PairFacts]) -> Vec<Entry> {
    let mut records: Vec<Vec<Record>> = Vec::with_capacity(facts.len());
    for (pair, fact) in facts.iter().enumerate() {
        let mut held = Vec::with_capacity(256);
        if let Some(Some((count, cells))) = rows.get(pair) {
            pass(&TableAt { kinds, keys, rows: *count, cells }, fact, &mut held);
        }
        records.push(held);
    }
    vector_of(&records, kinds)
}
