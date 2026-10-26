//! Computes `STREAMS_DIGEST`, which `streams_digest()` of the module gives: a
//! sha256 over every input of the compile of the crates that the streams
//! bindings and the module's init are built from, and over no file of the
//! tables crates.
//!
//! The crates are this one and the closure, over the path dependencies of
//! the manifests, of `arclog-bindings`. A crate of the tables export that
//! `arclog-bindings` came to depend on would enter the closure, and so the
//! digest. The inputs, hashed in sorted order of path, each as its path and
//! its bytes:
//!
//! - `engine/Cargo.toml`, `engine/Cargo.lock` and every file of `engine/lib/`;
//! - of each crate, its `Cargo.toml`, its `build.rs` where it has one, and
//!   every file of its `src/`.
//!
//! Then the output of `$RUSTC -vV`, and the values of `TARGET`, `PROFILE`,
//! `OPT_LEVEL`, `DEBUG`, `CARGO_ENCODED_RUSTFLAGS` and each `CARGO_FEATURE_*`,
//! `CARGO_CFG_*` and `CARGO_PROFILE_*` variable. No file of `tests/`,
//! `examples/` or `benches/` is hashed, since no package build compiles one.
//! The registry crates are fixed by the version and checksum in `Cargo.lock`.
//!
//! The script reruns where a hashed directory or file, or a variable it read,
//! changes.

use std::collections::BTreeSet;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use sha2::{Digest, Sha256};

/// The crate of the streams bindings, from this crate's directory.
const STREAMS_BINDINGS: &str = "../arclog-bindings";

/// The variables read by name.
const VARIABLES: [&str; 5] = ["TARGET", "PROFILE", "OPT_LEVEL", "DEBUG", "CARGO_ENCODED_RUSTFLAGS"];

/// The prefixes of the variables read by prefix.
const PREFIXES: [&str; 3] = ["CARGO_FEATURE_", "CARGO_CFG_", "CARGO_PROFILE_"];

fn main() {
    let this = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("cargo sets CARGO_MANIFEST_DIR"));
    let this = this.canonicalize().unwrap_or_else(|error| panic!("{} does not resolve: {error}", this.display()));
    let engine = this.parent().expect("the crate stands in the engine directory").to_path_buf();
    let mut crates = BTreeSet::from([this.clone()]);
    add_closure(&this.join(STREAMS_BINDINGS), &mut crates);

    let mut files = BTreeSet::from([engine.join("Cargo.toml"), engine.join("Cargo.lock")]);
    let mut directories = BTreeSet::from([engine.join("lib")]);
    for krate in &crates {
        files.insert(krate.join("Cargo.toml"));
        if krate.join("build.rs").is_file() {
            files.insert(krate.join("build.rs"));
        }
        directories.insert(krate.join("src"));
    }
    for directory in &directories {
        add_files(directory, &mut files);
    }

    let mut digest = Sha256::new();
    for file in &files {
        println!("cargo:rerun-if-changed={}", file.display());
        let name = file.strip_prefix(&engine).expect("a hashed file stands in the engine directory").to_string_lossy().replace('\\', "/");
        let bytes = fs::read(file).unwrap_or_else(|error| panic!("{} does not read: {error}", file.display()));
        digest.update(name.as_bytes());
        digest.update([0]);
        digest.update((bytes.len() as u64).to_le_bytes());
        digest.update(&bytes);
    }
    for directory in &directories {
        println!("cargo:rerun-if-changed={}", directory.display());
    }

    let rustc = env::var("RUSTC").expect("cargo sets RUSTC");
    println!("cargo:rerun-if-env-changed=RUSTC");
    let version = Command::new(&rustc).arg("-vV").output().unwrap_or_else(|error| panic!("{rustc} -vV does not run: {error}"));
    assert!(version.status.success(), "{rustc} -vV fails");
    digest.update(&version.stdout);
    let mut read: BTreeSet<String> = VARIABLES.iter().map(|name| name.to_string()).collect();
    read.extend(env::vars().map(|(name, _)| name).filter(|name| PREFIXES.iter().any(|prefix| name.starts_with(prefix))));
    for name in &read {
        println!("cargo:rerun-if-env-changed={name}");
        digest.update(format!("{name}={:?}\n", env::var(name).ok()).as_bytes());
    }

    let hex: String = digest.finalize().iter().map(|byte| format!("{byte:02x}")).collect();
    println!("cargo:rustc-env=STREAMS_DIGEST={hex}");
}

/// Adds the crate at `directory`, and each crate its manifest depends on by
/// path, as the manifests of those crates give them.
fn add_closure(directory: &Path, crates: &mut BTreeSet<PathBuf>) {
    let directory = directory.canonicalize().unwrap_or_else(|error| panic!("{} does not resolve: {error}", directory.display()));
    if !crates.insert(directory.clone()) {
        return;
    }
    let manifest = directory.join("Cargo.toml");
    let text = fs::read_to_string(&manifest).unwrap_or_else(|error| panic!("{} does not read: {error}", manifest.display()));
    for path in path_dependencies(&text) {
        add_closure(&directory.join(path), crates);
    }
}

/// The `path` of each dependency of a manifest's text that is a normal or a
/// build dependency, in the forms the engine's manifests use:
/// `name = { path = "..." }` under `[dependencies]` or `[build-dependencies]`,
/// and `path = "..."` under `[dependencies.name]`.
fn path_dependencies(manifest: &str) -> Vec<String> {
    let mut paths = Vec::new();
    let mut section = "";
    for line in manifest.lines().map(str::trim) {
        if let Some(header) = line.strip_prefix('[').and_then(|rest| rest.strip_suffix(']')) {
            section = header.trim();
        } else if is_dependency_section(section) && !line.starts_with('#') {
            if let Some(rest) = line.split("path = \"").nth(1) {
                paths.push(rest.split('"').next().expect("a split has a first part").to_string());
            }
        }
    }
    paths
}

/// Whether `section` of a manifest lists normal or build dependencies.
fn is_dependency_section(section: &str) -> bool {
    ["dependencies", "build-dependencies"].iter().any(|kind| section == *kind || section.starts_with(&format!("{kind}.")))
}

/// Adds each file below `directory`.
fn add_files(directory: &Path, files: &mut BTreeSet<PathBuf>) {
    let entries = fs::read_dir(directory).unwrap_or_else(|error| panic!("{} does not read: {error}", directory.display()));
    for entry in entries {
        let path = entry.unwrap_or_else(|error| panic!("{} does not list: {error}", directory.display())).path();
        if path.is_dir() {
            add_files(&path, files);
        } else {
            files.insert(path);
        }
    }
}
