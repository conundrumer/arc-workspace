//! `lib-compare`: the comparison of the lib with the Souffle lib. It
//! compares each solver with its expanded form, so each lib name that has a
//! definition with that definition inside every solver that uses it, and
//! each lib relation and component with its Souffle version on small
//! generated inputs, each in its eight D4 images and under one color
//! permutation, as `docs/engine/verification.md#lib-comparison` gives.
//!
//! Its arguments: the directory of the lib snapshot, the corpus directory,
//! the directory of the expanded corpus, and the directory of the task
//! files. The command writes each element's inputs under `inputs/` of the
//! snapshot's directory, and reads the Souffle rows of each from the
//! record `scripts/souffle_parity.py lib` writes beside them, under the
//! element's name. It starts no Souffle run.
//!
//! # An inputs file
//!
//! A JSON object: `element`, the element's arclog name; `kind`, `relation`
//! or `component`; `constants`, the name of each orientation constant of
//! the registry; and by kind:
//!
//! - a relation: `columns`, each column's name and the kind of its values;
//!   `domains`, the constants of each column of an orientation type;
//!   `modes`, for each mode, `mode`, the names of its columns, and `rows`,
//!   the rows of those columns. A relation with no mode has one mode of no
//!   column and one empty row.
//! - a component: `type_arguments`, the type each type parameter takes;
//!   `inputs`, each input's `port`, `columns` and `rows`; `outputs`, each
//!   output's `port` and `columns`.
//!
//! A value is a number, a Box as its margins `[t, b, l, r]`, or the name
//! of an orientation constant. The kind of a column's values is `number`,
//! `box` or `constant`.
//!
//! An element of the Souffle lib that declares no input of the element's
//! has a second inputs file, `<element>.souffle.json`, in which each such
//! input holds no row, and the Souffle side runs that file.

use std::collections::{BTreeMap, BTreeSet};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use arclog::algebra::orientation::{D4Element, Edge, Geometry};
use arclog::algebra::{algebra, Algebra};
use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::eval::instance::Constructions;
use arclog::eval::{Caps, Cancellation, Evaluation, GridValue, Limits, ParameterValues};
use arclog::harness::{read_corpus_solver, run_over_corpus, SolverResult};
use arclog::program::ColumnName;
use arclog::registry::{AlgebraRelation, Column, ColumnType, Component, LibEntry, LibName, Macro, Registry};
use arclog::resolver::resolve;
use arclog::session::{SessionBound, TaskSession};
use arclog::task::read_task;
use arclog::terms::{Color, Constant, Margins, Number, Term, TermId};
use arclog::types::ValueType;
use serde_json::{json, Value};

const USAGE: &str = "usage: arclog-cli lib-compare <lib-snapshot-dir> <corpus-dir> <expanded-corpus-dir> <tasks-dir>";

/// The call that writes the Souffle records of the inputs files.
const SOUFFLE_CALL: &str = "uv run python scripts/souffle_parity.py lib";

/// The bound on the bytes of the task session of each solver's run.
const SESSION_BYTES: usize = 1 << 32;

/// The seed of the inputs, so that a run gives the same inputs each time.
const SEED: u64 = 0x9e37_79b9_7f4a_7c15;

/// The rows of each mode of a relation's inputs, and of each input of a
/// component's.
const ROWS: usize = 12;

/// The values of one type that a component's inputs draw from, few so that
/// the rows of two inputs meet.
const POOL: usize = 4;

/// The height and width of the one frame that every generated Box lies
/// in, so that the Positions of one inputs file are cells of one grid.
const FRAME: (usize, usize) = (4, 5);

/// The type each type parameter of a component takes in its inputs, and
/// its name as arclog and Souffle write it.
const PARAMETER_TYPE: (ValueType, &str) = (ValueType::Box, "Box");

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    let [snapshot, corpus, expanded, tasks] = args else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let snapshot = PathBuf::from(snapshot);
    if let Err(error) = std::fs::create_dir_all(snapshot.join("inputs")) {
        eprintln!("{} cannot be made: {error}", snapshot.join("inputs").display());
        return ExitCode::from(2);
    }
    silence_panics();
    let mut report = Report::default();
    for element in elements() {
        report.element(&snapshot, &element);
    }
    let solvers = compare_solvers(Path::new(corpus), Path::new(expanded), Path::new(tasks));
    match solvers {
        Ok((differ, not_compared)) => {
            report.solvers = differ;
            report.not_compared.extend(not_compared);
        }
        Err(message) => {
            eprintln!("{message}");
            return ExitCode::from(2);
        }
    }
    report.print()
}

/// What the command found, by the part of the comparison that found it.
#[derive(Default)]
struct Report {
    /// Each element compared and found the same, by name.
    compared: Vec<String>,
    /// Each line on an element whose rows differ.
    differ: Vec<String>,
    /// Each line on an element or a solver not compared, with its reason.
    not_compared: Vec<String>,
    /// Each line on a solver whose two forms differ.
    solvers: Vec<String>,
}

impl Report {
    /// Writes the inputs of `element` and adds what its comparisons give.
    fn element(&mut self, snapshot: &Path, element: &Element<'_>) {
        let inputs = element.inputs();
        let path = inputs_path(snapshot, element.name(), "");
        if let Err(message) = write_json(&path, &inputs) {
            self.not_compared.push(format!("{}: {message}", element.name()));
            return;
        }
        let record = read_record(snapshot, element.name(), &inputs);
        let emptied = match &record {
            Record::Undeclared(ports) => ports.clone(),
            _ => Vec::new(),
        };
        let souffle_inputs = (!emptied.is_empty()).then(|| emptied_inputs(&inputs, &emptied));
        if let Some(souffle_inputs) = &souffle_inputs {
            if let Err(message) = write_json(&inputs_path(snapshot, element.name(), ".souffle"), souffle_inputs) {
                self.not_compared.push(format!("{}: {message}", element.name()));
                return;
            }
        }
        let Element::Relation { name, relation, .. } = element else {
            let note = if emptied.is_empty() { String::new() } else { format!(", with {} left empty", emptied.join(", ")) };
            self.not_compared.push(format!("{}: the engine evaluates no construction outside a case program{note}", element.name()));
            return;
        };
        let Some(native) = algebra(&LibName(name.clone())) else {
            self.not_compared.push(format!("{name}: the engine does not evaluate it"));
            return;
        };
        let rows = match evaluated(native, relation, &inputs) {
            Ok(rows) => rows,
            Err(message) => {
                self.not_compared.push(format!("{name}: the engine's run stops: {message}"));
                return;
            }
        };
        let mut lines = Vec::new();
        let against_souffle = match record {
            Record::Rows(souffle) => {
                lines.extend(differences(name, "Souffle", &rows, &souffle));
                true
            }
            Record::NoSouffleForm => {
                self.not_compared.push(format!("{name}: against Souffle: the Souffle lib has no form of it"));
                false
            }
            Record::Failed(failure) => {
                self.not_compared.push(format!("{name}: against Souffle: the Souffle run fails: {failure}"));
                false
            }
            Record::Missing => {
                self.not_compared.push(format!("{name}: against Souffle: no record of these inputs; `{SOUFFLE_CALL}` writes it"));
                false
            }
            Record::Undeclared(_) => unreachable!("a relation has no input of its Souffle form left undeclared"),
        };
        lines.extend(image_differences(name, native, relation, &inputs, &rows));
        if !lines.is_empty() {
            self.differ.extend(lines);
            self.differ.push(format!("{name}: its inputs are {}", path.display()));
        } else if against_souffle {
            self.compared.push(name.to_string());
        } else {
            self.compared.push(format!("{name} (its images alone)"));
        }
    }

    /// Prints the report, and gives success where nothing differs.
    fn print(&self) -> ExitCode {
        for line in self.differ.iter().chain(&self.solvers) {
            println!("{line}");
        }
        for line in &self.not_compared {
            println!("not compared: {line}");
        }
        println!("compared: {}", self.compared.join(", "));
        println!(
            "{} elements compared the same, {} lines on elements that differ, {} solvers whose two forms differ, {} elements and solvers not compared",
            self.compared.len(),
            self.differ.len(),
            self.solvers.len(),
            self.not_compared.len()
        );
        if self.differ.is_empty() && self.solvers.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
    }
}

/// A lib element the registry declares: a relation or a relation macro,
/// or a component.
enum Element<'r> {
    Relation { name: Box<str>, relation: &'r AlgebraRelation },
    Component { name: Box<str>, component: &'r Component },
}

/// Each relation, relation macro and component of the registry, in the
/// order of their names.
fn elements() -> Vec<Element<'static>> {
    let registry = Registry::get();
    let mut names: Vec<&LibName> = registry.names().collect();
    names.sort_by(|a, b| a.0.cmp(&b.0));
    names
        .into_iter()
        .filter_map(|name| {
            let name_text = name.0.clone();
            match registry.entry(name)? {
                LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => {
                    Some(Element::Relation { name: name_text, relation })
                }
                LibEntry::Component(component) => Some(Element::Component { name: name_text, component }),
                LibEntry::Proposer(_) => None,
            }
        })
        .collect()
}

impl Element<'_> {
    fn name(&self) -> &str {
        match self {
            Element::Relation { name, .. } | Element::Component { name, .. } => name,
        }
    }

    /// The element's inputs file, generated from its columns.
    fn inputs(&self) -> Value {
        let mut random = Random::of(self.name());
        let constants: BTreeSet<&str> = Geometry::get()
            .domain(&ValueType::Dir8)
            .iter()
            .chain(Geometry::get().domain(&ValueType::Axis4))
            .chain(Geometry::get().domain(&ValueType::D4))
            .chain(Geometry::get().domain(&ValueType::Sym))
            .chain(Geometry::get().domain(&ValueType::Sense))
            .map(|&id| constant_name(id))
            .collect();
        let mut out = json!({ "element": self.name(), "constants": constants.into_iter().collect::<Vec<_>>() });
        match self {
            Element::Relation { relation, .. } => {
                let modes: Vec<Vec<usize>> = if relation.modes.is_empty() {
                    vec![Vec::new()]
                } else {
                    relation.modes.iter().map(|mode| mode.grounded.iter().map(|c| column_index(relation, c)).collect()).collect()
                };
                let modes: Vec<Value> = modes
                    .iter()
                    .map(|mode| {
                        let count = if mode.is_empty() { 1 } else { ROWS };
                        let rows: Vec<Value> =
                            (0..count).map(|_| Value::from(mode.iter().map(|&i| random.value(&relation_type(&relation.columns[i]))).collect::<Vec<_>>())).collect();
                        let names: Vec<String> = mode.iter().map(|&i| column_text(&relation.columns[i].name)).collect();
                        json!({ "mode": names, "rows": rows })
                    })
                    .collect();
                let domains: BTreeMap<String, Vec<&str>> = relation
                    .columns
                    .iter()
                    .filter(|c| is_orientation(&relation_type(c)))
                    .map(|c| (column_text(&c.name), constant_names(&relation_type(c))))
                    .collect();
                out["kind"] = json!("relation");
                out["columns"] = columns_json(&relation.columns, &|c| relation_type(c));
                out["domains"] = json!(domains);
                out["modes"] = Value::from(modes);
            }
            Element::Component { component, .. } => {
                let ty = |column: &Column| component_type(column);
                let mut pools: Vec<(ValueType, Vec<Value>)> = Vec::new();
                let mut pooled = |ty: &ValueType| -> Value {
                    let at = match pools.iter().position(|(t, _)| t == ty) {
                        Some(at) => at,
                        None => {
                            let pool = (0..POOL).map(|_| random.value(ty)).collect();
                            pools.push((ty.clone(), pool));
                            pools.len() - 1
                        }
                    };
                    let index = random.below(POOL);
                    pools[at].1[index].clone()
                };
                let inputs: Vec<Value> = component
                    .inputs
                    .iter()
                    .map(|input| {
                        let rows: BTreeSet<String> = (0..ROWS)
                            .map(|_| Value::from(input.port.columns.iter().map(|c| pooled(&ty(c))).collect::<Vec<_>>()).to_string())
                            .collect();
                        let rows: Vec<Value> = rows.iter().map(|row| serde_json::from_str(row).expect("a row as JSON")).collect();
                        json!({ "port": &*input.port.name.0, "columns": columns_json(&input.port.columns, &ty), "rows": rows })
                    })
                    .collect();
                let outputs: Vec<Value> = component
                    .outputs
                    .iter()
                    .map(|output| json!({ "port": &*output.name.0, "columns": columns_json(&output.columns, &ty) }))
                    .collect();
                out["kind"] = json!("component");
                out["type_arguments"] = Value::from(vec![PARAMETER_TYPE.1; component.type_parameters.len()]);
                out["inputs"] = Value::from(inputs);
                out["outputs"] = Value::from(outputs);
            }
        }
        out
    }
}

/// The type of a relation's column: a Pose column takes D4's constants.
fn relation_type(column: &Column) -> ValueType {
    match &column.ty {
        ColumnType::Fixed(ty) | ColumnType::PoseOr(ty) => ty.clone(),
        ColumnType::Pose | ColumnType::SharedPose => ValueType::D4,
        ColumnType::Parameter(_) => panic!("a relation's column is of no type parameter"),
    }
}

/// The type of a component's column, a type parameter taking
/// [`PARAMETER_TYPE`].
fn component_type(column: &Column) -> ValueType {
    match &column.ty {
        ColumnType::Parameter(_) => PARAMETER_TYPE.0,
        _ => relation_type(column),
    }
}

fn column_index(relation: &AlgebraRelation, name: &ColumnName) -> usize {
    relation.columns.iter().position(|c| c.name == *name).expect("a mode's column is a column of its relation")
}

fn column_text(name: &ColumnName) -> String {
    match name {
        ColumnName::Written(text) => text.to_string(),
        ColumnName::Slot(slot) => format!("#{slot}"),
    }
}

/// Each column's name and the kind of its values.
fn columns_json(columns: &[Column], ty: &dyn Fn(&Column) -> ValueType) -> Value {
    Value::from(columns.iter().map(|c| json!([column_text(&c.name), value_kind(&ty(c))])).collect::<Vec<_>>())
}

/// The kind of the values of `ty` in an inputs file.
fn value_kind(ty: &ValueType) -> &'static str {
    if is_orientation(ty) {
        "constant"
    } else if *ty == ValueType::Box {
        "box"
    } else {
        "number"
    }
}

fn is_orientation(ty: &ValueType) -> bool {
    !matches!(ty, ValueType::Number | ValueType::Color | ValueType::Example | ValueType::Unit | ValueType::Box | ValueType::Ident | ValueType::Record(_))
}

fn constant_name(id: TermId) -> &'static str {
    let registry = Registry::get();
    for ty in [ValueType::Dir8, ValueType::Axis4, ValueType::D4, ValueType::Sym, ValueType::Sense] {
        if Geometry::get().domain(&ty).contains(&id) {
            if let Term::Constant(Constant::Orientation(c)) = Term::decode(id, &ty) {
                return registry.constant_name(c);
            }
        }
    }
    panic!("an orientation constant's term id")
}

/// The names of the constants of the orientation type `ty`, in their
/// order.
fn constant_names(ty: &ValueType) -> Vec<&'static str> {
    let names: BTreeSet<&str> = Geometry::get().domain(ty).iter().map(|&id| constant_name(id)).collect();
    names.into_iter().collect()
}

/// A fixed generator of the inputs: SplitMix64 from a seed and the
/// element's name, so that an element's inputs do not change when another
/// element is added.
struct Random(u64);

impl Random {
    fn of(name: &str) -> Random {
        Random(name.bytes().fold(SEED, |state, byte| (state ^ u64::from(byte)).wrapping_mul(0x0100_0000_01b3)))
    }

    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    }

    fn below(&mut self, n: usize) -> usize {
        (self.next() % n as u64) as usize
    }

    /// A value of `ty`: a number from 0 to 5, a Box of [`FRAME`], half of
    /// them a cell, a color, or a constant of an orientation type, picked
    /// from its constants in the order of their names.
    fn value(&mut self, ty: &ValueType) -> Value {
        match ty {
            ValueType::Box => {
                let cell = self.below(2) == 0;
                let mut span = |extent: usize| {
                    let near = self.below(extent);
                    let far = if cell { extent - 1 - near } else { self.below(extent - near) };
                    (near, far)
                };
                let ((top, bottom), (left, right)) = (span(FRAME.0), span(FRAME.1));
                json!([top, bottom, left, right])
            }
            ValueType::Color => Value::from(self.below(10)),
            _ if is_orientation(ty) => {
                let names = constant_names(ty);
                Value::from(names[self.below(names.len())])
            }
            _ => Value::from(self.below(6)),
        }
    }
}

fn inputs_path(snapshot: &Path, element: &str, suffix: &str) -> PathBuf {
    snapshot.join("inputs").join(format!("{element}{suffix}.json"))
}

fn write_json(path: &Path, value: &Value) -> Result<(), String> {
    let text = serde_json::to_string(value).expect("JSON prints");
    std::fs::write(path, text + "\n").map_err(|error| format!("{} cannot be written: {error}", path.display()))
}

/// The inputs with each input of `ports` holding no row.
fn emptied_inputs(inputs: &Value, ports: &[String]) -> Value {
    let mut out = inputs.clone();
    for input in out["inputs"].as_array_mut().into_iter().flatten() {
        if input["port"].as_str().is_some_and(|port| ports.iter().any(|p| p == port)) {
            input["rows"] = json!([]);
        }
    }
    out
}

/// The Souffle side of an element, as its record gives it.
enum Record {
    /// The rows of each mode, or of each output, each as JSON text.
    Rows(Vec<BTreeSet<String>>),
    /// The Souffle lib has no form of the element.
    NoSouffleForm,
    /// The kind of the Souffle run's failure.
    Failed(String),
    /// The inputs of the element that its Souffle form does not declare.
    Undeclared(Vec<String>),
    /// No record of the element's present inputs.
    Missing,
}

/// The record of `element` whose inputs are `inputs`: that of its second
/// inputs file where the record of `inputs` gives undeclared inputs and the
/// second file has a record.
fn read_record(snapshot: &Path, element: &str, inputs: &Value) -> Record {
    let record = record_of(&snapshot.join(format!("{element}.json")), inputs);
    let Record::Undeclared(ports) = &record else { return record };
    match record_of(&snapshot.join(format!("{element}.souffle.json")), &emptied_inputs(inputs, ports)) {
        Record::Missing => record,
        second => second,
    }
}

fn record_of(path: &Path, inputs: &Value) -> Record {
    let Ok(text) = std::fs::read_to_string(path) else { return Record::Missing };
    let Ok(record) = serde_json::from_str::<Value>(&text) else { return Record::Missing };
    if record.get("inputs") != Some(inputs) {
        return Record::Missing;
    }
    if let Some(ports) = record.get("undeclared").and_then(Value::as_array) {
        return Record::Undeclared(ports.iter().filter_map(Value::as_str).map(str::to_owned).collect());
    }
    if record.get("no_souffle_form").and_then(Value::as_bool) == Some(true) {
        return Record::NoSouffleForm;
    }
    if let Some(failure) = record.get("failure").and_then(Value::as_str) {
        return Record::Failed(failure.to_owned());
    }
    match record.get("rows").and_then(Value::as_array) {
        Some(parts) => Record::Rows(parts.iter().map(|rows| rows.as_array().into_iter().flatten().map(Value::to_string).collect()).collect()),
        None => Record::Missing,
    }
}

/// The engine's rows of each mode of the relation's inputs, each row as
/// JSON text, or the stop of the run or the panic of an evaluation the
/// engine does not yet give.
fn evaluated(native: &dyn Algebra, relation: &AlgebraRelation, inputs: &Value) -> Result<Vec<BTreeSet<String>>, String> {
    let types: Vec<ValueType> = relation.columns.iter().map(relation_type).collect();
    let mut out = Vec::new();
    for mode in inputs["modes"].as_array().into_iter().flatten() {
        let columns = mode_columns(relation, mode);
        let mut rows = BTreeSet::new();
        for probe in mode["rows"].as_array().into_iter().flatten() {
            let mut bound = vec![None; types.len()];
            for (&column, value) in columns.iter().zip(probe.as_array().into_iter().flatten()) {
                bound[column] = Some(term_id(value, &types[column])?);
            }
            let mut emitted = Vec::new();
            let run = catch_unwind(AssertUnwindSafe(|| {
                native.evaluate(&bound, Registry::get(), &mut |row| emitted.push(row.to_vec()))
            }));
            match run {
                Ok(Ok(())) => {}
                Ok(Err(reached)) => return Err(format!("a Box past the margin bound: {:?}", reached.margins)),
                Err(_) => return Err(format!("a panic at {}", last_panic())),
            }
            rows.extend(emitted.iter().map(|row| row_json(row, &types).to_string()));
        }
        out.push(rows);
    }
    Ok(out)
}

/// The index of each column of a mode of an inputs file, in the mode's
/// order.
fn mode_columns(relation: &AlgebraRelation, mode: &Value) -> Vec<usize> {
    let names = mode["mode"].as_array().into_iter().flatten().filter_map(Value::as_str);
    names.map(|name| relation.columns.iter().position(|c| column_text(&c.name) == name).expect("a mode's column is a column of its relation")).collect()
}

/// The term id of an inputs file's `value` at type `ty`.
fn term_id(value: &Value, ty: &ValueType) -> Result<TermId, String> {
    let term = match (ty, value) {
        (ValueType::Box, Value::Array(m)) => {
            let margin = |i: usize| m.get(i).and_then(Value::as_i64).map(|n| n as i32).ok_or_else(|| format!("{value} is no Box"));
            Term::Box(Margins { top: margin(0)?, bottom: margin(1)?, left: margin(2)?, right: margin(3)? })
        }
        (ValueType::Color, Value::Number(n)) => {
            let digit = n.as_u64().and_then(|d| u8::try_from(d).ok()).and_then(Color::from_digit).ok_or_else(|| format!("{value} is no color"))?;
            Term::Constant(Constant::Color(digit))
        }
        (_, Value::String(name)) if is_orientation(ty) => {
            Term::Constant(Constant::Orientation(Registry::get().orientation_constant(name).ok_or_else(|| format!("{name} is no constant"))?))
        }
        (_, Value::Number(n)) => Term::Number(Number(n.as_i64().ok_or_else(|| format!("{value} is no number"))? as i32)),
        _ => return Err(format!("{value} is no value of {ty:?}")),
    };
    term.encode().map_err(|reached| format!("a Box past the margin bound: {:?}", reached.margins))
}

/// A row as an inputs file writes its values.
fn row_json(row: &[TermId], types: &[ValueType]) -> Value {
    Value::from(row.iter().zip(types).map(|(&id, ty)| value_json(id, ty)).collect::<Vec<_>>())
}

fn value_json(id: TermId, ty: &ValueType) -> Value {
    match Term::decode(id, ty) {
        Term::Number(Number(n)) => Value::from(n),
        Term::Box(m) => json!([m.top, m.bottom, m.left, m.right]),
        Term::Constant(Constant::Color(color)) => Value::from(digit(color)),
        Term::Constant(Constant::Orientation(c)) => Value::from(Registry::get().constant_name(c)),
        other => Value::from(format!("{other:?}")),
    }
}

/// Each line on a difference between the engine's rows and `other`'s, by
/// mode.
fn differences(name: &str, other: &str, engine: &[BTreeSet<String>], expected: &[BTreeSet<String>]) -> Vec<String> {
    if engine.len() != expected.len() {
        return vec![format!("{name}: the engine gives {} modes, {other} {}", engine.len(), expected.len())];
    }
    let mut lines = Vec::new();
    for (mode, (got, want)) in engine.iter().zip(expected).enumerate() {
        let extra: Vec<&String> = got.difference(want).collect();
        let missing: Vec<&String> = want.difference(got).collect();
        if !extra.is_empty() || !missing.is_empty() {
            lines.push(format!(
                "{name}, mode {mode}: against {other}, the engine gives {} rows {other} lacks, such as {}, and lacks {} rows, such as {}",
                extra.len(),
                extra.first().map_or("none", |r| r.as_str()),
                missing.len(),
                missing.first().map_or("none", |r| r.as_str())
            ));
        }
    }
    lines
}

/// The images the comparison runs the inputs under: each D4 element by its
/// constant's name, and one color permutation.
enum Image {
    D4(&'static str, D4Element),
    Colors,
}

impl Image {
    fn each() -> Vec<Image> {
        let geometry = Geometry::get();
        let elements: BTreeMap<&str, D4Element> = geometry.domain(&ValueType::D4).iter().map(|&id| (constant_name(id), geometry.element(id))).collect();
        elements.into_iter().map(|(name, g)| Image::D4(name, g)).chain([Image::Colors]).collect()
    }

    fn name(&self) -> String {
        match self {
            Image::D4(name, _) => format!("the D4 image {name}"),
            Image::Colors => "the color permutation".to_owned(),
        }
    }

    /// The image of `value`, a value of `ty` as this command writes it.
    fn of(&self, value: &Value, ty: &ValueType) -> Value {
        let id = term_id(value, ty).expect("a value this command wrote");
        let image = match (self, Term::decode(id, ty)) {
            (Image::D4(_, g), Term::Box(m)) => {
                // The margin at each edge goes to that edge's image.
                let mut out = [0; 4];
                for (margin, edge) in [m.top, m.bottom, m.left, m.right].into_iter().zip(Edge::ALL) {
                    out[g.image(edge) as usize] = margin;
                }
                let [top, bottom, left, right] = out;
                Term::Box(Margins { top, bottom, left, right }).encode().expect("a Box's image has its margins")
            }
            (Image::D4(_, g), Term::Constant(Constant::Orientation(_))) => Geometry::get().under(*g, id),
            (Image::Colors, Term::Constant(Constant::Color(color))) => {
                let digit = digit(color);
                Term::Constant(Constant::Color(Color::from_digit((digit * 3 + 1) % 10).expect("a digit is a color"))).encode().expect("a color's id")
            }
            _ => id,
        };
        value_json(image, ty)
    }

    fn row(&self, row: &Value, types: &[ValueType]) -> Value {
        Value::from(row.as_array().into_iter().flatten().zip(types).map(|(v, ty)| self.of(v, ty)).collect::<Vec<_>>())
    }
}

/// Each line on an image of the inputs whose rows are not the image of the
/// rows of the inputs.
fn image_differences(name: &str, native: &dyn Algebra, relation: &AlgebraRelation, inputs: &Value, rows: &[BTreeSet<String>]) -> Vec<String> {
    let types: Vec<ValueType> = relation.columns.iter().map(relation_type).collect();
    let mut lines = Vec::new();
    for image in Image::each() {
        let mut moved = inputs.clone();
        for mode in moved["modes"].as_array_mut().into_iter().flatten() {
            let mode_types: Vec<ValueType> = mode_columns(relation, mode).into_iter().map(|i| types[i].clone()).collect();
            let probes: Vec<Value> = mode["rows"].as_array().into_iter().flatten().map(|row| image.row(row, &mode_types)).collect();
            mode["rows"] = Value::from(probes);
        }
        let expected: Vec<BTreeSet<String>> = rows
            .iter()
            .map(|set| set.iter().map(|row| image.row(&serde_json::from_str(row).expect("a row as JSON"), &types).to_string()).collect())
            .collect();
        match evaluated(native, relation, &moved) {
            Ok(got) => lines.extend(differences(name, &format!("the rows' image under {}", image.name()), &got, &expected)),
            Err(message) => lines.push(format!("{name}: under {}, the engine's run stops: {message}", image.name())),
        }
    }
    lines
}

/// The lines on the solvers of the corpus: each solver whose concept case
/// gives other grids than in the expanded corpus, then each that is not
/// compared, with what stops it, each in the order of the task ids.
fn compare_solvers(corpus: &Path, expanded: &Path, tasks: &Path) -> Result<(Vec<String>, Vec<String>), String> {
    let found = std::sync::Mutex::new(BTreeMap::new());
    run_over_corpus(corpus, |solver| {
        let id = &solver.task_id;
        let line = match (outcomes(corpus, tasks, id), outcomes(expanded, tasks, id)) {
            (Ok(a), Ok(b)) if a == b => None,
            (Ok(a), Ok(b)) => {
                let pairs: Vec<String> = a.iter().zip(&b).filter(|(x, y)| x != y).map(|(x, _)| x.0.clone()).collect();
                Some(Ok(format!("{id}: the two forms differ at {}", pairs.join(", "))))
            }
            (Err(fault), _) => Some(Err(format!("{id}: the given form: {fault}"))),
            (_, Err(fault)) => Some(Err(format!("{id}: the expanded form: {fault}"))),
        };
        if let Some(line) = line {
            found.lock().expect("no check panics holding the lock").insert(id.clone(), line);
        }
        SolverResult::Pass
    })
    .map_err(|error| format!("the corpus does not read: {error:?}"))?;
    let found = found.into_inner().expect("no check panics holding the lock");
    let (differ, not_compared): (Vec<_>, Vec<_>) = found.into_values().partition(Result::is_ok);
    Ok((differ.into_iter().filter_map(Result::ok).collect(), not_compared.into_iter().filter_map(Result::err).collect()))
}

/// The outcome of the concept case of the solver `id` of `corpus` on each
/// example, with the example's place in the task, or the fault that stops
/// it; a form the engine does not yet evaluate gives the place of its
/// panic.
fn outcomes(corpus: &Path, tasks: &Path, id: &str) -> Result<Vec<(String, String)>, String> {
    catch_unwind(|| concept_outcomes(corpus, tasks, id)).unwrap_or_else(|_| Err(format!("the engine does not yet evaluate a form it reads: {}", last_panic())))
}

fn concept_outcomes(corpus: &Path, tasks: &Path, id: &str) -> Result<Vec<(String, String)>, String> {
    let solver = read_corpus_solver(corpus, id).ok_or("the solver's files do not read")?;
    let task = read_task(&tasks.join(format!("{id}.json"))).map_err(|error| format!("the task does not read: {error:?}"))?;
    let registry = Registry::get();
    let case = solver.concept_case();
    let resolved = resolve(&case.program, None, &solver.derived_relations(), registry).value;
    let clauses = SolverClauses::of(&solver, registry);
    let program = check_program(resolved, &clauses, registry, &mut CheckCache::default()).map_err(|refusals| {
        let messages: Vec<&str> = refusals.iter().map(|d| &*d.message).collect();
        format!("the checker refuses the concept case: {}", messages.join("; "))
    })?;
    let parameters = ParameterValues::stored(solver.arcdata.value());
    let session = TaskSession::new(SessionBound { bytes: SESSION_BYTES }, Caps::PROVISIONAL);
    let constructions = Constructions::new(Vec::new(), registry).map_err(|fault| format!("no table of constructions: {fault:?}"))?;
    let limits = Limits { deadline: None, cancellation: Cancellation::default() };
    let evaluation = Evaluation { program: &program, task: &task, parameters: &parameters, session: &session, registry, constructions: &constructions, limits: &limits };
    let outputs = evaluation.outputs().map_err(|fault| format!("a fault of the run at {:?}: {}", fault.form, fault.message))?;
    let outputs = outputs.map_err(|reason| format!("the case gives no grid columns of `&output`: {reason:?}"))?;
    Ok(outputs.iter().enumerate().map(|(index, (_, grid))| (format!("example {index}"), grid_text(grid))).collect())
}

fn grid_text(grid: &GridValue) -> String {
    match grid {
        GridValue::Grid(grid) => format!("{:?}", grid.rows()),
        GridValue::Undefined => "undefined".to_owned(),
        GridValue::Stopped(stop) => format!("a stop at {:?}", stop.bound),
    }
}

std::thread_local! {
    /// The place of the last panic on this thread.
    static PANIC: std::cell::RefCell<String> = const { std::cell::RefCell::new(String::new()) };
}

/// Keeps a panic's place for [`last_panic`] in place of printing it, since
/// each form the engine does not yet evaluate panics.
fn silence_panics() {
    std::panic::set_hook(Box::new(|info| {
        let place = info.location().map_or("an unknown place".to_owned(), |l| format!("{}:{}", l.file(), l.line()));
        PANIC.with(|p| *p.borrow_mut() = place);
    }));
}

fn last_panic() -> String {
    PANIC.with(|p| p.borrow().clone())
}

/// The digit of `color`, as a task file writes it.
fn digit(color: Color) -> u8 {
    (0u8..=9).find(|&d| Color::from_digit(d) == Some(color)).expect("a color has a digit")
}
