//! The path by which an edit, a diagnostic or the layout names a node.
//!
//! Implements `work/engine/reader.md`, Programs as values: "An edit names the
//! node it changes by its path: its form, and its index in the source order of
//! each list above it."

/// One step of a path: the index of a node in the source order of a list.
///
/// Implements `work/engine/reader.md`, Programs as values: "An edit names the node it changes by its path".
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct PathStep(pub u32);

/// The path of a node: the index of its top-level form, then its index in
/// the source order of each list below that form.
///
/// Implements `work/engine/reader.md`, Programs as values: "An edit names the node it changes by its path".
#[derive(Clone, PartialEq, Eq, Hash, Debug, Default)]
pub struct NodePath(pub Box<[PathStep]>);
