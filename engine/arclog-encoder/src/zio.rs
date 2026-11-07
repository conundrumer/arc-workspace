//! Generated data on disk. A path that ends in `.zst` is streamable zstd, and any other is plain.
//! A reader takes a path with or without the suffix, and reads whichever stands.

use std::io::{Read, Write};
use std::path::{Path, PathBuf};

const LEVEL: i32 = 3;

fn is_zstd(path: &Path) -> bool {
    path.extension().is_some_and(|extension| extension == "zst")
}

/// The file that stands for a path: the path itself, or the path with `.zst`.
fn standing(path: &Path) -> PathBuf {
    if path.exists() {
        return path.to_path_buf();
    }
    let mut with = path.as_os_str().to_os_string();
    with.push(".zst");
    let with = PathBuf::from(with);
    if with.exists() {
        with
    } else {
        path.to_path_buf()
    }
}

/// Whether a path stands, with or without `.zst`.
pub fn exists(path: impl AsRef<Path>) -> bool {
    standing(path.as_ref()).exists()
}

/// A file's bytes. A stream cut short gives what it holds up to the cut, so a run that stopped
/// leaves its finished records readable.
pub fn read_bytes(path: impl AsRef<Path>) -> Result<Vec<u8>, String> {
    let path = standing(path.as_ref());
    if !is_zstd(&path) {
        return std::fs::read(&path).map_err(|error| format!("{}: {error}", path.display()));
    }
    let file = std::fs::File::open(&path).map_err(|error| format!("{}: {error}", path.display()))?;
    let mut reader = zstd::stream::read::Decoder::new(file).map_err(|error| error.to_string())?;
    let mut out = Vec::new();
    let mut block = vec![0u8; 1 << 16];
    loop {
        match reader.read(&mut block) {
            Ok(0) => return Ok(out),
            Ok(count) => out.extend_from_slice(&block[..count]),
            Err(error) if out.is_empty() => return Err(format!("{}: {error}", path.display())),
            Err(_) => return Ok(out),
        }
    }
}

pub fn read_text(path: impl AsRef<Path>) -> Result<String, String> {
    String::from_utf8(read_bytes(path)?).map_err(|error| error.to_string())
}

/// A whole file, which stands only once it is complete.
pub fn write_bytes(path: impl AsRef<Path>, bytes: &[u8]) -> Result<(), String> {
    let path = path.as_ref();
    let mut temporary = path.as_os_str().to_os_string();
    temporary.push(".tmp");
    let temporary = PathBuf::from(temporary);
    if is_zstd(path) {
        let packed = zstd::stream::encode_all(bytes, LEVEL).map_err(|error| error.to_string())?;
        std::fs::write(&temporary, packed).map_err(|error| error.to_string())?;
    } else {
        std::fs::write(&temporary, bytes).map_err(|error| error.to_string())?;
    }
    std::fs::rename(&temporary, path).map_err(|error| error.to_string())
}

/// A file written by parts, which stands only once it is complete.
pub fn write_with(path: impl AsRef<Path>, write: impl FnOnce(&mut dyn std::io::Write) -> Result<(), String>) -> Result<(), String> {
    let path = path.as_ref();
    let mut temporary = path.as_os_str().to_os_string();
    temporary.push(".tmp");
    let temporary = PathBuf::from(temporary);
    let file = std::fs::File::create(&temporary).map_err(|error| error.to_string())?;
    if is_zstd(path) {
        let mut encoder = zstd::stream::write::Encoder::new(file, LEVEL).map_err(|error| error.to_string())?;
        write(&mut encoder)?;
        encoder.finish().map_err(|error| error.to_string())?;
    } else {
        let mut writer = std::io::BufWriter::new(file);
        write(&mut writer)?;
        std::io::Write::flush(&mut writer).map_err(|error| error.to_string())?;
    }
    std::fs::rename(&temporary, path).map_err(|error| error.to_string())
}

pub fn write_text(path: impl AsRef<Path>, text: &str) -> Result<(), String> {
    write_bytes(path, text.as_bytes())
}

/// A stream of records. `flush` puts what stands so far where a reader can read it, and each
/// run that appends adds a frame.
pub fn writer(path: impl AsRef<Path>, append: bool) -> Result<Box<dyn Write + Send>, String> {
    let path = path.as_ref();
    let file = if append { std::fs::OpenOptions::new().create(true).append(true).open(path) } else { std::fs::File::create(path) };
    let file = file.map_err(|error| format!("{}: {error}", path.display()))?;
    if is_zstd(path) {
        let encoder = zstd::stream::write::Encoder::new(file, LEVEL).map_err(|error| error.to_string())?;
        Ok(Box::new(encoder.auto_finish()))
    } else {
        Ok(Box::new(std::io::BufWriter::new(file)))
    }
}

/// A file's name with no `.zst` and no `.json`.
pub fn stem(path: impl AsRef<Path>) -> String {
    let name = path.as_ref().file_name().map(|name| name.to_string_lossy().to_string()).unwrap_or_default();
    let name = name.strip_suffix(".zst").unwrap_or(&name);
    name.strip_suffix(".json").unwrap_or(name).to_string()
}
