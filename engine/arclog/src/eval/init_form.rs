//! What an `INIT` form gives the evaluation of its instance, which the
//! evaluation of a construction's instance and of an `Unfold` instance
//! read: the form's instance and component, its key groups, the clause of
//! each input it writes, the types of its row positions, the rows of a
//! written input at each key group, and the rows of an input it does not
//! write.

use std::sync::Arc;

use crate::check::instance_inputs::inputs_at;
use crate::check::{CheckedProgram, InstanceClause};
use crate::eval::ir::{self, ClauseIr, IrPaths};
use crate::eval::join;
use crate::eval::{Evaluation, FormBodies, Outcome, RelationValue, RunFault};
use crate::terms::{Constant, Term};
use crate::hash::StableHashMap;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Body, ColumnName, Instance, InstanceInput, InstanceInputPart, InstancePart, KeyClausePart, LabelId, Out, PortName, Site};
use crate::registry::{is_key, Column, ColumnType, Component, InputPort, LibEntry, TypeParameter};
use crate::relations::{Relation, Row, RowSet};
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
    Ok(key_rows(evaluation, bodies, form, &shape.key_body, &shape.key_labels(), example)?.map(|(groups, _)| groups))
}

/// The key groups of a form whose key body is `key_body` with the key
/// columns `key_labels`: the rows of the relation [`key_relation`] gives,
/// as [`key_group_rows`] gives them, with that relation where the form has
/// a key clause. The form is an `INIT` form or a `DEMONSTRATED` form.
pub(super) fn key_rows(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    key_body: &Option<(&Body, NodePath)>,
    key_labels: &[LabelId],
    example: Option<Example>,
) -> Outcome<Result<(Vec<Row>, Option<Arc<Relation>>), RelationValue>> {
    Ok(key_relation(evaluation, bodies, form, key_body, key_labels, example)?.map(|key| (key_group_rows(key.as_deref()), key)))
}

/// The relation of the key clause of a form whose key body is `key_body`
/// with the key columns `key_labels`, read as [`relation_read`] gives it;
/// `None` where the form has no key clause, or the value of the key body
/// where it holds no rows. The relation's rows are not walked.
pub(super) fn key_relation(
    evaluation: &Evaluation<'_>,
    bodies: &FormBodies<'_>,
    form: &NodePath,
    key_body: &Option<(&Body, NodePath)>,
    key_labels: &[LabelId],
    example: Option<Example>,
) -> Outcome<Result<Option<Arc<Relation>>, RelationValue>> {
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let Some(key_body) = key_body else {
        return Ok(Ok(None));
    };
    let (clause, _, _) = key_clause_memo(evaluation.program, form, key_body, key_labels)
        .map_err(|compile| fault(format!("the key body does not compile: {compile:?}")))?;
    Ok(relation_read(evaluation, form, bodies.relation(form, &clause, example)?, key_labels.len()).map_err(&fault)?.map(Some))
}

/// The key groups of a form whose key clause has the relation `key`: its
/// rows, or the one empty row where the form has no key clause.
pub(super) fn key_group_rows(key: Option<&Relation>) -> Vec<Row> {
    key.map_or_else(|| vec![Row::default()], relation_rows)
}

/// The clause of the key body `key_body` of the form at `form`, whose
/// columns are the key's labels `key_labels`, with the paths of its nodes:
/// the one compile of a key body, which the evaluation of the key and the
/// column flows of the form's relations read.
pub(crate) fn key_clause_memo(program: &CheckedProgram, form: &NodePath, key_body: &(&Body, NodePath), key_labels: &[LabelId]) -> Result<InstanceClause, ir::CompileFault> {
    program.instance_clause(form, None, || key_clause(program, form, key_body, key_labels).map(|(clause, paths)| (clause, paths, 0)))
}

/// The clause of the body of the `OUT` form `out` at `form`, whose columns
/// are its `^` labels in order of appearance, with the paths of its nodes:
/// the compile of a key body, as [`key_clause_memo`] gives it.
pub(crate) fn out_clause(program: &CheckedProgram, form: &NodePath, out: &Out) -> Result<InstanceClause, ir::CompileFault> {
    let labels: Vec<LabelId> = out.key.columns.iter().map(|column| column.label).collect();
    key_clause_memo(program, form, &(out.key.body.value(), form.child(Out::BODY)), &labels)
}

/// The clause of the key body `key_body` of the form at `form`, whose
/// columns are the key's labels `key_labels`, with the paths of its nodes.
fn key_clause(program: &CheckedProgram, form: &NodePath, key_body: &(&Body, NodePath), key_labels: &[LabelId]) -> Result<(ClauseIr, IrPaths), ir::CompileFault> {
    ir::compile_instance_pathed(program, form, std::slice::from_ref(key_body), key_labels)
}

/// The clause of an input whose body is `body` and whose head holds the
/// labels `head`, in a form whose key body is `key_body`: a keyed input is
/// its body joined with the rows of the key clause at the key's labels,
/// its columns the key's labels first, with the paths of its nodes and the
/// number of those columns.
/// The error is the fault of the compile.
pub(crate) fn joined_clause(
    program: &CheckedProgram,
    form: &NodePath,
    key_body: &Option<(&Body, NodePath)>,
    key_labels: &[LabelId],
    keyed: bool,
    body: (&Body, NodePath),
    head: &[LabelId],
) -> Result<(ClauseIr, IrPaths, usize), ir::CompileFault> {
    let key = match key_body {
        Some(key_body) if keyed => Some(key_clause(program, form, key_body, key_labels)?),
        _ => None,
    };
    let Some((clause, key_paths)) = key else {
        let (clause, paths) = ir::compile_instance_pathed(program, form, &[body], head)?;
        return Ok((clause, paths, 0));
    };
    let columns: Vec<LabelId> = key_labels.iter().chain(head).copied().collect();
    let read = ir::KeyRead { form: form.clone(), clause };
    let (clause, paths) = ir::compile_keyed_body(program, form, (read, key_paths, key_labels), body, &columns)?;
    Ok((clause, paths, key_labels.len()))
}

/// What an `INIT` form binds a type parameter of its component to: the
/// labels of its binding, by which its types are given, with the fields of
/// the record it is bound to, or `None` for one label, or the parameter's
/// fixed bound. An unbound parameter with no bound is a zero-field record
/// and contributes no row positions.
enum Binding {
    Labels { fields: Option<Box<[ColumnName]>>, labels: Vec<LabelId> },
    Fixed(ValueType),
}

/// The clause of an input the form writes, whose columns are the key's
/// `key` labels where the input stands in the key clause, then the labels
/// of `head` that are not `None`.
pub(super) struct InputClause {
    pub(super) clause: Arc<ClauseIr>,
    /// The paths of the nodes of `clause`.
    pub(crate) paths: Arc<IrPaths>,
    key: usize,
    head: Vec<Option<LabelId>>,
    /// The first logical input column, if it has a native position.
    cursor: Option<ir::Variable>,
}

impl InputClause {
    /// Bind a state-local query at its key and cursor. A Unit cursor
    /// matches only the Unit state. Variables use the form's canonical IDs.
    pub(super) fn at_state(&self,key:&[TermId],cursor:TermId)->Result<Option<Vec<(ir::Variable,TermId)>>,String> {
        // An unkeyed input applies at every key, as InputClause::grouped
        // does. A keyed input binds its own key positions exactly.
        if self.key!=0 && key.len()!=self.key {return Err("recursive input and state key arities differ".into());}
        let mut bound=self.clause.columns[..self.key].iter().copied().zip(key.iter().copied()).collect::<Vec<_>>();
        match self.cursor {
            Some(variable)=>bound.push((variable,cursor)),
            None if cursor==Term::Constant(Constant::Unit).encode().expect("Unit term")=>{},
            None=>return Ok(None),
        }
        Ok(Some(bound))
    }
    pub(super) fn expanded_rows(&self,rows:&crate::relations::Relation)->RowSet {
        let mut expanded=RowSet::empty((self.key+self.head.len()) as u16);
        super::join::each_row(rows,&mut |row|{expanded.insert(row.into());});
        expanded
    }
    /// `rows`, the rows of a broadcast input, at each of `groups`: the key's
    /// `key_width` columns of the group, then the row. A broadcast input's rows
    /// hold at every key group, as [`InputClause::grouped`] gives them.
    pub(super) fn broadcast_rows(&self,key_width:usize,groups:&[Row],rows:&crate::relations::Relation)->RowSet {
        let mut laid=RowSet::empty(key_width as u16+rows.arity());
        for group in groups {
            super::join::each_row(rows,&mut |row|{laid.insert(group.iter().chain(row).copied().collect());});
        }
        laid
    }
    /// Whether the clause's rows hold key columns.
    pub(super) fn keyed(&self)->bool {
        self.key!=0
    }
    /// The number of columns of the clause's rows.
    pub(super) fn arity(&self) -> usize {
        self.key + self.head.iter().flatten().count()
    }

    /// `rows`, rows of the clause, at each of `groups`, in the input's row
    /// positions other than `key`.
    pub(super) fn grouped(&self, groups: &[Row], rows: Vec<Row>) -> Vec<RowSet> {
        grouped(groups, self.key, self.head.len(), rows)
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
        program: &'p CheckedProgram,
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
            bindings.insert(parameter, match &parameter.bound {
                Some(ty)=>Binding::Fixed(ty.clone()),
                None=>Binding::Labels {fields:Some(Box::new([])),labels:Vec::new()},
            });
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
        let types = ir::label_types(program, form);
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
    pub(crate) fn input_clause(&self, program: &CheckedProgram, form: &NodePath, input: &InputPort) -> Result<Option<InputClause>, String> {
        let name = &input.port.name;
        let Some((path, keyed, written)) = self.written.iter().find(|(_, _, written)| written.name == *name) else { return Ok(None) };
        let head = self.head_labels(written, &input.port.columns)?;
        let body = (written.body.value(), path.child(written.position(InstanceInputPart::Body)));
        let flat: Vec<LabelId> = head.iter().flatten().copied().collect();
        let (clause, paths, key) = program
            .instance_clause(form, Some(name), || joined_clause(program, form, &self.key_body, &self.key_labels(), *keyed, body, &flat))
            .map_err(|compile| format!("input `{}` does not compile: {compile:?}", name.0))?;
        let first = input.port.columns.iter().find(|column|!is_key(column));
        let cursor = match first {
            Some(column) if !self.column_types(column)?.is_empty()=>clause.columns.get(key).copied(),
            _=>None,
        };
        Ok(Some(InputClause { clause, paths, key, head, cursor }))
    }

    /// The clause that the evaluation joins for the body at `at`, a path
    /// after the form's own, of the `INIT` form at `form` of `component`:
    /// its key body, or the body of a written input. `None` where `at` is
    /// neither, the error where the clause does not compile.
    pub(crate) fn clause_at(&self, program: &CheckedProgram, form: &NodePath, component: &Component, at: &NodePath) -> Option<Result<(Arc<ClauseIr>, Arc<IrPaths>), String>> {
        if let Some(key_body) = self.key_body.as_ref().filter(|(_, path)| path == at) {
            let found = key_clause_memo(program, form, key_body, &self.key_labels());
            return Some(found.map(|(clause, paths, _)| (clause, paths)).map_err(|compile| format!("the key body does not compile: {compile:?}")));
        }
        let (_, _, written) = self.written.iter().find(|(path, _, input)| &path.child(input.position(InstanceInputPart::Body)) == at)?;
        let port = component.inputs.iter().find(|own| own.port.name == written.name)?;
        match self.input_clause(program, form, port) {
            Ok(found) => found.map(|input| Ok((input.clause, input.paths))),
            Err(message) => Some(Err(message)),
        }
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
                Binding::Fixed(ty) => Ok(vec![ty.clone()]),
            },
            ty => ty.fixed().cloned().map(|ty| vec![ty]).ok_or_else(|| format!("the column {:?} has no type of its own", column.name)),
        }
    }

    /// The number of row positions of each of `columns` in a port's rows,
    /// or `None` for its `key` column, which takes the width of
    /// [`Self::key_width`] positions.
    pub(super) fn widths(&self, columns: &[Column]) -> Result<Vec<Option<usize>>, String> {
        columns.iter().map(|column| if is_key(column) { Ok(None) } else { self.column_types(column).map(|types| Some(types.len())) }).collect()
    }

    /// Private Unfold atoms: a zero-field value has one singleton handle.
    /// Program relation rows never use this scalar representation.
    pub(super) fn scalar_widths(&self, columns:&[Column])->Result<Vec<usize>,String> {
        columns.iter().filter(|c|!is_key(c)).map(|column| {
            let width=self.column_types(column)?.len();
            if width>1 {return Err("Unfold cursor/item must be scalar or an empty record".into());}
            Ok(width)
        }).collect()
    }
    pub(super) fn scalar_rows(&self, columns:&[Column], rows:&RowSet)->Result<RowSet,String> {
        let widths=self.scalar_widths(columns)?;
        let mut atoms=RowSet::empty(widths.len() as u16);
        let unit=Term::Constant(Constant::Unit).encode().expect("singleton handle");
        for row in rows.rows() {
            let mut cells=row.iter();
            atoms.insert(widths.iter().map(|width| if *width==0 {unit} else {*cells.next().expect("native input width")}).collect());
        }
        Ok(atoms)
    }

    /// The count of row positions of a port whose columns have `widths`.
    pub(super) fn arity(&self, widths: &[Option<usize>]) -> usize {
        widths.iter().map(|width| width.unwrap_or(self.key_width())).sum()
    }

    /// The count of key columns of the instance's output rows: the key
    /// clause's columns, and none where the form has no key clause.
    pub(super) fn key_width(&self) -> usize {
        if self.key_body.is_some() { self.key_columns.len() } else { 0 }
    }

    /// `row`, a row of a port whose columns have `widths`, with the key's
    /// positions first where the form has a key clause, and left out where
    /// it has none.
    pub(super) fn key_first(&self, widths: &[Option<usize>], row: &Row) -> Row {
        let (mut key, mut values) = (Vec::new(), Vec::new());
        let mut rest = &row[..];
        for width in widths {
            let (taken, after) = rest.split_at(width.unwrap_or(self.key_width()));
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
    /// bound to one label or a fixed bound.
    fn fields(&self, column: &Column) -> Option<&[ColumnName]> {
        match &column.ty {
            ColumnType::Parameter(parameter) => match self.binding(parameter) {
                Binding::Labels { fields, .. } => fields.as_deref(),
                Binding::Fixed(_) => None,
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
    /// fields. An unbound parameter has zero fields and no head position.
    fn head_labels(&self, input: &InstanceInput, columns: &[Column]) -> Result<Vec<Option<LabelId>>, String> {
        let mut labels = Vec::new();
        for column in columns.iter().filter(|column| !is_key(column)) {
            let fields = match &column.ty {
                ColumnType::Parameter(parameter) => match self.binding(parameter) {
                    Binding::Labels { fields, .. } => fields.as_deref(),
                    Binding::Fixed(_) => None,
                },
                _ => None,
            };
            if fields.is_some_and(|fields|fields.is_empty()) {continue;}
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
    /// `groups`: its default rows at each, or, where the input is
    /// marked [`InputPort::from_key`], the rows the key fills, or no row.
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
        if !input.from_key {
            return Ok(vec![rows; groups.len()]);
        }
        let Some(filled) = self.key_filled(input)? else { return Ok(vec![rows; groups.len()]) };
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
    fn key_filled(&self, input: &InputPort) -> Result<Option<Vec<usize>>, String> {
        if !input.port.columns.iter().any(is_key) {
            return Ok(None);
        }
        let key_types: Vec<ValueType> = self.key_labels().into_iter().map(|label| self.label_type(label)).collect::<Result<_, _>>()?;
        let columns = input.port.columns.iter().filter(|column|!is_key(column))
            .map(|column|self.column_types(column)).collect::<Result<Vec<_>,_>>()?;
        Ok(crate::registry::key_fill(&key_types, columns.iter().map(Vec::as_slice)))
    }
}


/// The labels at `site`, each with its column path from the site's column.
pub(super) fn site_labels(site: &Site) -> Vec<(Vec<ColumnName>, LabelId)> {
    let mut labels = Vec::new();
    each_site_label(site, &mut Vec::new(), &mut |use_, path| labels.extend(use_label(use_).map(|label| (path.to_vec(), label))));
    labels
}

/// The rows of `value`, of `arity` columns, or the value where it holds no
/// rows, read in `evaluation` at `form` as [`relation_read`] gives.
pub(super) fn rows_of(evaluation: &Evaluation<'_>, form: &NodePath, value: RelationValue, arity: usize) -> Result<Result<Vec<Row>, RelationValue>, String> {
    Ok(relation_read(evaluation, form, value, arity)?.map(|relation| relation_rows(&relation)))
}

/// The relation of `value`, of `arity` columns, or the value where it holds
/// no rows. A relation of another arity is a fault. The walk of the
/// relation's product is counted as [`join::charge_walk`] gives, and its
/// stop is the value; the rows are not walked, as [`relation_rows`] gives
/// them.
pub(super) fn relation_read(evaluation: &Evaluation<'_>, form: &NodePath, value: RelationValue, arity: usize) -> Result<Result<Arc<Relation>, RelationValue>, String> {
    let RelationValue::Rows(relation) = value else { return Ok(Err(value)) };
    if relation.arity() as usize != arity {
        return Err(format!("a body gives {} columns, where {arity} are read", relation.arity()));
    }
    if let Err(stop) = join::charge_walk(evaluation, &relation, form) {
        return Ok(Err(RelationValue::Stopped(stop)));
    }
    Ok(Ok(relation))
}

/// The rows of `relation`, the product of its parts.
pub(super) fn relation_rows(relation: &Relation) -> Vec<Row> {
    let mut rows = Vec::new();
    join::each_row(relation, &mut |row| rows.push(row.into()));
    rows
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

#[path = "render_init.rs"] pub(crate) mod render_metadata;
