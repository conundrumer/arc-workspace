//! The program relations of `work/feature-spec/feature-spec.md#program-relations`:
//! the program itself as data, for the QueryVector and the candidate block.

/// The names of the program relations.
pub const NAMES: [&str; 9] = ["query_kind", "query_atom", "query_reads", "query_computes", "column_type", "column_source", "column_frame", "column_lineage", "label_site"];

/// Whether `name` is a program relation.
pub fn is_program_relation(name: &str) -> bool {
    NAMES.contains(&name)
}
