//! The rows of each of many atoms joined to the body in progress at a state of
//! a decode, with no program made for any of them.

use std::collections::HashMap;
use std::sync::Arc;

use super::interface::{relation_dets, SubBody};
use super::{Assigned, Decoder};
use crate::eval::ir::{Argument, Arguments, AtomSource, ClauseIr, Filter, IrNode, LibAtom, RelationAtom, Variable, VariableInfo};
use crate::eval::join::{self, Budget, JoinInputs, NodeInput};
use crate::eval::{examples, plan};
use crate::eval::{Evaluation, Limits, Outcome, ParameterValues, ReachedBound, RelationValue, TableWork};
use crate::program::{FactRelation, ProgramRelation, RelationRef};
use crate::relations::{ColumnIndex, Relation, RelationPart};
use crate::resolver::DependencyKind;
use crate::stream::{Control, Token};
use crate::terms::{Example, TermId};
use crate::types::{GraphRelation, ValueType};

/// The body's rows at each assignment of each example, each part of them held
/// as a relation of its own, so that its indexes serve each atom.
pub struct BaseRows {
    /// The labels of the body's columns, in order, and their types.
    pub columns: Vec<(crate::program::LabelId, ValueType)>,
    /// The `DET`s of the body's assignments.
    dets: Vec<ProgramRelation>,
    /// For each example, at each assignment: the assignment and the body's value.
    examples: Vec<(Option<Example>, Outcome<Assigned<HeldBase>>)>,
    /// Whether the body is evaluated once for the task.
    task_wide: bool,
}

/// The value of a body at one assignment of one example.
struct HeldBase {
    value: RelationValue,
    /// One relation for each part of the value's rows.
    parts: Vec<Arc<Relation>>,
}

/// One candidate atom as the join reads it.
struct AtomPlan {
    negated: bool,
    source: PlanSource,
    /// The column of the relation and what stands at it, for each site.
    sites: Vec<(ColumnIndex, PlanArgument)>,
    /// The type of each label the atom makes.
    made: Vec<ValueType>,
    /// The type of each column of the body after the atom, in order.
    types: Vec<ValueType>,
    /// The variables of a clause of the body's columns and the labels the atom makes.
    variables: Box<[VariableInfo]>,
}

#[derive(Clone)]
enum PlanSource {
    Lib(crate::registry::LibName),
    Fact(FactRelation),
    Relation(GraphRelation, u32),
}

#[derive(Clone, Copy)]
enum PlanArgument {
    Column(u16),
    Made(u16),
    Zero,
}

/// What is known of a relation that an atom opens.
#[derive(Clone)]
struct OpenedRelation {
    reference: RelationRef,
    columns: Arc<[crate::program::ColumnName]>,
    source: PlanSource,
    /// The place among the relation's rows of each column of `columns`, where
    /// it is not the column's own place.
    places: Option<Vec<u16>>,
}

/// What the join gives for one atom.
pub enum AtomRows {
    /// The types of the columns of the atom's table, and for each example, at
    /// each assignment, the value.
    Rows { types: Vec<ValueType>, examples: Vec<(Option<Example>, Outcome<Assigned<Vec<RelationValue>>>)> },
    /// The body with the atom is no body that a program holds, so it has no table.
    NoTable,
    /// The atom's work passed the cap.
    OverCap,
    /// The join does not read the atom. A program made for it does.
    ByProgram,
}

impl<'a> Decoder<'a> {
    /// The rows of the body `sub`, none for a body of no conjunct, at each
    /// assignment of each example.
    pub fn base_rows(&self, sub: Option<&SubBody>, columns: Vec<(crate::program::LabelId, ValueType)>, dets: Vec<ProgramRelation>, work: &TableWork) -> BaseRows {
        let Some(sub) = sub else {
            let unit = |example: Option<Example>| (example, Ok(Assigned { at: vec![(Vec::new(), HeldBase { value: RelationValue::Rows(Arc::new(Relation::from_parts(0, Box::new([])))), parts: Vec::new() })], stop: None }));
            let task_wide = self.body_is_task_wide();
            let scope = if task_wide { examples::ExampleScope::TaskWide } else { examples::ExampleScope::PerExample };
            return BaseRows { columns, dets, examples: self.examples_of(scope).into_iter().map(unit).collect(), task_wide };
        };
        let examples = self.examples_of(sub.scope).into_iter().zip(self.values_of(sub, Some(work)).into_vec()).map(|(example, value)| {
            let held = value.map(|assigned| Assigned {
                at: assigned.at.into_iter().map(|(values, value)| {
                    let value = value.0;
                    let parts = match &value {
                        RelationValue::Rows(rows) => rows.parts().iter().map(|part| Arc::new(join::one_part(part.rows.clone()))).collect(),
                        _ => Vec::new(),
                    };
                    (values, HeldBase { value, parts })
                }).collect(),
                stop: assigned.stop,
            });
            (example, held)
        }).collect();
        BaseRows { columns, dets, examples, task_wide: sub.scope == examples::ExampleScope::TaskWide }
    }

    /// What is known of the relation that the token `id` opens, none for a
    /// token that opens no atom of a relation the join reads.
    fn opened_relation(&self, sub: Option<&SubBody>, base: &BaseRows, id: u32) -> Option<OpenedRelation> {
        let token = self.vocabulary().token(id)?;
        let opened = self.next_state(token).ok()?.0;
        let (columns, no_site) = opened.open_atom_columns()?;
        if !no_site {
            return None;
        }
        let reference = opened.open_relation()?;
        // A read of a relation can give an `INIT` form a side of its own, and a body of another side has other rows.
        if matches!(token, Token::Fact(_) | Token::Relation(_)) && !self.keeps_side(&opened, base.task_wide) {
            return None;
        }
        let mut places = None;
        let source = match token {
            Token::Lib(name) => {
                // A rule that reads whether two labels stand in one grid reads what only a program tells.
                if self.context.registry.algebra_relation(name)?.rules.iter().any(|rule| !rule.same_frame.is_empty()) {
                    return None;
                }
                PlanSource::Lib(name.clone())
            }
            Token::Fact(fact) => {
                if base.task_wide && fact.per_example() {
                    return None;
                }
                PlanSource::Fact(*fact)
            }
            Token::Relation(slot) => {
                let program = &sub?.program;
                let node = program.program.program_read(&reference)?;
                let output = match (&reference, &program.program.graph.nodes[node.0 as usize].kind) {
                    (RelationRef::Output(name), DependencyKind::RigidAssembly(_) | DependencyKind::RecursiveInstance(_)) => Some(name.path.clone()),
                    _ => None,
                };
                let relation = GraphRelation { node, output };
                if base.task_wide && examples::scope_of(program, &relation) == examples::ExampleScope::PerExample {
                    return None;
                }
                if !program.program.example_columns(relation.node, relation.output.as_deref()).is_empty() {
                    return None;
                }
                if !relation_dets(program, node).iter().all(|det| base.dets.contains(&det.relation)) {
                    return None;
                }
                if relation.output.is_some() {
                    return None;
                }
                let rows = program.program.read_row_paths(node)?;
                places = Some(columns.iter().map(|name| rows.iter().position(|path| matches!(&path[..], [one] if one == name)).and_then(|at| u16::try_from(at).ok())).collect::<Option<Vec<u16>>>()?);
                PlanSource::Relation(relation, *slot)
            }
            _ => return None,
        };
        Some(OpenedRelation { reference, columns, source, places })
    }

    /// How the join reads the atom `tokens`, or what stands in place of it.
    /// `labels` is the count of labels at this state.
    fn atom_plan(&self, opened: &OpenedRelation, base: &BaseRows, labels: u32, negated: bool, sites: &[u32], column_type: &dyn Fn(&RelationRef, &crate::program::ColumnName) -> Option<ValueType>) -> Result<AtomPlan, AtomRows> {
        let vocabulary = self.vocabulary();
        let token = |id: &u32| vocabulary.token(*id).expect("an id of the vocabulary");
        let mut types: Vec<ValueType> = base.columns.iter().map(|(_, ty)| ty.clone()).collect();
        let mut made: Vec<ValueType> = Vec::new();
        let mut plan: Vec<(ColumnIndex, PlanArgument)> = Vec::new();
        let mut at = sites.iter();
        while let Some(column) = at.next() {
            let Token::Column(position) = token(column) else { return Err(AtomRows::ByProgram) };
            let name = opened.columns.get(*position as usize).ok_or(AtomRows::ByProgram)?;
            let ty = column_type(&opened.reference, name).ok_or(AtomRows::ByProgram)?;
            // A program places a column of Examples by rules of its own.
            if ty == ValueType::Example {
                return Err(AtomRows::ByProgram);
            }
            let column = match &opened.places {
                Some(places) => ColumnIndex(*places.get(*position as usize).ok_or(AtomRows::ByProgram)?),
                None => ColumnIndex(u16::try_from(*position).map_err(|_| AtomRows::ByProgram)?),
            };
            match token(at.next().ok_or(AtomRows::ByProgram)?) {
                Token::Label(label) if *label >= labels => {
                    let index = (*label - labels) as usize;
                    let held = made.get_mut(index).ok_or(AtomRows::ByProgram)?;
                    match held.meet(&ty) {
                        crate::types::Meet::Type(met) => *held = met,
                        crate::types::Meet::Empty => return Err(AtomRows::ByProgram),
                    }
                    plan.push((column, PlanArgument::Made(index as u16)));
                }
                Token::Label(label) => {
                    let place = base.columns.iter().position(|(held, _)| held.0 == *label).ok_or(AtomRows::ByProgram)?;
                    match types[place].meet(&ty) {
                        crate::types::Meet::Type(met) if !negated => types[place] = met,
                        crate::types::Meet::Type(_) => {}
                        crate::types::Meet::Empty => return Err(AtomRows::ByProgram),
                    }
                    plan.push((column, PlanArgument::Column(place as u16)));
                }
                // In a body that a clause reads, a label that a key marks is a label that the body makes.
                Token::Control(Control::Fresh | Control::Key) => {
                    // No check passes a `NOT` atom one of whose sites makes a label.
                    if negated {
                        return Err(AtomRows::NoTable);
                    }
                    plan.push((column, PlanArgument::Made(made.len() as u16)));
                    made.push(ty);
                }
                Token::Control(Control::Zero) => plan.push((column, PlanArgument::Zero)),
                _ => return Err(AtomRows::ByProgram),
            }
        }
        self.apply_rules(opened, &plan, &mut types, &mut made, negated).ok_or(AtomRows::ByProgram)?;
        let width = base.columns.len();
        let variables = types[..width].iter().cloned().chain(made.iter().cloned()).map(|ty| VariableInfo { ty }).collect();
        if !negated {
            types.extend(made.iter().cloned());
        }
        Ok(AtomPlan { negated, source: opened.source.clone(), sites: plan, made, types, variables })
    }

    /// Meets the type of each label at a site of a lib relation with what a
    /// type rule of the relation gives its column there; none where the types
    /// have no meet.
    fn apply_rules(&self, opened: &OpenedRelation, sites: &[(ColumnIndex, PlanArgument)], types: &mut [ValueType], made: &mut [ValueType], negated: bool) -> Option<()> {
        let PlanSource::Lib(name) = &opened.source else { return Some(()) };
        let rules = &self.context.registry.algebra_relation(name)?.rules;
        if rules.is_empty() {
            return Some(());
        }
        let argument_at = |column: &crate::program::ColumnName| {
            let position = opened.columns.iter().position(|name| name == column)? as u16;
            sites.iter().find(|(at, _)| at.0 == position).map(|&(_, argument)| argument)
        };
        // A rule reads the types of the labels that the others leave: two rounds reach what one rule gives another.
        for _ in 0..2 {
            for rule in rules.iter() {
                let held = rule.holds(&|column: &crate::program::ColumnName| match argument_at(column)? {
                    PlanArgument::Column(place) => Some(types[usize::from(place)].clone()),
                    PlanArgument::Made(index) => Some(made[usize::from(index)].clone()),
                    PlanArgument::Zero => None,
                }, &|_, _| false);
                if !held {
                    continue;
                }
                for (column, ty) in rule.gives.iter() {
                    let slot = match argument_at(column) {
                        Some(PlanArgument::Column(place)) if !negated => &mut types[usize::from(place)],
                        Some(PlanArgument::Made(index)) => &mut made[usize::from(index)],
                        _ => continue,
                    };
                    match slot.meet(ty) {
                        crate::types::Meet::Type(met) => *slot = met,
                        crate::types::Meet::Empty => return None,
                    }
                }
            }
        }
        Some(())
    }

    /// What the join gives for each atom of `atoms`, each its token ids.
    /// `labels` is the count of labels at this state, and each atom's work
    /// counts under `cap`.
    pub fn atom_rows(&self, sub: Option<&SubBody>, base: &BaseRows, labels: u32, atoms: &[Box<[u32]>], cap: u64) -> Vec<AtomRows> {
        // A `NOT` that stands before the atoms reads them in a way that the tokens of an atom do not show.
        if self.state.negation_pending() {
            return atoms.iter().map(|_| AtomRows::ByProgram).collect();
        }
        let limits = self.limits();
        let mut opened: HashMap<u32, Option<OpenedRelation>> = HashMap::new();
        let not = self.vocabulary().id(&Token::Control(Control::Not));
        let plans: Vec<Result<AtomPlan, AtomRows>> = self.with_checks_at_state(|checks| {
            let column_type = |relation: &RelationRef, column: &crate::program::ColumnName| self.fixed_column_type(checks, relation, column);
            atoms.iter().map(|atom| {
                let negated = atom.first().copied() == not;
                let rest = if negated { &atom[1..] } else { &atom[..] };
                let (relation, sites) = rest.split_first().ok_or(AtomRows::ByProgram)?;
                let held = opened.entry(*relation).or_insert_with(|| self.opened_relation(sub, base, *relation));
                let held = held.as_ref().ok_or(AtomRows::ByProgram)?;
                self.atom_plan(held, base, labels, negated, sites, &column_type)
            }).collect()
        });
        // The rows of a relation that atoms read, at each assignment of each example.
        let mut read: HashMap<(u32, usize, usize), Option<Arc<Relation>>> = HashMap::new();
        plans.into_iter().map(|plan| {
            let plan = match plan {
                Ok(plan) => plan,
                Err(other) => return other,
            };
            let work = TableWork::new(cap);
            let limits = limits.clone().counted_in(work);
            let mut found = Vec::with_capacity(base.examples.len());
            for (at_example, (example, held)) in base.examples.iter().enumerate() {
                let value = match held {
                    Err(fault) => Err(fault.clone()),
                    Ok(assigned) => {
                        let mut at = Vec::with_capacity(assigned.at.len());
                        for (at_assignment, (values, held)) in assigned.at.iter().enumerate() {
                            let value = match &held.value {
                                RelationValue::Rows(rows) => {
                                    let input = match &plan.source {
                                        PlanSource::Relation(relation, slot) => {
                                            let rows = read.entry((*slot, at_example, at_assignment)).or_insert_with(|| {
                                                let program = &sub.expect("a body where an atom reads a relation of the program").program;
                                                let (task, session, constructions) = self.evaluation_inputs();
                                                let parameters = ParameterValues::determined(values.clone());
                                                let evaluation = Evaluation { program, concept: None, task, session, constructions, registry: self.context.registry, parameters: &parameters, limits: &limits };
                                                let on = (examples::scope_of(program, relation) == examples::ExampleScope::PerExample).then_some(*example).flatten();
                                                match evaluation.relation(relation, on) {
                                                    Ok(RelationValue::Rows(rows)) => Some(rows),
                                                    _ => None,
                                                }
                                            });
                                            match rows {
                                                Some(rows) => NodeInput::Relation(Arc::clone(rows)),
                                                None => return AtomRows::ByProgram,
                                            }
                                        }
                                        PlanSource::Fact(fact) => {
                                            let on = fact.per_example().then_some(*example).flatten();
                                            NodeInput::Relation(self.session.fact_relation(self.task, *fact, on))
                                        }
                                        PlanSource::Lib(_) => NodeInput::Unread,
                                    };
                                    match self.joined(rows, &held.parts, &plan, input, base.columns.len(), &limits) {
                                        Ok(value) => value,
                                        Err(ReachedBound::TableWork { .. }) => return AtomRows::OverCap,
                                        Err(_) => return AtomRows::ByProgram,
                                    }
                                }
                                other => other.clone(),
                            };
                            at.push((values.clone(), vec![value]));
                        }
                        Ok(Assigned { at, stop: assigned.stop.clone() })
                    }
                };
                found.push((*example, value));
            }
            AtomRows::Rows { types: plan.types, examples: found }
        }).collect()
    }

    /// The value of the atom of `plan`, reading `input`, joined to the body's rows `rows`.
    fn joined(&self, rows: &Relation, parts: &[Arc<Relation>], plan: &AtomPlan, input: NodeInput, width: usize, limits: &Limits) -> Result<RelationValue, ReachedBound> {
        // The variable of a column of the body is its place, and that of a made label follows them.
        let variable_of = |argument: PlanArgument| match argument {
            PlanArgument::Column(column) => Argument::Variable(Variable(column)),
            PlanArgument::Made(index) => Argument::Variable(Variable(width as u16 + index)),
            PlanArgument::Zero => Argument::Term(TermId::from_encoding(0)),
        };
        let arguments = Arguments(plan.sites.iter().map(|&(column, argument)| (column, variable_of(argument))).collect());
        let joins = |column: u16| plan.sites.iter().any(|&(_, argument)| matches!(argument, PlanArgument::Column(held) if held == column));
        let mut nodes: Vec<IrNode> = Vec::new();
        let mut inputs: Vec<NodeInput> = Vec::new();
        let mut kept: Vec<RelationPart> = Vec::new();
        let mut joined_columns: Vec<Variable> = Vec::new();
        for (part, held) in rows.parts().iter().zip(parts) {
            if part.columns.iter().any(|column| joins(column.0)) {
                let arguments = part.columns.iter().enumerate().map(|(at, column)| (ColumnIndex(at as u16), Argument::Variable(Variable(column.0)))).collect();
                nodes.push(IrNode::Atom(RelationAtom { source: AtomSource::Fact(FactRelation::Input), train_only: false, arguments: Arguments(arguments) }));
                inputs.push(NodeInput::Relation(Arc::clone(held)));
                joined_columns.extend(part.columns.iter().map(|column| Variable(column.0)));
            } else {
                kept.push(part.clone());
            }
        }
        let node = match &plan.source {
            PlanSource::Lib(name) => IrNode::Lib(LibAtom { relation: name.clone(), arguments }),
            PlanSource::Fact(fact) => IrNode::Atom(RelationAtom { source: AtomSource::Fact(*fact), train_only: false, arguments }),
            PlanSource::Relation(relation, _) => IrNode::Atom(RelationAtom { source: AtomSource::Relation(relation.clone()), train_only: false, arguments }),
        };
        if plan.negated {
            let mut outer: Vec<Variable> = plan.sites.iter().filter_map(|&(_, argument)| match argument { PlanArgument::Column(column) => Some(Variable(column)), _ => None }).collect();
            outer.sort_by_key(|variable| variable.0);
            outer.dedup();
            let body = ClauseIr { variables: plan.variables.clone(), nodes: Box::new([node]), columns: Box::new([]) };
            nodes.push(IrNode::Not(Filter { outer: outer.into(), body: Box::new(body) }));
            inputs.push(NodeInput::Clauses(Box::new([JoinInputs(Box::new([input]))])));
        } else {
            joined_columns.extend((0..plan.made.len()).map(|index| Variable(width as u16 + index as u16)));
            nodes.push(node);
            inputs.push(input);
        }
        let clause = ClauseIr { variables: plan.variables.clone(), nodes: nodes.into(), columns: joined_columns.into() };
        let inputs = JoinInputs(inputs.into());
        let order = plan::variable_order(&clause, &join::sizes(&clause, &inputs), &[]);
        let all: Vec<usize> = (0..clause.nodes.len()).collect();
        let mut budget = Budget::new(limits, self.session);
        for part in join::parts(&clause, &all, &|node| node) {
            let columns = part.columns(&clause);
            let found = join::search_part(&clause, &part.nodes, part.order(&order, &[]), &inputs, self.context.registry, &columns, &mut budget)?;
            kept.extend(found.parts().iter().map(|found| RelationPart {
                columns: found.columns.iter().map(|column| ColumnIndex(clause.columns[usize::from(columns[usize::from(column.0)].0)].0)).collect(),
                rows: found.rows.clone(),
            }));
        }
        let arity = if plan.negated { width } else { width + plan.made.len() };
        let kept: Vec<RelationPart> = kept.into_iter().filter(|part| !part.columns.is_empty() || part.rows.is_empty()).collect();
        let relation = Relation::from_parts(arity as u16, kept.into());
        // A program counts the rows of a product as the bindings of its walk, and stops at their cap.
        budget.charge_product(&relation)?;
        Ok(RelationValue::Rows(Arc::new(relation)))
    }
}
