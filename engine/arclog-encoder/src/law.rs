//! The check of the transformation law on a sample of tables, which
//! `work/feature-spec/directive.md` gives: an element of D4 and a color
//! permutation act on a table's rows and on the grids, the result is read as
//! stored rows, and each feature is compared. An invariant feature keeps its
//! value, and an equivariant one moves by the group's action. A difference is a
//! fault of the expander or of a lib element.

use std::collections::BTreeMap;
use std::ops::ControlFlow;

use arclog::algebra::boxes::apply;
use arclog::algebra::geometry::{D4Element, Edge, Geometry};
use arclog::registry::Registry;
use arclog::task::{Grid, Task, TrainPair};
use arclog::terms::{Color, Constant, Term, TermId};
use arclog::types::ValueType;

use crate::encoder::{law_of, Law};
use crate::enumerate::{value_kinds, Space, Typed};
use crate::expression::{Feature, Leaf};
use crate::run::{Evaluated, Host, ModelValue, StoredRows, Value};

/// An element of the group: an element of D4 and a color permutation.
#[derive(Clone, Debug)]
pub struct Element {
    pub name: String,
    pub g: D4Element,
    /// The image of each color.
    pub colors: [u8; 10],
}

impl Element {
    /// The element whose D4 part the constant `name` gives, with `colors`.
    pub fn new(name: &str, colors: [u8; 10]) -> Element {
        let registry = Registry::get();
        let constant = registry.orientation_constant(name).unwrap_or_else(|| panic!("`{name}` is an orientation constant"));
        let id = Term::Constant(Constant::Orientation(constant)).encode().expect("a constant's term id");
        let g = Geometry::get().element(id);
        Element { name: format!("{name}/{}", colors.iter().map(|digit| digit.to_string()).collect::<String>()), g, colors }
    }

    fn color(&self, color: Color) -> Color {
        Color::from_digit(self.colors[usize::from(color.digit())]).expect("a digit of a color")
    }

    /// The image of the value `id` at a column of type `ty`.
    pub fn cell(&self, id: TermId, ty: &ValueType) -> TermId {
        match Term::decode(id, ty) {
            Term::Box(margins) => Term::Box(apply(self.g, margins)).encode().expect("a permutation of margins within a byte"),
            Term::Constant(Constant::Color(color)) => Term::Constant(Constant::Color(self.color(color))).encode().expect("a color's term id"),
            Term::Constant(Constant::Orientation(_)) => Geometry::get().try_under(self.g, id).unwrap_or(id),
            Term::Number(_) | Term::Ident(_) | Term::Constant(Constant::Example(_) | Constant::Unit | Constant::LibName(_)) => id,
        }
    }

    /// The image of `rows`, whose columns have `types`.
    pub fn rows(&self, rows: &[Vec<TermId>], types: &[ValueType]) -> Vec<Vec<TermId>> {
        rows.iter().map(|row| row.iter().zip(types).map(|(id, ty)| self.cell(*id, ty)).collect()).collect()
    }

    fn grid(&self, grid: &Grid) -> Grid {
        let rows = grid.rows();
        let (height, width) = (rows.len() as i32, rows[0].len() as i32);
        let swaps = matches!(self.g.image(Edge::Top), Edge::Left | Edge::Right);
        let (new_height, new_width) = if swaps { (width as usize, height as usize) } else { (height as usize, width as usize) };
        let mut cells = vec![vec![Color::from_digit(0).expect("a color"); new_width]; new_height];
        for (r, row) in rows.iter().enumerate() {
            for (c, color) in row.iter().enumerate() {
                let position = arclog::terms::Margins { top: r as i32, bottom: height - 1 - r as i32, left: c as i32, right: width - 1 - c as i32 };
                let image = apply(self.g, position);
                cells[image.top as usize][image.left as usize] = self.color(*color);
            }
        }
        Grid::from_rows(cells.into_iter().map(Vec::into_boxed_slice).collect()).expect("a grid of equal rows")
    }

    /// The image of `task`.
    pub fn task(&self, task: &Task) -> Task {
        Task {
            train: task.train.iter().map(|pair| TrainPair { input: self.grid(&pair.input), output: self.grid(&pair.output) }).collect(),
            test: task.test.iter().map(|grid| self.grid(grid)).collect(),
        }
    }
}

/// The rows of `value` under a canonical name for each Ident: a label of a
/// content has no number that a feature can read, so two values compare up to a
/// renaming of their Idents. Each Ident takes the sorted texts of the rows it
/// stands in, with the other Idents under their names of the round before.
fn canonical(rows: &[Vec<TermId>], types: &[ValueType]) -> Vec<String> {
    let cell = |id: TermId, ty: &ValueType, names: &BTreeMap<(usize, u32), String>, at: usize| -> String {
        match ty {
            ValueType::Ident(_) => names.get(&(at, id.encoding())).cloned().unwrap_or_default(),
            _ => id.encoding().to_string(),
        }
    };
    let mut names: BTreeMap<(usize, u32), String> = BTreeMap::new();
    for _ in 0..3 {
        let mut next: BTreeMap<(usize, u32), Vec<String>> = BTreeMap::new();
        for row in rows {
            let text: Vec<String> = row.iter().zip(types).enumerate().map(|(at, (id, ty))| cell(*id, ty, &names, at)).collect();
            let text = text.join(",");
            for (at, (id, ty)) in row.iter().zip(types).enumerate() {
                if matches!(ty, ValueType::Ident(_)) {
                    next.entry((at, id.encoding())).or_default().push(format!("{at}:{text}"));
                }
            }
        }
        names = next.into_iter().map(|(key, mut texts)| {
            texts.sort();
            let digest = arclog::hash::digest_text(&texts.join("|"));
            (key, digest)
        }).collect();
    }
    let mut texts: Vec<String> = rows.iter().map(|row| row.iter().zip(types).enumerate().map(|(at, (id, ty))| cell(*id, ty, &names, at)).collect::<Vec<_>>().join(",")).collect();
    texts.sort();
    texts
}

/// One difference that the check found.
#[derive(Clone, Debug)]
pub struct Difference {
    pub expression: String,
    pub law: Option<Law>,
    pub detail: String,
}

/// The counts of one table under one element.
#[derive(Clone, Debug, Default)]
pub struct Tally {
    pub compared: u64,
    pub invariant: u64,
    pub equivariant: u64,
    pub both_refused: u64,
    pub both_fault: u64,
    pub stopped: u64,
    pub differences: Vec<Difference>,
}

fn compare_models(expression: &str, element: &Element, value: &Value, moved: &Value, tally: &mut Tally) {
    let law = law_of(&value.types);
    // A bound stopped the walk of a side, so that side has no value to compare.
    if value.stop.is_some() || moved.stop.is_some() {
        tally.stopped += 1;
        return;
    }
    let (Some(first), Some(second)) = (value.at.first(), moved.at.first()) else {
        tally.differences.push(Difference { expression: expression.to_string(), law: Some(law), detail: "a value with no assignment".to_string() });
        return;
    };
    if first.examples.len() != second.examples.len() {
        tally.differences.push(Difference { expression: expression.to_string(), law: Some(law), detail: "another count of examples".to_string() });
        return;
    }
    for ((example, models), (_, moved_models)) in first.examples.iter().zip(&second.examples) {
        if models.len() != moved_models.len() {
            tally.differences.push(Difference { expression: expression.to_string(), law: Some(law), detail: format!("{} models and {} at {example:?}", models.len(), moved_models.len()) });
            return;
        }
        for (model, moved_model) in models.iter().zip(moved_models) {
            match (model, moved_model) {
                (ModelValue::Rows(rows), ModelValue::Rows(moved_rows)) => {
                    let image = element.rows(rows, &value.types);
                    let (a, b) = (canonical(&image, &value.types), canonical(moved_rows, &moved.types));
                    if a != b {
                        let shown = |items: &[String]| items.iter().take(4).cloned().collect::<Vec<_>>().join(" ");
                        tally.differences.push(Difference {
                            expression: expression.to_string(),
                            law: Some(law),
                            detail: format!("at {example:?}: {} rows move to {} expected, and {} found: expected {} found {}", rows.len(), a.len(), b.len(), shown(&a), shown(&b)),
                        });
                        return;
                    }
                }
                (ModelValue::Undefined, ModelValue::Undefined) => {}
                (ModelValue::Stopped(_), _) | (_, ModelValue::Stopped(_)) => {
                    tally.stopped += 1;
                    return;
                }
                (a, b) => {
                    let kind = |model: &ModelValue| match model {
                        ModelValue::Rows(rows) => format!("{} rows", rows.len()),
                        ModelValue::Undefined => "undefined".to_string(),
                        ModelValue::Stopped(stop) => format!("stopped {stop}"),
                    };
                    tally.differences.push(Difference { expression: expression.to_string(), law: Some(law), detail: format!("at {example:?}: {} and {}", kind(a), kind(b)) });
                    return;
                }
            }
        }
    }
    tally.compared += 1;
    match law {
        Law::Invariant => tally.invariant += 1,
        Law::Equivariant => tally.equivariant += 1,
    }
}

/// Whether the text `expression` falls in the sample of `rate` in a million.
fn sampled(expression: &str, salt: &str, rate: u32) -> bool {
    let digest = arclog::hash::digest_text(&format!("{salt}/{expression}"));
    let bits = u32::from_str_radix(&digest[..7], 16).unwrap_or(0);
    bits % 1_000_000 < rate
}

/// What a sample covers.
#[derive(Clone, Debug)]
pub struct Sample {
    pub size: usize,
    pub rate_per_million: u32,
    pub max_inputs: Option<usize>,
    pub work_cap: u64,
    /// A negative control: the element that the comparison expects, in place
    /// of the one that moves the table, so the check must report differences.
    pub control: Option<Element>,
}

/// Compares the features of `table` on `task` with those of its image under
/// `element`.
pub fn compare_table(table: &StoredRows, task: &Task, element: &Element, sample: &Sample, tally: &mut Tally, progress: &mut dyn FnMut(&Tally)) -> Result<(), String> {
    let plain = Host::stored(task.clone(), table)?;
    let moved_table = table.moved(element);
    let moved = Host::stored(element.task(task), &moved_table)?;
    plain.set_work_cap(sample.work_cap);
    moved.set_work_cap(sample.work_cap);
    let registry = Registry::get();
    let name = table.table.clone();
    for task_wide in [false, true] {
        let space = Space {
            registry,
            tables: &plain,
            task_wide,
            table_names: vec![name.clone()],
            program_relations: false,
            kinds: value_kinds(),
            max_inputs: sample.max_inputs,
            frames: Vec::new(),
        };
        let mut lower: Vec<Vec<Typed>> = Vec::new();
        for size in 0..=sample.size {
            let keep = size < sample.size;
            let mut terms = Vec::new();
            let _ = space.generate(&lower, size, &mut |term| {
                let _ = space.roots(&term, &mut |feature| {
                    if space.task_wide && !has_task_wide_leaf(&feature, table) {
                        return ControlFlow::Continue(());
                    }
                    let expression = feature.to_string();
                    if !sampled(&expression, &element.name, sample.rate_per_million) {
                        return ControlFlow::Continue(());
                    }
                    match (plain.evaluate(&feature), moved.evaluate(&feature)) {
                        (Evaluated::Value(value), Evaluated::Value(image)) => compare_models(&expression, sample.control.as_ref().unwrap_or(element), &value, &image, tally),
                        (Evaluated::Refused(_), Evaluated::Refused(_)) => tally.both_refused += 1,
                        (Evaluated::Fault(_), Evaluated::Fault(_)) => tally.both_fault += 1,
                        (a, b) => {
                            let kind = |evaluated: &Evaluated| match evaluated {
                                Evaluated::Value(_) => "a value".to_string(),
                                Evaluated::Refused(message) => format!("refused: {message}"),
                                Evaluated::Fault(message) => format!("fault: {message}"),
                            };
                            tally.differences.push(Difference { expression, law: None, detail: format!("{} and {}", kind(&a), kind(&b)) });
                        }
                    }
                    progress(tally);
                    ControlFlow::Continue(())
                });
                if keep {
                    terms.push(term);
                }
                ControlFlow::Continue(())
            });
            lower.push(terms);
        }
    }
    Ok(())
}

fn has_task_wide_leaf(feature: &Feature, table: &StoredRows) -> bool {
    let mut found = false;
    if let Some(rel) = feature.relation() {
        rel.each_leaf(&mut |leaf| {
            found |= match leaf {
                Leaf::ExInput | Leaf::ExOutput | Leaf::Proposer(_) => true,
                Leaf::Table(_) => !table.per_input && table.has_example,
                _ => false,
            };
        });
    }
    found
}
