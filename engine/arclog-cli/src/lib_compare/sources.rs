//! The digest of the Souffle sources a record was made from.
//!
//! A record gives, as `sources`, the digest of the Souffle sources it was
//! made from, and a record whose digest is not that of the present sources
//! is not compared. The digest is 64-bit FNV-1a, as 16 lowercase hex
//! digits, over each source in turn: its path from the root of the tree,
//! a 0 byte, its bytes and a 0 byte. The sources are `programs/lib.dl`,
//! each `.dl` file of `programs/lib/` in the byte order of their names,
//! and `work/arclog/libmap/__init__.py` of the main worktree.

use std::path::{Path, PathBuf};

/// The offset basis of 64-bit FNV-1a.
pub(super) const FNV_OFFSET_BASIS: u64 = 0xcbf2_9ce4_8422_2325;

/// 64-bit FNV-1a over `bytes`, from the state `state`.
pub(super) fn fnv1a(state: u64, bytes: impl IntoIterator<Item = u8>) -> u64 {
    bytes.into_iter().fold(state, |state, byte| (state ^ u64::from(byte)).wrapping_mul(0x0100_0000_01b3))
}

/// The digest of the present Souffle sources, as the module comment gives
/// it, or the fault that keeps a source from being read.
pub(super) fn sources_digest() -> Result<String, String> {
    let unread = |error: std::io::Error| format!("the Souffle sources programs/lib cannot be read: {error}");
    let mut names: Vec<String> = Vec::new();
    for entry in std::fs::read_dir("programs/lib").map_err(unread)? {
        let name = entry.map_err(unread)?.file_name();
        let name = name.into_string().map_err(|name| format!("programs/lib/{name:?} is no UTF-8 name"))?;
        if name.ends_with(".dl") {
            names.push(name);
        }
    }
    names.sort_by(|a, b| a.as_bytes().cmp(b.as_bytes()));
    let libmap = "work/arclog/libmap/__init__.py";
    let mut sources: Vec<(String, PathBuf)> = vec![("programs/lib.dl".to_owned(), PathBuf::from("programs/lib.dl"))];
    sources.extend(names.into_iter().map(|name| (format!("programs/lib/{name}"), Path::new("programs/lib").join(name))));
    sources.push((libmap.to_owned(), main_worktree()?.join(libmap)));
    let mut state = FNV_OFFSET_BASIS;
    for (shown, path) in sources {
        let bytes = std::fs::read(&path).map_err(|error| format!("the Souffle source {} cannot be read: {error}", path.display()))?;
        state = fnv1a(state, shown.bytes().chain([0]).chain(bytes).chain([0]));
    }
    Ok(format!("{state:016x}"))
}

/// The main worktree: the directory that holds the common git directory.
pub(super) fn main_worktree() -> Result<PathBuf, String> {
    let out = std::process::Command::new("git")
        .args(["rev-parse", "--path-format=absolute", "--git-common-dir"])
        .output()
        .map_err(|error| format!("git does not run: {error}"))?;
    if !out.status.success() {
        return Err(format!("git rev-parse fails: {}", String::from_utf8_lossy(&out.stderr).trim()));
    }
    let common = PathBuf::from(String::from_utf8_lossy(&out.stdout).trim());
    common.parent().map(Path::to_path_buf).ok_or_else(|| format!("{} has no parent", common.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The digest that `tests/parity/test_lib_digest.py` gives the same
    /// bytes, so that a record's digest is the one this command computes.
    #[test]
    fn fnv1a_gives_the_digest_of_the_python_side() {
        assert_eq!(format!("{:016x}", fnv1a(FNV_OFFSET_BASIS, *b"lib.dl\0souffle\0")), "b57d808609a766c8");
    }
}
