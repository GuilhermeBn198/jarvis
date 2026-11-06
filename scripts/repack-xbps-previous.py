#!/usr/bin/env python3
"""Create a lower-revision XBPS test package from an already built package."""
from __future__ import annotations

import argparse
import plistlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path


CREATE_OPTIONS = {
    "built_with": "-B",
    "conflicts": "-C",
    "changelog": "-c",
    "run_depends": "-D",
    "config_files": "-F",
    "homepage": "-H",
    "license": "-l",
    "mutable_files": "-M",
    "maintainer": "-m",
    "provides": "-P",
    "reverts": "-r",
    "replaces": "-R",
    "long_desc": "-S",
    "short_desc": "-s",
    "tags": "-t",
    "alternatives": "--alternatives",
    "build_options": "--build-options",
    "shlib-provides": "--shlib-provides",
    "shlib-requires": "--shlib-requires",
}


def previous_revision_properties(properties: dict) -> dict:
    """Return metadata for the immediately preceding XBPS revision."""
    pkgname = properties.get("pkgname")
    pkgver = properties.get("pkgver")
    version = properties.get("version")
    if not all(isinstance(value, str) and value for value in (pkgname, pkgver, version)):
        raise ValueError("XBPS package is missing pkgname, pkgver or version")
    if pkgver != f"{pkgname}-{version}":
        raise ValueError("XBPS pkgver/version mismatch")

    match = re.fullmatch(r"(?P<upstream>.+)_(?P<revision>[1-9][0-9]*)", version)
    if not match or int(match.group("revision")) < 2:
        raise ValueError("no previous XBPS revision can be generated")

    prior_version = f"{match.group('upstream')}_{int(match.group('revision')) - 1}"
    prior = dict(properties)
    prior["version"] = prior_version
    prior["pkgver"] = f"{pkgname}-{prior_version}"
    if "provides" in prior:
        prior["provides"] = [value.replace(version, prior_version) for value in prior["provides"]]
    return prior


def _read_properties(package: Path) -> dict:
    result = subprocess.run(
        ["tar", "--zstd", "-xOf", str(package), "./props.plist"],
        check=True, capture_output=True,
    )
    properties = plistlib.loads(result.stdout)
    if not isinstance(properties, dict):
        raise ValueError("XBPS props.plist is not a dictionary")
    return properties


def _members(package: Path) -> set[str]:
    result = subprocess.run(["tar", "--zstd", "-tf", str(package)], check=True,
                            capture_output=True, text=True)
    return {line for line in result.stdout.splitlines() if line not in ("./props.plist", "./files.plist")}


def create_previous_revision(package: Path, output_dir: Path) -> Path:
    package = package.resolve(strict=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    original = _read_properties(package)
    prior = previous_revision_properties(original)
    architecture = original.get("architecture")
    if not isinstance(architecture, str) or not architecture:
        raise ValueError("XBPS package is missing architecture")
    output = output_dir / f"{prior['pkgver']}.{architecture}.xbps"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing package: {output}")

    with tempfile.TemporaryDirectory(prefix="xbps-previous-", dir=output_dir) as temporary:
        stage = Path(temporary) / "stage"
        stage.mkdir()
        subprocess.run(["tar", "--zstd", "-xf", str(package), "-C", str(stage)], check=True)
        for metadata_file in ("props.plist", "files.plist"):
            (stage / metadata_file).unlink(missing_ok=True)

        arguments = ["xbps-create", "-q", "-A", architecture, "-n", prior["pkgver"]]
        for field, option in CREATE_OPTIONS.items():
            value = prior.get(field)
            if value is None or value == "" or value == []:
                continue
            arguments.extend((option, " ".join(map(str, value)) if isinstance(value, list) else str(value)))
        if prior.get("preserve"):
            arguments.append("-p")
        arguments.extend(("--compression", "zstd", str(stage)))
        subprocess.run(arguments, cwd=output_dir, check=True, capture_output=True, text=True)

    generated = _read_properties(output)
    if generated.get("pkgver") != prior["pkgver"] or generated.get("architecture") != architecture:
        raise ValueError("xbps-create emitted unexpected package identity")
    if generated.get("run_depends", []) != prior.get("run_depends", []):
        raise ValueError("xbps-create did not preserve runtime dependencies")
    if _members(package) != _members(output):
        raise ValueError("repacked package payload file list differs from source package")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="newer .xbps package")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output = create_previous_revision(args.package, args.output_dir)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        print(f"could not create prior XBPS revision: {detail or exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"could not create prior XBPS revision: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
