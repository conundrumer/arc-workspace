//! `TableVector`: the features of one parameterized table at one assignment, and the base tables',
//! as the contract and the specification's section on vectors give them. A shape gives two numbers
//! at each ARC example: the greatest and the sum of its ground expressions' values, or for a `ratio`
//! the greatest and the least. Within an ARC example it takes the mean over the ARC example's tables.
//!
//! A vector is a function of the parameterized table's tables and of the grids it is given, so two
//! parameterized tables with one `TableHash` have one vector. A caller that reads a parameterized
//! table against other outputs gives other grids.

use std::path::Path;
use std::sync::Arc;

use arclog::task::Task;

use crate::catalog_facts::GridFacts;
use crate::generate::{constants_of, leaves_at, Generated, Generators, Number, RootOf, RootTable, ShapeMask, Slot, SlotState, Walker, READS_OUTPUT};
use crate::native::Table;
use crate::stored::Stored;

/// A task's grids and what the parts read of them, at each example: the train pairs, then the test
/// inputs. The outputs are data, so a reader can give a pair another pair's output.
pub struct Grids {
    pub train: usize,
    pub inputs: Vec<Arc<Table>>,
    pub outputs: Vec<Arc<Table>>,
    pub constants: Vec<Vec<Option<Arc<Table>>>>,
    /// What the catalog reads of each train pair, and of each test input, which stands in for its own output.
    pub facts: Vec<crate::catalog_facts::PairFacts>,
    pub test_facts: Vec<crate::catalog_facts::PairFacts>,
    /// What the catalog reads of each train input as its own output, so a kind over the output also reads the input.
    pub input_facts: Vec<crate::catalog_facts::PairFacts>,
}

impl Grids {
    /// The grids of a task. `order` gives the train pair whose output each train pair reads.
    pub fn of(task: &Task, task_json: &serde_json::Value, order: Option<&[usize]>) -> Grids {
        let train = task.train.len();
        let total = train + task.test.len();
        let grid = |fact: arclog::program::FactRelation, at: usize| {
            let relation = task.fact_rows(fact, Some(arclog::terms::Example::at(at as u16)));
            let mut cells = Vec::new();
            arclog::eval::join::each_row(&relation, &mut |row| cells.extend(row.iter().map(|cell| cell.encoding())));
            Table::new(2, cells)
        };
        let inputs = (0..total).map(|at| grid(arclog::program::FactRelation::Input, at)).collect();
        let outputs = (0..train).map(|at| grid(arclog::program::FactRelation::Output, order.map_or(at, |order| order[at]))).collect();
        let facts = crate::catalog_run::pairs_of_task(task_json, order);
        let empty = Vec::new();
        let tests: Vec<GridFacts> = task_json["test"].as_array().unwrap_or(&empty).iter().map(|pair| crate::catalog_run::grid_of(&pair["input"])).collect();
        let constants = constants_of(&facts, &tests);
        let test_facts = tests.iter().map(|test| crate::catalog_facts::PairFacts::new(test.clone(), test.clone())).collect();
        let input_facts = facts.iter().map(|fact| crate::catalog_facts::PairFacts::new(fact.input.clone(), fact.input.clone())).collect();
        Grids { train, inputs, outputs, constants, facts, test_facts, input_facts }
    }

    /// The grids of the task stored at `task_dir` under `name`.
    pub fn of_file(task_dir: &Path, name: &str, order: Option<&[usize]>) -> Result<(Task, Grids), String> {
        let path = task_dir.join(format!("{name}.json"));
        let task = arclog::task::read_task(&path).map_err(|error| format!("the task does not read: {error:?}"))?;
        let json: serde_json::Value = serde_json::from_str(&crate::zio::read_text(&path)?).map_err(|error| error.to_string())?;
        let grids = Grids::of(&task, &json, order);
        Ok((task, grids))
    }
}

/// A table's vector: each shape that is not at its default at some example, sorted by name, with
/// its numbers at each example.
pub struct TableVector {
    pub train: usize,
    pub examples: usize,
    pub shapes: Vec<u64>,
    /// What each shape reads, its size, and which kind of root it is.
    pub meta: Vec<(u8, u8, RootOf)>,
    /// `examples` slots per shape.
    pub slots: Vec<Slot>,
    /// The mean and the greatest over the ARC examples of the count of an ARC example's tables.
    pub table_rows: (f64, u32),
    /// Whether the walk passed its bound on the cells of values, so that the terms after that point have no value.
    pub over_budget: bool,
}

impl TableVector {
    pub fn at(&self, shape: usize) -> &[Slot] {
        &self.slots[shape * self.examples..(shape + 1) * self.examples]
    }

    /// The examples that a shape combines over: the train examples where it reads the output, and
    /// every example otherwise.
    pub fn scope(&self, shape: usize) -> usize {
        if self.meta[shape].0 & READS_OUTPUT != 0 { self.train } else { self.examples }
    }

    /// Whether a shape has one value at every example of its scope that is not its default: the
    /// protocol's stable root, which a reader of Candidate recognition takes.
    pub fn stable(&self, shape: usize) -> bool {
        let at = self.at(shape);
        let scope = &at[..self.scope(shape)];
        scope.first().is_some_and(|first| first.state == SlotState::Value && scope.iter().all(|slot| slot.state == SlotState::Value && slot.digest == first.digest))
    }

    /// `:min`, `:mean` and `:max` of one of a shape's two numbers over its scope, and how many
    /// examples have a value there. A default counts as its value, and a stopped example counts
    /// for nothing.
    pub fn over_examples(&self, shape: usize, second: bool) -> (f64, f64, f64, usize) {
        let at = self.at(shape);
        let (mut least, mut most, mut sum, mut count) = (f64::INFINITY, f64::NEG_INFINITY, 0.0, 0usize);
        for slot in &at[..self.scope(shape)] {
            let value = match slot.state {
                SlotState::NoValue => continue,
                SlotState::Default => 0.0,
                SlotState::Value => if second { slot.second.float() } else { slot.greatest.float() },
            };
            least = least.min(value);
            most = most.max(value);
            sum += value;
            count += 1;
        }
        if count == 0 {
            return (f64::NAN, f64::NAN, f64::NAN, 0);
        }
        (least, sum / count as f64, most, count)
    }

    /// Whether a shape's value at each example of its scope equals its value on `other`.
    pub fn same_at_each_example(&self, shape: usize, other: &TableVector) -> bool {
        let Ok(place) = other.shapes.binary_search(&self.shapes[shape]) else { return false };
        let (own, theirs) = (self.at(shape), other.at(place));
        (0..self.scope(shape)).all(|example| own[example].state == theirs[example].state && own[example].digest == theirs[example].digest)
    }
}

/// The vector of a walk, one slot per shape and example. `example_of` gives the example of each instance of the walk, in the order of the instances. An example with several instances
/// takes the mean over them, and one with none has no value.
fn combined(table: RootTable, example_of: &[usize], examples: usize, train: usize, over_budget: bool) -> TableVector {
    let instances = example_of.len();
    let order = table.sorted_roots();
    let mut per_example = vec![0u32; examples];
    for example in example_of {
        per_example[*example] += 1;
    }
    // Each instance stands for the example at its own place, so the walk's slots are the vector's.
    let identity = instances == examples && example_of.iter().enumerate().all(|(place, example)| *example == place);
    // The instances of example `e`, in order, are `members[starts[e]..starts[e + 1]]`.
    let (mut starts, mut members) = (Vec::new(), Vec::new());
    if !identity {
        starts.reserve(examples + 1);
        starts.push(0usize);
        for count in &per_example {
            starts.push(starts[starts.len() - 1] + *count as usize);
        }
        members = vec![0usize; instances];
        let mut next = starts.clone();
        for (instance, example) in example_of.iter().enumerate() {
            members[next[*example]] = instance;
            next[*example] += 1;
        }
    }
    let mut slots = Vec::with_capacity(order.len() * examples);
    let mut shapes = Vec::with_capacity(order.len());
    let mut meta = Vec::with_capacity(order.len());
    let mut held: Vec<&Slot> = Vec::new();
    for (hash, at) in order {
        shapes.push(hash as u64);
        meta.push(table.meta[at]);
        let own = &table.slots[at * instances..(at + 1) * instances];
        if identity {
            slots.extend_from_slice(own);
            continue;
        }
        for example in 0..examples {
            held.clear();
            held.extend(members[starts[example]..starts[example + 1]].iter().map(|instance| &own[*instance]));
            slots.push(mean_over_models(&held));
        }
    }
    let total: u32 = per_example.iter().sum();
    let table_rows = (f64::from(total) / examples.max(1) as f64, per_example.iter().copied().max().unwrap_or(0));
    TableVector { train, examples, shapes, meta, slots, table_rows, over_budget }
}

/// A root's numbers at an ARC example: the mean over its tables, where a default counts as 0.
fn mean_over_models(held: &[&Slot]) -> Slot {
    // An example with no instance has no table, so its root has no value. An example whose table is empty has an instance, and its roots have values.
    let Some(first) = held.first() else { return Slot { state: SlotState::NoValue, ..Slot::default() } };
    if held.len() == 1 {
        return **first;
    }
    if held.iter().any(|slot| slot.state == SlotState::NoValue) {
        return Slot { state: SlotState::NoValue, ..Slot::default() };
    }
    if held.iter().all(|slot| slot.state == SlotState::Default) {
        return Slot::default();
    }
    let total = |read: &dyn Fn(&Slot) -> Number| -> Number {
        // The fraction stays reduced, since the denominators of many tables multiply past any word.
        fn shared(mut a: i128, mut b: i128) -> i128 {
            while b != 0 {
                (a, b) = (b, a % b);
            }
            a.abs().max(1)
        }
        let exact = || -> Option<(i128, i128)> {
            let (mut top, mut denominator) = (0i128, 1i128);
            for slot in held {
                let value = read(slot);
                let down = i128::from(value.bottom.max(1));
                let common = shared(denominator, down);
                top = top.checked_mul(down / common)?.checked_add(i128::from(value.top).checked_mul(denominator / common)?)?;
                denominator = (denominator / common).checked_mul(down)?;
                let common = shared(top, denominator);
                top /= common;
                denominator /= common;
            }
            let bottom = denominator.checked_mul(held.len() as i128)?;
            let common = shared(top, bottom);
            Some((top / common, bottom / common))
        };
        // A Number holds 31 bits over 32 bits. A fraction past them keeps its value and loses its last digits, since a fraction clamped part by part would read as another number.
        let signed = |below: bool, held: Number| if below { Number { top: -held.top, bottom: held.bottom } } else { held };
        match exact() {
            Some((top, bottom)) => {
                let size = top.abs();
                let excess = (128 - size.leading_zeros()).saturating_sub(31).max((128 - bottom.leading_zeros()).saturating_sub(32));
                signed(top < 0, Number::fraction((size >> excess) as u64, ((bottom >> excess) as u64).max(1)))
            }
            None => {
                let mean = held.iter().map(|slot| read(slot).float()).sum::<f64>() / held.len() as f64;
                let scale = (f64::from(i32::MAX) / mean.abs().max(1.0)).floor();
                signed(mean < 0.0, Number::fraction((mean.abs() * scale) as u64, scale as u64))
            }
        }
    };
    let digest = held.iter().fold(0u64, |sum, slot| sum.wrapping_add(slot.digest));
    Slot { greatest: total(&|slot| slot.greatest), second: total(&|slot| slot.second), digest, state: SlotState::Value, undefined: 0 }
}

/// The vector of `table` over the first `examples` examples of `grids`.
pub fn table_vector(walker: &mut Walker<'_>, table: &Stored, grids: &Grids, examples: usize, only_output: bool) -> TableVector {
    table_vector_of(walker, table, grids, examples, only_output, None)
}

/// The vector of `table` over the first `examples` examples of `grids`, for the shapes of `mask` alone: the walk
/// covers the terms that those shapes need and no other, and the vector holds the listed shapes that a full
/// walk's vector holds, with its values. `mask` is made for the walker's family, by [`Generated::shape_mask`].
/// The walk adds up the cells of the terms it walks alone, so a table that passes the walk's bound in a full walk
/// may stay within it here, and the vector's `over_budget` says whether this walk passed it.
pub fn table_vector_of_shapes(walker: &mut Walker<'_>, table: &Stored, grids: &Grids, examples: usize, only_output: bool, mask: &ShapeMask) -> TableVector {
    table_vector_of(walker, table, grids, examples, only_output, Some(mask))
}

fn table_vector_of(walker: &mut Walker<'_>, table: &Stored, grids: &Grids, examples: usize, only_output: bool, mask: Option<&ShapeMask>) -> TableVector {
    let mut example_of = Vec::with_capacity(examples);
    let mut rows = Vec::with_capacity(examples);
    for (example, models) in table.rows.iter().take(examples).enumerate() {
        if models.is_empty() {
            example_of.push(example);
            rows.push(None);
        }
        for model in models {
            example_of.push(example);
            rows.push(Some(model.clone()));
        }
    }
    let train = example_of.iter().filter(|example| **example < grids.train).count();
    let leaves = leaves_at(&rows, &example_of, &grids.inputs, &grids.outputs, &grids.constants);
    let found = match mask {
        Some(mask) => walker.walk_shapes(&leaves, train, only_output, mask),
        None => walker.walk(&leaves, train, only_output),
    };
    combined(found, &example_of, examples, grids.train.min(examples), walker.over_budget)
}

/// The base tables' vectors, as the contract keys them: `input`, at every example, and `ex_output`,
/// read at each train example.
pub struct BaseVectors {
    pub input: TableVector,
    pub ex_output: TableVector,
}

pub fn base_vectors(grids: &Grids, families: &Generators, d: usize) -> BaseVectors {
    let input = Stored::of_grids(&grids.inputs);
    let output = Stored::of_grids(&grids.outputs);
    let family: Arc<Generated> = families.get(&input, d);
    let mut walker = Walker::new(&family);
    let input_vector = table_vector(&mut walker, &input, grids, grids.inputs.len(), false);
    let output_vector = table_vector(&mut walker, &output, grids, grids.train, false);
    BaseVectors { input: input_vector, ex_output: output_vector }
}

/// A pair's own numbers, which read the base tables and no other table, at every example.
pub fn pair_vector(grids: &Grids, families: &Generators, d: usize, only_output: bool) -> TableVector {
    let family: Arc<Generated> = families.get_grids(d);
    let mut walker = Walker::new(&family);
    let no_table = Stored { key: String::new(), types: Vec::new(), keys: Vec::new(), rows: vec![Vec::new(); grids.inputs.len()] };
    table_vector(&mut walker, &no_table, grids, grids.inputs.len(), only_output)
}

/// The vector of two tables of a state, over one instance per model of each at each example.
pub fn two_tables_vector(walker: &mut Walker<'_>, t: &Stored, u: &Stored, grids: &Grids, examples: usize, only_output: bool) -> TableVector {
    let mut example_of = Vec::with_capacity(examples);
    let mut t_rows = Vec::with_capacity(examples);
    let mut u_rows: Vec<Option<Arc<Table>>> = Vec::with_capacity(examples);
    for example in 0..examples {
        let (own, theirs) = (t.rows.get(example).map_or(&[][..], Vec::as_slice), u.rows.get(example).map_or(&[][..], Vec::as_slice));
        if own.is_empty() || theirs.is_empty() {
            example_of.push(example);
            t_rows.push(None);
            u_rows.push(None);
            continue;
        }
        for first in own {
            for second in theirs {
                example_of.push(example);
                t_rows.push(Some(first.clone()));
                u_rows.push(Some(second.clone()));
            }
        }
    }
    let train = example_of.iter().filter(|example| **example < grids.train).count();
    let mut leaves = leaves_at(&t_rows, &example_of, &grids.inputs, &grids.outputs, &grids.constants);
    leaves.push(u_rows.iter().map(|table| table.clone().map_or(crate::native::Val::None, crate::native::Val::of_table)).collect());
    let found = walker.walk(&leaves, train, only_output);
    combined(found, &example_of, examples, grids.train.min(examples), walker.over_budget)
}

/// `AssignmentVector`: one parameterized table across its assignments, as the contract gives it.
pub struct AssignmentVector {
    pub count: usize,
    pub capped: bool,
    /// The count of distinct `TableHash`es over the assignments, divided by `count`.
    pub distinct: f64,
    /// Whether its tables differ at two assignments.
    pub differ: bool,
    pub examples: usize,
    pub shapes: Vec<u64>,
    pub meta: Vec<(u8, u8, RootOf)>,
    /// Per shape and example, `:min`, `:mean` and `:max` over the assignments of each of its two
    /// numbers. An assignment where the shape has no entry counts its default, and one where a
    /// bound stopped it counts for nothing.
    pub pools: Vec<[f64; 6]>,
}

/// The vector of a table over its assignments, from its vector and its hash at each.
pub fn assignment_vector(tables: &[(u128, &TableVector)], capped: bool) -> AssignmentVector {
    let count = tables.len();
    let hashes: std::collections::BTreeSet<u128> = tables.iter().map(|(hash, _)| *hash).collect();
    let examples = tables.first().map_or(0, |(_, vector)| vector.examples);
    let mut all: Vec<(u64, (u8, u8, RootOf))> = tables.iter().flat_map(|(_, vector)| vector.shapes.iter().copied().zip(vector.meta.iter().copied())).collect();
    all.sort_unstable_by_key(|held| held.0);
    all.dedup_by_key(|held| held.0);
    let mut pools = Vec::with_capacity(all.len() * examples);
    for (shape, _) in &all {
        for example in 0..examples {
            let mut seen = Vec::with_capacity(count);
            for (_, vector) in tables {
                match vector.shapes.binary_search(shape) {
                    Ok(place) => {
                        let slot = &vector.at(place)[example];
                        match slot.state {
                            SlotState::NoValue => {}
                            SlotState::Default => seen.push((0.0, 0.0)),
                            SlotState::Value => seen.push((slot.greatest.float(), slot.second.float())),
                        }
                    }
                    // A table that has no such shape counts as 0, as a default does.
                    Err(_) => seen.push((0.0, 0.0)),
                }
            }
            let pool = |read: &dyn Fn(&(f64, f64)) -> f64| -> (f64, f64, f64) {
                if seen.is_empty() {
                    return (f64::NAN, f64::NAN, f64::NAN);
                }
                let values: Vec<f64> = seen.iter().map(read).collect();
                (values.iter().copied().fold(f64::INFINITY, f64::min), values.iter().sum::<f64>() / values.len() as f64, values.iter().copied().fold(f64::NEG_INFINITY, f64::max))
            };
            let (a, b, c) = pool(&|held| held.0);
            let (d, e, f) = pool(&|held| held.1);
            pools.push([a, b, c, d, e, f]);
        }
    }
    AssignmentVector {
        count,
        capped,
        distinct: hashes.len() as f64 / count.max(1) as f64,
        differ: hashes.len() >= 2,
        examples,
        shapes: all.iter().map(|held| held.0).collect(),
        meta: all.iter().map(|held| held.1).collect(),
        pools,
    }
}

/// A table's task-wide entries: each root with its two numbers once, as the specification gives,
/// from the table in its lifted form. A table with several models at an example has none.
pub struct TaskWideVector {
    pub shapes: Vec<u64>,
    pub meta: Vec<(u8, u8, RootOf)>,
    pub slots: Vec<Slot>,
}

pub fn task_wide_vector(table: &Stored, grids: &Grids, families: &Generators, d: usize, only_output: bool) -> Option<TaskWideVector> {
    let lifted = crate::generate::lifted_rows(&table.rows)?;
    let family = families.get_task_wide(table, d);
    let mut walker = Walker::new(&family);
    walker.examples = grids.inputs.len() as u32;
    let grid = |tables: &[Arc<Table>]| -> Vec<Vec<Arc<Table>>> { tables.iter().map(|table| vec![table.clone()]).collect() };
    let ex_output = crate::generate::lifted_rows(&grid(&grids.outputs))?;
    let ex_input = crate::generate::lifted_rows(&grid(&grids.inputs))?;
    let leaves = vec![
        vec![crate::native::Val::of_table(lifted)],
        vec![crate::native::Val::of_table(ex_output)],
        vec![crate::native::Val::of_table(ex_input)],
        vec![crate::native::Val::None],
    ];
    let found = walker.walk(&leaves, 1, only_output);
    let order = found.sorted_roots();
    Some(TaskWideVector {
        shapes: order.iter().map(|held| held.0 as u64).collect(),
        meta: order.iter().map(|held| found.meta[held.1]).collect(),
        slots: order.iter().map(|held| found.slots[held.1]).collect(),
    })
}
