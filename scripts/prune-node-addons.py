#!/usr/bin/env python3
"""Remove optional native Node addons built for the other libc."""
import argparse
from pathlib import Path


def prune(target_libc: str, opencode_root: Path) -> list[Path]:
    incompatible_libc = "musl" if target_libc == "glibc" else "glibc"
    addon_root = opencode_root / "node_modules" / "@msgpackr-extract"
    removed = []
    if addon_root.is_dir():
        for addon in addon_root.rglob(f"*.{incompatible_libc}.node"):
            addon.unlink()
            removed.append(addon)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("libc", choices=("glibc", "musl"))
    parser.add_argument("opencode_root", type=Path)
    args = parser.parse_args()
    prune(args.libc, args.opencode_root)


if __name__ == "__main__":
    main()
