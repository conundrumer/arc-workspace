//! What an `INIT` form gives the evaluation of its instance, which the
//! evaluation of a construction's instance and of an `Unfold` instance
//! read: the form's instance and component, its key groups, the clause of
//! each input it writes, the types of its row positions, the rows of a
//! written input at each key group, and the rows of an input it does not
//! write.

use crate::check::instance_inputs::inputs_at;
use crate::eval::ir::{self, ClauseIr};
use crate::eval::join;
use crate::eval::values::OutputKey;
use crate::eval::{Evaluation, FormBodies, Outcome, RelationValue, RunFault};
use crate::hash::StableHashMap;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Body, ColumnName, Instance, InstanceInput, InstanceInputPart, InstancePart, KeyClausePart, LabelId, PortName, Site};
use crate::registry::{is_key, Column, ColumnType, Component, InputPort, LibEntry, TypeParameter};
use crate::relations::{Row, RowSet};
use crate::resolver::columns::projection;
use crate::terms::{Example, TermId};
use crate::types::{each_site_label, use_label, FormTypes, ValueType};

/// The `INIT` form at `form` and the component it instantiates, or a
/// [`RunFault`] where the registry declares no such component.
pub(super) fn instance_at<'p>(evaluation: &Evaluation<'p>, form: &NodePath) -> Outcome<(&'p Instance, &'p Component)> {
    let root = NodeRef::Program(evaluation.program.program.program.value());
    let Some(NodeRef::Instance(instance)) = node_at(root, form) else { panic!("an `INIT` form at the form of an instance's node") };
    match evaluation.registry.entry(&instance.component) {
        Some(LibEntry::Component(component)) => Ok((instance, component)),
        _ => Err(unevaluated(form, instance)),
    }
}

/// The fault of `instance`, the `INIT` form at `form`, whose component the
/// engine does not evaluate.
pub(super) fn unevaluated(form: &NodePath, instance: &Instance) -> RunFault {
    RunFault { message: format!("the engine does not evaluate the component `{}`", instance.component.0).into(), form: form.clone() }
}

/// The key groups of the instance of `shape`, the `INIT` form at `form`, on
/// `example`: the rows of its key clause, or the one empty row where it
/// has none, or the value of the key body where it holds no rows.
pub(super) fn key_groups(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    shape: &InstanceShape<'_>,
    example: Option<Example>,
) -> Outcome<Result<Vec<Row>, RelationValue>> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let Some(key_body) = &shape.key_body else { return Ok(Ok(vec![Row::default()])) };
    let key_labels = shape.key_labels();
    let clause = ir::compile_instance_body(evaluation.program, form, &[key_body.clone()], &key_labels)
        .map_err(|compile| fault(format!("the key body does not compile: {compile:?}")))?;
    rows_of(bodies.relation(form, &clause, example)?, key_labels.len()).map_err(&fault)
}

/// What an `INIT` form binds a type parameter of its component to: the
/// labels of its binding, by which its types are given, with the fields of
/// the record it is bound to, or `None` for one label, or `Unit`, where no
/// place of the form projects onto it.
enum Binding {
    Labels { fields: Option<Box<[ColumnName]>>, labels: Vec<LabelId> },
    Unit,
}

/// The clause of an input the form writes, whose columns are the key's
/// `key` labels where the input stands in the key clause, then the labels
/// of `head` that are not `None`.
pub(super) struct InputClause {
    pub(super) clause: ClauseIr,
    key: usize,
    head: Vec<Option<LabelId>>,
}

impl InputClause {
    /// The number of columns of the clause's rows.
    pub(super) fn arity(&self) -> usize {
        self.key + self.head.iter().flatten().count()
    }

    /// The number of the input's row positions other than `key`.
    pub(super) fn width(&self) -> usize {
        self.head.len()
    }

    /// `rows`, rows of the clause, at each of `groups`, in the input's row
    /// positions other than `key`.
    pub(super) fn grouped(&self, groups: &[Row], rows: Vec<Row>) -> Vec<RowSet> {
        grouped(groups, self.key, self.head.len(), rows.iter().map(|row| with_unit(self.key, &self.head, row)).collect())
    }
}

/// What an `INIT` form gives the evaluation of its instance: its key body
/// and key columns, the inputs it writes with their paths and whether each
/// stands in the key clause, the types of its labels, and its binding of
/// each type parameter of its component.
pub(super) struct InstanceShape<'p> {
    /// The key body with its path, where the form has a key clause.
    pub(super) key_body: Option<(&'p Body, NodePath)>,
    key_columns: Vec<(ColumnName, LabelId)>,
    /// Each input the form writes, with its path and whether it stands in
    /// the key clause.
    written: Vec<(NodePath, bool, &'p InstanceInput)>,
    types: &'p FormTypes,
    /// The binding of each type parameter of the component.
    bindings: StableHashMap<&'p TypeParameter, Binding>,
}

impl<'p> InstanceShape<'p> {
    /// The shape of `instance`, the `INIT` form at `form`, of `component`.
    pub(super) fn of(
        evaluation: &Evaluation<'p>,
        form: &NodePath,
        instance: &'p Instance,
        component: &'p Component,
    ) -> Self {
        let key = instance.key.as_ref().map(|key| key.value());
        let key_body = key.map(|key| (key.key.body.value(), form.child(instance.position(InstancePart::Key)).child(key.position(KeyClausePart::Body))));
        let key_columns = key.map_or_else(Vec::new, |key| key.key.columns.iter().map(|column| (column.name.clone(), column.label)).collect());
        let written = inputs_at(instance).into_iter().map(|(path, keyed, input)| (form.join(&path), keyed, input)).collect();
        let sites = crate::registry::binding_sites(instance, &component.inputs);
        let mut bindings = StableHashMap::default();
        for parameter in crate::registry::unbound(&component.type_parameters, &sites) {
            bindings.insert(parameter, Binding::Unit);
        }
        for sites in &sites {
            let binding = match sites.binding {
                crate::registry::ParameterSite::Key(_) => Binding::Labels {
                    fields: Some(key_columns.iter().map(|(name, _)| name.clone()).collect()),
                    labels: key_columns.iter().map(|(_, label)| *label).collect(),
                },
                crate::registry::ParameterSite::Head { site, .. } => Binding::Labels {
                    fields: projection(site),
                    labels: site_labels(site).into_iter().map(|(_, label)| label).collect(),
                },
            };
            bindings.insert(sites.parameter, binding);
        }
        let types = ir::label_types(evaluation.program, form);
        InstanceShape { key_body, key_columns, written, types, bindings }
    }

    /// The key's labels, in the order of its columns.
    pub(super) fn key_labels(&self) -> Vec<LabelId> {
        self.key_columns.iter().map(|(_, label)| *label).collect()
    }

    /// Whether the form writes the input of name `name`.
    pub(super) fn writes(&self, name: &PortName) -> bool {
        self.written.iter().any(|(_, _, input)| input.name == *name)
    }

    /// The clause of `input` where the form at `form` writes it. A keyed
    /// input is its body joined with the key body.
    pub(super) fn input_clause(&self, evaluation: &Evaluation<'_>, form: &NodePath, input: &InputPort) -> Result<Option<InputClause>, String> {
        let name = &input.port.name;
        let Some((path, keyed, written)) = self.written.iter().find(|(_, _, written)| written.name == *name) else { return Ok(None) };
        let head = self.head_labels(written, &input.port.columns)?;
        let body = (written.body.value(), path.child(written.position(InstanceInputPart::Body)));
        let key_labels = self.key_labels();
        let (parts, prefix): (Vec<(&Body, NodePath)>, &[LabelId]) = match (&self.key_body, keyed) {
            (Some(key_body), true) => (vec![key_body.clone(), body], &key_labels),
            _ => (vec![body], &[]),
        };
        let columns: Vec<LabelId> = prefix.iter().chain(head.iter().flatten()).copied().collect();
        let clause = ir::compile_instance_body(evaluation.program, form, &parts, &columns)
            .map_err(|compile| format!("input `{}` does not compile: {compile:?}", name.0))?;
        Ok(Some(InputClause { clause, key: prefix.len(), head }))
    }

    /// The type of `label`.
    fn label_type(&self, label: LabelId) -> Result<ValueType, String> {
        self.types.label(label).cloned().ok_or_else(|| format!("the label {label:?} has no type"))
    }

    /// The binding of `parameter`, a type parameter of the component.
    fn binding(&self, parameter: &TypeParameter) -> &Binding {
        self.bindings.get(parameter).expect("a binding of each type parameter of the component")
    }

    /// The types of the row positions of `column`: its fixed type, or the
    /// types of its type parameter's binding.
    fn column_types(&self, column: &Column) -> Result<Vec<ValueType>, String> {
        match &column.ty {
            ColumnType::Parameter(parameter) => match self.binding(parameter) {
                Binding::Labels { labels, .. } => labels.iter().map(|&label| self.label_type(label)).collect(),
                Binding::Unit => Ok(vec![ValueType::Unit]),
            },
            ty => ty.fixed().cloned().map(|ty| vec![ty]).ok_or_else(|| format!("the column {:?} has no type of its own", column.name)),
        }
    }

    /// The number of row positions of each of `columns` in a port's rows,
    /// or `None` for its `key` column, which takes the width of
    /// [`Self::output_key`] positions.
    pub(super) fn widths(&self, columns: &[Column]) -> Result<Vec<Option<usize>>, String> {
        columns.iter().map(|column| if is_key(column) { Ok(None) } else { self.column_types(column).map(|types| Some(types.len())) }).collect()
    }

    /// The count of row positions of a port whose columns have `widths`.
    pub(super) fn arity(&self, widths: &[Option<usize>]) -> usize {
        widths.iter().map(|width| width.unwrap_or(self.output_key().width())).sum()
    }

    /// The key columns of the instance's output rows.
    pub(super) fn output_key(&self) -> OutputKey {
        OutputKey::of(self.key_body.is_some().then_some(self.key_columns.len()))
    }

    /// `row`, a row of a port whose columns have `widths`, with the key's
    /// positions first where the form has a key clause, and left out where
    /// it has none.
    pub(super) fn key_first(&self, widths: &[Option<usize>], row: &Row) -> Row {
        let (mut key, mut values) = (Vec::new(), Vec::new());
        let mut rest = &row[..];
        for width in widths {
            let (taken, after) = rest.split_at(width.unwrap_or(self.output_key().width()));
            if width.is_some() {
                values.extend_from_slice(taken);
            } else if self.key_body.is_some() {
                key.extend_from_slice(taken);
            }
            rest = after;
        }
        key.extend(values);
        key.into()
    }

    /// The fields of the record that the type parameter of `column` is
    /// bound to, or `None` for a column of a fixed type or of a parameter
    /// bound to one label or `Unit`.
    fn fields(&self, column: &Column) -> Option<&[ColumnName]> {
        match &column.ty {
            ColumnType::Parameter(parameter) => match self.binding(parameter) {
                Binding::Labels { fields, .. } => fields.as_deref(),
                Binding::Unit => None,
            },
            _ => None,
        }
    }

    /// The type of each of `columns` other than `key`: its fixed type, the
    /// type of the one label its type parameter is bound to, or the record
    /// of its binding's fields, each field of the type of its label.
    pub(super) fn port_column_types(&self, columns: &[Column]) -> Result<Box<[ValueType]>, String> {
        let column_type = |column: &Column| {
            let types = self.column_types(column)?;
            match self.fields(column) {
                Some(fields) if fields.len() == types.len() => Ok(ValueType::Record(fields.iter().cloned().zip(types).collect())),
                None if types.len() == 1 => Ok(types.into_iter().next().expect("one type")),
                _ => Err(format!("the binding of column {:?} gives {} labels, which match no field of a record and no single label", column.name, types.len())),
            }
        };
        columns.iter().filter(|column| !is_key(column)).map(column_type).collect()
    }

    /// The types of the row positions of `columns` other than `key`.
    pub(super) fn port_types(&self, columns: &[Column]) -> Result<Box<[ValueType]>, String> {
        let mut types = Vec::new();
        for column in columns.iter().filter(|column| !is_key(column)) {
            types.extend(self.column_types(column)?);
        }
        Ok(types.into())
    }

    /// The labels of the head sites of `input` at the row positions of
    /// `columns` other than `key`, a record's in the order of its binding's
    /// fields, and `None` at the position of a column whose type parameter
    /// is `Unit`, on which the input writes no site.
    fn head_labels(&self, input: &InstanceInput, columns: &[Column]) -> Result<Vec<Option<LabelId>>, String> {
        let mut labels = Vec::new();
        for column in columns.iter().filter(|column| !is_key(column)) {
            let fields = match &column.ty {
                ColumnType::Parameter(parameter) => match self.binding(parameter) {
                    Binding::Labels { fields, .. } => fields.as_deref(),
                    Binding::Unit => {
                        labels.push(None);
                        continue;
                    }
                },
                _ => None,
            };
            let site = input.head.iter().find(|site| site.column == column.name);
            let site = site.ok_or_else(|| format!("input `{}` writes no head site on column {:?}", input.name.0, column.name))?;
            let at_site = site_labels(site);
            match (fields, &at_site[..]) {
                (None, [(_, label)]) => labels.push(Some(*label)),
                (Some(fields), _) => {
                    for field in fields {
                        let found = at_site.iter().find(|(path, _)| path.last() == Some(field) && path.len() > 1);
                        let (_, label) = found.ok_or_else(|| format!("head site {:?} of input `{}` gives no label of field {field:?}", column.name, input.name.0))?;
                        labels.push(Some(*label));
                    }
                }
                (None, _) => return Err(format!("head site {:?} of input `{}` holds other than one label", column.name, input.name.0)),
            }
        }
        Ok(labels)
    }

    /// The rows of `input`, which the form does not write, at each of
    /// `groups`: its default rows at each, or no row where the input is
    /// marked [`InputPort::explicit`], or the rows the key fills, or no
    /// row.
    pub(super) fn unwritten(
        &self,
        input: &InputPort,
        types: &[ValueType],
        groups: &[Row],
        evaluation: &Evaluation<'_>,
    ) -> Result<Vec<RowSet>, String> {
        let mut rows = RowSet::empty(types.len() as u16);
        if let Some(default) = &input.default {
            let mut table = evaluation.session.intern.write().expect("an intern table that no panic poisoned");
            for row in default.rows(types, evaluation.registry, &mut table).map_err(|error| format!("the default rows of input `{}` do not read: {error:?}", input.port.name.0))? {
                rows.insert(row);
            }
            return Ok(vec![rows; groups.len()]);
        }
        if input.explicit {
            return Ok(vec![rows; groups.len()]);
        }
        let Some(filled) = self.key_filled(input, types)? else { return Ok(vec![rows; groups.len()]) };
        Ok(groups
            .iter()
            .map(|key| {
                let mut rows = RowSet::empty(types.len() as u16);
                rows.insert(filled.iter().map(|&position| key[position]).collect());
                rows
            })
            .collect())
    }

    /// The position in the key of each row position of `input`, where the
    /// input has a `key` column and each of its other positions takes the
    /// one key label of its type.
    fn key_filled(&self, input: &InputPort, types: &[ValueType]) -> Result<Option<Vec<usize>>, String> {
        if !input.port.columns.iter().any(is_key) {
            return Ok(None);
        }
        let key_types: Vec<ValueType> = self.key_labels().into_iter().map(|label| self.label_type(label)).collect::<Result<_, _>>()?;
        let mut positions = Vec::with_capacity(types.len());
        for ty in types {
            let mut matching = key_types.iter().enumerate().filter(|(_, key)| *key == ty).map(|(position, _)| position);
            match (matching.next(), matching.next()) {
                (Some(position), None) => positions.push(position),
                _ => return Ok(None),
            }
        }
        Ok(Some(positions))
    }
}


/// The labels at `site`, each with its column path from the site's column.
fn site_labels(site: &Site) -> Vec<(Vec<ColumnName>, LabelId)> {
    let mut labels = Vec::new();
    each_site_label(site, &mut Vec::new(), &mut |use_, path| labels.extend(use_label(use_).map(|label| (path.to_vec(), label))));
    labels
}

/// `row`, whose first `prefix` positions are a key's and whose others are
/// the labels of `head` that are not `None`, with the one `Unit` term at each
/// position of `head` that is `None`.
fn with_unit(prefix: usize, head: &[Option<LabelId>], row: &Row) -> Row {
    let unit = OutputKey::Unit.columns(&[]);
    let (key, mut values) = (&row[..prefix], row[prefix..].iter());
    let mut filled = key.to_vec();
    for label in head {
        filled.push(match label {
            Some(_) => *values.next().expect("a row position for each label of the head"),
            None => unit[0],
        });
    }
    filled.into()
}

/// The rows of `value`, of `arity` columns, or the value where it holds no
/// rows.
pub(super) fn rows_of(value: RelationValue, arity: usize) -> Result<Result<Vec<Row>, RelationValue>, String> {
    let RelationValue::Rows(relation) = value else { return Ok(Err(value)) };
    if relation.arity() as usize != arity {
        return Err(format!("a body gives {} columns, where {arity} are read", relation.arity()));
    }
    let mut rows = Vec::new();
    join::each_row(&relation, &mut |row| rows.push(row.into()));
    Ok(Ok(rows))
}

/// `rows`, whose first `key` columns are a key and whose other `width`
/// columns are an input's, split into the rows of each of `groups` with
/// the key's columns left out; with no key columns, every row in each
/// group.
pub(super) fn grouped(groups: &[Row], key: usize, width: usize, rows: Vec<Row>) -> Vec<RowSet> {
    if key == 0 {
        let mut all = RowSet::empty(width as u16);
        for row in rows {
            all.insert(row);
        }
        return vec![all; groups.len()];
    }
    let mut by_key: StableHashMap<&[TermId], RowSet> = StableHashMap::default();
    for row in &rows {
        let (at, values) = row.split_at(key);
        by_key.entry(at).or_insert_with(|| RowSet::empty(width as u16)).insert(values.into());
    }
    groups.iter().map(|group| by_key.remove(&group[..]).unwrap_or_else(|| RowSet::empty(width as u16))).collect()
}
