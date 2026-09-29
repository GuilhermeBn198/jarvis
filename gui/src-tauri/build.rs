fn main() {
    let port = std::env::var("JARVIS_STATE_PORT").unwrap_or_else(|_| "8765".to_string());
    println!("cargo:rustc-env=JARVIS_STATE_PORT={port}");
    println!("cargo:rerun-if-env-changed=JARVIS_STATE_PORT");
    tauri_build::build()
}
