//! `check-diff`: compares the engine checker's diagnostics on each solver
//! given, or on every solver of the corpus, with the diagnostics of a base
//! engine, and prints each line that only one side gives, by solver, and
//! each solver whose check does not finish within the bound.
//!
//! Its arguments: the corpus directory, then the task ids of the solvers to
//! check, `--reads <name>` for the solvers that `.cache/parity/uses.json` of
//! the main worktree gives for a lib name or a form keyword, and `--base
//! <rev>` for the base engine, `git merge-base HEAD master` where it is not
//! given. It builds `check_one` of the checkout under check before it
//! hashes that checkout's sources, so each current result is computed by
//! the sources its key hashes.
//!
//! Each check runs `check_one` in a child process whose CPU time is limited
//! to [`BOUND_SECONDS`], and its result is stored in `.cache/check-diff/`
//! of the main worktree, under the key of the engine's sources and the key
//! of the solver's files. A run starts no check whose result is stored at
//! its keys, and two runs that overlap in time start one check for each
//! result, by a lock file beside it. The base engine is `git archive` of
//! the base's `engine/`, with `check_one.rs` of the checkout under check
//! copied in, built once for each key in `.cache/check-diff/engines/`.

use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};
use std::hash::Hasher;
use std::io::{Read, Write};
use std::os::unix::process::ExitStatusExt;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::Instant;

use arclog::harness::{corpus_solvers, read_corpus_solver, CorpusSolver};
use arclog::hash::StableHasher;
use arclog::read::read_solver;
use serde_json::{json, Value};

use crate::select::{read_json, selected};

const USAGE: &str = "usage: arclog-cli check-diff <corpus-dir> [<task_id> ...] [--reads <name> ...] [--base <rev>]";

/// The limit on the CPU time of each check. The engine key hashes it, so a
/// result stored as unfinished is the result of its keys.
const BOUND_SECONDS: u64 = 30;

/// The cargo profile `check_one` builds under: the release profile's
/// optimization, with incremental compilation, so a rebuild after an edit
/// compiles again only what the edit changed.
const PROFILE: &str = "tool";

/// The `--config` settings that define [`PROFILE`]. They stand here, not in
/// a manifest, so a base engine whose manifest lacks the profile builds
/// under it too. The engine key hashes them, as the code the profile
/// generates bears on which checks reach [`BOUND_SECONDS`].
fn profile_config() -> [String; 2] {
    [format!("profile.{PROFILE}.inherits=\"release\""), format!("profile.{PROFILE}.incremental=true")]
}

/// The file of the checker's binary, from the root of a checkout.
const CHECK_ONE: &str = "engine/arclog-cli/src/bin/check_one.rs";

/// The manifest of `arclog-cli`, from the root of a checkout.
const MANIFEST: &str = "engine/arclog-cli/Cargo.toml";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    let Some(arguments) = Arguments::parse(args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    match check_diff(&arguments) {
        Ok(report) => report.print(),
        Err(message) => {
            eprintln!("{message}");
            ExitCode::from(2)
        }
    }
}

/// The arguments of the subcommand.
struct Arguments {
    corpus: PathBuf,
    task_ids: Vec<String>,
    reads: Vec<String>,
    base: Option<String>,
}

impl Arguments {
    fn parse(args: &[String]) -> Option<Arguments> {
        let (mut positional, mut reads, mut base) = (Vec::new(), Vec::new(), None);
        let mut args = args.iter();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--reads" => reads.push(args.next()?.clone()),
                "--base" => base = Some(args.next()?.clone()),
                _ => positional.push(arg.clone()),
            }
        }
        let mut positional = positional.into_iter();
        let corpus = positional.next()?.into();
        Some(Arguments { corpus, task_ids: positional.collect(), reads, base })
    }
}

/// The result of the check of one solver on one engine.
#[derive(Clone, PartialEq, Debug)]
enum Outcome {
    /// Each line `check_one` printed, and the seconds the check took.
    Checked { lines: Vec<String>, seconds: f64 },
    /// The first line of the child's stderr.
    Panicked(String),
    /// The check reached [`BOUND_SECONDS`].
    Unfinished,
}

impl Outcome {
    fn to_json(&self) -> Value {
        match self {
            Outcome::Checked { lines, seconds } => json!({"checked": {"lines": lines, "seconds": seconds}}),
            Outcome::Panicked(line) => json!({"panicked": line}),
            Outcome::Unfinished => json!({"unfinished": {}}),
        }
    }

    fn from_json(value: &Value) -> Option<Outcome> {
        if let Some(checked) = value.get("checked") {
            let lines = checked.get("lines")?.as_array()?.iter().map(|l| l.as_str().map(str::to_owned)).collect::<Option<_>>()?;
            return Some(Outcome::Checked { lines, seconds: checked.get("seconds")?.as_f64()? });
        }
        if let Some(line) = value.get("panicked") {
            return Some(Outcome::Panicked(line.as_str()?.to_owned()));
        }
        value.get("unfinished").map(|_| Outcome::Unfinished)
    }

    /// The lines the comparison of two sides compares.
    fn lines(&self) -> BTreeSet<String> {
        match self {
            Outcome::Checked { lines, .. } => lines.iter().cloned().collect(),
            Outcome::Panicked(line) => BTreeSet::from([format!("panicked: {line}")]),
            Outcome::Unfinished => BTreeSet::new(),
        }
    }
}

/// The side of a comparison.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Side {
    Base,
    Current,
}

impl Side {
    const BOTH: [Side; 2] = [Side::Base, Side::Current];

    fn name(self) -> &'static str {
        match self {
            Side::Base => "base",
            Side::Current => "current",
        }
    }
}

/// The `check_one` of an engine: the one of the checkout under check, or the one
/// of a base engine, built the first time a check needs it.
enum Binary {
    Current(PathBuf),
    Base { root: PathBuf, rev: String, dir: PathBuf, built: OnceLock<Result<PathBuf, String>> },
}

impl Binary {
    fn path(&self) -> Result<PathBuf, String> {
        match self {
            Binary::Current(path) => Ok(path.clone()),
            Binary::Base { root, rev, dir, built } => built.get_or_init(|| build_base(root, rev, dir)).clone(),
        }
    }
}

/// An engine a side's checks run on.
struct Engine {
    key: String,
    binary: Binary,
}

/// The two sides' results on each selected solver, and how many checks the
/// run started.
struct Report {
    outcomes: Vec<(String, [Outcome; 2])>,
    run: usize,
    stored: usize,
}

impl Report {
    fn print(&self) -> ExitCode {
        let (mut differing, mut unfinished) = (0, 0);
        for (task_id, [base, current]) in &self.outcomes {
            let sides = Side::BOTH.into_iter().zip([base, current]);
            let reached: Vec<&str> = sides.filter(|(_, o)| **o == Outcome::Unfinished).map(|(side, _)| side.name()).collect();
            if !reached.is_empty() {
                unfinished += 1;
                println!("{task_id}: unfinished at the bound of {BOUND_SECONDS} s on the {} side", reached.join(" and "));
                continue;
            }
            let (base, current) = (base.lines(), current.lines());
            if base == current {
                continue;
            }
            differing += 1;
            for line in base.difference(&current) {
                println!("{task_id}: - {line}");
            }
            for line in current.difference(&base) {
                println!("{task_id}: + {line}");
            }
        }
        println!(
            "{} solvers compared, {differing} differ, {unfinished} unfinished; {} checks run, {} taken from the store",
            self.outcomes.len(),
            self.run,
            self.stored
        );
        if differing == 0 && unfinished == 0 { ExitCode::SUCCESS } else { ExitCode::FAILURE }
    }
}

fn check_diff(arguments: &Arguments) -> Result<Report, String> {
    let root = checkout();
    let store = main_worktree(&root)?.join(".cache");
    let ids = selected(&arguments.task_ids, &arguments.reads, &store.join("parity/uses.json"))?;
    let store = store.join("check-diff");
    let solvers: Vec<CorpusSolver> = corpus_solvers(&arguments.corpus)
        .map_err(|error| format!("the corpus does not read: {error:?}"))?
        .into_iter()
        .filter(|solver| ids.as_ref().is_none_or(|ids| ids.contains(&solver.task_id)))
        .collect();
    if let Some(ids) = &ids {
        let found: BTreeSet<&String> = solvers.iter().map(|s| &s.task_id).collect();
        if let Some(missing) = ids.iter().find(|id| !found.contains(id)) {
            return Err(format!("the corpus has no solver {missing}"));
        }
    }
    let toolchain = [output(Command::new("rustc").arg("-vV"))?, profile_config().concat().into_bytes()].concat();
    let rev = match &arguments.base {
        Some(rev) => rev.clone(),
        None => String::from_utf8_lossy(&git(&root, &["merge-base", "HEAD", "master"])?).trim().to_owned(),
    };
    let check_one = build_check_one(&root.join("engine"))?;
    let current = Engine { key: key_of(&current_files(&root)?, &toolchain), binary: Binary::Current(check_one) };
    let base_key = key_of(&base_files(&root, &rev)?, &toolchain);
    let dir = store.join("engines").join(&base_key);
    let base = Engine { key: base_key, binary: Binary::Base { root, rev, dir, built: OnceLock::new() } };
    let engines = [base, current];
    let solver_keys: Vec<String> = solvers.iter().map(|s| key_of(&solver_files(&arguments.corpus, &s.task_id), &[])).collect();

    let jobs: Vec<(usize, usize)> = (0..solvers.len()).flat_map(|s| [(s, 0), (s, 1)]).collect();
    let next = AtomicUsize::new(0);
    let results = Mutex::new(BTreeMap::new());
    let threads = std::thread::available_parallelism().map_or(1, |n| n.get());
    std::thread::scope(|scope| {
        for _ in 0..threads {
            scope.spawn(|| {
                while let Some(&(s, e)) = jobs.get(next.fetch_add(1, Ordering::Relaxed)) {
                    let result = settle(&store, &engines[e], &arguments.corpus, &solvers[s].task_id, &solver_keys[s]);
                    results.lock().expect("no worker panics").insert((s, e), result);
                }
            });
        }
    });
    let mut results = results.into_inner().expect("no worker panics");
    let (mut run, mut stored) = (0, 0);
    let mut outcomes = Vec::new();
    for (s, solver) in solvers.iter().enumerate() {
        let mut side = |e: usize| -> Result<Outcome, String> {
            let (outcome, ran) = results.remove(&(s, e)).expect("each job gives a result")?;
            if ran { run += 1 } else { stored += 1 }
            Ok(outcome)
        };
        outcomes.push((solver.task_id.clone(), [side(0)?, side(1)?]));
    }
    Ok(Report { outcomes, run, stored })
}

/// The result of the check of `task_id` on `engine`, and whether this run
/// computed it: the stored one where the store holds one, and otherwise the
/// one a check computes, once it holds the lock beside it.
fn settle(store: &Path, engine: &Engine, corpus: &Path, task_id: &str, solver_key: &str) -> Result<(Outcome, bool), String> {
    let dir = store.join("results").join(&engine.key);
    let result = dir.join(format!("{task_id}.{solver_key}.json"));
    if let Some(outcome) = stored(&result)? {
        return Ok((outcome, false));
    }
    std::fs::create_dir_all(&dir).map_err(|error| format!("{} cannot be made: {error}", dir.display()))?;
    let lock_path = dir.join(format!("{task_id}.{solver_key}.lock"));
    let lock = std::fs::File::options()
        .create(true)
        .truncate(false)
        .write(true)
        .open(&lock_path)
        .map_err(|error| format!("{} does not open: {error}", lock_path.display()))?;
    lock.lock().map_err(|error| format!("{} does not lock: {error}", lock_path.display()))?;
    if let Some(outcome) = stored(&result)? {
        return Ok((outcome, false));
    }
    let outcome = check(&engine.binary.path()?, corpus, task_id)?;
    write_whole(&result, serde_json::to_string(&outcome.to_json()).expect("an outcome writes as JSON").as_bytes())?;
    drop(lock);
    Ok((outcome, true))
}

/// The result stored at `path`, `None` where none stands.
fn stored(path: &Path) -> Result<Option<Outcome>, String> {
    if !path.exists() {
        return Ok(None);
    }
    Outcome::from_json(&read_json(path)?).map(Some).ok_or_else(|| format!("{} holds no result", path.display()))
}

/// Writes `bytes` to `path` by a rename from a temporary name in its
/// directory, so a reader finds no file or the whole file.
fn write_whole(path: &Path, bytes: &[u8]) -> Result<(), String> {
    static COUNT: AtomicUsize = AtomicUsize::new(0);
    let name = path.file_name().expect("a result path names a file").to_string_lossy();
    let temporary = path.with_file_name(format!(".{name}.{}.{}", std::process::id(), COUNT.fetch_add(1, Ordering::Relaxed)));
    std::fs::write(&temporary, bytes).map_err(|error| format!("{} cannot be written: {error}", temporary.display()))?;
    std::fs::rename(&temporary, path).map_err(|error| format!("{} cannot be written: {error}", path.display()))
}

/// The check of `task_id` by the `check_one` at `binary`, in a child
/// process whose CPU time is limited to [`BOUND_SECONDS`].
fn check(binary: &Path, corpus: &Path, task_id: &str) -> Result<Outcome, String> {
    const SIGKILL: i32 = 9;
    const SIGXCPU: i32 = 24;
    let start = Instant::now();
    let child = Command::new("sh")
        .arg("-c")
        .arg(format!("ulimit -t {BOUND_SECONDS}; exec nice -n 19 \"$0\" \"$@\""))
        .arg(binary)
        .arg(corpus)
        .arg(task_id)
        .stdin(Stdio::null())
        .output()
        .map_err(|error| format!("{} does not start: {error}", binary.display()))?;
    let seconds = start.elapsed().as_secs_f64();
    let text = |bytes: &[u8]| String::from_utf8_lossy(bytes).into_owned();
    match (child.status.code(), child.status.signal()) {
        (Some(0), _) => Ok(Outcome::Checked { lines: text(&child.stdout).lines().map(str::to_owned).collect(), seconds }),
        (_, Some(SIGXCPU | SIGKILL)) => Ok(Outcome::Unfinished),
        (Some(_), _) => {
            let stderr = text(&child.stderr);
            Ok(Outcome::Panicked(stderr.lines().find(|l| !l.is_empty()).unwrap_or("the check wrote nothing to stderr").to_owned()))
        }
        (None, signal) => Err(format!("the check of {task_id} ended by the signal {signal:?}")),
    }
}

/// The root of the checkout this executable was built from.
fn checkout() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}

/// The main worktree of the repository of `root`, which holds `.cache/`
/// for every worktree.
fn main_worktree(root: &Path) -> Result<PathBuf, String> {
    let common = git(root, &["rev-parse", "--path-format=absolute", "--git-common-dir"])?;
    let common = PathBuf::from(String::from_utf8_lossy(&common).trim());
    common.parent().map(Path::to_owned).ok_or_else(|| format!("{} has no parent", common.display()))
}

/// The stdout of `git` with `args` in `root`.
fn git(root: &Path, args: &[&str]) -> Result<Vec<u8>, String> {
    output(Command::new("git").arg("-C").arg(root).args(args))
}

/// The stdout of `command`, which must succeed.
fn output(command: &mut Command) -> Result<Vec<u8>, String> {
    let out = command.stderr(Stdio::inherit()).output().map_err(|error| format!("{command:?} does not start: {error}"))?;
    if !out.status.success() {
        return Err(format!("{command:?} fails: {}", out.status));
    }
    Ok(out.stdout)
}

/// The files of a key: each path, and its bytes, `None` where it stands in
/// no file.
type Files = BTreeMap<String, Option<Vec<u8>>>;

/// The key of `files` and `rest`, with [`BOUND_SECONDS`]: the hex of their
/// [`StableHasher`] hash, each path and its bytes in path order.
fn key_of(files: &Files, rest: &[u8]) -> String {
    let mut hasher = StableHasher::new();
    for (path, bytes) in files {
        hasher.write_usize(path.len());
        hasher.write(path.as_bytes());
        match bytes {
            Some(bytes) => {
                hasher.write_u8(1);
                hasher.write_usize(bytes.len());
                hasher.write(bytes);
            }
            None => hasher.write_u8(0),
        }
    }
    hasher.write_usize(rest.len());
    hasher.write(rest);
    hasher.write_u64(BOUND_SECONDS);
    format!("{:032x}", hasher.finish128().0)
}

/// The engine's files of the checkout at `root`: each file under `engine/`
/// that git tracks or does not ignore, less `arclog-cli` but its manifest
/// and `check_one.rs`, where it stands.
fn current_files(root: &Path) -> Result<Files, String> {
    let listed = git(root, &["ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "engine", ":!engine/arclog-cli"])?;
    let paths = listed.split(|b| *b == 0).filter(|p| !p.is_empty()).map(|p| String::from_utf8_lossy(p).into_owned());
    let mut files = Files::new();
    for path in paths.chain([MANIFEST.to_owned(), CHECK_ONE.to_owned()]) {
        if let Ok(bytes) = std::fs::read(root.join(&path)) {
            files.insert(path, Some(bytes));
        }
    }
    Ok(files)
}

/// The engine's files of the commit `rev`, as [`current_files`] gives them,
/// with `check_one.rs` of the checkout at `root`, which the base build runs.
fn base_files(root: &Path, rev: &str) -> Result<Files, String> {
    let listed = git(root, &["ls-tree", "-r", "-z", rev, "--", "engine"])?;
    let mut blobs = Vec::new();
    for entry in listed.split(|b| *b == 0).filter(|e| !e.is_empty()) {
        let entry = String::from_utf8_lossy(entry);
        let Some((meta, path)) = entry.split_once('\t') else { return Err(format!("`git ls-tree` gives the entry {entry}")) };
        let [_, kind, object] = meta.split(' ').collect::<Vec<_>>()[..] else { return Err(format!("`git ls-tree` gives the entry {entry}")) };
        if kind == "blob" && (!path.starts_with("engine/arclog-cli/") || path == MANIFEST) {
            blobs.push((path.to_owned(), object.to_owned()));
        }
    }
    let mut files: Files = blobs.iter().map(|(path, _)| path.clone()).zip(cat_blobs(root, blobs.iter().map(|(_, o)| o.as_str()))?.into_iter().map(Some)).collect();
    let check_one = root.join(CHECK_ONE);
    let bytes = std::fs::read(&check_one).map_err(|error| format!("{} does not read: {error}", check_one.display()))?;
    files.insert(CHECK_ONE.to_owned(), Some(bytes));
    Ok(files)
}

/// The bytes of each blob of `objects`, in their order, by `git cat-file
/// --batch`.
fn cat_blobs<'o>(root: &Path, objects: impl Iterator<Item = &'o str>) -> Result<Vec<Vec<u8>>, String> {
    let input: String = objects.map(|o| format!("{o}\n")).collect();
    let mut child = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(["cat-file", "--batch"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .map_err(|error| format!("`git cat-file` does not start: {error}"))?;
    let mut stdin = child.stdin.take().expect("stdin is piped");
    let writer = std::thread::spawn(move || stdin.write_all(input.as_bytes()));
    let mut out = Vec::new();
    child.stdout.take().expect("stdout is piped").read_to_end(&mut out).map_err(|error| format!("`git cat-file` does not read: {error}"))?;
    let _ = writer.join();
    child.wait().map_err(|error| format!("`git cat-file` fails: {error}"))?;
    let mut blobs = Vec::new();
    let mut rest = &out[..];
    while !rest.is_empty() {
        let end = rest.iter().position(|b| *b == b'\n').ok_or("`git cat-file` gives a header with no end")?;
        let header = String::from_utf8_lossy(&rest[..end]).into_owned();
        let size: usize = header.rsplit(' ').next().and_then(|s| s.parse().ok()).ok_or_else(|| format!("`git cat-file` gives the header {header}"))?;
        let body = rest.get(end + 1..end + 1 + size).ok_or("`git cat-file` gives a short blob")?;
        blobs.push(body.to_vec());
        rest = rest.get(end + 2 + size..).unwrap_or(&[]);
    }
    Ok(blobs)
}

/// The files the read of `task_id` opens: its own two files and those of
/// each solver a `representative` line names, by the callback the read
/// takes.
fn solver_files(corpus: &Path, task_id: &str) -> Files {
    let mut files = Files::new();
    let mut seen = BTreeSet::new();
    let mut pending = vec![task_id.to_owned()];
    while let Some(id) = pending.pop() {
        if !seen.insert(id.clone()) {
            continue;
        }
        let file = |extension: &str| std::fs::read_to_string(corpus.join(format!("{id}.{extension}"))).ok();
        let (arclog, arcdata) = (file("arclog"), file("arcdata"));
        if let (Some(arclog), Some(arcdata)) = (&arclog, &arcdata) {
            let named = RefCell::new(Vec::new());
            let _ = read_solver(&id, arclog, arcdata, &|other| {
                named.borrow_mut().push(other.to_owned());
                read_corpus_solver(corpus, other)
            });
            pending.extend(named.into_inner());
        }
        files.insert(format!("{id}.arclog"), arclog.map(String::into_bytes));
        files.insert(format!("{id}.arcdata"), arcdata.map(String::into_bytes));
    }
    files
}

/// The `check_one` of the base engine at `rev`, built in `dir`, which is
/// made from `git archive` of `engine/` at `rev` where it does not stand.
fn build_base(root: &Path, rev: &str, dir: &Path) -> Result<PathBuf, String> {
    if !dir.exists() {
        let engines = dir.parent().expect("an engine's directory stands in `engines/`");
        let temporary = engines.join(format!(".{}", std::process::id()));
        std::fs::create_dir_all(&temporary).map_err(|error| format!("{} cannot be made: {error}", temporary.display()))?;
        let mut archive = Command::new("git")
            .arg("-C")
            .arg(root)
            .args(["archive", rev, "engine"])
            .stdout(Stdio::piped())
            .spawn()
            .map_err(|error| format!("`git archive` does not start: {error}"))?;
        let stdout = archive.stdout.take().expect("stdout is piped");
        output(Command::new("tar").arg("-x").arg("-C").arg(&temporary).stdin(stdout))?;
        if !archive.wait().is_ok_and(|status| status.success()) {
            return Err(format!("`git archive {rev} engine` fails"));
        }
        let bin = temporary.join("engine/arclog-cli/src/bin");
        std::fs::create_dir_all(&bin).map_err(|error| format!("{} cannot be made: {error}", bin.display()))?;
        std::fs::copy(root.join(CHECK_ONE), bin.join("check_one.rs")).map_err(|error| format!("{CHECK_ONE} cannot be copied: {error}"))?;
        if std::fs::rename(&temporary, dir).is_err() && dir.exists() {
            let _ = std::fs::remove_dir_all(&temporary);
        }
    }
    build_check_one(&dir.join("engine")).map_err(|error| format!("the base engine at {rev}: {error}"))
}

/// The `check_one` of the engine workspace `engine`, once `cargo build`
/// under [`PROFILE`] has built it there.
fn build_check_one(engine: &Path) -> Result<PathBuf, String> {
    let built = Command::new("cargo")
        .arg("build")
        .args(profile_config().iter().flat_map(|setting| ["--config", setting]))
        .args(["--profile", PROFILE, "-p", "arclog-cli", "--bin", "check_one"])
        .current_dir(engine)
        .stdout(Stdio::null())
        .status()
        .map_err(|error| format!("`cargo build` does not start: {error}"))?;
    if !built.success() {
        return Err(format!("`check_one` does not build in {}", engine.display()));
    }
    Ok(engine.join("target").join(PROFILE).join("check_one"))
}

#[cfg(test)]
mod tests {
    use super::{key_of, solver_files};

    /// A solver's key changes when a file of the solver its
    /// `representative` line names changes, so its stored result is
    /// computed again.
    #[test]
    fn a_representative_file_moves_the_solver_key() {
        let corpus = std::env::temp_dir().join(format!("check-diff-test-{}", std::process::id()));
        std::fs::create_dir_all(&corpus).unwrap();
        let write = |name: &str, text: &str| std::fs::write(corpus.join(name), text).unwrap();
        write("aaaaaaaa.arclog", "");
        write("aaaaaaaa.arcdata", "(representative bbbbbbbb)\n");
        write("bbbbbbbb.arclog", "");
        write("bbbbbbbb.arcdata", "");
        let key = || key_of(&solver_files(&corpus, "aaaaaaaa"), &[]);
        let before = key();
        write("bbbbbbbb.arclog", "; a comment\n");
        let after = key();
        std::fs::remove_dir_all(&corpus).unwrap();
        assert_ne!(before, after);
    }
}
