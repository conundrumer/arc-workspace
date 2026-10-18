//! The solvers a subcommand runs on: those its arguments name by task id,
//! and those a `uses.json` file gives for each `--reads` name.

use std::collections::BTreeSet;
use std::path::Path;

use serde_json::Value;

/// The task ids of the solvers to run, `None` for every solver: each of
/// `task_ids`, and each solver that the `uses.json` file at `uses` gives for
/// a name of `reads`, a lib name or a form keyword. Fails where `reads` is
/// not empty and that file does not read, or gives no solver for a name.
pub fn selected(task_ids: &[String], reads: &[String], uses: &Path) -> Result<Option<BTreeSet<String>>, String> {
    if task_ids.is_empty() && reads.is_empty() {
        return Ok(None);
    }
    let mut ids: BTreeSet<String> = task_ids.iter().cloned().collect();
    if !reads.is_empty() {
        let uses = read_json(uses)?;
        for name in reads {
            let stems = uses.get(name).and_then(Value::as_array).ok_or_else(|| format!("`uses.json` gives no solver for `{name}`"))?;
            ids.extend(stems.iter().filter_map(Value::as_str).map(str::to_owned));
        }
    }
    Ok(Some(ids))
}

/// The JSON of the file at `path`.
pub fn read_json(path: &Path) -> Result<Value, String> {
    let text = std::fs::read_to_string(path).map_err(|error| format!("{} does not read: {error}", path.display()))?;
    serde_json::from_str(&text).map_err(|error| format!("{} is no JSON: {error}", path.display()))
}
