"""Download OpenTUI core binaries for the current platform."""

import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


PLATFORM_MAP = {
    ("darwin", "x86_64"): "darwin-x64",
    ("darwin", "arm64"): "darwin-arm64",
    ("linux", "x86_64"): "linux-x64",
    ("linux", "aarch64"): "linux-arm64",
    ("win32", "x86"): "win32-x64",  # Python doesn't distinguish x86 on Windows
    ("win32", "AMD64"): "win32-x64",
}


def get_platform() -> str:
    """Get the platform identifier for OpenTUI core."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        machine = "arm64" if machine == "arm64" else "x86_64"
    elif system == "linux":
        machine = "aarch64" if machine == "aarch64" else "x86_64"

    key = (system, machine)
    if key not in PLATFORM_MAP:
        raise RuntimeError(f"Unsupported platform: {system}-{machine}")

    return PLATFORM_MAP[key]


def get_package_name(platform_id: str) -> str:
    """Get the npm package name for the platform."""
    return f"@opentui/core-{platform_id}"


def download_and_extract_lib(package_name: str, dest_dir: Path) -> Path:
    """Download npm package and extract the shared library."""
    print(f"Downloading {package_name}...")

    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Download package using npm
        result = subprocess.run(
            ["npm", "pack", package_name, "--pack-destination", str(tmppath)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"Warning: npm pack failed: {result.stderr}")
            # Fallback: try using npx
            result = subprocess.run(
                ["npx", "-y", "@aspect/extract", package_name, str(tmppath)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to download {package_name}: {result.stderr}")

        # Find the downloaded package
        package_files = list(tmppath.glob("*.tgz"))
        if not package_files:
            # Try to find any downloaded file
            package_files = list(tmppath.glob("@opentui/*/*.tgz"))

        if package_files:
            package_file = package_files[0]
            print(f"Extracting {package_file.name}...")

            # Extract tarball
            with tarfile.open(package_file, "r:gz") as tar:
                # Extract to temp
                extract_dir = tmppath / "extracted"
                extract_dir.mkdir()
                tar.extractall(extract_dir)

                # Find the shared library
                # Package structure: package/package/files/...
                package_dir = extract_dir / "package"

                if platform.system().lower() == "darwin":
                    lib_name = "libopentui.dylib"
                elif platform.system().lower() == "linux":
                    lib_name = "libopentui.so"
                else:
                    lib_name = "libopentui.dll"

                # Search for the library
                lib_path = None
                for root, dirs, files in os.walk(package_dir):
                    if lib_name in files:
                        lib_path = Path(root) / lib_name
                        break

                if lib_path and lib_path.exists():
                    dest_path = dest_dir / lib_name
                    shutil.copy2(lib_path, dest_path)
                    print(f"Copied to {dest_path}")
                    return dest_path

                # Try .node files (native Node modules)
                for root, dirs, files in os.walk(package_dir):
                    for f in files:
                        if f.endswith(".node") or f.startswith("libopentui"):
                            src = Path(root) / f
                            dest_path = dest_dir / f
                            shutil.copy2(src, dest_path)
                            print(f"Copied to {dest_path}")
                            return dest_path

        raise RuntimeError(f"Could not find shared library in {package_name}")


def ensure_library(dest_dir: Path | None = None) -> Path:
    """Ensure the OpenTUI library is available."""
    if dest_dir is None:
        # Default to package directory
        dest_dir = Path(__file__).parent.parent / "src" / "opentui" / "opentui-libs"

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Check if already exists
    system = platform.system().lower()
    if system == "darwin":
        lib_name = "libopentui.dylib"
    elif system == "linux":
        lib_name = "libopentui.so"
    else:
        lib_name = "libopentui.dll"

    lib_path = dest_dir / lib_name
    if lib_path.exists():
        print(f"Library already exists at {lib_path}")
        return lib_path

    # Download
    platform_id = get_platform()
    package_name = get_package_name(platform_id)

    try:
        return download_and_extract_lib(package_name, dest_dir)
    except Exception as e:
        print(f"Error downloading library: {e}")
        print("Trying alternative approach...")

        # Fallback: try direct download
        try:
            import urllib.request
            import io

            # Try direct CDN download
            cdn_url = f"https://registry.npmjs.org/{package_name}/latest"
            response = urllib.request.urlopen(cdn_url)
            data = json.loads(response.read().decode())

            tarball_url = data.get("dist", {}).get("tarball")
            if tarball_url:
                print(f"Downloading from {tarball_url}")
                response = urllib.request.urlopen(tarball_url)
                tarball_data = io.BytesIO(response.read())

                extract_dir = dest_dir / "extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)

                with tarfile.open(fileobj=tarball_data, mode="r:gz") as tar:
                    tar.extractall(extract_dir)

                # Find and copy library
                package_dir = extract_dir / "package"
                for root, dirs, files in os.walk(package_dir):
                    for f in files:
                        if "opentui" in f.lower() and (
                            f.endswith(".so") or f.endswith(".dylib") or f.endswith(".dll")
                        ):
                            src = Path(root) / f
                            dest_path = dest_dir / f
                            shutil.copy2(src, dest_path)
                            return dest_path
        except Exception as e2:
            print(f"Alternative download also failed: {e2}")

        raise RuntimeError("Could not download OpenTUI library. Please install manually.")


def main():
    """Main entry point."""
    print("OpenTUI Python - Library Downloader")
    print("=" * 40)

    try:
        platform_id = get_platform()
        print(f"Detected platform: {platform_id}")

        lib_path = ensure_library()
        print(f"\nLibrary ready: {lib_path}")
        print("\nYou can now use opentui-python!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
