//! The arguments that `compare` and `speed` take.

use std::path::PathBuf;

/// The arguments of `compare` and `speed`: the snapshot's directory, the
/// corpus directory, the directory of the task files, the task ids, and the
/// names given after each `--reads`.
pub(crate) struct Arguments {
    pub(crate) snapshot: PathBuf,
    pub(crate) corpus: PathBuf,
    pub(crate) tasks: PathBuf,
    pub(crate) task_ids: Vec<String>,
    pub(crate) reads: Vec<String>,
}

impl Arguments {
    /// The arguments `args` give, `None` where they give fewer than three
    /// directories or a `--reads` with no name after it.
    pub(crate) fn parse(args: &[String]) -> Option<Arguments> {
        let mut positional = Vec::new();
        let mut reads = Vec::new();
        let mut args = args.iter();
        while let Some(arg) = args.next() {
            if arg == "--reads" {
                reads.push(args.next()?.clone());
            } else {
                positional.push(arg.clone());
            }
        }
        let mut positional = positional.into_iter();
        let (snapshot, corpus, tasks) = (positional.next()?, positional.next()?, positional.next()?);
        Some(Arguments { snapshot: snapshot.into(), corpus: corpus.into(), tasks: tasks.into(), task_ids: positional.collect(), reads })
    }
}
