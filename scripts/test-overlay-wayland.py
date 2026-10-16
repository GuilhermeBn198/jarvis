#!/usr/bin/env python3
"""Exercise a native Wayland overlay on an owned headless Weston session."""
import ctypes
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

fixture = Path(__file__).with_name("test-overlay-instance.py")
spec = importlib.util.spec_from_file_location("overlay_instance_fixture", fixture)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def main():
    binary = str(Path(sys.argv[1]).resolve(strict=True))
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "cannot own compositor helper processes")
    with tempfile.TemporaryDirectory(prefix="jarvis-wayland-test-") as directory:
        root = Path(directory)
        env = dict(os.environ, HOME=directory, GDK_BACKEND="wayland", XDG_SESSION_TYPE="wayland",
                   WAYLAND_DISPLAY="wayland-jarvis", LIBGL_ALWAYS_SOFTWARE="1", GTK_USE_PORTAL="0", GIO_USE_VFS="local")
        for name in ("DISPLAY", "AT_SPI_BUS_ADDRESS", "DBUS_SESSION_BUS_ADDRESS", "DBUS_STARTER_ADDRESS", "DBUS_STARTER_BUS_TYPE"):
            env.pop(name, None)
        for kind in ("CONFIG", "DATA", "CACHE", "STATE", "RUNTIME"):
            path = root / kind.lower()
            path.mkdir(mode=0o700)
            env[f"XDG_{kind}_{'DIR' if kind == 'RUNTIME' else 'HOME'}"] = str(path)
        with (root / "weston.log").open("w+") as log:
            server = subprocess.Popen(
                ["weston", "--backend=headless", "--renderer=pixman", "--no-config", "--idle-time=0",
                 "--width=640", "--height=480", "--socket=wayland-jarvis"], env=env, stdout=log, stderr=log,
            )
            try:
                socket = root / "runtime/wayland-jarvis"
                helpers.wait_for(socket.is_socket, [server], timeout=15)
                subprocess.run(["dbus-run-session", "--", sys.executable, str(fixture), "--inside-session", binary],
                               env=env, check=True, timeout=75)
            except BaseException:
                log.seek(0)
                print(log.read()[-12000:], file=sys.stderr)
                raise
            finally:
                helpers.stop(server)
                helpers.reap_helpers(set())
                document_mount = str(root / "runtime/doc")
                mounts = Path("/proc/self/mountinfo").read_text().splitlines()
                if any(line.split()[4] == document_mount for line in mounts):
                    helper = shutil.which("fusermount3") or shutil.which("fusermount")
                    assert helper, "cannot clean the test's document portal mount"
                    subprocess.run([helper, "-u", "-z", document_mount], check=True)
        print("PASS: native Wayland relaunch/exit on isolated Weston (full desktop/portal/audio pending)")


if __name__ == "__main__":
    main()
