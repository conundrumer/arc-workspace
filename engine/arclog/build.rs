//! Gives the engine a hash of its sources and of the lib it embeds, which marks
//! the data that only this build can read: the verdicts of
//! `arclog::decode::atom_verdicts`.

use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::path::{Path, PathBuf};

fn files_under(dir: &Path, found: &mut Vec<PathBuf>) {
    let entries = std::fs::read_dir(dir).unwrap_or_else(|error| panic!("{}: {error}", dir.display()));
    for entry in entries {
        let path = entry.expect("an entry of the directory").path();
        if path.is_dir() {
            files_under(&path, found);
        } else {
            found.push(path);
        }
    }
}

fn main() {
    println!("cargo:rerun-if-changed=src");
    println!("cargo:rerun-if-changed=../lib");
    let mut files = Vec::new();
    files_under(Path::new("src"), &mut files);
    files_under(Path::new("../lib"), &mut files);
    files.sort();
    let mut hasher = DefaultHasher::new();
    for file in &files {
        file.hash(&mut hasher);
        std::fs::read(file).unwrap_or_else(|error| panic!("{}: {error}", file.display())).hash(&mut hasher);
    }
    println!("cargo:rustc-env=ARCLOG_SOURCES_HASH={:016x}", hasher.finish());
}
