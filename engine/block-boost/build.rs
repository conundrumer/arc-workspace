// With the feature `gpu`, builds gpu/bbgpu.cu with nvcc into a static library and links it with the CUDA runtime.
use std::path::PathBuf;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=gpu/bbgpu.cu");
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-env-changed=BB_CUDA_ARCH");
    if std::env::var("CARGO_FEATURE_GPU").is_err() {
        return;
    }
    let out = PathBuf::from(std::env::var("OUT_DIR").unwrap());
    let cuda = std::env::var("CUDA_HOME").or_else(|_| std::env::var("CUDA_PATH")).unwrap_or_else(|_| "/usr/local/cuda".to_string());
    let nvcc = if PathBuf::from(&cuda).join("bin/nvcc").exists() { format!("{cuda}/bin/nvcc") } else { "nvcc".to_string() };
    // `native` is the card in this machine; BB_CUDA_ARCH=sm_89 (or another) names one.
    let arch = std::env::var("BB_CUDA_ARCH").unwrap_or_else(|_| "native".to_string());
    let object = out.join("bbgpu.o");
    let status = Command::new(&nvcc)
        .args(["-O3", "-std=c++17", "--compiler-options", "-fPIC", &format!("-arch={arch}"), "-lineinfo", "-c", "gpu/bbgpu.cu", "-o"])
        .arg(&object)
        .status()
        .unwrap_or_else(|e| panic!("{nvcc}: {e}"));
    assert!(status.success(), "nvcc failed");
    let library = out.join("libbbgpu.a");
    let _ = std::fs::remove_file(&library);
    let status = Command::new("ar").arg("crs").arg(&library).arg(&object).status().expect("ar");
    assert!(status.success(), "ar failed");
    println!("cargo:rustc-link-search=native={}", out.display());
    println!("cargo:rustc-link-search=native={cuda}/lib64");
    println!("cargo:rustc-link-search=native={cuda}/targets/x86_64-linux/lib");
    println!("cargo:rustc-link-lib=static=bbgpu");
    println!("cargo:rustc-link-lib=static=cudart_static");
    println!("cargo:rustc-link-lib=dylib=stdc++");
    println!("cargo:rustc-link-lib=dylib=dl");
    println!("cargo:rustc-link-lib=dylib=rt");
    println!("cargo:rustc-link-lib=dylib=pthread");
}
