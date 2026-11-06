#!/usr/bin/env python3
"""Build pinned desktop helper tools into the Slackware Jarvis package."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess


SOURCES = {
    "xdotool": (
        "https://github.com/jordansissel/xdotool.git",
        "d37c16111dbe38ea29194f20ac9de03cff8dfc1c",
    ),
    "xclip": (
        "https://github.com/astrand/xclip.git",
        "9aa7090c3b8b437c6489edca32ae43d82e0c1281",
    ),
    "wl-clipboard": (
        "https://github.com/bugaevc/wl-clipboard.git",
        "67a7b937895bceec1ae5ccebb10216f63f70ca1b",
    ),
}


def run(argv: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(argv, cwd=cwd, env=env, check=True)


def checkout(name: str, workdir: Path, env: dict[str, str]) -> Path:
    url, revision = SOURCES[name]
    source = workdir / name
    shutil.rmtree(source, ignore_errors=True)
    source.mkdir(parents=True)
    run(["git", "init", "-q"], cwd=source)
    run(["git", "remote", "add", "origin", url], cwd=source)
    run(["git", "fetch", "--depth", "1", "origin", revision], cwd=source, env=env)
    run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=source)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if actual != revision:
        raise RuntimeError(f"{name}: upstream revision mismatch: {actual}")
    return source


def build(workdir: Path, destdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    bindir = destdir / "usr/lib/jarvis/bin"
    bindir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    if env.get("SSL_CERT_FILE") and not env.get("GIT_SSL_CAINFO"):
        env["GIT_SSL_CAINFO"] = env["SSL_CERT_FILE"]

    xdotool = checkout("xdotool", workdir, env)
    run(["make", "-j2", "static"], cwd=xdotool)
    shutil.copy2(xdotool / "xdotool.static", bindir / "xdotool")
    (bindir / "xdotool").chmod(0o755)

    xclip = checkout("xclip", workdir, env)
    run(["autoreconf", "-fi"], cwd=xclip)
    run(["./configure", "--prefix=/usr"], cwd=xclip)
    run(["make", "-j2"], cwd=xclip)
    shutil.copy2(xclip / "xclip", bindir / "xclip")
    (bindir / "xclip").chmod(0o755)

    wl_clipboard = checkout("wl-clipboard", workdir, env)
    builddir = workdir / "wl-clipboard-build"
    shutil.rmtree(builddir, ignore_errors=True)
    run([
        "meson", "setup", str(builddir), str(wl_clipboard),
        "--prefix=/usr", "--bindir=lib/jarvis/bin", "--datadir=share",
        "--mandir=share/man",
        "-Dfishcompletiondir=/usr/lib/jarvis/share/fish/vendor_completions.d",
    ], env=env)
    run(["ninja", "-C", str(builddir), "-j2"], env=env)
    install_env = env | {"DESTDIR": str(destdir)}
    run(["ninja", "-C", str(builddir), "install"], env=install_env)

    for name in ("xdotool", "xclip", "wl-copy", "wl-paste"):
        executable = bindir / name
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise RuntimeError(f"desktop helper missing from package staging: {executable}")

    licenses = destdir / "usr/doc/jarvis-assistant-0.1.0/third-party"
    licenses.mkdir(parents=True, exist_ok=True)
    for source, name in (
        (xdotool / "COPYRIGHT", "xdotool-COPYRIGHT"),
        (xclip / "COPYING", "xclip-COPYING"),
        (wl_clipboard / "COPYING", "wl-clipboard-COPYING"),
    ):
        shutil.copy2(source, licenses / name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--destdir", required=True, type=Path)
    args = parser.parse_args()
    build(args.workdir.resolve(), args.destdir.resolve())


if __name__ == "__main__":
    main()
