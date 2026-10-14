use serde::Deserialize;
use std::sync::Mutex;

// Comando default do "cerebro". Pode ser sobrescrito por:
//   1) `JARVIS_LOOP_CMD` no build (`cargo build`), ou
//   2) `jarvis-config.json` ao lado do executavel (loop_cmd / distro).
#[cfg(windows)]
const DEFAULT_LOOP_CMD: &str = match option_env!("JARVIS_LOOP_CMD") {
    Some(cmd) => cmd,
    None => "JARVIS_REQUIRE_GUI=1 ~/github/jarvis/jarvis --voice",
};

/// Handle do cerebro nativo ou do processo WSL, conforme a plataforma.
///
/// Sem isso o overlay nao tinha como encerrar o cerebro ao sair: o `wsl.exe`
/// ficava orfao e o loop continuava "escutando eternamente" no WSL.
#[derive(Default)]
pub(crate) struct Brain(Mutex<Option<std::process::Child>>);

#[derive(Debug, Default, Deserialize)]
pub(crate) struct OverlayConfig {
    pub(crate) loop_cmd: Option<String>,
    pub(crate) launcher: Option<String>,
    #[cfg_attr(not(windows), allow(dead_code))]
    pub(crate) distro: Option<String>,
}

pub(crate) fn load_config(path: &std::path::Path) -> OverlayConfig {
    std::fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

fn config_path() -> std::path::PathBuf {
    if let Some(path) = std::env::var_os("JARVIS_OVERLAY_CONFIG") {
        return path.into();
    }
    #[cfg(not(windows))]
    {
        let base = std::env::var_os("XDG_CONFIG_HOME")
            .map(std::path::PathBuf::from)
            .filter(|p| p.is_absolute())
            .or_else(|| {
                std::env::var_os("HOME").map(|h| std::path::PathBuf::from(h).join(".config"))
            });
        if let Some(base) = base {
            return base.join("jarvis/overlay.json");
        }
    }
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("jarvis-config.json")))
        .unwrap_or_else(|| std::path::PathBuf::from("jarvis-config.json"))
}

/// `%LOCALAPPDATA%\jarvis\brain.log` (fallback: tempdir). Cria o diretorio.
///
/// O overlay sobe o cerebro com CREATE_NO_WINDOW, entao stdout/stderr eram
/// descartados; sem eles nao dava para diagnosticar o loop de voz.
pub(crate) fn brain_log_path() -> std::path::PathBuf {
    #[cfg(windows)]
    let dir = std::env::var_os("LOCALAPPDATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(std::env::temp_dir)
        .join("jarvis");
    #[cfg(not(windows))]
    let dir = linux_log_dir(&std::env::vars().collect())
        .unwrap_or_else(|_| std::env::temp_dir().join(format!("jarvis-{}", std::process::id())));
    let mut builder = std::fs::DirBuilder::new();
    builder.recursive(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::DirBuilderExt;
        builder.mode(0o700);
    }
    let _ = builder.create(&dir);
    dir.join("brain.log")
}

/// Encerra o cerebro: mata o `wsl.exe` rastreado e, como rede de seguranca,
/// mata o loop dentro do WSL (caso o processo tenha ficado orfao de um overlay
/// anterior, sem handle).
pub(crate) fn kill_brain(brain: &Brain) {
    if let Some(mut child) = brain.0.lock().unwrap().take() {
        let _ = stop_child(&mut child);
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
pub(crate) fn start_brain(state: tauri::State<Brain>) -> Result<(), String> {
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
        use std::os::unix::process::CommandExt;
        kill_brain(&state);
        let cfg = load_config(&config_path());
        let mut command = if let Some(cmd) = cfg.loop_cmd {
            let mut command = std::process::Command::new("/bin/sh");
            command.args(["-c", &format!("exec {cmd}")]);
            command
        } else {
            let launcher = native_launcher(cfg.launcher)?;
            let mut command = std::process::Command::new(launcher);
            command.arg("--voice");
            command
        };
        command
            .env("JARVIS_REQUIRE_GUI", "1")
            .process_group(0)
            .stdin(std::process::Stdio::null());
        let mut log_options = std::fs::OpenOptions::new();
        log_options.create(true).append(true);
        use std::os::unix::fs::OpenOptionsExt;
        log_options.mode(0o600);
        let log = log_options
            .open(brain_log_path())
            .map_err(|e| format!("log do cerebro: {e}"))?;
        command
            .stdout(log.try_clone().map_err(|e| e.to_string())?)
            .stderr(log);
        let child = command
            .spawn()
            .map_err(|e| format!("nao foi possivel iniciar cerebro: {e}"))?;
        *state.0.lock().unwrap() = Some(child);
        Ok(())
    }
}

#[tauri::command]
pub(crate) fn stop_brain(state: tauri::State<Brain>) -> Result<(), String> {
    kill_brain(&state);
    Ok(())
}

fn linux_log_dir(
    env: &std::collections::HashMap<String, String>,
) -> Result<std::path::PathBuf, String> {
    if let Some(path) = env
        .get("XDG_STATE_HOME")
        .map(std::path::PathBuf::from)
        .filter(|p| p.is_absolute())
    {
        return Ok(path.join("jarvis"));
    }
    env.get("HOME")
        .map(|home| std::path::PathBuf::from(home).join(".local/state/jarvis"))
        .ok_or_else(|| "HOME ou XDG_STATE_HOME necessario".into())
}

#[cfg(not(windows))]
fn native_launcher(configured: Option<String>) -> Result<std::path::PathBuf, String> {
    if let Some(path) = configured {
        return Ok(path.into());
    }
    if let Some(root) = std::env::var_os("JARVIS_PROJECT_ROOT") {
        return Ok(std::path::PathBuf::from(root).join("jarvis"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(prefix) = exe.parent().and_then(|p| p.parent()) {
            let installed = prefix.join("lib/jarvis/jarvis");
            if installed.is_file() {
                return Ok(installed);
            }
        }
    }
    #[cfg(debug_assertions)]
    {
        let source = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../jarvis");
        if source.is_file() {
            return Ok(source);
        }
    }
    Ok(std::path::PathBuf::from("jarvis"))
}

pub(crate) fn stop_child(child: &mut std::process::Child) -> Result<(), String> {
    #[cfg(unix)]
    {
        let group = -(child.id() as i32);
        // Keep the leader unreaped until both signals, preventing PID reuse.
        unsafe {
            libc::kill(group, libc::SIGTERM);
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
        unsafe {
            libc::kill(group, libc::SIGKILL);
        }
    }
    #[cfg(windows)]
    {
        let _ = child.kill();
    }
    child.wait().map(|_| ()).map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::path::PathBuf;

    #[test]
    fn xdg_logs_keep_spaces_and_ignore_relative_override() {
        let env = HashMap::from([
            ("HOME".into(), "/home/test".into()),
            ("XDG_STATE_HOME".into(), "/tmp/meus dados/ação".into()),
        ]);
        assert_eq!(
            linux_log_dir(&env).unwrap(),
            PathBuf::from("/tmp/meus dados/ação/jarvis")
        );
        let env = HashMap::from([
            ("HOME".into(), "/home/test".into()),
            ("XDG_STATE_HOME".into(), "relative".into()),
        ]);
        assert_eq!(
            linux_log_dir(&env).unwrap(),
            PathBuf::from("/home/test/.local/state/jarvis")
        );
        assert!(linux_log_dir(&HashMap::new()).is_err());
    }

    #[cfg(unix)]
    #[test]
    fn stop_only_owns_its_process_group() {
        use std::os::unix::process::CommandExt;
        use std::process::Command;
        let mut sentinel = Command::new("sleep").arg("30").spawn().unwrap();
        let mut child = Command::new("sh")
            .args(["-c", "sleep 30 & wait"])
            .process_group(0)
            .spawn()
            .unwrap();
        stop_child(&mut child).unwrap();
        assert!(child.try_wait().unwrap().is_some());
        assert!(sentinel.try_wait().unwrap().is_none());
        sentinel.kill().unwrap();
        sentinel.wait().unwrap();
    }
}
