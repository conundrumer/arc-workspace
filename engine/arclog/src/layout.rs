//! What a file holds beside its node values: places, label names, comments,
//! the elision of sites, and the strings.
//!
//! Implements `work/engine/reader.md`, Programs as values: "A node's places
//! in the files, the names of its labels, and its order of atoms and branches
//! are kept beside it, outside its hash, so the writer gives back the file's
//! bytes." and Solvers: "The tree keeps the comments and the strings". The
//! order of atoms and branches is the order of the node's lists, which its
//! canonical hash and its equality leave out, as [`crate::program`] gives.
//!
//! The reader fills a layout and the writer reads it. A synthesized program
//! has no layout, and the writer names its labels as
//! [`crate::write::write_synthesized`] gives.

#![allow(unused_variables, dead_code)]

use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::program::LabelId;

/// A file the s-expression reader reads: one of a solver's two files, or one
/// of the lib files under `engine/lib/`, as [`crate::registry`] gives.
///
/// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, the names of its labels, and its order of atoms and branches are kept beside it, outside its hash".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum SourceFile {
    Arclog,
    Arcdata,
    /// `engine/lib/registry.sexpr`.
    LibRegistry,
    /// `engine/lib/proposers.arclog`.
    LibProposers,
}

/// A place in a file: its byte span, and the line and column of its start,
/// both counted from 1.
///
/// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, the names of its labels, and its order of atoms and branches are kept beside it, outside its hash".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct SourcePlace {
    pub file: SourceFile,
    pub start: u32,
    pub end: u32,
    pub line: u32,
    pub column: u32,
}

/// A place in a solver's file, or in the file of the solver its
/// `representative` line names, which holds forms of its case programs: the
/// task id that names the file, or `None` for a lib file under
/// `engine/lib/`, and the place in it. A reader that reads one file gives
/// `None`, and [`crate::read::read_solver`] gives the solver's task id.
///
/// Implements `docs/arcdata.md`, Header: "The claims of a solver with a `representative` line belong to the representative's file", and `work/engine/reader.md`, Checker: "It reports each error once per place in the file".
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct FilePlace {
    pub task_id: Option<Box<str>>,
    pub place: SourcePlace,
}

/// A comment of a file, `;;` to the line's end, and where it stands.
///
/// Implements `work/engine/reader.md`, Solvers: "The tree keeps the comments and the strings".
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Comment {
    pub place: SourcePlace,
    pub text: Box<str>,
}

/// The layout of one node: where it stands, the names of the labels it
/// makes, and which of its sites the file elides.
///
/// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, the names of its labels, and its order of atoms and branches are kept beside it, outside its hash".
#[derive(Clone, Debug, Default)]
pub struct NodeLayout {
    pub place: Option<SourcePlace>,
    pub label_names: Box<[(LabelId, Box<str>)]>,
    /// The indexes of the node's sites that the file writes as the bare
    /// label, as `docs/arclog.md`, Sites, gives.
    pub elided_sites: Box<[u32]>,
}

/// The layout of a solver's two files. A node of the arclog file is keyed by
/// its path, as [`crate::program::path::node_at`] walks it, and a node of
/// the arcdata file by its path, as [`crate::program::path::data_node_at`]
/// walks it.
///
/// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, the names of its labels, and its order of atoms and branches are kept beside it, outside its hash".
#[derive(Clone, Debug, Default)]
pub struct Layout {
    pub nodes: StableHashMap<(SourceFile, NodePath), NodeLayout>,
    pub comments: Box<[Comment]>,
}

impl Layout {
    /// The layout of the node at `path` of `file`, if the file holds it.
    ///
    /// Implements `work/engine/reader.md`, Programs as values: "A node's places in the files, the names of its labels, and its order of atoms and branches are kept beside it, outside its hash".
    pub fn node(&self, file: SourceFile, path: &NodePath) -> Option<&NodeLayout> {
        todo!()
    }
}
