#!/usr/bin/env python3
"""Exercise installed GTK relaunches on an isolated X11 display and D-Bus."""
import json
import configparser
import ctypes
import os
from pathlib import Path
import select
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time


def wait_for(predicate, processes, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for process in processes:
            if process.poll() is not None:
                raise AssertionError(f"overlay exited unexpectedly: {process.returncode}")
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("overlay window did not become accessible")


def read_atspi(operation, stale_error, fallback=None):
    try:
        return operation()
    except stale_error:
        return fallback


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def reap_helpers(excluded):
    deadline = time.monotonic() + 5
    while True:
        children = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit() or int(entry.name) in excluded:
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if int(fields[1]) == os.getpid():
                    children.append(int(entry.name))
            except (OSError, ValueError, IndexError):
                continue
        if not children:
            return
        for pid in children:
            try:
                # Unreaped direct children cannot have their PIDs reused.
                if os.waitpid(pid, os.WNOHANG)[0] == 0 and time.monotonic() >= deadline:
                    os.kill(pid, signal.SIGKILL)
            except (ChildProcessError, ProcessLookupError):
                continue
        assert time.monotonic() < deadline + 5, "test helpers did not terminate"
        time.sleep(0.05)


def x11_environment(display):
    env = dict(
        os.environ,
        DISPLAY=f":{display}" if str(display).isdigit() else str(display),
        GDK_BACKEND="x11",
        LIBGL_ALWAYS_SOFTWARE="1",
        WEBKIT_DISABLE_COMPOSITING_MODE="1",
        GTK_USE_PORTAL="0",
        GIO_USE_VFS="local",
    )
    env["XDG_SESSION_TYPE"] = "x11"
    for name in (
        "AT_SPI_BUS_ADDRESS", "DBUS_STARTER_ADDRESS", "DBUS_STARTER_BUS_TYPE",
        "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP",
    ):
        env.pop(name, None)
    return env


def inside_session(binary):
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi, GLib
    # ARM emulation can take longer to answer an accessibility action than
    # the default one-second reply window, even when the application is healthy.
    Atspi.set_timeout(5000, 10000)
    # Own orphaned WebKit helpers as well, so cache writers are reaped before
    # removing the private data tree. This affects this fixture process only.
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "cannot own test helper processes")

    def owned_frame(pid):
        desktop = Atspi.get_desktop(0)
        for index in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(index)
            if app and app.get_process_id() == pid and app.get_child_count() > 0:
                return app.get_child_at_index(0)
        return None

    def button(pid, name):
        frame = read_atspi(lambda: owned_frame(pid), GLib.Error)
        pending = [(frame, 0)] if frame else []
        visited = 0
        while pending and visited < 400:
            item, depth = pending.pop()
            visited += 1
            item_name = read_atspi(item.get_name, GLib.Error)
            showing = read_atspi(
                lambda: item.get_state_set().contains(Atspi.StateType.SHOWING),
                GLib.Error,
                False,
            )
            if item_name == name and showing:
                return item
            if depth < 12:
                child_count = read_atspi(item.get_child_count, GLib.Error, 0)
                for index in range(min(child_count, 100)):
                    child = read_atspi(lambda: item.get_child_at_index(index), GLib.Error)
                    if child:
                        pending.append((child, depth + 1))
        return None

    processes = []
    with tempfile.TemporaryDirectory(prefix="jarvis-overlay-test-") as directory:
        root = Path(directory)
        # This test owns no microphone, agent server, models or user settings.
        config = root / "overlay.json"
        config.write_text(json.dumps({"launcher": "/bin/true"}))
        env = dict(os.environ, JARVIS_OVERLAY_CONFIG=str(config))
        reservation = socket.socket()
        reservation.bind(("127.0.0.1", 0))
        env["JARVIS_STATE_PORT"] = str(reservation.getsockname()[1])
        for kind in ("CONFIG", "DATA", "CACHE", "STATE"):
            path = root / kind.lower()
            path.mkdir()
            env[f"XDG_{kind}_HOME"] = str(path)
        try:
            service = configparser.ConfigParser(interpolation=None)
            service.read("/usr/share/dbus-1/accessibility-services/org.a11y.atspi.Registry.service")
            registry_binary = shlex.split(service["D-BUS Service"]["Exec"])[0]
            registry = subprocess.Popen([registry_binary])
            processes.append(registry)
            first = subprocess.Popen([binary], env=env)
            processes.append(first)
            wait_for(lambda: owned_frame(first.pid), [first, registry])
            second = subprocess.Popen([binary], env=env)
            processes.append(second)
            assert second.wait(timeout=15) == 0, "secondary launch failed"
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                assert first.poll() is None, "secondary launch crashed primary"
                assert owned_frame(first.pid), "primary window disappeared"
                time.sleep(0.1)
            for name in ("Abrir menu Jarvis", "Sair"):
                wait_for(lambda: button(first.pid, name), [first, registry])
                assert button(first.pid, name).get_action_iface().do_action(0)
            assert first.wait(timeout=10) == 0, "primary did not close cleanly"
        finally:
            for process in reversed(processes[1:]):
                stop(process)
            reap_helpers({registry.pid} if processes else set())
            if processes:
                stop(processes[0])
            reap_helpers(set())
            reservation.close()
    print("PASS: second launch exits and installed primary window survives")


def main():
    binary = str(Path(sys.argv[-1]).resolve(strict=True))
    if "--inside-session" in sys.argv:
        inside_session(binary)
        return
    read_fd, write_fd = os.pipe()
    server = subprocess.Popen(
        ["Xvfb", "-displayfd", str(write_fd), "-nolisten", "tcp", "-screen", "0", "640x480x24"],
        pass_fds=(write_fd,),
    )
    os.close(write_fd)
    try:
        assert select.select([read_fd], [], [], 10)[0], "Xvfb did not initialize"
        display = os.read(read_fd, 64).decode().strip()
        assert display.isdigit(), "Xvfb did not allocate a display"
        env = x11_environment(display)
        with tempfile.TemporaryDirectory(prefix="jarvis-display-test-") as directory:
            env["HOME"] = directory
            for kind in ("CONFIG", "DATA", "CACHE", "STATE", "RUNTIME"):
                path = Path(directory) / kind.lower()
                path.mkdir(mode=0o700)
                env[f"XDG_{kind}_{'DIR' if kind == 'RUNTIME' else 'HOME'}"] = str(path)
            try:
                subprocess.run(
                    ["dbus-run-session", "--", sys.executable, str(Path(__file__).resolve()), "--inside-session", binary],
                    env=env, check=True, timeout=75,
                )
            finally:
                # A portal activated on this private bus may leave its own FUSE
                # mount behind briefly after the bus exits. Detach only ours.
                document_mount = str(Path(directory) / "runtime/doc")
                mounts = Path("/proc/self/mountinfo").read_text().splitlines()
                if any(line.split()[4] == document_mount for line in mounts):
                    helper = shutil.which("fusermount3") or shutil.which("fusermount")
                    assert helper, "cannot clean the test's document portal mount"
                    detached = subprocess.run([helper, "-u", "-z", document_mount], capture_output=True, text=True)
                    if detached.returncode:
                        remaining = Path("/proc/self/mountinfo").read_text().splitlines()
                        assert not any(line.split()[4] == document_mount for line in remaining), detached.stderr
    finally:
        os.close(read_fd)
        stop(server)


if __name__ == "__main__":
    main()
