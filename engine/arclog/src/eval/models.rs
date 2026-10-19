//! The models of a case on an input, as `docs/engine/cases.md#models` gives
//! them: [`Evaluation::models`] gives the value of a relation at each model,
//! one at a time, until its visitor stops it, the models end, or a cap is
//! reached.
//!
//! A factor is an entry of a pick, a chosen relation on one example or
//! task-wide, or of an `Unfold` instance, and a model holds one choice at
//! each factor. The driver meets a factor as it evaluates the asked
//! relation, so it meets only the factors that relation reads, and each
//! after the factors its options read, which is the dependency order. The
//! enumeration is nested in that order: the options of a factor are built at
//! one model of the factors before it, and once more at each next model of
//! those. A change of the choice at a factor drops from the driver's memo
//! the values downstream of that factor alone, and the result cache serves
//! the clauses of the values dropped whose reads did not change.

use std::ops::ControlFlow;
use std::sync::Arc;

use super::determinations;
use super::driver::{record_whole, Driver};
use super::join::{self, Budget};
use super::picks::{self, pick_options};
use super::unfold::{self, JointWalks, StateGraph, UnfoldOutput};
use super::{Evaluation, Outcome, ReachedBound, RelationValue, RunFault, Stop};
use crate::constraints;
use crate::program::path::NodePath;
use crate::program::OutputStep;
use crate::relations::{Row, RowSet};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::terms::Example;
use crate::types::GraphRelation;

/// The entry of a factor: its node, and its example, or `None` for a
/// task-wide one.
pub(super) type Entry = (GraphNodeIndex, Option<Example>);

/// The choice of a model at a factor: the value of each relation of the
/// factor, the chosen relation's alone for a pick, and each output of an
/// instance in the order of [`UnfoldOutput::ALL`].
#[derive(Clone, Debug)]
pub(super) struct Choice(Box<[RelationValue]>);

impl Choice {
    /// The choice that gives `value` at each of `relations` relations.
    fn all(value: RelationValue, relations: usize) -> Choice {
        Choice(vec![value; relations].into())
    }
}

/// A factor the driver met, with what its models are drawn from.
#[derive(Debug)]
pub(super) struct Factor {
    entry: Entry,
    form: NodePath,
    options: Options,
}

/// What the models of a factor are drawn from.
#[derive(Debug)]
enum Options {
    /// The rows of the chosen relation that the options give, the pick over
    /// them, and the arity of the relation.
    Pick { rows: Vec<Row>, pick: constraints::Pick, arity: u16 },
    /// The state graph of each key of the instance, and the arity of its
    /// outputs.
    Walks { graphs: Vec<(Row, StateGraph)>, arity: u16 },
}

impl Options {
    /// The models of the factor, one at a time, from the first.
    fn draw<'f>(&'f self, driver: &Driver<'f, '_>) -> Draw<'f> {
        let evaluation = driver.evaluation;
        match self {
            Options::Pick { rows, pick, arity } => {
                Draw::Pick { rows, arity: *arity, models: pick.models(evaluation.session.caps.nodes, false) }
            }
            Options::Walks { graphs, arity } => {
                Draw::Walks { walks: JointWalks::of_instance(graphs, *arity), budget: Budget::new(evaluation.limits, evaluation.session) }
            }
        }
    }
}

/// The models of one factor, drawn one at a time.
enum Draw<'f> {
    Pick { rows: &'f [Row], arity: u16, models: constraints::Models<'f> },
    Walks { walks: JointWalks<'f>, budget: Budget<'f> },
}

impl Draw<'_> {
    /// The choice of the next model, `None` past the last, or the bound
    /// its search reached.
    fn next(&mut self) -> Result<Option<Choice>, ReachedBound> {
        let rows = |parts: Vec<RowSet>| Choice(parts.into_iter().map(|part| RelationValue::Rows(Arc::new(join::one_part(part)))).collect());
        match self {
            Draw::Pick { rows: options, arity, models } => match models.next() {
                None => Ok(None),
                Some(Err(constraints::NodeCapReached { cap })) => Err(ReachedBound::Nodes { cap }),
                Some(Ok(model)) => {
                    let mut kept = RowSet::empty(*arity);
                    for &option in model.iter() {
                        kept.insert(options[option].clone());
                    }
                    Ok(Some(rows(vec![kept])))
                }
            },
            Draw::Walks { walks, budget } => Ok(walks.next(budget)?.map(rows)),
        }
    }
}

/// The value of `relation`, a chosen relation, on `example` at the current
/// model, as [`choice`] gives it.
pub(super) fn pick_value(driver: &Driver<'_, '_>, relation: &GraphRelation, example: Option<Example>) -> Outcome<RelationValue> {
    let form = driver.program().form_of(relation.node);
    let fault = |message: String| RunFault { message: message.into(), form: form.clone() };
    let build = || {
        let options = match pick_options(&driver.bodies(), relation.node, example)? {
            picks::Pick::Options(options) => options,
            picks::Pick::Undefined => return Ok(Err(RelationValue::Undefined)),
            picks::Pick::Stopped(stop) => return Ok(Err(RelationValue::Stopped(stop))),
        };
        let groups: Vec<Box<[usize]>> = options.groups.into_iter().map(Vec::into_boxed_slice).collect();
        let pick = constraints::Pick::new(options.rows.len(), &groups, &options.never)
            .map_err(|error| fault(format!("the options of the chosen relation are no pick: {error:?}")))?;
        let arity = arity(driver, relation, form)?;
        Ok(Ok(Options::Pick { rows: options.rows, pick, arity }))
    };
    let many = match driver.det {
        Some(det) => {
            let DependencyKind::Chosen(pick) = &driver.program().graph.nodes[relation.node.0 as usize].kind else { panic!("the node of a chosen relation") };
            determinations::many_models(driver, det, pick)
        }
        None => "the chosen relation has more than one model, which this evaluation does not enumerate, and a `DET` reads a pick only where the pick has one model".into(),
    };
    let mut values = choice(driver, (relation.node, example), form, build, 1, &many)?.0.into_vec();
    Ok(values.pop().expect("the value of the chosen relation"))
}

/// The value of `relation`, an output of an `Unfold` instance, on
/// `example` at the current model, as [`choice`] gives it.
pub(super) fn walk_value(driver: &Driver<'_, '_>, relation: &GraphRelation, example: Option<Example>) -> Outcome<RelationValue> {
    let Some([OutputStep::Port(port)]) = relation.output.as_deref() else { panic!("an instance output read by its port") };
    let at = UnfoldOutput::ALL.iter().position(|output| *output == UnfoldOutput::of(port)).expect("an output of `Unfold`");
    let evaluation = driver.evaluation;
    let form = driver.program().form_of(relation.node);
    let build = || {
        let mut budget = Budget::new(evaluation.limits, evaluation.session);
        let graphs = unfold::unfold(evaluation, &driver.bodies(), form, relation, example, &mut budget)?;
        record_whole(&budget, graphs.as_ref().err());
        let graphs = match graphs {
            Ok(graphs) => graphs,
            Err(value) => return Ok(Err(value)),
        };
        Ok(Ok(Options::Walks { graphs, arity: arity(driver, relation, form)? }))
    };
    let many = "the instance gives more than one value, so the case has more than one model";
    let choice = choice(driver, (relation.node, example), form, build, UnfoldOutput::ALL.len(), many)?;
    Ok(choice.0[at].clone())
}

/// The arity of `relation`, whose form stands at `form`.
fn arity(driver: &Driver<'_, '_>, relation: &GraphRelation, form: &NodePath) -> Outcome<u16> {
    let types = driver.evaluation.program.types.columns(relation);
    let types = types.ok_or_else(|| RunFault { message: "the relation's columns have no types".into(), form: form.clone() })?;
    Ok(types.len() as u16)
}

/// The choice of the current model at the factor `entry`, whose form
/// stands at `form`, of `relations` relations, with `build` building its
/// options, or giving the value of a read of them that is `undefined` or
/// stopped, which each relation of the factor then takes.
///
/// Where the current model holds no choice at `entry`, the factor takes its
/// first model. In an enumeration, the driver then meets the factor, and
/// the current model holds that choice. Outside one, a factor of more than
/// one model is a fault of the run, with the message `many`. A stop in the
/// search of the first model, or, outside an enumeration, of the second, is
/// the value of each relation of the factor.
fn choice(
    driver: &Driver<'_, '_>,
    entry: Entry,
    form: &NodePath,
    build: impl FnOnce() -> Outcome<Result<Options, RelationValue>>,
    relations: usize,
    many: &str,
) -> Outcome<Choice> {
    if let Some(choice) = driver.model.borrow().get(&entry) {
        return Ok(choice.clone());
    }
    let fault = |message: &str| RunFault { message: message.into(), form: form.clone() };
    let stopped = |bound| Choice::all(RelationValue::Stopped(Stop { bound, form: form.clone() }), relations);
    let options = match build()? {
        Ok(options) => options,
        Err(value) => return Ok(Choice::all(value, relations)),
    };
    let mut draw = options.draw(driver);
    let first = match draw.next() {
        Ok(Some(first)) => first,
        Ok(None) => return Err(fault("the instance gives no walk, so the case has no model")),
        Err(bound) => return Ok(stopped(bound)),
    };
    if driver.met.borrow().is_none() {
        return match draw.next() {
            Ok(None) => Ok(first),
            Ok(Some(_)) => Err(fault(many)),
            Err(bound) => Ok(stopped(bound)),
        };
    }
    drop(draw);
    driver.model.borrow_mut().insert(entry, first.clone());
    let mut met = driver.met.borrow_mut();
    met.as_mut().expect("the factors met in an enumeration").push(Factor { entry, form: form.clone(), options });
    Ok(first)
}

/// How an enumeration of models ended.
#[derive(Clone, Debug)]
pub enum ModelsEnd {
    /// The visitor asked to stop.
    Visitor,
    /// The models ended.
    Exhausted,
    /// A bound was reached in the search of a model past the first: the
    /// model cap at the model past it, the node cap in the search of a
    /// pick, or another bound of the run.
    Stopped(Stop),
}

impl Evaluation<'_> {
    /// Calls `visit` with the value of `relation` on `example` at each model
    /// of the case on that input, in the search order, until `visit` gives
    /// [`ControlFlow::Break`], the models end, or a bound is reached, and
    /// gives which of these ended the enumeration. `example` is as
    /// [`Evaluation::relation`] takes it.
    ///
    /// The factors enumerated are those that `relation` reads. A task-wide
    /// pick that it reads, a `DET` with `(ONE)`, is enumerated in each call,
    /// so on each input. A value stopped in the search of the first model
    /// of a factor reaches `visit` as any stopped value does.
    pub fn models(
        &self,
        relation: &GraphRelation,
        example: Option<Example>,
        visit: &mut dyn FnMut(&RelationValue) -> ControlFlow<()>,
    ) -> Outcome<ModelsEnd> {
        let driver = Driver::new(self);
        *driver.met.borrow_mut() = Some(Vec::new());
        let graph = &self.program.program.graph;
        let mut readers = vec![Vec::new(); graph.nodes.len()];
        for (node, reads) in graph.reads.iter().enumerate() {
            for read in reads.iter() {
                readers[read.0 as usize].push(node);
            }
        }
        let mut enumeration = Enumeration { driver: &driver, relation, example, visit, readers, seen: 0 };
        Ok(enumeration.level(Vec::new())?.unwrap_or(ModelsEnd::Exhausted))
    }
}

/// One enumeration of the models of a case on an input.
struct Enumeration<'d, 'e, 'a> {
    driver: &'d Driver<'e, 'a>,
    relation: &'d GraphRelation,
    example: Option<Example>,
    visit: &'d mut dyn FnMut(&RelationValue) -> ControlFlow<()>,
    /// For each node of the dependency graph, the nodes that read it.
    readers: Vec<Vec<usize>>,
    /// The models given to `visit`.
    seen: u64,
}

impl Enumeration<'_, '_, '_> {
    /// Visits each model at the choices the current model holds, with
    /// `held`, factors met in that order and set at their first models,
    /// enumerated from their first models, innermost the last. Gives how the
    /// enumeration ended, or `None` where it goes on past these models.
    /// Each factor this sets it leaves unset.
    fn level(&mut self, held: Vec<Factor>) -> Outcome<Option<ModelsEnd>> {
        let mut factors = held;
        if factors.is_empty() {
            let value = self.driver.value(self.relation, self.example)?;
            factors = self.driver.met.replace(Some(Vec::new())).expect("the factors met in an enumeration");
            if factors.is_empty() {
                return Ok(self.visit_model(&value));
            }
        }
        let factor = factors.remove(0);
        let mut draw = factor.options.draw(self.driver);
        let stop = |bound| Some(ModelsEnd::Stopped(Stop { bound, form: factor.form.clone() }));
        let mut end = match draw.next() {
            Ok(_) => self.level(factors)?,
            Err(bound) => {
                factors.iter().for_each(|held| self.unset(held.entry));
                stop(bound)
            }
        };
        while end.is_none() {
            match draw.next() {
                Ok(None) => break,
                Ok(Some(choice)) => {
                    self.driver.model.borrow_mut().insert(factor.entry, choice);
                    self.invalidate(factor.entry.0);
                    end = self.level(Vec::new())?;
                }
                Err(bound) => end = stop(bound),
            }
        }
        self.unset(factor.entry);
        Ok(end)
    }

    /// Gives `value`, the value at one complete model, to the visitor, or
    /// the stop at the model cap where the visitor has seen as many models
    /// as the cap.
    fn visit_model(&mut self, value: &RelationValue) -> Option<ModelsEnd> {
        let cap = self.driver.evaluation.session.caps.models;
        if self.seen == cap {
            let form = self.driver.program().form_of(self.relation.node).clone();
            return Some(ModelsEnd::Stopped(Stop { bound: ReachedBound::Models { cap }, form }));
        }
        self.seen += 1;
        match (self.visit)(value) {
            ControlFlow::Break(()) => Some(ModelsEnd::Visitor),
            ControlFlow::Continue(()) => None,
        }
    }

    /// Removes the choice at `entry` from the current model.
    fn unset(&self, entry: Entry) {
        self.driver.model.borrow_mut().remove(&entry);
        self.invalidate(entry.0);
    }

    /// Drops from the driver's memo the values of `node` and of each node
    /// downstream of it.
    fn invalidate(&self, node: GraphNodeIndex) {
        let mut downstream = vec![false; self.readers.len()];
        let mut pending = vec![node.0 as usize];
        while let Some(at) = pending.pop() {
            if !std::mem::replace(&mut downstream[at], true) {
                pending.extend(&self.readers[at]);
            }
        }
        self.driver.values.borrow_mut().retain(|(relation, _), _| !downstream[relation.node.0 as usize]);
    }
}
