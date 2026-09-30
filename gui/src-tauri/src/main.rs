#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Deserialize;
use std::sync::Mutex;
use tauri::Manager;

// Comando default do "cerebro". Pode ser sobrescrito por:
//   1) `JARVIS_LOOP_CMD` no build (`cargo build`), ou
//   2) `jarvis-config.json` ao lado do executavel (loop_cmd / distro).
const DEFAULT_LOOP_CMD: &str = match option_env!("JARVIS_LOOP_CMD") {
    Some(cmd) => cmd,
    None => "JARVIS_REQUIRE_GUI=1 /home/guilherme/github/jarvis/jarvis --voice",
};

/// Handle do processo `wsl.exe` que roda o cerebro.
///
/// Sem isso o overlay nao tinha como encerrar o cerebro ao sair: o `wsl.exe`
/// ficava orfao e o loop continuava "escutando eternamente" no WSL.
#[derive(Default)]
struct Brain(Mutex<Option<std::process::Child>>);

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

/// `%LOCALAPPDATA%\jarvis\brain.log` (fallback: tempdir). Cria o diretorio.
///
/// O overlay sobe o cerebro com CREATE_NO_WINDOW, entao stdout/stderr eram
/// descartados; sem eles nao dava para diagnosticar o loop de voz.
fn brain_log_path() -> std::path::PathBuf {
    let dir = std::env::var_os("LOCALAPPDATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(std::env::temp_dir)
        .join("jarvis");
    let _ = std::fs::create_dir_all(&dir);
    dir.join("brain.log")
}

/// Encerra o cerebro: mata o `wsl.exe` rastreado e, como rede de seguranca,
/// mata o loop dentro do WSL (caso o processo tenha ficado orfao de um overlay
/// anterior, sem handle).
fn kill_brain(brain: &Brain) {
    if let Some(mut child) = brain.0.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let cfg = load_config(&config_path());
        let mut cmd = std::process::Command::new("wsl.exe");
        if let Some(distro) = cfg.distro {
            cmd.args(["-d", &distro]);
        }
        // `[l]oop.py` evita que o proprio pkill case com a sua linha de comando.
        cmd.args([
            "--",
            "bash",
            "-lc",
            "pkill -f '[l]oop.py' >/dev/null 2>&1 || true",
        ])
        .creation_flags(0x08000000) // CREATE_NO_WINDOW
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
        let _ = cmd.status();
    }
}

#[tauri::command]
fn start_brain(state: tauri::State<Brain>) -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        kill_brain(&state); // reinicio limpo: derruba qualquer loop anterior
        let cfg = load_config(&config_path());
        let cmd = cfg
            .loop_cmd
            .clone()
            .unwrap_or_else(|| DEFAULT_LOOP_CMD.to_string());
        let mut command = std::process::Command::new("wsl.exe");
        if let Some(distro) = cfg.distro {
            command.args(["-d", &distro]);
        }
        command
            .args(["--", "bash", "-lc", &cmd])
            .creation_flags(0x08000000) // CREATE_NO_WINDOW
            .stdin(std::process::Stdio::null());
        if let Ok(f) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(brain_log_path())
        {
            if let Ok(f2) = f.try_clone() {
                command.stdout(std::process::Stdio::from(f));
                command.stderr(std::process::Stdio::from(f2));
            }
        }
        let child = command.spawn().map_err(|e| e.to_string())?;
        *state.0.lock().unwrap() = Some(child);
        Ok(())
    }
    #[cfg(not(windows))]
    {
        let _ = &state;
        Err("start_brain so funciona no Windows".to_string())
    }
}

#[tauri::command]
fn stop_brain(state: tauri::State<Brain>) -> Result<(), String> {
    kill_brain(&state);
    Ok(())
}

#[tauri::command]
fn state_port() -> u16 {
    env!("JARVIS_STATE_PORT").parse().unwrap_or(8765)
}

fn main() {
    tauri::Builder::default()
        .manage(Brain::default())
        .invoke_handler(tauri::generate_handler![start_brain, stop_brain, state_port])
        .on_window_event(|window, event| {
            // Fechar o overlay (botao Sair ou X) SEMPRE encerra o cerebro.
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let brain = window.state::<Brain>();
                kill_brain(&brain);
            }
        })
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

    #[test]
    fn brain_log_path_points_to_brain_log() {
        let p = brain_log_path();
        assert!(p.to_string_lossy().ends_with("brain.log"));
        assert!(p.parent().is_some());
    }
}
