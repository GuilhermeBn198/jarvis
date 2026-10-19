#!/usr/bin/env python3
"""Smoke-test X11 automation and clipboard helpers on an isolated Xvfb."""
from __future__ import annotations

import os
import select
import shutil
import subprocess


def main() -> None:
    for tool in ("Xvfb", "xdotool", "xclip"):
        if not shutil.which(tool):
            raise SystemExit(f"required X11 test helper not found: {tool}")

    read_fd, write_fd = os.pipe()
    server = subprocess.Popen(
        ["Xvfb", "-displayfd", str(write_fd), "-nolisten", "tcp", "-screen", "0", "640x480x24"],
        pass_fds=(write_fd,),
    )
    os.close(write_fd)
    try:
        if not select.select([read_fd], [], [], 10)[0]:
            raise AssertionError("Xvfb did not allocate a display")
        display = os.read(read_fd, 64).decode().strip()
        if not display.isdigit():
            raise AssertionError(f"invalid Xvfb display number: {display!r}")
        env = dict(os.environ, DISPLAY=f":{display}")
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
        print("PASS: xdotool pointer query and xclip clipboard roundtrip on Xvfb")
    finally:
        os.close(read_fd)
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
