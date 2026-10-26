//! The confirmed rules of a `DEMONSTRATED` form on one input, as
//! `docs/engine/cases.md#demonstrated` gives them.
//!
//! The form's key clause gives its keys. At each key, the `value` input
//! gives the rows of the objects, and the `demonstration` input gives the
//! pairs `(o, o2)` of objects. The `&prediction` clauses of a `DEMO_RULE`
//! give the rule's predictions, whose columns are named as the key's columns
//! and the columns of the `value` head are, and are evaluated once for the
//! input, one entry that holds every key. A rule with fields stands for one
//! rule per value that its `&prediction` clauses bind for the fields.

use super::driver::{Driver, FormBodies};
use super::init_form::{grouped, joined_clause, key_clause_memo, key_rows, rows_of, site_labels};
use std::sync::Arc;

use super::ir::{self, ClauseIr, IrPaths};
use super::{Evaluation, Outcome, RelationValue, RunFault};
use crate::check::CheckedProgram;
use crate::hash::StableHashMap;
use crate::program::canonical::{prediction, relation_of};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{
    Body, ColumnName, DemoRule, Demonstrated, DemonstratedPart, Form, InstanceInput, InstanceInputPart, KeyClausePart, LabelId, RelationColumn,
};
use crate::relations::{Row, RowSet};
use crate::resolver::columns::projection;
use crate::safety::body_labels;
use crate::terms::{set_order, Example, TermId};
use crate::types::GraphRelation;

/// The name of the input that gives the rows of the objects, whose head
/// names the relation's columns after the key's.
const VALUE: &str = "value";
/// The name of the input that gives the pairs of objects of a key.
const DEMONSTRATION: &str = "demonstration";
/// The head site of the `value` and `demonstration` inputs that gives the
/// object, and the site of the `demonstration` input that gives the object
/// its prediction is to be consistent with.
const OBJECT: &str = "o";
const OBJECT_2: &str = "o2";
/// The head site of the `value` input that gives the index of a row.
const INDEX: &str = "i";

/// The clause that the evaluation joins for the body at `at`, a path after
/// the path `form` of the `DEMONSTRATED` form `demonstrated`: its key body,
/// or the body of its `value` input. `None` where `at` is neither, the
/// error where the clause does not compile.
pub(crate) fn clause_at(program: &CheckedProgram, demonstrated: &Demonstrated, form: &NodePath, at: &NodePath) -> Option<Result<(Arc<ClauseIr>, Arc<IrPaths>), String>> {
    let shape = Shape::of(demonstrated, form);
    if let Some(key_body) = shape.key_body.as_ref().filter(|(_, path)| path == at) {
        let found = key_clause_memo(program, form, key_body, &shape.key_labels());
        return Some(found.map(|(clause, paths, _)| (clause, paths)).map_err(|compile| format!("the key body does not compile: {compile:?}")));
    }
    let value = shape.inputs.iter().find(|input| *input.input.name.0 == *VALUE)?;
    if &value.path.child(value.input.position(InstanceInputPart::Body)) != at {
        return None;
    }
    let found = Head::of(value.input).and_then(|head| {
        shape.input_clause(program, form, value, &head.labels()).map(|(clause, paths, _)| (Arc::new(clause), Arc::new(paths))).map_err(|compile| format!("the input does not compile: {compile:?}"))
    });
    Some(found)
}

/// For each key of the `DEMONSTRATED` form of `relation` on `example` that
/// holds a demonstration and a confirmed rule, the distinct predictions of
/// its confirmed rules, each the rows of the relation at that key, in the
/// canonical order by content; or the value of a read that is `undefined`
/// or stopped.
pub(super) fn confirmed(driver: &Driver<'_, '_>, relation: &GraphRelation, example: Option<Example>) -> Outcome<Result<Vec<Vec<RowSet>>, RelationValue>> {
    let evaluation = driver.evaluation;
    let form = driver.program().form_of(relation.node);
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let root = NodeRef::Program(evaluation.program.program.program.value());
    let Some(NodeRef::Demonstrated(demonstrated)) = node_at(root, form) else { panic!("a `DEMONSTRATED` form at the form of its node") };
    let shape = Shape::of(demonstrated, form);
    let bodies = driver.bodies();
    let groups = match shape.groups(evaluation, &bodies, form, example)? {
        Ok(groups) => groups,
        Err(value) => return Ok(Err(value)),
    };
    let heads = shape.heads().map_err(&fault)?;
    let read = |input: &Input<'_>, labels: &[LabelId]| shape.input_rows(evaluation, &bodies, form, input, labels, &groups, example);
    let values = match read(heads.value_input, &heads.value.labels())? {
        Ok(values) => values,
        Err(value) => return Ok(Err(value)),
    };
    let demonstrations = match read(heads.demonstration_input, &heads.demonstration.labels())? {
        Ok(demonstrations) => demonstrations,
        Err(value) => return Ok(Err(value)),
    };
    let values: Vec<StableHashMap<Row, RowSet>> = values.iter().map(|rows| heads.value.by_object(rows)).collect();

    let mut candidates: Vec<Vec<RowSet>> = vec![Vec::new(); groups.len()];
    for (index, rule) in demonstrated.rules.iter().enumerate() {
        let path = form.child(demonstrated.position(DemonstratedPart::Rule(index)));
        let instances = match predictions(evaluation, &bodies, &shape, &heads, &path, rule.value(), &groups, example)? {
            Ok(instances) => instances,
            Err(value) => return Ok(Err(value)),
        };
        for sets in instances {
            for (at, set) in sets.iter().enumerate() {
                if demonstrations[at].is_empty() {
                    continue;
                }
                let predicted = heads.value.by_object(set);
                let confirms = demonstrations[at].rows().all(|pair| {
                    let pick = |positions: &[usize]| -> Row { positions.iter().map(|&position| pair[position]).collect() };
                    consistent(predicted.get(&pick(&heads.demonstration.object)), values[at].get(&pick(&heads.demonstration.other)), heads.value.index_width())
                });
                if confirms {
                    candidates[at].push(with_key(&groups[at], set));
                }
            }
        }
    }

    let types = evaluation.program.types.columns(relation).ok_or_else(|| fault("the relation's columns have no types".into()))?;
    let table = evaluation.session.intern.read().expect("an intern table that no panic poisoned");
    let order = |a: &RowSet, b: &RowSet| set_order(types, a.rows(), b.rows(), &table);
    let mut keys = Vec::new();
    for mut options in candidates {
        options.sort_by(&order);
        options.dedup_by(|a, b| order(a, b).is_eq());
        if !options.is_empty() {
            keys.push(options);
        }
    }
    Ok(Ok(keys))
}

/// Whether the prediction `predicted` for an object, rows of an index and a
/// value, with `index` columns of index first, is consistent with `shown`,
/// the rows of the object it is to equal, as `consistent` of the lib's
/// `DemonstrationConsistency` has it: the prediction holds a row, both hold
/// the same indices, and at each index both hold one value, the same.
fn consistent(predicted: Option<&RowSet>, shown: Option<&RowSet>, index: usize) -> bool {
    let (Some(predicted), Some(shown)) = (predicted, shown) else { return false };
    if predicted.is_empty() || predicted.len() != shown.len() {
        return false;
    }
    fn values(set: &RowSet, index: usize) -> StableHashMap<&[TermId], Vec<&[TermId]>> {
        let mut by: StableHashMap<&[TermId], Vec<&[TermId]>> = StableHashMap::default();
        for row in set.rows() {
            by.entry(&row[..index]).or_default().push(&row[index..]);
        }
        by
    }
    let (predicted, shown) = (values(predicted, index), values(shown, index));
    predicted.len() == shown.len() && predicted.iter().all(|(at, one)| one.len() == 1 && shown.get(at).is_some_and(|other| other == one))
}

/// `rows`, whose rows hold the columns of the `value` head, with the key
/// columns `key` before each.
fn with_key(key: &[TermId], rows: &RowSet) -> RowSet {
    let mut set = RowSet::empty(key.len() as u16 + rows.arity());
    for row in rows.rows() {
        set.insert(key.iter().chain(row).copied().collect());
    }
    set
}

/// An input the form writes, with its path and whether it stands in the key
/// clause.
struct Input<'p> {
    input: &'p InstanceInput,
    path: NodePath,
    keyed: bool,
}

/// What a `DEMONSTRATED` form gives the evaluation of its rules: its key
/// body and key columns, and the `value` and `demonstration` inputs.
struct Shape<'p> {
    key_body: Option<(&'p Body, NodePath)>,
    key_columns: &'p [RelationColumn],
    inputs: Vec<Input<'p>>,
}

impl<'p> Shape<'p> {
    /// The shape of `demonstrated`, the `DEMONSTRATED` form at `form`.
    fn of(demonstrated: &'p Demonstrated, form: &NodePath) -> Self {
        let key = demonstrated.key.as_ref().map(|key| key.value());
        let key_path = key.map(|_| form.child(demonstrated.position(DemonstratedPart::Key)));
        let key_body = key.zip(key_path.as_ref()).map(|(key, key_path)| (key.key.body.value(), key_path.child(key.position(KeyClausePart::Body))));
        let key_columns = key.map_or(&[][..], |key| &key.key.columns[..]);
        let mut inputs = Vec::new();
        if let Some((key, key_path)) = key.zip(key_path.as_ref()) {
            for (index, input) in key.inputs.iter().enumerate() {
                inputs.push(Input { input: input.value(), path: key_path.child(key.position(KeyClausePart::Input(index))), keyed: true });
            }
        }
        for (index, input) in demonstrated.inputs.iter().enumerate() {
            inputs.push(Input { input: input.value(), path: form.child(demonstrated.position(DemonstratedPart::Input(index))), keyed: false });
        }
        Shape { key_body, key_columns, inputs }
    }

    /// The labels of the key's columns.
    fn key_labels(&self) -> Vec<LabelId> {
        self.key_columns.iter().map(|column| column.label).collect()
    }

    /// The keys: the rows of the key clause, or the one empty row where the
    /// form has none, or the value of the key body where it holds no rows.
    fn groups(&self, evaluation: &Evaluation<'_>, bodies: &FormBodies<'_>, form: &NodePath, example: Option<Example>) -> Outcome<Result<Vec<Row>, RelationValue>> {
        Ok(key_rows(evaluation, bodies, form, &self.key_body, &self.key_labels(), example)?.map(|(groups, _)| groups))
    }

    /// The `value` and `demonstration` inputs with their head columns.
    fn heads(&self) -> Result<Heads<'_>, String> {
        let find = |name: &str| self.inputs.iter().find(|input| *input.input.name.0 == *name).ok_or_else(|| format!("the form writes no `{name}` input"));
        let (value_input, demonstration_input) = (find(VALUE)?, find(DEMONSTRATION)?);
        let value = Head::of(value_input.input)?;
        let demonstration = Head::of(demonstration_input.input)?;
        if demonstration.object.len() != value.object.len() || demonstration.other.len() != value.object.len() {
            return Err("the objects of the `value` and `demonstration` heads have different widths".into());
        }
        Ok(Heads { value_input, demonstration_input, value, demonstration })
    }

    /// The clause of `input`, whose head holds `labels`, with the paths of
    /// its nodes and the count of its key columns: its body, joined with the
    /// key clause where `input` is keyed.
    fn input_clause(&self, program: &CheckedProgram, form: &NodePath, input: &Input<'_>, labels: &[LabelId]) -> Result<(ClauseIr, IrPaths, usize), ir::CompileFault> {
        let body = (input.input.body.value(), input.path.child(input.input.position(InstanceInputPart::Body)));
        joined_clause(program, form, &self.key_body, &self.key_labels(), input.keyed, body, labels)
    }

    /// The rows of `input`, whose head holds `labels`, at each of `groups`.
    /// A keyed input is its body joined with the key body.
    #[allow(clippy::too_many_arguments)]
    fn input_rows(
        &self,
        evaluation: &Evaluation<'_>,
        bodies: &FormBodies<'_>,
        form: &NodePath,
        input: &Input<'_>,
        labels: &[LabelId],
        groups: &[Row],
        example: Option<Example>,
    ) -> Outcome<Result<Vec<RowSet>, RelationValue>> {
        let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
        let (clause, _, prefix) = self
            .input_clause(evaluation.program, form, input, labels)
            .map_err(|compile| fault(format!("the input `{}` does not compile: {compile:?}", input.input.name.0)))?;
        let rows = rows_of(evaluation, form, bodies.relation(form, &clause, example)?, prefix + labels.len()).map_err(&fault)?;
        Ok(rows.map(|rows| grouped(groups, prefix, labels.len(), rows)))
    }
}

/// The inputs that give a key's objects and demonstrations, with the columns
/// of their heads.
struct Heads<'p> {
    value_input: &'p Input<'p>,
    demonstration_input: &'p Input<'p>,
    value: Head,
    demonstration: Head,
}

/// The columns of the head of an input, in the order of its sites: each
/// with the name that a prediction names it by and its label, and the
/// positions of the object's columns, of the second object's, and of the
/// index's.
struct Head {
    columns: Vec<(Option<ColumnName>, LabelId)>,
    /// The positions of the columns of the site `o`.
    object: Vec<usize>,
    /// The positions of the columns of the site `o2`, or, where the input
    /// has none, of the columns other than the object's.
    other: Vec<usize>,
    /// The positions of the columns of the site `i`.
    index: Vec<usize>,
}

impl Head {
    /// The head of `input`: at each site, one column for a label, and one
    /// per field for a record, as the site names the fields. A column is
    /// named by the name its label has in the site.
    fn of(input: &InstanceInput) -> Result<Head, String> {
        let mut columns = Vec::new();
        let (mut object, mut other, mut index) = (Vec::new(), Vec::new(), Vec::new());
        let named_site = |site: &crate::program::Site, name: &str| site.column == ColumnName::Written(name.into());
        let second = input.head.iter().any(|site| named_site(site, OBJECT_2));
        for site in input.head.iter() {
            let at_site = site_labels(site);
            let named: Vec<(Option<ColumnName>, LabelId)> = match projection(site) {
                None => at_site.iter().map(|(path, label)| ((path.len() > 1).then(|| path.last().cloned()).flatten(), *label)).collect(),
                Some(fields) => {
                    let mut named = Vec::new();
                    for field in fields.iter() {
                        let found = at_site.iter().find(|(path, _)| path.last() == Some(field) && path.len() > 1);
                        let (_, label) = found.ok_or_else(|| format!("the head site {:?} of input `{}` gives no label of field {field:?}", site.column, input.name.0))?;
                        named.push((Some(field.clone()), *label));
                    }
                    named
                }
            };
            let positions = columns.len()..columns.len() + named.len();
            if named_site(site, OBJECT) {
                object.extend(positions);
            } else if named_site(site, INDEX) {
                index.extend(positions);
            } else if !second || named_site(site, OBJECT_2) {
                other.extend(positions);
            }
            columns.extend(named);
        }
        if object.is_empty() {
            return Err(format!("the input `{}` has no head site `{OBJECT}`", input.name.0));
        }
        Ok(Head { columns, object, other, index })
    }

    /// The labels of the columns.
    fn labels(&self) -> Vec<LabelId> {
        self.columns.iter().map(|(_, label)| *label).collect()
    }

    /// The count of the columns of an index.
    fn index_width(&self) -> usize {
        self.index.len()
    }

    /// `rows`, rows of the head, by the object: for each object, the rows of
    /// its index's columns and then the other columns, those of the object's
    /// left out.
    fn by_object(&self, rows: &RowSet) -> StableHashMap<Row, RowSet> {
        let rest: Vec<usize> = self.index.iter().copied().chain((0..self.columns.len()).filter(|at| !self.object.contains(at) && !self.index.contains(at))).collect();
        let mut by: StableHashMap<Row, RowSet> = StableHashMap::default();
        for row in rows.rows() {
            let object: Row = self.object.iter().map(|&at| row[at]).collect();
            by.entry(object).or_insert_with(|| RowSet::empty(rest.len() as u16)).insert(rest.iter().map(|&at| row[at]).collect());
        }
        by
    }
}

/// The predictions of the rule `rule`, at `rule_path`, at each of
/// `groups`: for each rule that it stands for, one per value its
/// `&prediction` clauses bind for the fields, the rows of the `value`
/// head's columns at each key. A prediction that names no column of a key
/// label holds at every value of that label.
#[allow(clippy::too_many_arguments)]
fn predictions(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    shape: &Shape<'_>,
    heads: &Heads<'_>,
    rule_path: &NodePath,
    rule: &DemoRule,
    groups: &[Row],
    example: Option<Example>,
) -> Outcome<Result<Vec<Vec<RowSet>>, RelationValue>> {
    let fault = |message: String| RunFault { message: message.into(), form: rule_path.clone() };
    let width = heads.value.columns.len() as u16;
    let by_key: StableHashMap<&[TermId], usize> = groups.iter().enumerate().map(|(at, group)| (&group[..], at)).collect();
    let mut instances: Vec<(Row, Vec<RowSet>)> = Vec::new();
    let mut at_fields: StableHashMap<Row, usize> = StableHashMap::default();
    for (index, form) in rule.forms.iter().enumerate() {
        let Form::Clause(clause) = form else { continue };
        let clause = clause.value();
        if relation_of(&clause.derives) != prediction() {
            continue;
        }
        let path = rule_path.child(index as u32);
        let body = clause.body.value();
        let held = body_labels(body);
        let mut named: Vec<(&ColumnName, LabelId)> = Vec::new();
        for column in clause.columns.iter().chain(rule.fields.iter()) {
            if held.contains(&column.label) && !named.iter().any(|(_, label)| *label == column.label) {
                named.push((&column.name, column.label));
            }
        }
        let labels: Vec<LabelId> = named.iter().map(|(_, label)| *label).collect();
        let conjuncts = body.conjuncts.iter().zip(0u32..).map(|(conjunct, at)| (conjunct, path.child(0).child(at))).collect();
        let (compiled, _) = ir::compile_safe(evaluation.program, &path, conjuncts, &labels).map_err(|compile| fault(format!("the prediction does not compile: {compile:?}")))?;
        let rows = match rows_of(evaluation, &path, bodies.relation(&path, &compiled, example)?, labels.len()).map_err(&fault)? {
            Ok(rows) => rows,
            Err(value) => return Ok(Err(value)),
        };
        let position = |name: &ColumnName| named.iter().position(|(found, _)| *found == name);
        let key_at: Vec<Option<usize>> = shape.key_columns.iter().map(|column| position(&column.name)).collect();
        let mut value_at = Vec::with_capacity(heads.value.columns.len());
        for (name, _) in &heads.value.columns {
            let found = name.as_ref().and_then(position);
            value_at.push(found.ok_or_else(|| fault(format!("the prediction names no column {name:?} of the `value` head")))?);
        }
        let field_at: Vec<usize> = rule.fields.iter().filter_map(|column| named.iter().position(|(_, label)| *label == column.label)).collect();
        for row in &rows {
            let fields: Row = field_at.iter().map(|&at| row[at]).collect();
            let instance = *at_fields.entry(fields.clone()).or_insert_with(|| {
                instances.push((fields, vec![RowSet::empty(width); groups.len()]));
                instances.len() - 1
            });
            let value: Row = value_at.iter().map(|&at| row[at]).collect();
            let keyed: Vec<(usize, TermId)> = key_at.iter().enumerate().filter_map(|(at, found)| found.map(|found| (at, row[found]))).collect();
            let sets = &mut instances[instance].1;
            if keyed.len() == key_at.len() {
                let key: Vec<TermId> = keyed.iter().map(|&(_, term)| term).collect();
                if let Some(&group) = by_key.get(&key[..]) {
                    sets[group].insert(value);
                }
            } else {
                for (group, key) in groups.iter().enumerate() {
                    if keyed.iter().all(|&(at, term)| key[at] == term) {
                        sets[group].insert(value.clone());
                    }
                }
            }
        }
    }
    if rule.fields.is_empty() && instances.is_empty() {
        instances.push((Row::default(), vec![RowSet::empty(width); groups.len()]));
    }
    Ok(Ok(instances.into_iter().map(|(_, sets)| sets).collect()))
}
