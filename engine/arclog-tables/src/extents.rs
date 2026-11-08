//! The extents of the made frames of a table's `Box` columns, per row.
//!
//! A `Box` value in a made frame covers a box of the frame, and its margins
//! alone do not say which: the frame's extent (V rows, H columns) does. The
//! engine keeps no extent, since a Box term is its four margins, so the extent
//! is computed here from the bodies that give the table's rows, with the
//! label of each column kept. An intact body whose columns are the relation's
//! columns, and which is its sole derivation, reads the table's rows relabeled
//! into query order; other bodies
//! are evaluated under the query caps
//! ([`arclog::eval::body_view::BodyView::widened`]).
//!
//! The extent of a frame follows from the own size of a value, the size of the
//! box it covers, which no move within frames changes: a Box `v` in a frame of
//! extent (V, H) has own size (V - top - bottom, H - left - right), and a
//! Position has own size (1, 1). The extent of the frame of `v` is its own
//! size plus (top + bottom, left + right).
//!
//! In a widened body, the extent of the frame of the value of a label is:
//!
//! - for a label of type `Position`, the one its value gives: (top + bottom +
//!   1, left + right + 1);
//! - for a label of type `Box`, the one of each source of the label in the
//!   body, using the sources and frames from [`body_column_flows`], and `None`
//!   where two differ or one has none:
//!   - the frame of the input or output grid: the extent of the example's
//!     grid;
//!   - a frame that a lib column makes, `Made`: the own size of the label at
//!     the `size` column of the maker's atom ([`Registry::frame_size`]), with
//!     its rows and columns swapped where the D4 element that the label at
//!     the `by` column holds moves the top edge to the left or the right edge,
//!     plus the margins of the label at the maker's column. A maker in the
//!     body of an input of an instance, which the body reads through that
//!     input's port, gives no extent, since its labels are of another scope;
//!   - the frame of the column the source reads, `Read`: the extent of the
//!     frame of that column in the latest earlier table of the relation read,
//!     at the rows of that table whose cells equal the labels of the atom's
//!     sites in the row, at the example and the assignment of the `DET`s of the
//!     row's evaluation: the grid's extent where the frame is the input's or
//!     the output's, the value's where the column is a `Position`, and the
//!     table's own extent where the column is one of its [`Extents::columns`].
//!     The example is the row's, or, where the atom reads its relation lifted
//!     over the examples, the one that the cell of the atom's Example label
//!     holds.
//!
//! The rows of an input of an instance come from the clauses that the instance
//! writes for it, widened in the same way ([`arclog::eval::body_view::BodyView::at`]),
//! and the rows of an output of an instance take the extent of the frame its
//! rule names (or of the input column it copies) over the rows of the input
//! with the row's key, or with any key where the output or the input has none.
//! The rows of a widened body are those of its relation at each model of each
//! assignment (`relation_examples` of the `tables` module), all of which give the
//! entry's rows.
//!
//! A row of a table takes the one extent that the rows of the widened bodies
//! that give it give ([`Merged`]), and none where they give two or where one
//! of them gives none.
//!
//! Every extent is at least 1 in each cell. A value whose margins reach past
//! its frame (a negative margin, in `programs/lib/box.dl`) can make a frame's
//! own size plus margins fall below 1: such a derivation gives no extent, and
//! so does a value that does not fit in its extent (`fitted_size`).
//!
//! The derivation has a work budget of the table work cap times the number
//! of assignments, at least one. Each
//! model of a body or of an output charges its count of rows to the count of
//! [`TableWork`] before the derivation visits them, as does each read of an
//! earlier table's rows. An entry whose model is refused the charge, or whose
//! derivation leaves the count past the cap, gets the stop
//! ([`EntryExtents::Stopped`]) in place of extents. A stop at this budget or
//! an evaluation bound leaves the table's rows available. Session-byte,
//! request-work and cancellation stops remain stops of the table.
//!
//! An entry that holds rows and has no extent says why in
//! [`EntryExtents::Lost`]: the fault of a widened body, or the reason the
//! extents do not derive its rows.
//!
//! The extents of a table stand beside its rows in [`Contents`], for each
//! example, assignment and model, as [`Extents::entry`] gives them. Where the
//! relation of an entry is the product of several parts and the extent of
//! each column reads the cells of one part (a Position reads its own cell, and
//! a Box whose frame is a grid reads its own cell and the cell that gives the
//! row's example), the extents are held per part, with a row for each row of
//! the part, and no row of the product is built or admitted ([`ExtentRows`]).

use std::cell::RefCell;
use std::ops::Range;
use std::rc::Rc;
use std::sync::Arc;

use arclog::algebra::geometry::{Edge, Geometry};
use arclog::check::CheckedProgram;
use arclog::decode::{relation_dets, Assigned, Decoder};
use arclog::eval::body_view::BodyView;
use arclog::eval::ir::{Argument, Arguments, IrNode, IrPaths, NodePaths};
use arclog::eval::determinations::relation_spelled;
use arclog::eval::join::{Budget, Materializer};
use arclog::eval::{RelationValue, Stop, TableWork};
use arclog::hash::StableHashMap;
use arclog::judge::determination::Assignment;
use arclog::program::path::{node_at, NodePath, NodeRef};
use arclog::program::{Atom, ColumnName, Conjunct, Instance, LabelId, PortName, Site};
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::resolver::given::Given;
use arclog::resolver::registry_columns;
use arclog::resolver::{DependencyKind, Resolution};
use arclog::terms::{Constant, Example, Margins, Term, TermId};
use arclog::types::{use_label, GraphRelation, ValueType};

use crate::columns::{column_frames, extent_columns, fault_spelled, locate, names_of, read_index, Named, TableNames, INPUT_FRAME, OUTPUT_FRAME};
use crate::flows::{body_column_flows, column_placements, output_copies, output_frames, ColumnSource, Maker, OutputFrame, Placement, SourceFrame};
use crate::tables::{relation_examples_with_context, Contents, ExampleRows, Table, EVIDENCE_FACTS};
use crate::tables::assignment_context::{AssignmentContext, AssignmentLayout, HeldAssignments};

#[path = "frame_context.rs"]
mod frame_context;
use frame_context::DirectContexts;

/// The extent of a frame: its count of rows V and its count of columns H, each
/// at least 1; [`Extent::new`] is the one constructor.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Extent {
    pub rows: i32,
    pub columns: i32,
}

impl Extent {
    /// The extent of `rows` rows and `columns` columns, none where either is
    /// below 1: no frame has a side below 1.
    pub fn new(rows: i32, columns: i32) -> Option<Extent> {
        (rows >= 1 && columns >= 1).then_some(Extent { rows, columns })
    }
}

/// The one extent that the derivations of a row give, as the derivations come:
/// none yet, one, or none because two differ or one has none.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub enum Merged {
    #[default]
    Unset,
    One(Extent),
    None,
}

impl Merged {
    /// Takes the extent `extent` of one more derivation.
    pub fn merge(&mut self, extent: Option<Extent>) {
        *self = match (*self, extent) {
            (Merged::Unset, Some(extent)) => Merged::One(extent),
            (Merged::One(held), Some(extent)) if held == extent => Merged::One(held),
            _ => Merged::None,
        };
    }

    /// The extent, none where there is none or no derivation gave one.
    pub fn extent(&self) -> Option<Extent> {
        match self {
            Merged::One(extent) => Some(*extent),
            Merged::Unset | Merged::None => None,
        }
    }
}

/// The extents of one entry of a table, a model at an assignment on an example.
#[derive(Clone, Debug)]
pub enum EntryExtents {
    /// For each row of the model's relation, in the order of [`arclog::eval::join::each_row`], the
    /// extent of each of the table's extent columns, in their order.
    Rows(std::sync::Arc<ExtentRows>),
    /// The entry has no extent: its model holds no rows.
    Absent,
    /// The entry holds rows and has no extent, for this reason: the message
    /// and form of the fault of a widened body (`"<message> at <form>"`), or
    /// why the extents do not derive its rows.
    Lost(String),
    /// The evaluation of the bodies stopped at this bound.
    Stopped(Stop),
}

/// Materialized data and the reservation held until its actual last owner
/// drops it. Clones of an Arc share both; genuine copies need new admission.
#[derive(Debug)]
pub struct Materialized<T> {
    value: T,
    _allocation: std::sync::Arc<arclog::session::SessionAllocation>,
}
impl<T> Materialized<T> {
    pub(crate) fn new(value:T,allocation:std::sync::Arc<arclog::session::SessionAllocation>)->Self {Self {value,_allocation:allocation}}
}
impl<T> std::ops::Deref for Materialized<T> {
    type Target=T;
    fn deref(&self)->&T {&self.value}
}

/// An entry's extent matrix, whose bytes the session reserves. Cloning
/// its Arc shares both the cells and their byte reservation.
///
/// The matrix is held as blocks: one block with a row for each row of the
/// relation, or, where each extent column's extent reads the cells of one part
/// of the relation, one block for each part that holds such a column, with a
/// row for each row of that part. The row `at` of the relation, in the order of
/// [`arclog::eval::join::each_row`], reads the row `at / stride % len` of each
/// block, as that order walks the parts with the first outermost.
#[derive(Debug)]
pub struct ExtentRows {
    blocks: Box<[ExtentBlock]>,
    /// For each extent column, its block and its place among the block's
    /// columns; none for a column whose extent is none at every row.
    places: Box<[Option<(usize, usize)>]>,
    /// The count of the relation's rows.
    len: u64,
    /// Direct evidence is computed from the row when read, with no matrix.
    direct: bool,
    _allocation: std::sync::Arc<arclog::session::SessionAllocation>,
}

#[derive(Debug)]
struct ExtentBlock {
    /// The part of the relation whose rows the block's rows are; none for a
    /// block over the relation's rows.
    part: Option<usize>,
    /// The product of the counts of the rows of the later parts; 1 for a
    /// block over the relation's rows.
    stride: u64,
    rows: Box<[Box<[Option<Extent>]>]>,
}

impl ExtentRows {
    pub(crate) fn is_direct(&self)->bool {self.direct}
    /// The extent of the extent column `k` at the row `at` of the relation,
    /// none past its rows.
    pub fn cell(&self, at: u64, k: usize) -> Option<Extent> {
        if at >= self.len { return None; }
        let (block, slot) = (*self.places.get(k)?)?;
        let block = &self.blocks[block];
        let row = usize::try_from(at / block.stride % block.rows.len() as u64).ok()?;
        block.rows.get(row)?.get(slot).copied().flatten()
    }

    /// Whether the matrix is held per part of the relation.
    pub fn by_part(&self) -> bool {
        !self.direct && self.blocks.iter().all(|block| block.part.is_some())
    }

    /// For a matrix held per part, the part whose rows give the extent column
    /// `k`; none for a column whose extent is none at every row.
    pub fn part_of(&self, k: usize) -> Option<usize> {
        let (block, _) = (*self.places.get(k)?)?;
        self.blocks[block].part
    }

    /// For a matrix held per part, the extent of the extent column `k` at the
    /// row `row` of its part.
    pub fn part_cell(&self, k: usize, row: usize) -> Option<Extent> {
        let (block, slot) = (*self.places.get(k)?)?;
        self.blocks[block].rows.get(row)?.get(slot).copied().flatten()
    }
}

/// The extents of the made frames of a table's `Box` columns.
#[derive(Clone, Debug)]
pub struct Extents {
    /// Every Position, Box and Offset column in native scalar-column order.
    pub columns: Vec<u32>,
    /// Native proof that a column has no reference grid (not missing evidence).
    pub no_grid: Vec<bool>,
    /// Direct grid evidence is independent of whether a different column's
    /// derivation stops. Keep it without retaining or re-evaluating any rows.
    contexts: DirectContexts,
    /// For each example of the table, for each assignment of its rows, for each
    /// model; empty for an example whose rows fault.
    examples: Vec<Vec<Vec<EntryExtents>>>,
}

#[derive(Clone, Copy, Debug)]
struct DirectGrids {
    input: Option<Extent>,
    output: Option<Extent>,
}

impl DirectGrids {
    fn at(&self, frame: &str) -> Option<Extent> {
        match frame {
            INPUT_FRAME => self.input,
            OUTPUT_FRAME => self.output,
            _ => None,
        }
    }
}

impl Extents {
    /// The extents of the entry at `model` of the assignment `assignment` on
    /// the example `example` of the table.
    pub fn entry(&self, example: usize, assignment: usize, model: usize) -> Option<&EntryExtents> {
        self.examples.get(example)?.get(assignment)?.get(model)
    }

    pub(crate) fn projected_ready(&self,column:usize,projected:&[usize])->bool {
        self.contexts.example_column(column).is_none_or(|example|projected.contains(&example))
    }

    /// Evidence that does not depend on a widened-body query. Also used by
    /// downstream native reads when another column's derivation stopped.
    pub(crate) fn direct_at(&self, contents: &Contents, example: usize, column: usize, row: &[TermId]) -> Option<Extent> {
        match contents.columns[column].ty {
            ValueType::Position => position_extent(row[column], &ValueType::Position),
            ValueType::Box => {
                let extent = self.contexts.at(contents, example, column, row)?;
                fitted_size(extent, margins_of(row[column], &ValueType::Box)?).map(|_| extent)
            }
            _ => None,
        }
    }
}

/// What the derivations of one entry of a relation give so far.
#[derive(Default)]
struct Gathered {
    /// For each row, the merged extent of each wanted column.
    rows: StableHashMap<Box<[TermId]>, Vec<Merged>>,
    /// The bound that stopped the evaluation of a body at this entry.
    stop: Option<Stop>,
    /// The first reason that a body which gives the entry's rows faulted, or
    /// that the extents cannot derive them.
    lost: Option<String>,
    allocations: Vec<std::sync::Arc<arclog::session::SessionAllocation>>,
}

impl Gathered {
    fn admit(&mut self,reads:&Reads<'_>,rows:&Relation,columns:usize,form:&NodePath)->Result<(),Stop> {
        let payload=usize::from(rows.arity()).saturating_mul(std::mem::size_of::<TermId>()).saturating_add(columns.saturating_mul(std::mem::size_of::<Merged>()));
        match reads.materializer().admit(rows,Materializer::row_bytes(payload,4)) {
            Ok(owner)=>{self.allocations.push(owner);Ok(())},
            Err(bound)=>{let stop=Stop {bound,form:form.clone()};self.stop=Some(stop.clone());Err(stop)}
        }
    }
    /// Records `reason` as the reason the entry lost its extents, where it has
    /// none yet.
    fn lose(&mut self, reason: &str) {
        self.lost.get_or_insert_with(|| reason.to_owned());
    }
}

/// The relation whose rows' extents are wanted: its node, the type of each of
/// its row positions, its rows on each example at each assignment, and the
/// row positions (increasing) whose extents are wanted.
struct Subject<'a> {
    assignment_layout: &'a AssignmentLayout,
    checked: &'a CheckedProgram,
    relation: Option<&'a GraphRelation>,
    types: &'a [ValueType],
    examples: &'a [ExampleRows],
    columns: &'a [u32],
    /// Parallel to the full extent-column list, never a compressed interface.
    /// Recursive ports apply the same evidence planner before selection.
    needed: Option<&'a [bool]>,
}

impl Subject<'_> {
    fn needs(&self, column: usize) -> bool {
        self.needed.is_none_or(|needed| needed[column])
    }
}

/// One demand policy for public tables, body queries and recursive ports.
/// Missing frame evidence does not prove no_grid: it still requests bounded
/// derivation. Intrinsic Position and proved direct grids never request it.
struct EvidencePlan {
    columns: Vec<u32>,
    no_grid: Vec<bool>,
    contexts: DirectContexts,
    needed: Vec<bool>,
    stop: Option<Stop>,
}

impl EvidencePlan {
    fn new(materializer:&Materializer<'_>,decoder:&Decoder<'_>,earlier:&[&Table],checked:&CheckedProgram,form:&NodePath,contents:&Contents)->Self {
        let types=contents.columns.iter().map(|c|c.ty.clone()).collect::<Vec<_>>();
        let columns=extent_columns(&types,&contents.frames);
        let no_grid=no_grid_columns(decoder,earlier,contents,&columns);
        let contexts=DirectContexts::new(decoder,checked,form,contents,earlier);
        let (needed,stop)=match derivation_mask(materializer,contents,&columns,&no_grid,&contexts) {
            Ok(needed)=>(needed,None),Err(bound)=>(vec![false;columns.len()],Some(Stop {bound,form:form.clone()})),
        };
        Self {columns,no_grid,contexts,needed,stop}
    }

    fn wanted(&self,columns:&[u32])->Vec<bool> {
        columns.iter().map(|column|self.columns.iter().position(|c|c==column)
            .is_some_and(|i|self.needed[i])).collect()
    }
}

/// Export coverage does not request evaluation. Only a Box without a direct
/// proof needs a widened derivation. A task-wide row can carry its own proved
/// Example binding; the absence of an outer example does not erase that proof.
fn derivation_mask(materializer:&Materializer<'_>,contents:&Contents,columns:&[u32],no_grid:&[bool],contexts:&DirectContexts)->Result<Vec<bool>,arclog::eval::ReachedBound> {
    columns.iter().enumerate().map(|(k,&column)| {
        let column=column as usize;
        if contents.columns[column].ty!=ValueType::Box || no_grid[k] {return Ok(false);}
        contexts.complete(materializer,contents,column).map(|complete|!complete)
    }).collect()
}

/// Only positive native provenance proves no_grid. Empty/unknown frame names
/// alone do not. Copying a previously proved no-grid column preserves that fact.
fn no_grid_columns(decoder:&Decoder<'_>, earlier:&[&Table], contents:&Contents, columns:&[u32])->Vec<bool> {
    let names=names_of(decoder.registry(),earlier);
    let dets=contents.dets.iter().map(|d|relation_spelled(&d.relation)).collect::<Vec<_>>();
    columns.iter().map(|c| {
        if contents.columns[*c as usize].ty==ValueType::Offset {return true;}
        let Some(sources)=contents.flows.get(*c as usize).filter(|s|!s.is_empty()) else {return false;};
        sources.iter().all(|source| {
            if source.frames.is_empty() && matches!(source.kind,crate::flows::SourceKind::Constant|crate::flows::SourceKind::LibName) {return true;}
            if source.frames.iter().any(|f|!matches!(f,SourceFrame::Read)) {return false;}
            let located=locate(&names,&dets,source);
            let Some(named)=located.table else {return false;};
            let Some(index)=read_index(&located,source) else {return false;};
            let Some(table)=named.row.checked_sub(EVIDENCE_FACTS.len() as u32).and_then(|i|earlier.get(i as usize)) else {return false;};
            table.contents.as_ref().ok().and_then(|c|c.extents.as_ref()).is_some_and(|e| {
                e.columns.iter().position(|c|*c as usize==index).is_some_and(|k|e.no_grid[k])
            })
        })
    }).collect()
}

/// The extent of the extent column `k`, at `column`, of `row`, a row of an
/// entry on `example`: the direct one, or else the one the derivations of the
/// row give (`slots`).
fn completed_cell(contexts:&DirectContexts,contents:&Contents,example:usize,k:usize,column:usize,no_grid:bool,row:&[TermId],slots:Option<&[Merged]>)->Option<Extent> {
    if no_grid {return None;}
    match &contents.columns[column].ty {
        ValueType::Position=>position_extent(row[column],&ValueType::Position),
        ValueType::Box=>{
            let extent=contexts.at(contents,example,column,row)
                .or_else(||slots.and_then(|s|s[k].extent()))?;
            fitted_size(extent,margins_of(row[column],&ValueType::Box)?).map(|_|extent)
        },
        _=>None,
    }
}

/// The extents of the rows of `relation`, held per part where
/// [`part_places`] gives each column's part, and per row otherwise.
fn completed_rows(reads:&Reads<'_>,contexts:&DirectContexts,contents:&Contents,example:usize,relation:&Relation,columns:&[u32],no_grid:&[bool],gathered:Option<&Gathered>)->Result<std::sync::Arc<ExtentRows>,Stop> {
    match part_places(contexts,contents,relation,columns,no_grid,gathered) {
        Some(places)=>part_rows(reads,contexts,contents,example,relation,columns,no_grid,&places),
        None=>flat_rows(reads,contexts,contents,example,relation,columns,no_grid,gathered),
    }
}

/// For each extent column, the part of `relation` whose cells alone give its
/// extent at each row, none for a column whose extent is none at every row: a
/// Position reads its own cell, and a Box its own cell and the cell that
/// gives its row's example. None in all where the relation has one part or no
/// row, or where a column reads the cells of two parts or the derivations of
/// whole rows (`gathered`).
fn part_places(contexts:&DirectContexts,contents:&Contents,relation:&Relation,columns:&[u32],no_grid:&[bool],gathered:Option<&Gathered>)->Option<Vec<Option<usize>>> {
    let parts=relation.parts();
    if parts.len()<2 || relation.is_empty() {return None;}
    let part_of=|column:usize|parts.iter().position(|part|part.columns.iter().any(|own|usize::from(own.0)==column));
    let mut derived=vec![false;columns.len()];
    for slots in gathered.iter().flat_map(|entry|entry.rows.values()) {
        for (held,slot) in derived.iter_mut().zip(slots) {*held|=slot.extent().is_some();}
    }
    columns.iter().enumerate().map(|(k,&column)| {
        let column=column as usize;
        if no_grid[k] {return Some(None);}
        match contents.columns[column].ty {
            ValueType::Position=>part_of(column).map(Some),
            ValueType::Box if derived[k]=>None,
            ValueType::Box=>{
                let part=part_of(column)?;
                match contexts.example_column(column) {
                    Some(at) if part_of(at)!=Some(part)=>None,
                    _=>Some(Some(part)),
                }
            }
            _=>Some(None),
        }
    }).collect()
}

/// The extents of the rows of `relation` held per row, in the order of
/// [`arclog::eval::join::each_row`].
fn flat_rows(reads:&Reads<'_>,contexts:&DirectContexts,contents:&Contents,example:usize,relation:&Relation,columns:&[u32],no_grid:&[bool],gathered:Option<&Gathered>)->Result<std::sync::Arc<ExtentRows>,Stop> {
    let stopped=|bound|Stop {bound,form:reads.form.clone()};
    let materializer=reads.materializer();
    let bytes=Materializer::row_bytes(columns.len().saturating_mul(std::mem::size_of::<Option<Extent>>()),2);
    let allocation=materializer.admit(relation,bytes).map_err(stopped)?;
    let mut result=Vec::with_capacity(usize::try_from(relation.len()).expect("admitted row count"));
    materializer.walk(relation,&mut |row| {
        let slots=gathered.and_then(|e|e.rows.get(row)).map(Vec::as_slice);
        result.push(columns.iter().enumerate().map(|(k,c)|completed_cell(contexts,contents,example,k,*c as usize,no_grid[k],row,slots)).collect());
    }).map_err(stopped)?;
    let block=ExtentBlock {part:None,stride:1,rows:result.into_boxed_slice()};
    let places=(0..columns.len()).map(|k|Some((0,k))).collect();
    Ok(std::sync::Arc::new(ExtentRows {blocks:Box::new([block]),places,len:relation.len(),direct:false,_allocation:allocation}))
}

/// The extents of the rows of `relation` held per part, each column in the
/// part `places` gives it. No row of the product is built, and the rows
/// admitted are those of the parts.
fn part_rows(reads:&Reads<'_>,contexts:&DirectContexts,contents:&Contents,example:usize,relation:&Relation,columns:&[u32],no_grid:&[bool],places:&[Option<usize>])->Result<std::sync::Arc<ExtentRows>,Stop> {
    let stopped=|bound|Stop {bound,form:reads.form.clone()};
    let materializer=reads.materializer();
    let parts=relation.parts();
    // The parts that hold a column, each with the extent columns it holds.
    let held=(0..parts.len()).filter_map(|p| {
        let own=places.iter().enumerate().filter(|(_,place)|**place==Some(p)).map(|(k,_)|k).collect::<Vec<_>>();
        (!own.is_empty()).then_some((p,own))
    }).collect::<Vec<_>>();
    let rows=held.iter().map(|(p,_)|parts[*p].rows.len() as u64).fold(0u64,u64::saturating_add);
    let bytes=held.iter().map(|(p,own)|parts[*p].rows.len().saturating_mul(Materializer::row_bytes(own.len().saturating_mul(std::mem::size_of::<Option<Extent>>()),2))).fold(0usize,usize::saturating_add);
    let allocation=materializer.hold(rows,bytes).map_err(stopped)?;
    // A row of the relation's width, whose cells outside the part walked are never read.
    let mut row=vec![Term::encode_number(0);usize::from(relation.arity())];
    let mut visited=0usize;
    let mut blocks=Vec::with_capacity(held.len());
    for (p,own) in &held {
        let part=&parts[*p];
        let stride=parts[p+1..].iter().fold(1u64,|count,later|count.saturating_mul(later.rows.len() as u64));
        let mut cells=Vec::with_capacity(part.rows.len());
        for part_row in part.rows.rows() {
            if visited%1024==0 {materializer.check().map_err(stopped)?;}visited+=1;
            for (column,&value) in part.columns.iter().zip(part_row) {row[usize::from(column.0)]=value;}
            cells.push(own.iter().map(|&k|completed_cell(contexts,contents,example,k,columns[k] as usize,no_grid[k],&row,None)).collect());
        }
        blocks.push(ExtentBlock {part:Some(*p),stride,rows:cells.into_boxed_slice()});
    }
    let mut at=vec![None;columns.len()];
    for (block,(_,own)) in held.iter().enumerate() {
        for (slot,&k) in own.iter().enumerate() {at[k]=Some((block,slot));}
    }
    Ok(std::sync::Arc::new(ExtentRows {blocks:blocks.into_boxed_slice(),places:at.into_boxed_slice(),len:relation.len(),direct:false,_allocation:allocation}))
}

fn stopped_extents(contexts:DirectContexts,contents:&Contents,columns:Vec<u32>,no_grid:Vec<bool>,stop:Stop)->Extents {
    let examples=contents.examples.iter().map(|e|e.rows.as_ref().map_or_else(|_|Vec::new(),|a|a.at.iter().map(|(_,models)|models.iter().map(|v|if matches!(v,RelationValue::Rows(_)){EntryExtents::Stopped(stop.clone())}else{EntryExtents::Absent}).collect()).collect())).collect();
    Extents {columns,no_grid,contexts,examples}
}

fn direct_extents(reads:&Reads<'_>,contexts:DirectContexts,contents:&Contents,columns:Vec<u32>,no_grid:Vec<bool>)->Extents {
    // Position cells and proved grid frames carry their extent already.
    // Keep the evidence and compute it at a read; no per-row matrix is needed.
    let examples=contents.examples.iter().map(|e|e.rows.as_ref().map_or_else(|_|Vec::new(),|a|a.at.iter().map(|(_,models)|models.iter().map(|v|match v {
        RelationValue::Rows(rows)=>match reads.materializer().copy(128+columns.len()*std::mem::size_of::<Option<(usize,usize)>>()) {
            Ok(allocation)=>EntryExtents::Rows(Arc::new(ExtentRows {blocks:Box::new([]),places:vec![None;columns.len()].into_boxed_slice(),len:rows.len(),direct:true,_allocation:allocation})),
            Err(bound)=>EntryExtents::Stopped(Stop {bound,form:reads.form.clone()}),
        },
        _=>EntryExtents::Absent,
    }).collect()).collect())).collect();
    Extents {columns,no_grid,examples,contexts}
}

/// Native per-cell annotation, in the relation's each_row order. This is used
/// for body/component buffers and the full-held-choice sidecar alike.
pub fn annotated_rows(materializer:&Materializer<'_>,form:&NodePath,contents:&Contents,example:usize,assignment:usize,model:usize,relation:&Relation)->Result<Materialized<Vec<Vec<(u8,Option<Extent>)>>>,Stop> {
    if let Some(EntryExtents::Stopped(stop))=contents.extents.as_ref().and_then(|e|e.entry(example,assignment,model)) {return Err(stop.clone());}
    let columns=contents.columns.iter().filter(|c|c.ty.is_box()).count();
    let allocation=materializer.admit(relation,Materializer::row_bytes(columns.saturating_mul(std::mem::size_of::<(u8,Option<Extent>)>()),2))
        .map_err(|bound|Stop {bound,form:form.clone()})?;
    let mut result=Vec::with_capacity(usize::try_from(relation.len()).expect("admitted row count"));
    visit_annotated_rows(materializer,form,contents,example,assignment,model,relation,&mut |row|result.push(row.to_vec()))?;
    Ok(Materialized::new(result,allocation))
}

/// Visits annotations in native row order, reusing one row of scratch. The
/// caller admits its destination before the walk; no full annotation matrix
/// is retained here.
pub(crate) fn visit_annotated_rows(materializer:&Materializer<'_>,form:&NodePath,contents:&Contents,example:usize,assignment:usize,model:usize,relation:&Relation,visit:&mut dyn FnMut(&[(u8,Option<Extent>)]))->Result<(),Stop> {
    let columns=contents.columns.iter().enumerate().filter(|(_,c)|c.ty.is_box()).map(|(i,_)|i as u32).collect::<Vec<_>>();
    let extents=contents.extents.as_ref();
    let held=extents.and_then(|e|e.entry(example,assignment,model));
    // A stopped lazy product has never been admitted as a full row buffer.
    // Preserve its stop rather than retrying through direct-cell fallbacks.
    if let Some(EntryExtents::Stopped(stop))=held { return Err(stop.clone()); }
    let stopped=|bound|Stop {bound,form:form.clone()};
    let mut annotations=Vec::with_capacity(columns.len());let mut at=0u64;
    materializer.walk(relation,&mut |row| {
        annotations.clear();
        annotations.extend(columns.iter().enumerate().map(|(k,c)| {
            let no_grid=contents.columns[*c as usize].ty==ValueType::Offset || extents.is_some_and(|e|e.no_grid.get(k)==Some(&true));
            if no_grid {return (0,None);}
            let extent=match held {Some(EntryExtents::Rows(rows))=>rows.cell(at,k),_=>None}
                .or_else(||match contents.columns[*c as usize].ty {
                    ValueType::Position=>position_extent(row[*c as usize],&ValueType::Position),
                    ValueType::Box=>extents?.direct_at(contents,example,*c as usize,row),
                    _=>None,
                });
            (if extent.is_some(){1}else{2},extent)
        }));
        visit(&annotations);at+=1;
    }).map_err(stopped)
}

/// The extents of the made frames of the `Box` columns of the table of
/// `relation`, whose contents are `contents` with their `frames`, in `checked`:
/// none where the table has no such column. The columns are those of
/// `extent_columns` of `contents.frames`. `earlier` are the tables before it
/// that its rows read.
pub fn table_extents(decoder: &Decoder<'_>, earlier: &[&Table], checked: &CheckedProgram, relation: &GraphRelation, contents: &Contents) -> Option<Extents> {
    table_extents_with_context(decoder, earlier, checked, relation, contents, AssignmentContext::Search)
}

pub(crate) fn table_extents_with_context(decoder: &Decoder<'_>, earlier: &[&Table], checked: &CheckedProgram, relation: &GraphRelation, contents: &Contents, context: AssignmentContext<'_>) -> Option<Extents> {
    let types: Vec<ValueType> = contents.columns.iter().map(|column| column.ty.clone()).collect();
    let reads=Reads::with_context(decoder,earlier,checked.program.form_of(relation.node),context,contents);
    let EvidencePlan {columns,no_grid,contexts,needed,stop}=EvidencePlan::new(&reads.materializer(),decoder,earlier,checked,checked.program.form_of(relation.node),contents);
    if columns.is_empty() { return None; }
    if let Some(stop)=stop {return Some(stopped_extents(contexts,contents,columns,no_grid,stop));}
    if !needed.iter().any(|needed| *needed) {
        return Some(direct_extents(&reads,contexts,contents,columns,no_grid));
    }
    let subject = Subject { assignment_layout:&contents.assignment_layout, checked, relation:Some(relation), types: &types, examples: &contents.examples, columns: &columns, needed:Some(&needed) };
    let gathered = derive(decoder, &reads, &subject);
    Some(Extents { examples: finish(&reads,&contexts, contents, &gathered, &columns, &no_grid), columns, no_grid, contexts })
}

/// Extents of a checked body query, using the same native derivation and
/// earlier-table lookup as relation tables, with its exact result interface.
pub fn body_extents(decoder:&Decoder<'_>,earlier:&[&Table],checked:&CheckedProgram,view:&BodyView,contents:&Contents)->Option<Extents> {
    body_extents_with_context(decoder, earlier, checked, view, contents, AssignmentContext::Search)
}

pub(crate) fn body_extents_with_context(decoder:&Decoder<'_>,earlier:&[&Table],checked:&CheckedProgram,view:&BodyView,contents:&Contents,context:AssignmentContext<'_>)->Option<Extents> {
    let reads=Reads::with_context(decoder,earlier,&view.form,context,contents);
    body_extents_in(decoder,&reads,checked,view,contents)
}

/// Nested key evidence shares the parent work count and source lookup cache.
fn body_extents_in(decoder:&Decoder<'_>,reads:&Reads<'_>,checked:&CheckedProgram,view:&BodyView,contents:&Contents)->Option<Extents> {
    let types=contents.columns.iter().map(|c|c.ty.clone()).collect::<Vec<_>>();
    let EvidencePlan {columns,no_grid,contexts,needed,stop}=EvidencePlan::new(&reads.materializer(),decoder,reads.tables,checked,&view.form,contents);
    if columns.is_empty() {return None;}
    if let Some(stop)=stop {return Some(stopped_extents(contexts,contents,columns,no_grid,stop));}
    if !needed.iter().any(|needed| *needed) {
        return Some(direct_extents(reads,contexts,contents,columns,no_grid));
    }
    let subject=Subject {assignment_layout:&contents.assignment_layout,checked,relation:None,types:&types,examples:&contents.examples,columns:&columns,needed:Some(&needed)};
    let mut gathered=subject.examples.iter().map(|e|e.rows.as_ref().map_or_else(|_|Vec::new(),|a|a.at.iter().map(|_|Gathered::default()).collect())).collect::<Vec<Vec<Gathered>>>();
    let placements=view.clause.columns.iter().enumerate().map(|(i,v)|Some(Placement {slot:i as u32,label:Some(view.paths.labels[v.0 as usize])})).collect::<Vec<_>>();
    let dets=contents.dets.iter().map(|d|relation_spelled(&d.relation)).collect::<Vec<_>>();
    match view.widened() {
        Ok(views)=>for sub in &views {gather(decoder,reads,&dets,&subject,sub,&placements,&mut gathered)},
        Err(fault)=>lose_all(&mut gathered,&fault_spelled(&fault)),
    }
    Some(Extents {examples:finish(reads,&contexts,contents,&gathered,&columns,&no_grid),columns,no_grid,contexts})
}

/// What the derivations of the rows of `subject` give for each of its
/// examples, for each of its assignments: the widened bodies of the clauses
/// that give the relation, or of the clauses that an instance writes for an
/// input, or the inputs of the instance that an output reads.
fn derive(decoder: &Decoder<'_>, reads: &Reads<'_>, subject: &Subject<'_>) -> Vec<Vec<Gathered>> {
    let registry = decoder.registry();
    let (checked, relation) = (subject.checked, subject.relation.expect("relation derivation has a subject"));
    let mut gathered: Vec<Vec<Gathered>> = subject.examples.iter().map(|example| example.rows.as_ref().map_or_else(|_| Vec::new(), |rows| rows.at.iter().map(|_| Gathered::default()).collect())).collect();
    let dets: Vec<String> = relation_dets(checked, relation.node).iter().map(|det| relation_spelled(&det.relation)).collect();
    let kind = &checked.program.graph.nodes[relation.node.0 as usize].kind;
    let root = NodeRef::Program(checked.program.program.value());
    // The clauses that the instance of an input writes, widened, and how many of them the givens have used.
    let mut used = 0;
    for given in checked.program.given(relation.node, registry) {
        if relation.output.as_deref().zip(given.output.as_deref()).is_some_and(|(read, own)| read != own) {
            continue;
        }
        let placements = || column_placements(checked, relation.node, relation.output.as_deref(), &given.form, subject.types.len(), registry);
        match (node_at(root, &given.form), kind) {
            (Some(NodeRef::Clause(_)), _) => {
                let placements=placements();
                gather_view(decoder,reads,&dets,subject,&given.form.child(0),&placements,&mut gathered);
            }
            (Some(NodeRef::Choose(_)), _) => {
                let placements=placements();
                // Every selected row is an original option. Match its whole
                // native row against the checked for/from derivations; do
                // not treat selection as a new frame or widen the pick.
                match BodyView::choose_options(checked,&given.form).and_then(|view|view.widened()) {
                    Ok(views)=>for view in &views {gather(decoder,reads,&dets,subject,view,&placements,&mut gathered)},
                    Err(fault)=>lose_all(&mut gathered,&fault_spelled(&fault)),
                }
            }
            (Some(NodeRef::RigidDet(_)), DependencyKind::RigidAssembly(_)) => {
                // Rigid outputs are native D4 images, not the rows of a
                // widened clause. flows_visiting deliberately marks moved
                // part frames Unknown: the pre-image's frame is not proof
                // of the image's extent. Leave these slots Unset, which
                // finish exports as unresolved, rather than reporting a
                // fault in already evaluated native rows. Intrinsic Position
                // and known grid-frame evidence is completed independently.
            }
            (Some(NodeRef::Instance(_)), DependencyKind::InstanceInput { input, .. }) => {
                let placements=placements();
                let all=checked.program.input_bodies(&given.form,input);
                match all.get(used) {
                    Some(body)=>gather_view(decoder,reads,&dets,subject,&given.form.join(body),&placements,&mut gathered),
                    None=>lose_all(&mut gathered,"the instance writes no clause for the input at this form"),
                }
                used+=1;
            }
            (Some(NodeRef::Instance(instance)),DependencyKind::RecursiveInstance(_))=>{
                let port=given.output.as_deref().and_then(|steps|match steps {[arclog::program::OutputStep::Port(port)]=>Some(port),_=>None});
                let component=registry_columns::component(registry,&instance.component).expect("checked component");
                match port {
                    Some(port) if !component.outputs.iter().any(|own|own.name==*port)=>{
                        let placements=placements();
                        let all=checked.program.input_bodies(&given.form,port);
                        for at in all {gather_view(decoder,reads,&dets,subject,&given.form.join(&at),&placements,&mut gathered);}
                    }
                    _=>gather_output(decoder,reads,subject,&given,instance,&mut gathered),
                }
            }
            (Some(NodeRef::Instance(instance)), DependencyKind::InstanceOutput { .. }) => gather_output(decoder, reads, subject, &given, instance, &mut gathered),
            (Some(NodeRef::Demonstrated(_)), DependencyKind::Demonstrated(_)) => {
                // A row at a key is a prediction of a rule that the key's
                // demonstrations confirm, so the bodies of the rules'
                // `&prediction` clauses derive the rows.
                match BodyView::predictions(checked, &given.form) {
                    Ok(predictions) => for (view, labels) in &predictions {
                        let placements = labels.iter().enumerate().map(|(slot, label)| Some(Placement { slot: slot as u32, label: *label })).collect::<Vec<_>>();
                        match view.widened() {
                            Ok(views) => for sub in &views { gather(decoder, reads, &dets, subject, sub, &placements, &mut gathered) },
                            Err(fault) => lose_all(&mut gathered, &fault_spelled(&fault)),
                        }
                    },
                    Err(fault) => lose_all(&mut gathered, &fault_spelled(&fault)),
                }
            }
            _ => lose_all(&mut gathered, &format!("the rows of a {} form are not derived", kind_spelled(kind))),
        }
    }
    gathered
}

/// The spelling of the kind of form that gives a relation's rows, as the
/// program writes the form where it has a keyword.
fn kind_spelled(kind: &DependencyKind) -> &'static str {
    match kind {
        DependencyKind::Fact(_) => "fact",
        DependencyKind::Clause(_) => "clause",
        DependencyKind::InstanceInput { .. } => "instance input",
        DependencyKind::InstanceOutput { .. } => "instance output",
        DependencyKind::Parameter(_) => "parameter",
        DependencyKind::Chosen(_) => "CHOOSE",
        DependencyKind::RigidAssembly(_) => "RIGID_DET",
        DependencyKind::Demonstrated(_) => "DEMONSTRATED",
        DependencyKind::RecursiveInstance(_) => "recursive instance",
        DependencyKind::Out(_) => "OUT",
    }
}

/// Marks every entry as lost, for `reason`.
fn lose_all(gathered: &mut [Vec<Gathered>], reason: &str) {
    for entry in gathered.iter_mut().flatten() {
        entry.lose(reason);
    }
}

/// Adds to `gathered` the extents that the rows of the widened body `body`
/// give: each row of the body derives the relation's row at the label of each of
/// its columns (`placements`), with the extent of each wanted column. `dets` are
/// the `DET`s of the relation.
fn gather_view(decoder:&Decoder<'_>,reads:&Reads<'_>,dets:&[String],subject:&Subject<'_>,at:&NodePath,placements:&[Option<Placement>],gathered:&mut [Vec<Gathered>]) {
    match BodyView::derivation_at(subject.checked,at).and_then(|view|view.widened()) {
        Ok(views)=>for view in &views {gather(decoder,reads,dets,subject,view,placements,gathered)},
        Err(fault)=>lose_all(gathered,&fault_spelled(&fault)),
    }
}

fn gather(decoder: &Decoder<'_>, reads: &Reads<'_>, dets: &[String], subject: &Subject<'_>, sub: &BodyView, placements: &[Option<Placement>], gathered: &mut [Vec<Gathered>]) {
    let at_label = |placement: &Option<Placement>| placement.and_then(|placement| placement.label).and_then(|label| sub.column_of(label));
    let Some(key) = placements.iter().map(at_label).collect::<Option<Vec<usize>>>() else {
        let missing=placements.iter().enumerate().filter(|(_,placement)|at_label(placement).is_none())
            .map(|(column,placement)|(column,placement.and_then(|placement|placement.label))).collect::<Vec<_>>();
        let labels=sub.clause.columns.iter().map(|variable|sub.paths.labels[variable.0 as usize]).collect::<Vec<_>>();
        return lose_all(gathered, &format!("a relation column has no label in its checked derivation: relation {:?}, form {:?}, input {:?}, missing physical columns/labels {:?}, query labels {:?}",subject.relation,sub.form,sub.input,missing,labels));
    };
    let checked=subject.checked;
    let types=sub.clause.columns.iter().map(|v|sub.clause.variables[v.0 as usize].ty.clone()).collect::<Vec<_>>();
    let sources=body_column_flows(checked,&sub.clause,&sub.paths,decoder.registry());
    let keys=match key_evidence(decoder,reads,checked,sub) {
        Ok(keys)=>keys,
        Err(fault)=>return lose_all(gathered,&fault_spelled(&fault)),
    };
    let analysis=Analysis {decoder,registry:decoder.registry(),checked,sub,types:&types,sources,reads,dets,keys:&keys};
    let walked=crate::tables::body_tables::dets(checked,sub);
    let sole_derivation = subject.relation.is_none_or(|relation| {
        let givens = checked.program.given(relation.node, decoder.registry()).into_iter().filter(|given|
            !relation.output.as_deref().zip(given.output.as_deref()).is_some_and(|(read, own)| read != own)).collect::<Vec<_>>();
        if givens.len() != 1 || givens[0].form != sub.form {return false;}
        match &checked.program.graph.nodes[relation.node.0 as usize].kind {
            DependencyKind::Clause(_) => true,
            DependencyKind::InstanceInput {input, ..} => checked.program.input_bodies(&sub.form, input).len() == 1,
            _ => false,
        }
    });
    let values = if sole_derivation && !sub.union_expanded && key.len() == sub.clause.columns.len() && {
        let mut columns = key.clone(); columns.sort_unstable(); columns == (0..key.len()).collect::<Vec<_>>()
    } {
        // Relabel the compact parts; no product or second join is evaluated.
        subject.examples.iter().map(|example| ExampleRows {
            example: example.example,
            rows: example.rows.clone().map(|assigned| Assigned {
                at: assigned.at.into_iter().map(|(assignment, models)| {
                    let models = models.into_iter().map(|model| match model {
                        RelationValue::Rows(rows) => RelationValue::Rows(Arc::new(Relation::from_parts(rows.arity(), rows.parts().iter().map(|part|
                            arclog::relations::RelationPart {columns: part.columns.iter().map(|c| arclog::relations::ColumnIndex(key[c.0 as usize] as u16)).collect(), rows: part.rows.clone()}).collect()))),
                        other => other,
                    }).collect();
                    (assignment, models)
                }).collect(),
                stop: assigned.stop,
            }),
        }).collect::<Vec<_>>()
    } else {
        crate::tables::body_tables::examples_with_context(decoder,checked,sub,&walked,&reads.work,reads.query_context())
    };
    for (place, example) in subject.examples.iter().enumerate() {
        let Ok(rows) = &example.rows else { continue };
        let entries = &mut gathered[place];
        let Some(found) = values.iter().find(|own| own.example == example.example) else {
            entries.iter_mut().for_each(|entry| entry.lose("the widened body is not evaluated on the example"));
            continue;
        };
        let assigned = match &found.rows {
            Ok(assigned) => assigned,
            Err(fault) => {
                entries.iter_mut().for_each(|entry| entry.lose(&fault_spelled(fault)));
                continue;
            }
        };
        for (table_at, ((table_assignment, _), entry)) in rows.at.iter().zip(entries.iter_mut()).enumerate() {
            let mut matched = false;
            let body_layout=reads.query_context().layout();
            for body_at in subject.assignment_layout.select(table_at,table_assignment,&body_layout,assigned) {
                let (body_assignment,models)=&assigned.at[body_at];
                matched = true;
                for value in models {
                    match value {
                        RelationValue::Rows(body_rows) => {
                            if let Err(stop) = reads.charge(body_rows.len(), &sub.form) {
                                entry.stop = Some(stop);
                                continue;
                            }
                            if entry.admit(reads,body_rows,subject.columns.len(),&sub.form).is_err() {continue;}
                            let Some(full)=body_layout.full(body_at,body_assignment) else {entry.lose("extent query assignment ordinal is outside its held receipt");continue};
                            let ctx = Ctx::new(example.example, full, &body_layout, body_at);
                            if let Some(stop)=analysis.key_stop(&ctx) {entry.stop=Some(stop);}
                            if let Some(fault)=analysis.key_fault(&ctx) {entry.lose(&fault);}
                            let walked=reads.materializer().walk(body_rows, &mut |row| {
                                let derived: Box<[TermId]> = key.iter().map(|&column| row[column]).collect();
                                let slots = entry.rows.entry(derived).or_insert_with(|| vec![Merged::Unset; subject.columns.len()]);
                                for (k, (slot, &column)) in slots.iter_mut().zip(subject.columns).enumerate() {
                                    // None absorbs every later derivation.
                                    // Re-reading its sources can add no frame
                                    // evidence and needlessly spends the table's
                                    // budget on an already settled cell.
                                    if subject.needs(k) && *slot != Merged::None {
                                        slot.merge(analysis.extent_of(key[column as usize], row, &ctx, 0));
                                    }
                                }
                            });
                            if let Err(bound)=walked {entry.stop=Some(Stop {bound,form:sub.form.clone()});}
                            // The reads of earlier tables that the rows made may have passed the cap.
                            if let Err(stop) = reads.charge(0, &sub.form) {
                                entry.stop = Some(stop);
                            }
                        }
                        RelationValue::Stopped(stop) => entry.stop = Some(stop.clone()),
                        RelationValue::Undefined => entry.lose("the relation of the widened body is undefined"),
                    }
                }
            }
            if !matched {
                entry.stop = entry.stop.take().or_else(|| assigned.stop.clone());
            }
        }
    }
}

/// An input of an instance that the extents of an output read: its name, its
/// node, the row positions of its key, the row positions whose extents are
/// wanted, and their derivation.
struct PortRows {
    name: PortName,
    relation:GraphRelation,
    key: Option<Range<usize>>,
    wanted: Vec<u32>,
    derived: Option<(Vec<ExampleRows>, Vec<Vec<Gathered>>, AssignmentLayout)>,
}

impl PortRows {
    /// What the derivations give of the port at the assignment `assigned` on
    /// `example`.
    fn entry(&self, ctx:&Ctx<'_>) -> Vec<&Gathered> {
        let Some((examples, gathered, layout)) = &self.derived else {return Vec::new()};
        let Some(place) = examples.iter().position(|own| own.example == ctx.example) else {return Vec::new()};
        let Ok(rows) = &examples[place].rows else {return Vec::new()};
        ctx.layout.select(ctx.ordinal,ctx.assignment,layout,rows).into_iter().filter_map(|at|gathered[place].get(at)).collect()
    }
}

/// Where the extent of an output column comes from: the wanted position of the
/// port `port` at index `slot` among the port's wanted positions.
struct Source {
    port: usize,
    slot: usize,
}

/// How the extent of a wanted column of an output is found: from the rows of
/// the `sources`, matched to the output's rows by the key and the cell of the
/// column where `by_cell` holds, and by the key alone otherwise.
struct ColumnPlan {
    sources: Vec<Source>,
    by_cell: bool,
}

/// The inputs of an instance that the extents of its output read, and how each
/// wanted column of the output reads them, none for a column with no extent.
struct OutputPlan {
    ports: Vec<PortRows>,
    columns: Vec<Option<ColumnPlan>>,
    /// The row positions of the output's key.
    key: Option<Range<usize>>,
}

impl OutputPlan {
    /// The plan for the wanted columns of the output of the instance `instance`
    /// that `given` gives, where each wanted column `c` takes its extent from:
    ///
    /// - a column of the output's key: the same key column of an input that has a
    ///   key, over the rows of that input with the row's key;
    /// - a column that a declared row of `copies` maps from input columns: those
    ///   columns, over the rows of the inputs with the row's key whose cell
    ///   there equals the row's;
    /// - another column whose frame rule makes no frame and names input columns:
    ///   those columns, over the rows of the inputs with the row's key.
    ///
    /// The key is dropped where the output or an input has none. Any other
    /// column has no extent.
    fn new(decoder: &Decoder<'_>, subject: &Subject<'_>, given: &Given, instance: &Instance) -> Option<OutputPlan> {
        let registry = decoder.registry();
        let (checked, relation) = (subject.checked, subject.relation.expect("relation derivation has a subject"));
        let width = subject.types.len();
        let frames = output_frames(checked, relation.node, relation.output.as_deref(), &given.form, width, registry);
        let copies = output_copies(checked, relation.node, relation.output.as_deref(), &given.form, width, registry);
        let component = registry_columns::component(registry, &instance.component)?;
        let key = key_range(given.slots.iter().map(|slot| (slot.is_key, slot.width)));
        let mut ports: Vec<PortRows> = Vec::new();
        // The index among `ports` of the input `name`, which `ports` gains when it lacks it.
        let port_of = |name: &PortName, ports: &mut Vec<PortRows>| -> Option<usize> {
            if let Some(place) = ports.iter().position(|own| own.name == *name) {
                return Some(place);
            }
            let relation=arclog::eval::input_relation(checked,&instance.name,name)?;
            let input = component.inputs.iter().find(|input| input.port.name == *name)?;
            let slots = checked.program.instance_port_slots(&given.form, &input.port, registry)?;
            ports.push(PortRows { name: name.clone(), relation, key: key_range(slots.iter().map(|slot| (slot.is_key, slot.width))), wanted: Vec::new(), derived: None });
            Some(ports.len() - 1)
        };
        let mut columns: Vec<Option<ColumnPlan>> = Vec::new();
        for (k, &column) in subject.columns.iter().enumerate() {
            if !subject.needs(k) {
                columns.push(None);
                continue;
            }
            let position = column as usize;
            let wants: Option<(Vec<(PortName, usize)>, bool)> = match &key {
                Some(key) if key.contains(&position) => component.inputs.iter().find_map(|input| {
                    let place = port_of(&input.port.name, &mut ports)?;
                    let held = ports[place].key.as_ref().filter(|held| held.len() == key.len())?;
                    Some((vec![(input.port.name.clone(), held.start + position - key.start)], false))
                }),
                _ if !copies[position].is_empty() => copies[position].iter().all(|(_, range)| range.len() == 1).then(|| (copies[position].iter().map(|(name, range)| (name.clone(), range.start)).collect(), true)),
                _ => frames[position].as_ref().filter(|frame| usable(frame)).map(|frame| (frame.named.iter().map(|(name, range)| (name.clone(), range.start)).collect(), false)),
            };
            columns.push(wants.and_then(|(wants, by_cell)| {
                let sources = wants
                    .iter()
                    .map(|(name, wanted)| {
                        let port = port_of(name, &mut ports)?;
                        let wanted = u32::try_from(*wanted).ok()?;
                        let slot = ports[port].wanted.iter().position(|&own| own == wanted).unwrap_or_else(|| {
                            ports[port].wanted.push(wanted);
                            ports[port].wanted.len() - 1
                        });
                        Some(Source { port, slot })
                    })
                    .collect::<Option<Vec<Source>>>()?;
                Some(ColumnPlan { sources, by_cell })
            }));
        }
        Some(OutputPlan { ports, columns, key })
    }

    /// Derives the rows of each input whose extents a column wants.
    fn derive_ports(&mut self, decoder: &Decoder<'_>, reads: &Reads<'_>, checked: &CheckedProgram) -> arclog::eval::Outcome<()> {
        for port in self.ports.iter_mut().filter(|port| !port.wanted.is_empty()) {
            let port_relation=port.relation.clone();
            let form=checked.program.form_of(port_relation.node);
            let types=checked.types.columns(&port_relation).ok_or_else(||arclog::eval::RunFault {message:"component input has no checked types".into(),form:form.clone()})?;
            let dets=relation_dets(checked,port_relation.node);
            let examples=relation_examples_with_context(decoder,checked,&port_relation,&dets,&reads.work,reads.query_context());
            // This metadata is private to the query, not a published slot.
            let mut contents=crate::tables::relation_metadata(decoder.registry(),checked,form,&port_relation,0,&dets,examples)?;
            contents.assignment_layout=reads.query_context().layout();
            contents.frames=column_frames(&reads.names,&contents);
            let plan=EvidencePlan::new(&reads.materializer(),decoder,reads.tables,checked,form,&contents);
            let needed=plan.wanted(&port.wanted);
            let examples=contents.examples.to_vec();
            if let Some(stop)=&plan.stop {
                let derived=examples.iter().map(|e|e.rows.as_ref().map_or_else(|_|Vec::new(),|a|a.at.iter().map(|_|Gathered {stop:Some(stop.clone()),..Gathered::default()}).collect())).collect();
                port.derived=Some((examples,derived,contents.assignment_layout.clone()));continue;
            }
            let port_subject=Subject {assignment_layout:&contents.assignment_layout,checked,relation:Some(&port_relation),types,examples:&examples,columns:&port.wanted,needed:Some(&needed)};
            let mut derived=if needed.iter().any(|n|*n) {derive(decoder,reads,&port_subject)} else {
                examples.iter().map(|e|e.rows.as_ref().map_or_else(|_|Vec::new(),|a|a.at.iter().map(|_|Gathered::default()).collect())).collect()
            };
            // Retain full native row identities and wanted-slot order. Complete
            // intrinsic/direct slots independently of other slots' stops.
            for (example,e) in examples.iter().enumerate() {if let Ok(assigned)=&e.rows {
                for (at,(_,models)) in assigned.at.iter().enumerate() {for model in models {
                    if let RelationValue::Rows(rows)=model {
                        let completed=match flat_rows(reads,&plan.contexts,&contents,example,rows,&port.wanted,
                            &port.wanted.iter().map(|c|plan.columns.iter().position(|x|x==c).is_some_and(|k|plan.no_grid[k])).collect::<Vec<_>>(),Some(&derived[example][at])) {
                            Ok(rows)=>rows,Err(stop)=>{derived[example][at].stop=Some(stop);continue;}
                        };
                        if derived[example][at].admit(reads,rows,port.wanted.len(),form).is_err() {continue;}
                        let mut i=0u64;
                        let mut budget=Budget::new(&reads.limits,reads.session);
                        if let Err(bound)=budget.walk_rows(rows,&mut |row| {
                            derived[example][at].rows.insert(row.into(),(0..port.wanted.len()).map(|k|completed.cell(i,k).map_or(Merged::None,Merged::One)).collect());
                            i+=1;
                        }) {derived[example][at].stop=Some(Stop {bound,form:form.clone()});}
                    } else if let RelationValue::Stopped(stop)=model {
                        derived[example][at].stop=Some(stop.clone());
                    } else {
                        derived[example][at].lose("the component input is undefined");
                    }
                }}
            }}
            port.derived = Some((examples, derived, contents.assignment_layout.clone()));
        }
        Ok(())
    }

    /// The extents that the inputs give each wanted column at the assignment
    /// `assigned` on `example`; a stop of an input's derivation stops `entry`.
    fn lookups(&self,reads:&Reads<'_>, ctx:&Ctx<'_>, entry: &mut Gathered) -> Vec<Lookup> {
        let held = self.ports.iter().map(|port| port.entry(ctx)).collect::<Vec<_>>();
        self.columns
            .iter()
            .map(|plan| {
                let mut lookup = Lookup::default();
                let Some(plan) = plan else {
                    lookup.bad = true;
                    return lookup;
                };
                lookup.by_cell = plan.by_cell;
                lookup.keyed = self.key.is_some() && plan.sources.iter().all(|source| self.ports[source.port].key.is_some());
                for source in &plan.sources {
                    let port = &self.ports[source.port];
                    if held[source.port].is_empty() { lookup.bad=true; }
                    for rows in &held[source.port] {
                    if let Some(stop) = &rows.stop {
                        entry.stop = Some(stop.clone());
                    }
                    lookup.bad |= rows.lost.is_some();
                    let position = port.wanted[source.slot] as usize;
                    if lookup.by_cell || lookup.keyed {
                        let width=rows.rows.keys().next().map_or(0,|row|row.len());
                        let bytes=rows.rows.len().saturating_mul(Materializer::row_bytes(width.saturating_mul(std::mem::size_of::<TermId>()).saturating_add(std::mem::size_of::<Merged>()),3));
                        match reads.materializer().copy(bytes) {
                            Ok(owner)=>lookup.allocations.push(owner),
                            Err(bound)=>{entry.stop=Some(Stop {bound,form:reads.form.clone()});lookup.bad=true;continue;}
                        }
                    }
                    let mut visited=0;
                    for (row, slots) in &rows.rows {
                        if visited%1024==0 {if let Err(bound)=reads.materializer().check() {entry.stop=Some(Stop {bound,form:reads.form.clone()});break;}}visited+=1;
                        let extent = slots[source.slot].extent();
                        let key: Box<[TermId]> = match (&port.key, lookup.keyed) {
                            (Some(key), true) => row[key.clone()].into(),
                            _ => Box::default(),
                        };
                        lookup.any.merge(extent);
                        if lookup.by_cell {
                            lookup.cells.entry((key, row[position])).or_insert(Merged::Unset).merge(extent);
                        } else if lookup.keyed {
                            lookup.keys.entry(key).or_insert(Merged::Unset).merge(extent);
                        }
                    }
                }
                }
                lookup
            })
            .collect()
    }
}

/// Adds to `gathered` the extents of the rows of the output of the instance
/// `instance` that `given` gives, as [`OutputPlan::new`] gives them.
fn gather_output(decoder: &Decoder<'_>, reads: &Reads<'_>, subject: &Subject<'_>, given: &Given, instance: &Instance, gathered: &mut [Vec<Gathered>]) {
    let Some(mut plan) = OutputPlan::new(decoder, subject, given, instance) else { return lose_all(gathered, "the component of the instance is not in the registry") };
    if let Err(fault)=plan.derive_ports(decoder,reads,subject.checked) {return lose_all(gathered,&fault_spelled(&fault));}
    for (place, example) in subject.examples.iter().enumerate() {
        let Ok(rows) = &example.rows else { continue };
        for (ordinal, ((assigned, models), entry)) in rows.at.iter().zip(gathered[place].iter_mut()).enumerate() {
            let Some(full)=subject.assignment_layout.full(ordinal,assigned) else {entry.lose("component assignment ordinal is outside its held receipt");continue};
            let ctx=Ctx::new(example.example,full,subject.assignment_layout,ordinal);
            let lookups = plan.lookups(reads,&ctx, entry);
            for model in models {
                let RelationValue::Rows(model_rows) = model else { continue };
                if let Err(stop) = reads.charge(model_rows.len(), &given.form) {
                    entry.stop = Some(stop);
                    continue;
                }
                if entry.admit(reads,model_rows,subject.columns.len(),&given.form).is_err() {continue;}
                let walked=reads.materializer().walk(model_rows, &mut |row| {
                    let slots: Vec<Merged> = subject.columns.iter().zip(&lookups).map(|(&column, lookup)| lookup.of(row, column as usize, plan.key.as_ref())).collect();
                    entry.rows.entry(row.into()).or_insert(slots);
                });
                if let Err(bound)=walked {entry.stop=Some(Stop {bound,form:given.form.clone()});}
            }
        }
    }
}

/// The extents that the rows of the inputs of an instance give one wanted
/// column of its output.
#[derive(Default)]
struct Lookup {
    allocations:Vec<std::sync::Arc<arclog::session::SessionAllocation>>,
    /// Whether the column has no extent.
    bad: bool,
    /// Whether the rows match by the key, and by the cell of the column.
    keyed: bool,
    by_cell: bool,
    /// The merged extent at all the rows, at each key, and at each key and cell.
    any: Merged,
    keys: StableHashMap<Box<[TermId]>, Merged>,
    cells: StableHashMap<(Box<[TermId]>, TermId), Merged>,
}

impl Lookup {
    /// The extent of the output row `row`, whose cell at the wanted column
    /// `column` is `row[column]` and whose key stands at `key`.
    fn of(&self, row: &[TermId], column: usize, key: Option<&Range<usize>>) -> Merged {
        if self.bad {
            return Merged::None;
        }
        let key: Box<[TermId]> = match key {
            Some(key) if self.keyed => row[key.clone()].into(),
            _ => Box::default(),
        };
        let found = match (self.by_cell, self.keyed) {
            (true, _) => self.cells.get(&(key, row[column])),
            (false, true) => self.keys.get(&key),
            (false, false) => return self.any,
        };
        found.copied().unwrap_or(Merged::Unset)
    }
}

/// The row positions of the key among those of a relation whose columns are
/// `slots`, each whether it is the `key` column and its width.
fn key_range(slots: impl Iterator<Item = (bool, usize)>) -> Option<Range<usize>> {
    let mut start = 0;
    for (is_key, width) in slots {
        if is_key {
            return Some(start..start + width);
        }
        start += width;
    }
    None
}

/// Whether the frame rule `frame` of an output column gives the frame of the
/// columns it names, each of one row position: a rule that makes no frame and
/// names a column.
fn usable(frame: &OutputFrame) -> bool {
    !frame.rule.makes && !frame.named.is_empty() && frame.named.iter().all(|(_, range)| range.len() == 1)
}

/// The extents of `contents`' entries, from what their derivations gave.
fn finish(reads:&Reads<'_>,contexts: &DirectContexts, contents: &Contents, gathered: &[Vec<Gathered>], columns: &[u32], no_grid: &[bool]) -> Vec<Vec<Vec<EntryExtents>>> {
    contents
        .examples
        .iter()
        .zip(gathered)
        .enumerate()
        .map(|(place, (example, entries))| match &example.rows {
            Err(_) => Vec::new(),
            Ok(rows) => rows
                .at
                .iter()
                .zip(entries)
                .map(|((_, models), entry)| {
                    models
                        .iter()
                        .map(|value| match (value, &entry.stop) {
                            (RelationValue::Rows(relation), _) if entry.lost.is_some() => {
                                if relation.is_empty() {EntryExtents::Absent} else {EntryExtents::Lost(entry.lost.clone().expect("a recorded loss"))}
                            },
                            (RelationValue::Rows(_), Some(stop)) => EntryExtents::Stopped(stop.clone()),
                            (RelationValue::Rows(relation), None) => match &entry.lost {
                                Some(reason) if !relation.is_empty() => EntryExtents::Lost(reason.clone()),
                                Some(_) => EntryExtents::Absent,
                                None => match completed_rows(reads,contexts,contents,place,relation,columns,no_grid,Some(entry)) {
                                    Ok(rows)=>EntryExtents::Rows(rows),Err(stop)=>EntryExtents::Stopped(stop),
                                },
                            },
                            _ => EntryExtents::Absent,
                        })
                        .collect()
                })
                .collect(),
        })
        .collect()
}

/// Where a row is evaluated: its example, and the assignment of the `DET`s of
/// the body that gives it.
struct Ctx<'a> {
    example: Option<Example>,
    assignment: &'a [Assignment],
    layout: &'a AssignmentLayout,
    ordinal: usize,
    /// The entries of each table read that agree with the assignment, by the
    /// table's number and the place of the example, as [`Reads::extent_at`]
    /// selects them. They depend on the context alone, so a walk of a body's
    /// rows compares the assignments once per table, and not once per row.
    selected: RefCell<StableHashMap<(u32, usize), Rc<[usize]>>>,
}

impl<'a> Ctx<'a> {
    fn new(example: Option<Example>, assignment: &'a [Assignment], layout: &'a AssignmentLayout, ordinal: usize) -> Self {
        Ctx { example, assignment, layout, ordinal, selected: RefCell::default() }
    }
}

/// The earlier tables that the rows of a table read, and the work count of the
/// table's derivation.
struct Reads<'a> {
    /// The tables before the table, as the columns of the case name them.
    names: TableNames,
    tables: &'a [&'a Table],
    /// For a column of a table read, the extent at each key of the cells of the
    /// columns that the read fixes, as [`Reads::extent_at`] builds it.
    cache: RefCell<StableHashMap<LookupKey, Rc<Materialized<StableHashMap<Box<[TermId]>, Merged>>>>>,
    /// The count that the derivation's evaluations, and the rows it visits, are charged to.
    work: TableWork,
    limits: arclog::eval::Limits,
    receipt: Option<&'a Arc<HeldAssignments>>,
    session: &'a arclog::session::TaskSession,
    form: NodePath,
    failure: RefCell<Option<Stop>>,
}

/// A table of the stream by its number, the place of the example and of the
/// assignment of its entry, the column read, and the columns whose cells the
/// read fixes.
type LookupKey = (u32, usize, usize, usize, Vec<usize>);

impl<'a> Reads<'a> {
    fn materializer(&self)->Materializer<'_> {Materializer::new(self.session,&self.limits)}

    /// The count of an observation of the rows that `contents` holds: the table work cap
    /// of the settings for each distinct assignment of its rows.
    fn work_of(decoder:&Decoder<'a>,contents:&Contents)->TableWork {
        let mut assignments: Vec<&[Assignment]> = Vec::new();
        for (values, _) in contents.examples.iter().filter_map(|e|e.rows.as_ref().ok()).flat_map(|a|&a.at) {
            if !assignments.iter().any(|held| held.len() == values.len() && held.iter().zip(values).all(|((name, rows), (other, value))| name == other && arclog::session::same_rows(rows, value))) {
                assignments.push(values);
            }
        }
        let assignments = (assignments.len() as u64).max(1);
        TableWork::new(decoder.settings().table_work_cap.saturating_mul(assignments))
    }

    fn new(decoder:&Decoder<'a>,tables:&'a [&'a Table],form:&NodePath,contents:&Contents)->Self {
        Self::new_in(decoder,tables,form,decoder.limits(),Self::work_of(decoder,contents),None)
    }

    fn new_in(decoder:&Decoder<'a>,tables:&'a [&'a Table],form:&NodePath,limits:arclog::eval::Limits,work:TableWork,receipt:Option<&'a Arc<HeldAssignments>>)->Self {
        Self {names:names_of(decoder.registry(),tables),tables,cache:RefCell::default(),limits:limits.counted_in(work.clone()),work,receipt,session:decoder.evaluation_inputs().1,form:form.clone(),failure:RefCell::new(None)}
    }

    fn with_context(decoder:&Decoder<'a>,tables:&'a [&'a Table],form:&NodePath,context:AssignmentContext<'a>,contents:&Contents)->Self {
        match context {
            // The count keeps the gauges of the first limits that count it, so a held assignment's count starts under the limits of the context.
            AssignmentContext::Held {receipt,limits,..} => Self::new_in(decoder,tables,form,limits.clone(),Self::work_of(decoder,contents),Some(receipt)),
            AssignmentContext::Search => Self::new(decoder,tables,form,contents),
        }
    }

    fn query_context(&self)->AssignmentContext<'_> {
        match self.receipt {
            None => AssignmentContext::Search,
            Some(receipt) => AssignmentContext::Held {receipt,limits:&self.limits,work:&self.work},
        }
    }

    /// Adds `rows` visited rows to the table's work count and to the request's;
    /// the stop at either cap, at the form `form`, where the count is then past it.
    fn charge(&self, rows: u64, form: &NodePath) -> Result<(), Stop> {
        if let Some(stop)=self.failure.borrow().as_ref() {return Err(stop.clone());}
        self.materializer().check().and_then(|_|self.limits.request.charge(rows)).and_then(|_|self.work.charge(rows)).map_err(|bound| Stop { bound, form: form.clone() })
    }

    /// The extent of the frame of the column `index` of the table `named`, at its rows
    /// whose cells at the columns of `constraints` are the cells they pair them
    /// with, on `example` at the assignment `assignment`; none where the rows give
    /// two extents, where none matches, or where the table has more than one model at
    /// the assignment.
    fn extent_at(&self, named: &Named, index: usize, example: Option<Example>, constraints: &[(usize, TermId)], ctx: &Ctx<'_>) -> Option<Extent> {
        let table = self.tables.get((named.row as usize).checked_sub(EVIDENCE_FACTS.len())?)?;
        let contents = table.contents.as_ref().ok()?;
        let place = contents.examples.iter().position(|own| own.example == example).or_else(|| contents.examples.iter().position(|own| own.example.is_none()))?;
        let rows = contents.examples[place].rows.as_ref().ok()?;
        let mut result=Merged::Unset;
        let held=ctx.selected.borrow().get(&(named.row, place)).cloned();
        let selected=held.unwrap_or_else(|| {
            let selected:Rc<[usize]>=ctx.layout.select(ctx.ordinal,ctx.assignment,&contents.assignment_layout,rows).into();
            ctx.selected.borrow_mut().insert((named.row, place), Rc::clone(&selected));
            selected
        });
        for &at in selected.iter() {
            let [RelationValue::Rows(relation)] = &rows.at[at].1[..] else {return None};
            let fixed: Vec<usize> = constraints.iter().map(|&(column, _)| column).collect();
            let key = (named.row, place, at, index, fixed);
            let held = self.cache.borrow().get(&key).cloned();
            let lookup = match held {
                Some(held) => held,
                None => {
                    let built=match self.build(contents,place,at,relation,index,&key.4) {Ok(built)=>Rc::new(built),Err(stop)=>{*self.failure.borrow_mut()=Some(stop);return None;}};
                    self.cache.borrow_mut().insert(key, Rc::clone(&built));
                    built
                }
            };
            let cells: Box<[TermId]> = constraints.iter().map(|&(_, cell)| cell).collect();
            result.merge(lookup.get(&cells).and_then(Merged::extent));
        }
        result.extent()
    }

    /// The merged extent of the frame of the column `index` of the rows `relation` of
    /// the entry (`place`, `at`) of `contents`, by the cells of the columns `fixed`.
    fn build(&self, contents: &Contents, place: usize, at: usize, relation: &Relation, index: usize, fixed: &[usize]) -> Result<Materialized<StableHashMap<Box<[TermId]>, Merged>>,Stop> {
        let ty = contents.columns.get(index).map(|column| &column.ty);
        let held = match contents.extents.as_ref().and_then(|extents| extents.entry(place, at, 0)) {
            Some(EntryExtents::Rows(held)) => Some(held),
            _ => None,
        };
        let held_at = contents.extents.as_ref().and_then(|extents| extents.columns.iter().position(|&column| column as usize == index));
        let mut merged: StableHashMap<Box<[TermId]>, Merged> = StableHashMap::default();
        self.charge(relation.len(),&self.form)?;
        let materializer=self.materializer();
        let bytes=Materializer::row_bytes(fixed.len().saturating_mul(std::mem::size_of::<TermId>()).saturating_add(std::mem::size_of::<Merged>()),3);
        let allocation=materializer.admit(relation,bytes).map_err(|bound|Stop {bound,form:self.form.clone()})?;
        let mut row_at = 0u64;
        materializer.walk(relation, &mut |row| {
            let extent = match ty {
                Some(ValueType::Position) => position_extent(row[index], &ValueType::Position),
                _ => held.zip(held_at).and_then(|(held, column)| held.cell(row_at, column))
                    .or_else(|| contents.extents.as_ref()?.direct_at(contents, place, index, row)),
            };
            let key: Box<[TermId]> = fixed.iter().map(|&column| row[column]).collect();
            merged.entry(key).or_insert(Merged::Unset).merge(extent);
            row_at += 1;
        }).map_err(|bound|Stop {bound,form:self.form.clone()})?;
        Ok(Materialized::new(merged,allocation))
    }
}

/// The analysis of a widened body: the sources of the labels of its columns.
struct Analysis<'a> {
    decoder: &'a Decoder<'a>,
    registry: &'a Registry,
    checked:&'a CheckedProgram,
    sub: &'a BodyView,
    /// The type of each column of the body's relation.
    types: &'a [ValueType],
    /// The sources of each column ([`column_flows`]).
    sources: Vec<Vec<ColumnSource>>,
    reads: &'a Reads<'a>,
    /// The `DET`s of the relation the body gives rows of, as their relations are spelled.
    dets: &'a [String],
    keys: &'a [KeyEvidence],
}

#[path = "key_evidence.rs"]
mod key_evidence;
use key_evidence::{KeyEvidence, key_evidence};

/// The deepest chain of sizes that the extent of a frame follows.
const DEPTH: u8 = 16;

impl Analysis<'_> {
    /// The extent of the frame of the value at column `column` of `row`, a row
    /// of the body.
    fn extent_of(&self, column: usize, row: &[TermId], ctx: &Ctx<'_>, depth: u8) -> Option<Extent> {
        match self.types.get(column)? {
            ValueType::Position => position_extent(row[column], &ValueType::Position),
            ValueType::Box if depth < DEPTH => {
                let mut found: Option<Extent> = None;
                for source in &self.sources[column] {
                    if self.key_source_present(source,row,ctx)==Some(false) {continue;}
                    for frame in &source.frames {
                        let extent = match frame {
                            SourceFrame::Unknown => None,
                            SourceFrame::Made { maker, at, .. } => self.made_extent(maker, at, row, ctx, depth),
                            SourceFrame::Read => self.read_extent(source, row, ctx),
                        }?;
                        if *found.get_or_insert(extent) != extent {
                            return None;
                        }
                    }
                }
                found
            }
            _ => None,
        }
    }

    /// The extent of the frame that the lib column `maker` makes at the atom
    /// `at`: the own size of the value at the maker's `size` column of the atom,
    /// with its rows and columns swapped where the D4 element at the `by` column
    /// moves the top edge to the left or the right edge, plus the margins of the
    /// value at the maker's column.
    fn made_extent(&self, maker: &Maker, at: &NodePath, row: &[TermId], ctx: &Ctx<'_>, depth: u8) -> Option<Extent> {
        // A column of an output makes a frame in the output's table alone: a body reads it as a column of that table.
        let Maker::Relation { relation, column } = maker else { return None };
        let size = self.registry.frame_size(relation, column)?;
        let atom = atom_at(self.checked, at)?;
        if let Some(extent)=self.key_made_extent(at,site_label(atom,column)?,row,ctx) {return extent;}
        // The maker of a source read through an instance's input stands in that
        // input's body: its labels are of that scope, and no label id of this body
        // can stand for them.
        frame_context::node_at_path(&self.sub.clause,&self.sub.paths,at)?;
        let made =self.sub.column_of(site_label(atom, column)?)?;
        let sized = self.sub.column_of(site_label(atom, &size.column.column)?)?;
        let margins = margins_of(row[made], self.types.get(made)?)?;
        let (mut own_rows, mut own_columns) = self.own_size(sized, row, ctx, depth)?;
        if let Some(by) = &size.by {
            let element = self.sub.column_of(site_label(atom, &by.column)?)?;
            // A row whose `by` cell is no D4 element gives no extent.
            Geometry::get().each(Some(row[element]), &ValueType::D4).next()?;
            if matches!(Geometry::get().element(row[element]).image(Edge::Top), Edge::Left | Edge::Right) {
                (own_rows, own_columns) = (own_columns, own_rows);
            }
        }
        Extent::new(own_rows + margins.top + margins.bottom, own_columns + margins.left + margins.right)
    }

    /// The own size of the value at column `column` of `row`: (1, 1) for a
    /// Position, and for a Box the extent of its frame less its margins
    /// ([`fitted_size`]).
    fn own_size(&self, column: usize, row: &[TermId], ctx: &Ctx<'_>, depth: u8) -> Option<(i32, i32)> {
        match self.types.get(column)? {
            ValueType::Position => Some((1, 1)),
            ValueType::Box => {
                let extent = self.extent_of(column, row, ctx, depth + 1)?;
                fitted_size(extent, margins_of(row[column], &ValueType::Box)?)
            }
            _ => None,
        }
    }

    /// The extent of the frame of the column that `source` reads, in the latest
    /// earlier table of the relation it reads.
    fn read_extent(&self, source: &ColumnSource, row: &[TermId], ctx: &Ctx<'_>) -> Option<Extent> {
        if let Some(extent)=self.key_read_extent(source,row,ctx) {return extent;}
        let located = locate(&self.reads.names, self.dets, source);
        let named = located.table?;
        let index = read_index(&located, source)?;
        let frame = named.frames.get(index)?;
        // A global frame name can be unavailable while exact matching source
        // rows still carry an unambiguous native per-row extent.
        let example = self.read_example(source, row, ctx)?;
        if let Some(extent) = grid_extent(self.decoder, frame, example) { return Some(extent); }
        // A task-wide source can retain its Example in its native rows even
        // though it has no single outer example. Match the exact read arguments
        // and use that source column's proved row context, not an arbitrary E.
        let constraints = self.constraints(named, located.det, source, row)?;
        self.reads.extent_at(named, index, example, &constraints, ctx)
    }

    /// The arguments of the atom of `source` in the IR of the body, with the
    /// paths of the IR; none where the body does not compile.
    fn read_arguments(&self, source: &ColumnSource) -> Option<(&Arguments, &IrPaths)> {
        let (atom, paths) = frame_context::read_at(&self.sub.clause, &self.sub.paths, &source.atom)?;
        Some((&atom.arguments, paths))
    }

    /// The column of the body that the label of `argument` stands at, none for
    /// a term.
    fn argument_column(&self, argument: &Argument, paths: &IrPaths) -> Option<usize> {
        match frame_context::RowExample::from_argument(*argument, paths, |label| self.sub.column_of(label))? {
            frame_context::RowExample::Column(column) => Some(column),
            frame_context::RowExample::Constant(_) => None,
        }
    }

    /// The example that the read of `source` is on: the row's, or, where the
    /// atom reads its relation lifted over the examples, the one that the cell
    /// of its Example label holds. The outer none is a lifted read whose
    /// Example label holds no example.
    fn read_example(&self, source: &ColumnSource, row: &[TermId], ctx: &Ctx<'_>) -> Option<Option<Example>> {
        let (atom, paths) = frame_context::read_at(&self.sub.clause, &self.sub.paths, &source.atom)?;
        let argument = match frame_context::example_argument(self.checked, &source.atom, atom) {
            frame_context::ExampleArgument::Ambient => return Some(ctx.example),
            frame_context::ExampleArgument::Explicit(argument) => argument?,
        };
        frame_context::RowExample::from_argument(argument, paths, |label| self.sub.column_of(label))?.get(row).map(Some)
    }

    /// The cells of the columns of the table `named` that the atom of `source`
    /// fixes in `row`: each argument of the atom that stands on a label of the
    /// body, with the column of the table at its position, which is one less
    /// than the atom's where the atom reads its relation lifted over the
    /// examples and its first argument is the Example. None where the body does
    /// not compile.
    fn constraints(&self, named: &Named, det: i32, source: &ColumnSource, row: &[TermId]) -> Option<Vec<(usize, TermId)>> {
        let program = &self.checked.program;
        let lifted = program.reads_lifted(&source.atom);
        let (arguments, paths) = self.read_arguments(source)?;
        let Some(Resolution::Node(node)) = program.resolution(&source.atom) else { return None };
        let node_paths = program.row_paths(*node);
        let mut fixed = Vec::new();
        for (position, argument) in arguments.0.iter() {
            let Some(column) = self.argument_column(argument, paths) else { continue };
            let Some(crate::flows::SourceColumn::Position(position))=crate::flows::ReadCoordinates::new(false,lifted).source(position.0) else {continue};
            let position=usize::from(position);
            let held = match (&named.paths, node_paths.as_ref().and_then(|paths| paths.get(position))) {
                (Some(held), Some(path)) => held.iter().position(|own| own == path),
                (None, _) if det < 0 => Some(position),
                _ => None,
            };
            if let Some(held) = held {
                fixed.push((held, row[column]));
            }
        }
        Some(fixed)
    }
}

/// The extent of the frame of a value of type `ty` that is a Position: (top +
/// bottom + 1, left + right + 1).
pub(crate) fn position_extent(id: TermId, ty: &ValueType) -> Option<Extent> {
    let margins = margins_of(id, ty)?;
    Extent::new(margins.top + margins.bottom + 1, margins.left + margins.right + 1)
}

/// The own size of a Box of margins `margins` in a frame of extent `extent`:
/// the extent less the margins, none where that is below 1 on an axis, which is
/// where the value does not fit in the frame.
fn fitted_size(extent: Extent, margins: Margins) -> Option<(i32, i32)> {
    let own = Extent::new(extent.rows - margins.top - margins.bottom, extent.columns - margins.left - margins.right)?;
    Some((own.rows, own.columns))
}

fn margins_of(id: TermId, ty: &ValueType) -> Option<Margins> {
    match Term::decode(id, ty) {
        Term::Box(margins) => Some(margins),
        _ => None,
    }
}

/// The extent of the input grid, for the frame `input`, or the output grid, for
/// `output`, of `example`: none for a task-wide request and for a test example's
/// output.
fn grid_extent(decoder: &Decoder<'_>, frame: &str, example: Option<Example>) -> Option<Extent> {
    let example = example?;
    let (task, _, _) = decoder.evaluation_inputs();
    let grid = match frame {
        INPUT_FRAME => task.input(example),
        OUTPUT_FRAME => &task.train.get(usize::from(example.index()))?.output,
        _ => return None,
    };
    let rows = grid.rows();
    Extent::new(i32::try_from(rows.len()).ok()?, i32::try_from(rows.first()?.len()).ok()?)
}

/// The atom at `path` of `program`.
fn atom_at<'p>(program: &'p CheckedProgram, path: &NodePath) -> Option<&'p Atom> {
    match node_at(NodeRef::Program(program.program.program.value()), path)? {
        NodeRef::Conjunct(Conjunct::Atom(atom)) => Some(atom.value()),
        NodeRef::Atom(atom) => Some(atom),
        _ => None,
    }
}

/// The label at the site of `atom` on the column `column`, none where the atom
/// writes no site there or the site holds anything but one label.
fn site_label(atom: &Atom, column: &ColumnName) -> Option<LabelId> {
    single_label(atom.sites.iter().find(|site| site.column == *column)?)
}

/// The label that `site` holds alone.
fn single_label(site: &Site) -> Option<LabelId> {
    let [arg] = &site.value.args[..] else { return None };
    arg.label().and_then(use_label)
}
