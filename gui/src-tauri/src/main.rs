#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod brain;

#[cfg(test)]
use brain::{brain_log_path, load_config};
use brain::{kill_brain, Brain};
use tauri::Manager;

fn resolve_port(value: &str, default: u16) -> u16 {
    value
        .parse::<u16>()
        .ok()
        .filter(|port| *port > 0)
        .unwrap_or(default)
}

#[tauri::command]
fn state_port() -> u16 {
    let default = resolve_port(env!("JARVIS_STATE_PORT"), 8765);
    std::env::var("JARVIS_STATE_PORT")
        .map(|value| resolve_port(&value, default))
        .unwrap_or(default)
}

#[tauri::command]
fn platform_info() -> serde_json::Value {
    serde_json::json!({"platform": std::env::consts::OS,
        "tts_backends": if cfg!(windows) { vec!["piper","sapi"] } else { vec!["piper"] }})
}

fn main() {
    let mut context = tauri::generate_context!();
    #[cfg(target_os = "linux")]
    if std::env::var_os("WAYLAND_DISPLAY").is_some()
        && std::env::var("JARVIS_WINDOW_MODE").as_deref() != Ok("orb")
    {
        if let Some(window) = context.config_mut().app.windows.first_mut() {
            window.decorations = true;
            window.skip_taskbar = false;
            window.always_on_top = false;
        }
    }
    tauri::Builder::default()
        .manage(Brain::default())
        .invoke_handler(tauri::generate_handler![
            brain::start_brain,
            brain::stop_brain,
            state_port,
            platform_info
        ])
        .on_window_event(|window, event| {
            // Fechar o overlay (botao Sair ou X) SEMPRE encerra o cerebro.
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let brain = window.state::<Brain>();
                kill_brain(&brain);
            }
        })
        .run(context)
        .expect("error while running jarvis overlay");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(target_os = "linux")]
    #[test]
    fn gtk_application_identifier_is_enabled() {
        let config: tauri::Config =
            serde_json::from_str(include_str!("../tauri.conf.json")).unwrap();
        assert!(config.app.enable_gtk_app_id);
        assert_eq!(config.identifier, "com.jarvis.overlay");
    }

    #[test]
    fn runtime_port_override_is_validated() {
        assert_eq!(resolve_port("18765", 8765), 18765);
        assert_eq!(resolve_port("invalid", 8765), 8765);
        assert_eq!(resolve_port("0", 8765), 8765);
        assert_eq!(resolve_port("65536", 8765), 8765);
    }

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
