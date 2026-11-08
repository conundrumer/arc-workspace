//! The cells of an export that wait on disk, compressed, until Python reads them.
//!
//! A call that keeps the exports of several candidates at once (`successor_tables`)
//! keeps in memory the cells of its candidates up to the setting
//! `spill_resident_bytes`, and writes the cells of each later candidate to a file
//! of the call's folder as zstd frames. `CaseTables.values` of such a candidate reads
//! the file at each access and gives the cells it was given, byte for byte. The folder
//! stands under the folder a caller names, or under the system's temporary folder, and
//! it is removed with its files when the last result of the call that holds it drops.

use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

/// The cells of one zstd frame.
const FRAME_CELLS: usize = 1 << 22;

/// The zstd level of a frame: the cells of a table are runs of small numbers, which a fast level packs well.
const LEVEL: i32 = 1;

static FOLDERS: AtomicU64 = AtomicU64::new(0);

/// The folder of the spill files of one call. It is removed, with its files, when the last holder drops.
pub(crate) struct SpillFolder {
    path: PathBuf,
    files: AtomicU64,
}

impl SpillFolder {
    /// A new folder under `under`, or under the system's temporary folder where `under` is `None`.
    pub(crate) fn create(under: Option<&Path>) -> std::io::Result<Arc<SpillFolder>> {
        let base = under.map_or_else(std::env::temp_dir, Path::to_path_buf);
        let path = base.join(format!("arclog-spill-{}-{}", std::process::id(), FOLDERS.fetch_add(1, Ordering::Relaxed)));
        std::fs::create_dir_all(&path)?;
        Ok(Arc::new(SpillFolder { path, files: AtomicU64::new(0) }))
    }
}

impl Drop for SpillFolder {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.path);
    }
}

/// The cells of one export, in a file of a [`SpillFolder`].
pub(crate) struct Spilled {
    _folder: Arc<SpillFolder>,
    file: PathBuf,
    /// The stored bytes of each frame, in order.
    frames: Vec<u64>,
}

impl Spilled {
    /// Writes `cells` to a new file of `folder`.
    pub(crate) fn write(folder: &Arc<SpillFolder>, cells: &[i32]) -> std::io::Result<Spilled> {
        let file = folder.path.join(format!("{}.zst", folder.files.fetch_add(1, Ordering::Relaxed)));
        let mut writer = std::io::BufWriter::new(std::fs::File::create(&file)?);
        let mut frames = Vec::with_capacity(cells.len() / FRAME_CELLS + 1);
        let mut raw: Vec<u8> = Vec::with_capacity(FRAME_CELLS.min(cells.len()) * std::mem::size_of::<i32>());
        for chunk in cells.chunks(FRAME_CELLS) {
            raw.clear();
            for cell in chunk {
                raw.extend_from_slice(&cell.to_ne_bytes());
            }
            let packed = zstd::stream::encode_all(&raw[..], LEVEL)?;
            writer.write_all(&packed)?;
            frames.push(packed.len() as u64);
        }
        writer.flush()?;
        Ok(Spilled { _folder: Arc::clone(folder), file, frames })
    }

    /// The cells as native bytes, as they were given to [`Spilled::write`].
    pub(crate) fn read(&self) -> std::io::Result<Vec<u8>> {
        let mut reader = std::io::BufReader::new(std::fs::File::open(&self.file)?);
        let mut out = Vec::new();
        let mut packed = Vec::new();
        for &stored in &self.frames {
            packed.resize(usize::try_from(stored).map_err(std::io::Error::other)?, 0);
            reader.read_exact(&mut packed)?;
            out.extend_from_slice(&zstd::stream::decode_all(&packed[..])?);
        }
        Ok(out)
    }
}
