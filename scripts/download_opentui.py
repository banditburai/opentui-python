"""Download OpenTUI core binaries from npm registry (pure Python, no node required)."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import platform
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

OPENTUI_VERSION = "0.1.91"

NPM_REGISTRY = "https://registry.npmjs.org"

PLATFORM_MAP = {
    ("darwin", "x86_64"): "darwin-x64",
    ("darwin", "arm64"): "darwin-arm64",
    ("linux", "x86_64"): "linux-x64",
    ("linux", "aarch64"): "linux-arm64",
    ("windows", "x86_64"): "win32-x64",
    ("windows", "amd64"): "win32-x64",
}

LIB_NAMES = {
    "darwin": ["libopentui.dylib"],
    "linux": ["libopentui.so"],
    "windows": ["opentui.dll", "libopentui.dll"],
}

DEFAULT_DEST = Path(__file__).resolve().parent.parent / "src" / "opentui" / "opentui-libs"


def get_platform_id() -> str:
    """Map current OS/arch to npm platform package suffix."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    key = (system, machine)
    if key not in PLATFORM_MAP:
        raise RuntimeError(f"Unsupported platform: {system}-{machine}")
    return PLATFORM_MAP[key]


def get_lib_names() -> list[str]:
    """Return candidate library filenames for the current OS."""
    system = platform.system().lower()
    return LIB_NAMES.get(system, ["libopentui.so"])


def fetch_json(url: str) -> dict:
    """Fetch JSON from a URL."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def verify_integrity(data: bytes, integrity: str | None, shasum: str | None) -> None:
    """Verify tarball integrity using SRI hash or SHA-1 fallback."""
    if integrity:
        # SRI format: "sha512-<base64>"
        algo, expected_b64 = integrity.split("-", 1)
        digest = hashlib.new(algo, data).digest()
        actual_b64 = base64.b64encode(digest).decode()
        if actual_b64 != expected_b64:
            raise RuntimeError(
                f"Integrity check failed ({algo}):\n"
                f"  expected: {expected_b64}\n"
                f"  got:      {actual_b64}"
            )
        print(f"  Integrity verified ({algo})")
    elif shasum:
        actual = hashlib.sha1(data).hexdigest()
        if actual != shasum:
            raise RuntimeError(f"SHA-1 check failed:\n  expected: {shasum}\n  got:      {actual}")
        print("  Integrity verified (sha1)")
    else:
        print("  Warning: no integrity data available, skipping verification")


def download_library(version: str, dest_dir: Path) -> Path:
    """Download and extract the OpenTUI shared library from npm."""
    platform_id = get_platform_id()
    package = f"@opentui/core-{platform_id}"
    lib_names = get_lib_names()

    # 1. Fetch package metadata for the pinned version
    meta_url = f"{NPM_REGISTRY}/{package}/{version}"
    print(f"Fetching metadata: {meta_url}")
    meta = fetch_json(meta_url)

    dist = meta.get("dist", {})
    tarball_url = dist.get("tarball")
    integrity = dist.get("integrity")
    shasum = dist.get("shasum")

    if not tarball_url:
        raise RuntimeError(f"No tarball URL in metadata for {package}@{version}")

    # 2. Download tarball
    print(f"Downloading: {tarball_url}")
    with urllib.request.urlopen(tarball_url, timeout=60) as resp:
        tarball_data = resp.read()
    print(f"  Downloaded {len(tarball_data)} bytes")

    # 3. Verify integrity
    verify_integrity(tarball_data, integrity, shasum)

    # 4. Extract library from tarball (safe: read individual members, no extractall)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(tarball_data), mode="r:gz") as tar:
        for member in tar.getmembers():
            basename = Path(member.name).name
            if basename in lib_names and member.isfile():
                fileobj = tar.extractfile(member)
                if fileobj is None:
                    continue
                dest_path = dest_dir / basename
                with open(dest_path, "wb") as out:
                    shutil.copyfileobj(fileobj, out)
                print(f"  Extracted: {dest_path}")
                return dest_path

    raise RuntimeError(
        f"Shared library not found in {package}@{version}.\n  Searched for: {lib_names}"
    )


def ensure_library(version: str, dest_dir: Path, *, force: bool = False) -> Path:
    """Download library if not already present (or if --force)."""
    if not force:
        for name in get_lib_names():
            path = dest_dir / name
            if path.exists():
                print(f"Library already exists: {path}")
                return path

    return download_library(version, dest_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download OpenTUI core binaries")
    parser.add_argument(
        "--version",
        default=OPENTUI_VERSION,
        help=f"npm package version (default: {OPENTUI_VERSION})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if library already exists",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"Destination directory (default: {DEFAULT_DEST})",
    )
    args = parser.parse_args()

    print(f"OpenTUI Python - Library Downloader v{args.version}")
    print("=" * 50)

    try:
        platform_id = get_platform_id()
        print(f"Platform: {platform_id}")
        lib_path = ensure_library(args.version, args.dest, force=args.force)
        print(f"\nLibrary ready: {lib_path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
