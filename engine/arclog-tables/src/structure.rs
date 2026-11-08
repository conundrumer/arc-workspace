//! The structure of the bodies that the evaluator joins for each table of a
//! case program, and the symmetries of the tables and of the bodies, under
//! the identities of [`crate::identity`].
//!
//! Each of the three texts below is JSON, one per table, in the order of the
//! tables of the export. A text depends on no name and no order that the
//! program's author chose (a rename of the declared relations, instances and
//! labels, a reorder of the top-level forms that keeps dependency order, of a
//! body's conjuncts, of an `OR`'s branches, of the sites of an atom, of the
//! head sites of an instance input and of the fields of a record), apart from
//! an exchange of two things that a symmetry of the content exchanges, and
//! apart from the numbers of tables, which stand at the order of the tables.
//! Every list below that has no meaning in its order is sorted by the text of
//! its members.
//!
//! - [`Structure::bodies`]: a list of bodies, `[]` where the table has none.
//!   A body is the clause IR ([`arclog::eval::ir::ClauseIr`]) that the
//!   evaluator joins for the table, one for each body that a form giving the
//!   table's relation writes at a column of it, with
//!   `form` (the identity of the top-level form that holds the body),
//!   `scope` (the canonical path of the body's label scope in the form, empty
//!   for the form's own), `variables` (each `{"id","type"}`, in the order of
//!   the canonical positions of the scope's labels; `id` is `#<position>`, or
//!   `<scope>/#<position>` in a scope other than the form's own, so it
//!   differs for each variable of the form, and is the identity of the label
//!   in the scope's canonical labeling), `table_columns` (each
//!   `[column identity, variable id]`: the variable that the body binds at a
//!   column of the table), `symmetries` (the permutations of the positions of
//!   the scope's labels that its canonical search found, under which the
//!   scope's content is the same; `p[a] = b` maps the variable `#a` to `#b`)
//!   and `clause`. A clause is `{"columns": [variable ids], "nodes": [node]}`,
//!   a node one of
//!   - `{"k":"atom","form","path","read","train_only","args"}` for an atom of
//!     a relation with rows. `form` and `path` are the atom's identity, as
//!     the `atom_form` and `atom_path` of a flow give it (`path` is `key` for
//!     the read of a key clause). `read` is `{"table": n}` for a relation
//!     that the table number `n` stands for (-1 where the export holds no
//!     such table), `{"fact": name, "table": n}` for a fact relation,
//!     `{"key": clause}` for the key clause of an `INIT` form, or
//!     `{"undefined": true}`. `args` are `[column identity, argument]`, the
//!     column identity that of the table read, `@example` for the example
//!     column of a lifted read, and the id of the key clause's variable for a
//!     key read; an argument is `{"v": variable id}` or `{"t": term}`;
//!   - `{"k":"lib","form","path","relation","args","mode","computes"}` for an
//!     atom of an algebra relation of the lib. `args` are `[lib column name,
//!     argument]`. `mode` is the lib columns that the first mode the
//!     placed variables satisfy binds, `null` where the relation has no
//!     mode, and `computes` the variables that the atom gives values to: its
//!     variables that no atom of a relation, no `=`, no union and no earlier
//!     algebra relation places, other than those of an orientation type,
//!     which the evaluator binds by the type's domain;
//!   - `{"k":"cmp","op","first","second","binds_first"}` for a comparison,
//!     `second` an argument;
//!   - `{"k":"not","outer","body"}` and `{"k":"all","outer","body"}` for a
//!     `NOT` and for the counterexample relation of an `ALL`, `outer` the
//!     variables of the enclosing clause that the body reads;
//!   - `{"k":"or","exported","branches"}` for an `OR` or an `IF`.
//! - [`Structure::instances`]: for a table that an output of an instance
//!   gives, `{"component": lib name, "inputs": [[port name, table number]]}`,
//!   -1 for an input that the export holds no table of, and the empty string
//!   for every other table.
//! - [`Structure::column_symmetries`]: a list of permutations of the table's
//!   column identities under which its content is the same, each a list of
//!   `[column identity, column identity it is replaced by]` for each column
//!   that it moves.

use std::collections::BTreeMap;

use arclog::algebra::satisfied_mode;
use arclog::check::CheckedProgram;
use arclog::hash::StableHashMap;
use arclog::eval::ir::{Argument, Arguments, AtomSource, ClauseIr, IrNode, IrPaths, NodePaths, Operand, Variable};
use arclog::eval::read_coordinates::{ReadCoordinates, SourceColumn};
use arclog::program::path::NodePath;
use arclog::program::{column_spelled, ConstraintOp, FactRelation, LabelId};
use arclog::read::spelling::{spelling, FACT_RELATIONS};
use arclog::registry::Registry;
use arclog::resolver::given::Given;
use arclog::resolver::registry_columns;
use arclog::resolver::DependencyKind;
use arclog::types::GraphRelation;
use serde_json::{json, Value};

use crate::columns::type_names;
use crate::identity::{atom_identity, Forms, Identities};
use crate::tables::{Point, Table, TableRelation};

/// The three texts of each table, as the module doc gives them.
#[derive(Clone, Debug, Default)]
pub struct Structure {
    pub bodies: Vec<String>,
    pub instances: Vec<String>,
    pub column_symmetries: Vec<String>,
}

/// The identity of a table of a program that holds no rows, of each of its columns, and the bodies that the evaluator joins for it, as
/// [`Structure::bodies`] gives them. An atom's `read` names the table of its relation by that table's place in the list `relations`, -1 for
/// a relation that the list does not hold.
pub struct RelationBodies {
    pub identity: String,
    pub columns: Vec<String>,
    pub bodies: Vec<Value>,
    /// The table's contents, with the sources of its columns.
    pub contents: crate::tables::Contents,
}

/// For each of `relations`, a graph relation with the form where its table stands and its name, the table's [`RelationBodies`], none where
/// the relation has no contents.
pub fn relation_bodies(checked: &CheckedProgram, registry: &Registry, relations: &[(GraphRelation, NodePath, String)]) -> Vec<Option<RelationBodies>> {
    let mut forms = Forms::new(checked, registry);
    let mut kept: Vec<usize> = Vec::new();
    let mut tables: Vec<Table> = Vec::new();
    for (at, (relation, form, name)) in relations.iter().enumerate() {
        if let Ok(contents) = crate::identity::relation_contents(checked, registry, relation, form, name) {
            kept.push(at);
            tables.push(Table { form: form.clone(), point: Point::Relation, contents: Ok(contents) });
        }
    }
    let mut identities = Identities::default();
    for table in &tables {
        let (ident, columns) = crate::identity::table_identity(&mut forms, table);
        identities.tables.push(ident);
        identities.columns.push(columns);
    }
    let graphs: Vec<Option<GraphRelation>> = kept.iter().map(|at| Some(relations[*at].0.clone())).collect();
    let shared = Shared { checked, registry, tables: tables.iter().collect(), graphs, identities: &identities, sees_all: true };
    let bodies: Vec<Vec<Value>> = (0..tables.len()).map(|place| shared.bodies(&mut forms, place)).collect();
    drop(shared);
    let mut out: Vec<Option<RelationBodies>> = relations.iter().map(|_| None).collect();
    for (place, ((at, table), bodies)) in kept.iter().zip(tables).zip(bodies).enumerate() {
        let Ok(contents) = table.contents else { continue };
        out[*at] = Some(RelationBodies { identity: identities.tables[place].clone(), columns: identities.columns[place].clone(), bodies, contents });
    }
    out
}

/// What every table's description reads: the case program, the tables with
/// the graph relation each stands for, and their identities.
struct Shared<'a> {
    checked: &'a CheckedProgram,
    registry: &'a Registry,
    tables: Vec<&'a Table>,
    graphs: Vec<Option<GraphRelation>>,
    identities: &'a Identities,
    /// Whether an atom reads the table of its relation wherever it stands among the tables, in place of only at or before the table that the body gives.
    sees_all: bool,
}

/// The structure of each of `tables`, the evidence tables and then the tables
/// of the case, with `graphs` the graph relation each stands for.
pub(crate) fn describe(
    checked: &CheckedProgram,
    registry: &Registry,
    forms: &mut Forms,
    tables: Vec<&Table>,
    graphs: Vec<Option<GraphRelation>>,
    identities: &Identities,
) -> Structure {
    let shared = Shared { checked, registry, tables, graphs, identities, sees_all: false };
    let mut out = Structure::default();
    for at in 0..shared.tables.len() {
        out.bodies.push(Value::Array(shared.bodies(forms, at)).to_string());
        out.instances.push(shared.instance(at).map(|value| value.to_string()).unwrap_or_default());
        out.column_symmetries.push(Value::Array(shared.column_symmetries(forms, at)).to_string());
    }
    out
}

impl Shared<'_> {
    /// The latest table at or before `at` that stands for `relation`.
    fn table_of(&self, relation: &GraphRelation, at: usize) -> Option<usize> {
        let last = self.graphs.len().saturating_sub(1);
        (0..=if self.sees_all { last } else { at.min(last) }).rev().find(|&other| self.graphs[other].as_ref() == Some(relation))
    }

    /// The evidence table of the fact relation `fact`, `ex_input` for `input`.
    fn fact_table(&self, fact: FactRelation) -> Option<usize> {
        let fact = if fact == FactRelation::Input { FactRelation::ExInput } else { fact };
        self.tables.iter().position(|table| matches!(&table.contents, Ok(contents) if contents.relation == TableRelation::Fact(fact)))
    }

    /// The identity of column `index` of table `table`.
    fn column(&self, table: usize, index: usize) -> String {
        self.identities.columns.get(table).and_then(|columns| columns.get(index)).cloned().unwrap_or_else(|| format!("?{index}"))
    }

    /// The bodies that the evaluator joins for the table `at`.
    fn bodies(&self, forms: &mut Forms, at: usize) -> Vec<Value> {
        let table = self.tables[at];
        let (Some(graph), Ok(contents)) = (&self.graphs[at], &table.contents) else { return Vec::new() };
        let width = contents.columns.len();
        let program = &self.checked.program;
        let output = graph.output.as_deref();
        let given: Vec<Given> = program
            .given(graph.node, self.registry)
            .into_iter()
            .filter(|relation| output.zip(relation.output.as_deref()).is_none_or(|(read, own)| read == own))
            .collect();
        let mut seen: Vec<(NodePath, NodePath)> = Vec::new();
        let mut bodies: Vec<Value> = Vec::new();
        for relation in &given {
            let bindings = program.column_bindings(graph.node, output, &relation.form, width, self.registry);
            let mut paths: Vec<NodePath> = relation.slots.iter().flat_map(|slot| slot.labels.iter().map(|label| label.body.clone())).collect();
            paths.sort();
            paths.dedup();
            for body in paths {
                if seen.contains(&(relation.form.clone(), body.clone())) {
                    continue;
                }
                seen.push((relation.form.clone(), body.clone()));
                let Some(ir) = self.checked.body_ir(self.registry, relation, &body) else { continue };
                let (clause, ir_paths) = ir.parts();
                if let Some(value) = self.body(forms, at, relation, &body, clause, ir_paths, &bindings) {
                    bodies.push(value);
                }
            }
        }
        bodies.sort_by_cached_key(Value::to_string);
        bodies
    }

    /// The body at `body` below the form of `relation`, compiled to `clause`
    /// with `paths`, `bindings` the bindings of the table's columns.
    #[allow(clippy::too_many_arguments)]
    fn body(
        &self,
        forms: &mut Forms,
        at: usize,
        relation: &Given,
        body: &NodePath,
        clause: &ClauseIr,
        paths: &IrPaths,
        bindings: &[arclog::resolver::given::PhysicalColumnBinding],
    ) -> Option<Value> {
        let top = relation.form.0.first()?.0 as usize;
        let identity = forms.of(top)?;
        let (query, form_hex) = &*identity;
        let order = &query.order;
        let within = NodePath(relation.form.join(body).0[1..].into());
        let scopes = order.label_scopes();
        let scope = scopes.iter().map(|(scope, _)| scope).filter(|scope| within.0.starts_with(&scope.0)).max_by_key(|scope| scope.0.len()).cloned().unwrap_or_default();
        let scope_spelled = order.try_canonical_path(&scope).map(|path| crate::identity::spelled(&path)).unwrap_or_default();
        let prefix = if scope_spelled.is_empty() { String::new() } else { format!("{scope_spelled}/") };
        let mut ids: Vec<String> = Vec::new();
        let mut positions: Vec<u32> = Vec::new();
        for label in paths.labels.iter() {
            match order.label_position(&scope, *label) {
                Some(position) => {
                    ids.push(format!("{prefix}#{position}"));
                    positions.push(position);
                }
                None => {
                    ids.push(format!("{prefix}?{}", label.0));
                    positions.push(u32::MAX);
                }
            }
        }
        let mut variables: Vec<(u32, Value)> = (0..ids.len())
            .map(|index| (positions[index], json!({"id": ids[index], "type": type_names(std::slice::from_ref(&clause.variables[index].ty)).remove(0)})))
            .collect();
        variables.sort_by_key(|(position, _)| *position);
        let by_label: StableHashMap<LabelId, &str> = paths.labels.iter().copied().zip(ids.iter().map(String::as_str)).collect();
        let mut table_columns: Vec<Value> = Vec::new();
        for (index, column) in bindings.iter().enumerate() {
            for binding in column.bindings.iter().filter(|binding| binding.form == relation.form && binding.body == *body) {
                if let Some(id) = by_label.get(&binding.label) {
                    table_columns.push(json!([self.column(at, index), id]));
                }
            }
        }
        table_columns.sort_by_cached_key(Value::to_string);
        let symmetries = order.label_permutations(&scope);
        let mut walk = Walk { shared: self, forms, table: at, ids, positions, form_hex: form_hex.clone() };
        let placed = vec![false; clause.variables.len()];
        let clause = walk.clause(clause, paths, placed);
        Some(json!({
            "form": form_hex,
            "scope": scope_spelled,
            "variables": variables.into_iter().map(|(_, value)| value).collect::<Vec<_>>(),
            "table_columns": table_columns,
            "symmetries": symmetries,
            "clause": clause,
        }))
    }

    /// The component and the input tables of the table `at`, where it stands
    /// for an output of an instance.
    fn instance(&self, at: usize) -> Option<Value> {
        let graph = self.graphs[at].as_ref()?;
        let program = &self.checked.program;
        let instance = match &program.graph.nodes[graph.node.0 as usize].kind {
            DependencyKind::InstanceOutput { instance, .. } | DependencyKind::RecursiveInstance(instance) => instance.clone(),
            _ => return None,
        };
        let form = self.tables[at].form.clone();
        let Some(arclog::program::path::NodeRef::Instance(written)) = arclog::program::path::node_at(arclog::program::path::NodeRef::Program(program.program.value()), &form) else { return None };
        let component = registry_columns::component(self.registry, &written.component)?;
        let mut inputs: Vec<Value> = Vec::new();
        for input in component.inputs.iter() {
            let number = (0..self.tables.len())
                .find(|&other| {
                    self.tables[other].form == form
                        && self.graphs[other].as_ref().is_some_and(|graph| {
                            matches!(&program.graph.nodes[graph.node.0 as usize].kind, DependencyKind::InstanceInput { instance: owner, input: port } if *owner == instance && *port == input.port.name)
                        })
                })
                .map_or(-1, |other| other as i64);
            inputs.push(json!([input.port.name.0, number]));
        }
        Some(json!({"component": written.component.0, "inputs": inputs}))
    }

    /// The permutations of the column identities of the table `at` under which
    /// its content is the same: those that a symmetry of the labels of its
    /// form's scope induces on the columns that the labels bind.
    fn column_symmetries(&self, forms: &mut Forms, at: usize) -> Vec<Value> {
        let table = self.tables[at];
        let Ok(contents) = &table.contents else { return Vec::new() };
        if !matches!(table.point, Point::Relation) || matches!(contents.relation, TableRelation::Fact(_)) {
            return Vec::new();
        }
        let Some(top) = table.form.0.first().map(|step| step.0 as usize) else { return Vec::new() };
        let Some(identity) = forms.of(top) else { return Vec::new() };
        let order = &identity.0.order;
        let root = NodePath::default();
        let labels: Vec<Vec<u32>> = (0..contents.columns.len())
            .map(|index| {
                let bound = contents.bound_labels.get(index).map(|labels| &labels[..]).unwrap_or_default();
                let mut positions: Vec<u32> = contents.columns[index].label_id.iter().chain(bound).filter_map(|label| order.label_position(&root, *label)).collect();
                positions.sort_unstable();
                positions.dedup();
                positions
            })
            .collect();
        let mut found: Vec<Vec<(usize, usize)>> = Vec::new();
        for permutation in order.label_permutations(&root) {
            let mut moved: Vec<(usize, usize)> = Vec::new();
            let mut taken = vec![false; labels.len()];
            let mut valid = true;
            for (index, positions) in labels.iter().enumerate() {
                if positions.is_empty() {
                    taken[index] = true;
                    continue;
                }
                let mut image: Vec<u32> = positions.iter().map(|position| permutation.get(*position as usize).copied().unwrap_or(u32::MAX)).collect();
                image.sort_unstable();
                let target = if labels[index] == image && !taken[index] { Some(index) } else { (0..labels.len()).find(|&other| !taken[other] && labels[other] == image) };
                match target {
                    Some(target) => {
                        taken[target] = true;
                        if target != index {
                            moved.push((index, target));
                        }
                    }
                    None => {
                        valid = false;
                        break;
                    }
                }
            }
            if valid && !moved.is_empty() && !found.contains(&moved) {
                found.push(moved);
            }
        }
        found.sort();
        found.into_iter().map(|moved| Value::Array(moved.into_iter().map(|(from, to)| json!([self.column(at, from), self.column(at, to)])).collect())).collect()
    }
}

/// The walk over one body's IR.
struct Walk<'w, 'a, 'f> {
    shared: &'w Shared<'a>,
    forms: &'w mut Forms<'f>,
    /// The table whose body this is.
    table: usize,
    /// The id of each variable of the clause, by its index.
    ids: Vec<String>,
    /// The canonical position of each variable's label in its scope.
    positions: Vec<u32>,
    form_hex: String,
}

impl Walk<'_, '_, '_> {
    fn id(&self, variable: Variable) -> &str {
        self.ids.get(usize::from(variable.0)).map_or("?", String::as_str)
    }

    /// The ids of `variables`, in the order of their canonical positions.
    fn ids_of(&self, variables: &[Variable]) -> Vec<&str> {
        let mut sorted: Vec<Variable> = variables.to_vec();
        sorted.sort_by_key(|variable| (self.positions.get(usize::from(variable.0)).copied().unwrap_or(u32::MAX), variable.0));
        sorted.into_iter().map(|variable| self.id(variable)).collect()
    }

    fn argument(&self, argument: &Argument) -> Value {
        match argument {
            Argument::Variable(variable) => json!({"v": self.id(*variable)}),
            Argument::Term(term) => json!({"t": term.encoding().to_string()}),
        }
    }

    /// A clause, `placed` the variables that are bound before it.
    fn clause(&mut self, clause: &ClauseIr, paths: &IrPaths, placed: Vec<bool>) -> Value {
        let uses = lib_uses(self.shared.registry, clause, &placed);
        let mut nodes: Vec<Value> = Vec::new();
        for (index, node) in clause.nodes.iter().enumerate() {
            let at = paths.nodes.get(index);
            nodes.push(self.node(node, at, uses.get(&index)));
        }
        nodes.sort_by_cached_key(Value::to_string);
        json!({"columns": self.ids_of(&clause.columns), "nodes": nodes})
    }

    fn node(&mut self, node: &IrNode, at: Option<&NodePaths>, lib: Option<&LibUse>) -> Value {
        match node {
            IrNode::Atom(atom) => {
                let (form, path) = match at {
                    Some(NodePaths::Atom(path)) => atom_identity(self.forms, path),
                    Some(NodePaths::Key(_)) => (self.form_hex.clone(), "key".to_owned()),
                    _ => (String::new(), String::new()),
                };
                let lifted_path = if let Some(NodePaths::Atom(path)) = at { Some(path) } else { None };
                let (read, args) = self.read(&atom.source, &atom.arguments, at, lifted_path);
                json!({"k": "atom", "form": form, "path": path, "read": read, "train_only": atom.train_only, "args": args})
            }
            IrNode::Lib(atom) => {
                let (form, path) = match at {
                    Some(NodePaths::Atom(path)) => atom_identity(self.forms, path),
                    _ => (String::new(), String::new()),
                };
                let relation = self.shared.registry.algebra_relation(&atom.relation);
                let mut args: Vec<Value> = atom
                    .arguments
                    .0
                    .iter()
                    .map(|(column, argument)| {
                        let name = relation.and_then(|relation| relation.columns.get(usize::from(column.0))).map_or_else(|| format!("{}", column.0), |column| column_spelled(&column.name));
                        json!([name, self.argument(argument)])
                    })
                    .collect();
                args.sort_by_cached_key(Value::to_string);
                let (mode, computes) = match lib {
                    Some(lib) => (lib.mode.as_ref().map(|mode| json!(mode)).unwrap_or(Value::Null), self.ids_of(&lib.computes).into_iter().map(str::to_owned).collect::<Vec<_>>()),
                    None => (Value::Null, Vec::new()),
                };
                json!({"k": "lib", "form": form, "path": path, "relation": atom.relation.0, "args": args, "mode": mode, "computes": computes})
            }
            IrNode::Comparison(comparison) => {
                let second = match comparison.second {
                    Operand::Variable(variable) => json!({"v": self.id(variable)}),
                    Operand::Zero => json!({"t": "0"}),
                };
                json!({"k": "cmp", "op": op_spelled(comparison.op), "first": self.id(comparison.first), "second": second, "binds_first": comparison.binds_first})
            }
            IrNode::Not(filter) | IrNode::Counterexample(filter) => {
                let kind = if matches!(node, IrNode::Not(_)) { "not" } else { "all" };
                let empty = IrPaths::default();
                let inner = match at {
                    Some(NodePaths::Filter(paths)) => &**paths,
                    _ => &empty,
                };
                let mut placed = vec![false; filter.body.variables.len()];
                for variable in filter.outer.iter() {
                    if let Some(held) = placed.get_mut(usize::from(variable.0)) {
                        *held = true;
                    }
                }
                let body = self.clause(&filter.body, inner, placed);
                json!({"k": kind, "outer": self.ids_of(&filter.outer), "body": body})
            }
            IrNode::Or(union) => {
                let branch_paths: &[IrPaths] = match at {
                    Some(NodePaths::Branches(branches)) => branches,
                    _ => &[],
                };
                let empty = IrPaths::default();
                let mut branches: Vec<Value> = Vec::new();
                for (index, branch) in union.branches.iter().enumerate() {
                    let mut placed = vec![false; branch.variables.len()];
                    for variable in branch.columns.iter().filter(|variable| !union.exported.contains(variable)) {
                        if let Some(held) = placed.get_mut(usize::from(variable.0)) {
                            *held = true;
                        }
                    }
                    branches.push(self.clause(branch, branch_paths.get(index).unwrap_or(&empty), placed));
                }
                branches.sort_by_cached_key(Value::to_string);
                json!({"k": "or", "exported": self.ids_of(&union.exported), "branches": branches})
            }
        }
    }

    /// What an atom of a relation with rows reads, and its arguments, each at
    /// the identity of the column read.
    fn read(&mut self, source: &AtomSource, arguments: &Arguments, at: Option<&NodePaths>, path: Option<&NodePath>) -> (Value, Vec<Value>) {
        let shared = self.shared;
        let program = &shared.checked.program;
        let mut args: Vec<Value> = Vec::new();
        let read = match source {
            AtomSource::Key(read) => {
                let empty = IrPaths::default();
                let inner = match at {
                    Some(NodePaths::Key(paths)) => &**paths,
                    _ => &empty,
                };
                for (column, argument) in arguments.0.iter() {
                    let name = read.clause.columns.get(usize::from(column.0)).map_or_else(|| format!("?{}", column.0), |variable| self.id(*variable).to_owned());
                    args.push(json!([name, self.argument(argument)]));
                }
                let placed = vec![false; read.clause.variables.len()];
                json!({"key": self.clause(&read.clause, inner, placed)})
            }
            AtomSource::Undefined(_) => {
                for (column, argument) in arguments.0.iter() {
                    args.push(json!([format!("@{}", column.0), self.argument(argument)]));
                }
                json!({"undefined": true})
            }
            AtomSource::Fact(_) | AtomSource::Relation(_) => {
                let (target, node, fact) = match source {
                    AtomSource::Fact(fact) => (shared.fact_table(*fact), None, Some(*fact)),
                    AtomSource::Relation(relation) => (shared.table_of(relation, self.table), Some(relation.node), None),
                    _ => unreachable!("a fact or a relation"),
                };
                let input = fact == Some(FactRelation::Input);
                let lifted = path.is_some_and(|path| program.reads_lifted(path));
                let coordinates = ReadCoordinates::new(input, lifted);
                let rows = node.and_then(|node| program.row_paths(node));
                let held = target.and_then(|target| match &shared.tables[target].contents {
                    Ok(contents) => contents.rows.as_ref(),
                    Err(_) => None,
                });
                for (column, argument) in arguments.0.iter() {
                    let name = match coordinates.source(column.0) {
                        Some(SourceColumn::Position(position)) => match target {
                            None => format!("@{position}"),
                            Some(target) => {
                                let index = match (&rows, held) {
                                    (Some(now), Some(held)) => now.get(usize::from(position)).and_then(|path| held.iter().position(|row| row == path)),
                                    _ => Some(usize::from(position)),
                                };
                                index.map_or_else(|| format!("?{position}"), |index| shared.column(target, index))
                            }
                        },
                        Some(SourceColumn::Example) => "@example".to_owned(),
                        _ => format!("?{}", column.0),
                    };
                    args.push(json!([name, self.argument(argument)]));
                }
                let table = target.map_or(-1, |target| target as i64);
                match fact {
                    Some(fact) => json!({"fact": spelling(FACT_RELATIONS, &fact), "table": table}),
                    None => json!({"table": table}),
                }
            }
        };
        args.sort_by_cached_key(Value::to_string);
        (read, args)
    }
}

fn op_spelled(op: ConstraintOp) -> &'static str {
    match op {
        ConstraintOp::Eq => "=",
        ConstraintOp::Ne => "!=",
        ConstraintOp::Lt => "<",
        ConstraintOp::Le => "<=",
        ConstraintOp::Gt => ">",
        ConstraintOp::Ge => ">=",
    }
}

/// What an algebra relation's atom does in its clause: the lib columns that
/// the mode it holds at binds (none where the relation has no mode), and the
/// variables that it gives values to.
struct LibUse {
    mode: Option<Vec<String>>,
    computes: Vec<Variable>,
}

/// The mode of each algebra relation's atom of `clause` (by the atom's node
/// index), where `placed` are the variables bound before the clause. The
/// variables that an atom of a relation with rows reads, that an `=` with `0`
/// gives, that a union exports and that have an orientation type are placed
/// from the start, the last since the evaluator binds them by their domain.
/// Then, until nothing changes, an `=` places the other variable of a placed
/// one, and each algebra relation whose columns at the placed variables
/// satisfy a mode, or that has no mode, holds at that mode and gives values
/// to its variables that were not placed when the round began. An atom whose
/// mode never holds is left out.
fn lib_uses(registry: &Registry, clause: &ClauseIr, placed: &[bool]) -> BTreeMap<usize, LibUse> {
    let mut placed = placed.to_vec();
    placed.resize(clause.variables.len(), false);
    let place = |placed: &mut Vec<bool>, variable: Variable| -> bool {
        let held = &mut placed[usize::from(variable.0)];
        !std::mem::replace(held, true)
    };
    for (index, info) in clause.variables.iter().enumerate() {
        if info.ty.orientation_types().is_some() {
            placed[index] = true;
        }
    }
    for node in clause.nodes.iter() {
        match node {
            IrNode::Atom(atom) => {
                for (_, argument) in atom.arguments.0.iter() {
                    if let Argument::Variable(variable) = argument {
                        place(&mut placed, *variable);
                    }
                }
            }
            IrNode::Or(union) => {
                for variable in union.exported.iter() {
                    place(&mut placed, *variable);
                }
            }
            IrNode::Comparison(comparison) if comparison.op == ConstraintOp::Eq && comparison.second == Operand::Zero => {
                place(&mut placed, comparison.first);
            }
            _ => {}
        }
    }
    let mut uses: BTreeMap<usize, LibUse> = BTreeMap::new();
    loop {
        let mut changed = false;
        for node in clause.nodes.iter() {
            if let IrNode::Comparison(comparison) = node {
                if let (ConstraintOp::Eq, Operand::Variable(second)) = (comparison.op, comparison.second) {
                    let (first_placed, second_placed) = (placed[usize::from(comparison.first.0)], placed[usize::from(second.0)]);
                    if first_placed && !second_placed {
                        changed |= place(&mut placed, second);
                    } else if second_placed && !first_placed {
                        changed |= place(&mut placed, comparison.first);
                    }
                }
            }
        }
        let round = placed.clone();
        for (index, node) in clause.nodes.iter().enumerate() {
            let IrNode::Lib(atom) = node else { continue };
            if uses.contains_key(&index) {
                continue;
            }
            let Some(relation) = registry.algebra_relation(&atom.relation) else { continue };
            let mut columns = vec![false; relation.columns.len()];
            for (column, argument) in atom.arguments.0.iter() {
                if let Some(held) = columns.get_mut(usize::from(column.0)) {
                    *held = match argument {
                        Argument::Term(_) => true,
                        Argument::Variable(variable) => round[usize::from(variable.0)],
                    };
                }
            }
            let mode = if relation.modes.is_empty() {
                Some(None)
            } else {
                satisfied_mode(relation, &columns).map(|mode| Some(relation.modes[mode].bound.iter().map(column_spelled).collect::<Vec<_>>()))
            };
            let Some(mode) = mode else { continue };
            let mut computes: Vec<Variable> = Vec::new();
            for (_, argument) in atom.arguments.0.iter() {
                if let Argument::Variable(variable) = argument {
                    if !round[usize::from(variable.0)] && !computes.contains(variable) {
                        computes.push(*variable);
                    }
                }
            }
            for variable in &computes {
                place(&mut placed, *variable);
            }
            changed = true;
            uses.insert(index, LibUse { mode, computes });
        }
        if !changed {
            break;
        }
    }
    uses
}

/// The graph relation each of `tables` stands for, none for a table that is
/// not a relation of a form.
pub(crate) fn graph_relations(
    checked: &CheckedProgram,
    registry: &Registry,
    relations: &[arclog::program::ProgramRelation],
    tables: &[&Table],
) -> Vec<Option<GraphRelation>> {
    tables
        .iter()
        .map(|table| {
            let contents = table.contents.as_ref().ok()?;
            let TableRelation::Slot(slot) = contents.relation else { return None };
            if !matches!(table.point, Point::Relation) {
                return None;
            }
            crate::tables::graph_relation(checked, registry, &table.form, relations.get(slot as usize)?)
        })
        .collect()
}
