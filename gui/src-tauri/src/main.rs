#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Deserialize;

// Comando default do "cerebro". Pode ser sobrescrito por:
//   1) `JARVIS_LOOP_CMD` no build (`cargo build`), ou
//   2) `jarvis-config.json` ao lado do executavel (loop_cmd / distro).
const DEFAULT_LOOP_CMD: &str = match option_env!("JARVIS_LOOP_CMD") {
    Some(cmd) => cmd,
    None => "JARVIS_REQUIRE_GUI=1 /home/guilherme/github/jarvis/jarvis --voice",
};

#[derive(Debug, Default, Deserialize)]
struct OverlayConfig {
    loop_cmd: Option<String>,
    distro: Option<String>,
}

fn load_config(path: &std::path::Path) -> OverlayConfig {
    std::fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

fn config_path() -> std::path::PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("jarvis-config.json")))
        .unwrap_or_else(|| std::path::PathBuf::from("jarvis-config.json"))
}

#[tauri::command]
fn start_brain() -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let cfg = load_config(&config_path());
        let cmd = cfg.loop_cmd.unwrap_or_else(|| DEFAULT_LOOP_CMD.to_string());
        let mut command = std::process::Command::new("wsl.exe");
        if let Some(distro) = cfg.distro {
            command.args(["-d", &distro]);
        }
        command
            .args(["--", "bash", "-lc", &cmd])
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

#[tauri::command]
fn state_port() -> u16 {
    env!("JARVIS_STATE_PORT").parse().unwrap_or(8765)
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![start_brain, state_port])
        .run(tauri::generate_context!())
        .expect("error while running jarvis overlay");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn load_config_parses_fields() {
        let path = std::env::temp_dir().join("jarvis-config-test.json");
        std::fs::write(
            &path,
            r#"{"loop_cmd": "echo hi", "distro": "Ubuntu-22.04"}"#,
        )
        .unwrap();
        let cfg = load_config(&path);
        assert_eq!(cfg.loop_cmd.as_deref(), Some("echo hi"));
        assert_eq!(cfg.distro.as_deref(), Some("Ubuntu-22.04"));
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn load_config_defaults_on_missing_or_bad() {
        let missing = std::env::temp_dir().join("jarvis-config-does-not-exist.json");
        let cfg = load_config(&missing);
        assert!(cfg.loop_cmd.is_none());
        assert!(cfg.distro.is_none());

        let bad = std::env::temp_dir().join("jarvis-config-bad.json");
        std::fs::write(&bad, "not json").unwrap();
        let cfg = load_config(&bad);
        assert!(cfg.loop_cmd.is_none());
        let _ = std::fs::remove_file(&bad);
    }
}
