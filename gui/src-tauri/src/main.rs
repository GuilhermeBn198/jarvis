#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

const LOOP_CMD: &str =
    "cd /home/guilherme/github/jarvis/voice && . .venv/bin/activate && \
     JARVIS_REQUIRE_GUI=1 python loop.py --voice";

#[tauri::command]
fn start_brain() -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        std::process::Command::new("wsl.exe")
            .args(["--", "bash", "-lc", LOOP_CMD])
            .creation_flags(0x08000000) // CREATE_NO_WINDOW
            .spawn()
            .map(|_| ())
            .map_err(|e| e.to_string())
    }
    #[cfg(not(windows))]
    {
        Err("start_brain so funciona no Windows".to_string())
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![start_brain])
        .run(tauri::generate_context!())
        .expect("error while running jarvis overlay");
}
