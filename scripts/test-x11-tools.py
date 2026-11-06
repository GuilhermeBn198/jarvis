#!/usr/bin/env python3
"""Smoke-test X11 automation and clipboard helpers on an isolated X server."""
from __future__ import annotations

import os
import select
import shutil
import subprocess


def main() -> None:
    external_display = os.environ.get("JARVIS_X11_EXTERNAL") == "1"
    if external_display and not os.environ.get("DISPLAY"):
        raise SystemExit("JARVIS_X11_EXTERNAL=1 requires DISPLAY from the X server wrapper")
    for tool in (("xdotool", "xclip") if external_display else ("Xvfb", "xdotool", "xclip")):
        if not shutil.which(tool):
            raise SystemExit(f"required X11 test helper not found: {tool}")

    server = None
    read_fd = None
    try:
        env = dict(os.environ)
        if not external_display:
            read_fd, write_fd = os.pipe()
            server = subprocess.Popen(
                ["Xvfb", "-displayfd", str(write_fd), "-nolisten", "tcp", "-screen", "0", "640x480x24"],
                pass_fds=(write_fd,),
            )
            os.close(write_fd)
            if not select.select([read_fd], [], [], 10)[0]:
                raise AssertionError("Xvfb did not allocate a display")
            display = os.read(read_fd, 64).decode().strip()
            if not display.isdigit():
                raise AssertionError(f"invalid Xvfb display number: {display!r}")
            env["DISPLAY"] = f":{display}"
        location = subprocess.check_output(
            ["xdotool", "getmouselocation", "--shell"], env=env, text=True, timeout=10
        )
        if "X=" not in location or "Y=" not in location:
            raise AssertionError(f"xdotool returned unexpected location: {location!r}")

        value = f"jarvis-xclip-smoke-{os.getpid()}"
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-i"],
            input=value, env=env, text=True, check=True, timeout=10,
        )
        actual = subprocess.check_output(
            ["xclip", "-selection", "clipboard", "-o"], env=env, text=True, timeout=10
        )
        if actual != value:
            raise AssertionError(f"xclip roundtrip mismatch: {actual!r}")
        server_name = "external X server" if external_display else "Xvfb"
        print(f"PASS: xdotool pointer query and xclip clipboard roundtrip on {server_name}")
    finally:
        if read_fd is not None:
            os.close(read_fd)
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    main()
