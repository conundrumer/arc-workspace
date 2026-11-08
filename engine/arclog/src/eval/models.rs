//! The models of a case on an input, as `docs/engine/cases.md#models` gives
//! them: [`Evaluation::models`] gives the value of a relation at each model,
//! one at a time, until its visitor stops it, the models end, or a cap is
//! reached; [`Evaluation::models_with_picks`] gives as well the choice at
//! each model of the chosen relations its caller names.
//!
//! A factor is an entry of a pick, a chosen relation on one example or
//! task-wide, of a `DEMONSTRATED` relation, or of an `Unfold` instance, and a model holds one choice at
//! each factor. The driver meets a factor as it evaluates the asked
//! relation, so it meets only the factors that relation reads, and each
//! after the factors its options read, which is the dependency order. The
//! enumeration is nested in that order: the options of a factor are built at
//! one model of the factors before it, and once more at each next model of
//! those. A change of the choice at a factor drops from the driver's memo
//! the values downstream of that factor alone, and the result cache serves
//! the clauses of the values dropped whose reads did not change.

use std::cell::RefCell;
use std::ops::ControlFlow;
use std::sync::Arc;

use super::demonstrated;
use super::determinations;
use super::driver::{record_whole, Driver};
use super::join::{self, Budget};
use super::picks::{self, pick_options};
use super::unfold::{self, JointWalks, StateGraph, UnfoldOutput};
use super::{Evaluation, Gauge, Gauges, Outcome, ReachedBound, RelationValue, RunFault, Stop};
use crate::constraints;
use crate::program::path::NodePath;
use crate::program::OutputStep;
use crate::relations::{Row, RowSet};
use crate::resolver::{DependencyKind, GraphNodeIndex};
use crate::terms::Example;
use crate::trace::{RunRecord, RunTrace};
use crate::types::GraphRelation;

/// The entry of a factor: its node, and its example, or `None` for a
/// task-wide one.
pub(super) type Entry = (GraphNodeIndex, Option<Example>);

/// The choice of a model at a factor: the value of each relation of the
/// factor, the chosen relation's alone for a pick, and each output of an
/// instance in the order of [`UnfoldOutput::ALL`].
#[derive(Clone, Debug)]
pub(super) struct Choice(Box<[RelationValue]>,Option<Vec<unfold::WalkContext>>);

impl Choice {
    /// The choice that gives `value` at each of `relations` relations.
    fn all(value: RelationValue, relations: usize) -> Choice {
        Choice(vec![value; relations].into(),None)
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
    Walks { graphs: Vec<(Row, StateGraph)>, arity: u16, layout:unfold::OutputLayout },
    /// For each key of a `DEMONSTRATED` relation that holds a confirmed
    /// rule, the distinct predictions of its confirmed rules in the
    /// canonical order by content, and the arity of the relation.
    Demonstrated { keys: Vec<Vec<RowSet>>, arity: u16 },
}

impl Options {
    /// The models of the factor, one at a time, from the first.
    fn draw<'f>(&'f self, driver: &Driver<'f, '_>) -> Draw<'f> {
        let evaluation = driver.evaluation;
        match self {
            Options::Pick { rows, pick, arity } => Draw::Pick {
                rows,
                arity: *arity,
                models: pick.models(evaluation.session.caps.nodes, false),
                gauges: evaluation.limits.request.gauges(),
                cap: evaluation.session.caps.nodes,
                budget: Budget::new(evaluation.limits, evaluation.session),
            },
            Options::Walks { graphs, arity, layout } => {
                Draw::Walks { walks: JointWalks::of_layout(graphs, *arity,*layout), budget: Budget::new(evaluation.limits, evaluation.session) }
            }
            Options::Demonstrated { keys, arity } => Draw::Demonstrated { keys, arity: *arity, at: Some(vec![0; keys.len()]), budget: Budget::new(evaluation.limits, evaluation.session) },
        }
    }

    /// The rows that building the options read, as content. The options of
    /// a walk count their states where the state graph is built.
    fn read_rows(&self) -> u64 {
        match self {
            Options::Pick { rows, .. } => rows.len() as u64,
            Options::Walks { .. } => 0,
            Options::Demonstrated { keys, .. } => keys.iter().flatten().map(|rows| rows.len() as u64).fold(0, u64::saturating_add),
        }
    }
}

/// The models of one factor, drawn one at a time.
enum Draw<'f> {
    /// `budget` counts the rows of each model as content.
    Pick { rows: &'f [Row], arity: u16, models: constraints::Models<'f>, gauges: &'f Gauges, cap: u64, budget: Budget<'f> },
    Walks { walks: JointWalks<'f>, budget: Budget<'f> },
    /// The product of the options of the keys, one choice per key, the last
    /// key's choice changing first; `at` holds the choice of the next model.
    Demonstrated { keys: &'f [Vec<RowSet>], arity: u16, at: Option<Vec<usize>>, budget: Budget<'f> },
}

impl Draw<'_> {
    /// The choice of the next model, `None` past the last, or the bound
    /// its search reached.
    fn next(&mut self) -> Result<Option<Choice>, ReachedBound> {
        let rows = |parts: Vec<RowSet>| Choice(parts.into_iter().map(|part| RelationValue::Rows(Arc::new(join::one_part(part)))).collect(),None);
        match self {
            Draw::Pick { rows: options, arity, models, gauges, cap: node_cap, budget } => match models.next() {
                None => Ok(None),
                Some(Err(constraints::NodeCapReached { cap })) => {
                    gauges.hit(Gauge::Nodes, models.most_nodes().max(cap.saturating_add(1)), cap);
                    Err(ReachedBound::Nodes { cap })
                }
                Some(Ok(model)) => {
                    gauges.note(Gauge::Nodes, models.most_nodes(), *node_cap);
                    let mut kept = RowSet::empty(*arity);
                    for &option in model.iter() {
                        kept.insert(options[option].clone());
                    }
                    // The content of a model: the rows it keeps.
                    budget.charge_content(kept.len() as u64)?;
                    Ok(Some(rows(vec![kept])))
                }
            },
            Draw::Walks { walks, budget } => Ok(walks.next_with_contexts(budget)?.map(|(parts,contexts)|{let mut choice=rows(parts);choice.1=Some(contexts);choice})),
            Draw::Demonstrated { keys, arity, at, budget } => {
                let Some(mut chosen) = at.take() else { return Ok(None) };
                let mut kept = RowSet::empty(*arity);
                for (options, &choice) in keys.iter().zip(&chosen) {
                    for row in options[choice].rows() {
                        kept.insert(row.into());
                    }
                }
                let carry = chosen.iter_mut().zip(keys.iter()).rev().find_map(|(choice, options)| {
                    *choice += 1;
                    if *choice < options.len() { Some(()) } else { *choice = 0; None }
                });
                *at = carry.map(|()| chosen);
                budget.charge_content(kept.len() as u64)?;
                Ok(Some(rows(vec![kept])))
            }
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
    let mut values = choice(driver, (relation.node, example), form, build, 1, Some(&many))?.0.into_vec();
    Ok(values.pop().expect("the value of the chosen relation"))
}

/// The value of `relation`, a `DEMONSTRATED` relation, on `example` at the
/// current model, as [`choice`] gives it.
pub(super) fn demonstrated_value(driver: &Driver<'_, '_>, relation: &GraphRelation, example: Option<Example>) -> Outcome<RelationValue> {
    let form = driver.program().form_of(relation.node);
    let build = || {
        let keys = match demonstrated::confirmed(driver, relation, example)? {
            Ok(keys) => keys,
            Err(value) => return Ok(Err(value)),
        };
        Ok(Ok(Options::Demonstrated { keys, arity: arity(driver, relation, form)? }))
    };
    let mut values = choice(driver, (relation.node, example), form, build, 1, None)?.0.into_vec();
    Ok(values.pop().expect("the value of the `DEMONSTRATED` relation"))
}

/// The value of `relation`, an output of an `Unfold` instance, on
/// `example` at the current model, as [`choice`] gives it.
pub(super) fn walk_value(driver: &Driver<'_, '_>, relation: &GraphRelation, example: Option<Example>) -> Outcome<RelationValue> {
    let Some([OutputStep::Port(port)]) = relation.output.as_deref() else { panic!("an instance output read by its port") };
    let Some(at)=UnfoldOutput::ALL.iter().position(|output|output.port()==*port) else {
        return super::body_context::input_value(driver,relation,port,example);
    };
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
        Ok(Ok(Options::Walks { graphs, arity: arity(driver, relation, form)?,layout:unfold::OutputLayout::at(evaluation,form)? }))
    };
    let many = "the instance gives more than one value, so the case has more than one model";
    let choice = choice(driver, (relation.node, example), form, build, UnfoldOutput::ALL.len(), Some(many))?;
    Ok(choice.0[at].clone())
}

pub(super) fn walk_contexts(driver:&Driver<'_, '_>,node:GraphNodeIndex,example:Option<Example>)->Outcome<Result<Vec<unfold::WalkContext>,RelationValue>> {
    let relation=GraphRelation {node,output:Some(Arc::from([OutputStep::Port(UnfoldOutput::Taken.port())]))};
    let value=walk_value(driver,&relation,example)?;
    match value {
        RelationValue::Rows(_)=>{
            let held=driver.model.borrow();
            let contexts=held.get(&(node,example)).and_then(|c|c.1.clone());
            contexts.map(Ok).ok_or_else(||RunFault {message:"recursive query has no selected walk context".into(),form:driver.program().form_of(node).clone()})
        }
        other=>Ok(Err(other)),
    }
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
/// one model is a fault of the run, with the message `many`, or, where `many` is `None`, takes its first model. A stop in the
/// search of the first model, or, outside an enumeration, of the second, is
/// the value of each relation of the factor.
fn choice(
    driver: &Driver<'_, '_>,
    entry: Entry,
    form: &NodePath,
    build: impl FnOnce() -> Outcome<Result<Options, RelationValue>>,
    relations: usize,
    many: Option<&str>,
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
    // The rows that the options were built from are content.
    if let Err(bound) = Budget::new(driver.evaluation.limits, driver.evaluation.session).charge_content(options.read_rows()) {
        return Ok(stopped(bound));
    }
    let mut draw = options.draw(driver);
    let first = match draw.next() {
        Ok(Some(first)) => first,
        Ok(None) => return Err(fault("the factor gives no model, so the case has no model")),
        Err(bound) => return Ok(stopped(bound)),
    };
    if driver.met.borrow().is_none() {
        return match draw.next() {
            Ok(None) => Ok(first),
            Ok(Some(_)) => many.map_or(Ok(first), |message| Err(fault(message))),
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
        self.enumerate(None, relation, example, &[], &mut |value, _| visit(value))
    }

    /// [`Evaluation::models`], with `visit` given as well the value at the
    /// model of each of `picks`, a chosen relation and the example it is
    /// read on, as [`Evaluation::relation`] takes it, in the order of
    /// `picks`: the choice that the model holds at it, `None` where the
    /// model holds none, as where `relation` does not read it. The
    /// enumeration is that of `relation` alone.
    pub fn models_with_picks(
        &self,
        relation: &GraphRelation,
        example: Option<Example>,
        picks: &[(GraphRelation, Option<Example>)],
        visit: &mut dyn FnMut(&RelationValue, &[Option<RelationValue>]) -> ControlFlow<()>,
    ) -> Outcome<ModelsEnd> {
        self.enumerate(None, relation, example, picks, visit)
    }

    /// [`Evaluation::models`], with the records of the evaluation of
    /// `relation` at each model appended to `trace`, as
    /// [`Evaluation::relation_traced`] appends them, and, once the
    /// enumeration ends without a fault, one last record of `relation` on
    /// `example`: the enumeration's, which holds the models visited and the
    /// bound of a [`ModelsEnd::Stopped`].
    pub fn models_traced(
        &self,
        relation: &GraphRelation,
        example: Option<Example>,
        visit: &mut dyn FnMut(&RelationValue) -> ControlFlow<()>,
        trace: &mut RunTrace,
    ) -> Outcome<ModelsEnd> {
        let cell = RefCell::new(std::mem::take(trace));
        let end = self.enumerate(Some(&cell), relation, example, &[], &mut |value, _| visit(value));
        *trace = cell.into_inner();
        end
    }

    fn enumerate(
        &self,
        trace: Option<&RefCell<RunTrace>>,
        relation: &GraphRelation,
        example: Option<Example>,
        picks: &[(GraphRelation, Option<Example>)],
        visit: &mut dyn FnMut(&RelationValue, &[Option<RelationValue>]) -> ControlFlow<()>,
    ) -> Outcome<ModelsEnd> {
        self.enumerate_target(trace,Target::Relation(relation),example,picks,visit)
    }

    /// Enumerate models of an already checked body query. This preserves
    /// pick enumeration for body views as well as complete relations.
    pub fn body_models(&self,view:&super::body_view::BodyView,example:Option<Example>,visit:&mut dyn FnMut(&RelationValue)->ControlFlow<()>)->Outcome<ModelsEnd> {
        self.enumerate_target(None,Target::Body(view),example,&[],&mut |value,_|visit(value))
    }

    fn enumerate_target(&self,trace:Option<&RefCell<RunTrace>>,target:Target<'_>,example:Option<Example>,picks:&[(GraphRelation,Option<Example>)],visit:&mut dyn FnMut(&RelationValue,&[Option<RelationValue>])->ControlFlow<()>)->Outcome<ModelsEnd> {
        let driver = Driver::nested(self, trace);
        *driver.met.borrow_mut() = Some(Vec::new());
        let graph = &self.program.program.graph;
        let mut readers = vec![Vec::new(); graph.nodes.len()];
        for (node, reads) in graph.reads.iter().enumerate() {
            for read in reads.iter() {
                readers[read.0 as usize].push(node);
            }
        }
        let mut enumeration = Enumeration { driver: &driver, target, example, picks, visit, readers, seen: 0 };
        let end = enumeration.level(Vec::new())?.unwrap_or(ModelsEnd::Exhausted);
        if let (Some(trace),Target::Relation(relation)) = (trace,target) {
            let stop = match &end {
                ModelsEnd::Stopped(stop) => Some(stop.bound.into()),
                ModelsEnd::Visitor | ModelsEnd::Exhausted => None,
            };
            trace.borrow_mut().push(RunRecord { relation: relation.clone(), example, rows: None, models: enumeration.seen, values_determined: 0, stop });
        }
        Ok(end)
    }
}

#[derive(Clone,Copy)]
enum Target<'a> {
    Relation(&'a GraphRelation),
    Body(&'a super::body_view::BodyView),
}
impl Target<'_> {
    fn value(&self,driver:&Driver<'_, '_>,example:Option<Example>)->Outcome<RelationValue> {
        match self {Self::Relation(relation)=>driver.value(relation,example),Self::Body(view)=>super::body_context::value(driver,view,example)}
    }
    fn form(&self,driver:&Driver<'_, '_>)->NodePath {
        match self {Self::Relation(relation)=>driver.program().form_of(relation.node).clone(),Self::Body(view)=>view.form.clone()}
    }
}

/// One enumeration of the models of a case on an input.
struct Enumeration<'d, 'e, 'a> {
    driver: &'d Driver<'e, 'a>,
    target: Target<'d>,
    example: Option<Example>,
    /// The chosen relations whose values at each model `visit` gets.
    picks: &'d [(GraphRelation, Option<Example>)],
    visit: &'d mut dyn FnMut(&RelationValue, &[Option<RelationValue>]) -> ControlFlow<()>,
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
            let value = self.target.value(self.driver,self.example)?;
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

    /// Gives `value`, the value at one complete model, and the values of the
    /// picks at it, to the visitor, or the stop at the model cap where the
    /// visitor has seen as many models as the cap.
    fn visit_model(&mut self, value: &RelationValue) -> Option<ModelsEnd> {
        let cap = self.driver.evaluation.session.caps.models;
        let gauges = self.driver.evaluation.limits.request.gauges();
        if self.seen == cap {
            gauges.hit(Gauge::Models, cap.saturating_add(1), cap);
            let form = self.target.form(self.driver);
            return Some(ModelsEnd::Stopped(Stop { bound: ReachedBound::Models { cap }, form }));
        }
        self.seen += 1;
        gauges.note(Gauge::Models, self.seen, cap);
        let model = self.driver.model.borrow();
        let picks: Vec<Option<RelationValue>> = self
            .picks
            .iter()
            .map(|(pick, example)| {
                let chosen = matches!(self.driver.program().graph.nodes[pick.node.0 as usize].kind, DependencyKind::Chosen(_));
                model.get(&(pick.node, *example)).filter(|_| chosen).map(|choice| choice.0[0].clone())
            })
            .collect();
        drop(model);
        match (self.visit)(value, &picks) {
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
