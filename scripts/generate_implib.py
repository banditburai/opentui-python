"""Generate a .lib import library from opentui.dll using MSVC tools.

Run after download_opentui.py on Windows. Requires Visual Studio (dumpbin, lib).
Uses vswhere to locate the MSVC toolchain when tools aren't on PATH.
"""

import glob
import os
import re
import subprocess
import sys


def find_msvc_tools() -> dict[str, str]:
    """Locate dumpbin.exe and lib.exe via vswhere + MSVC directory structure."""
    tools: dict[str, str] = {}

    # Check if already on PATH
    for tool in ("dumpbin", "lib"):
        try:
            subprocess.run([tool], capture_output=True, timeout=5)
            tools[tool] = tool
        except FileNotFoundError:
            pass

    if len(tools) == 2:
        return tools

    # Use vswhere to find Visual Studio installation
    vswhere = os.path.join(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        "Microsoft Visual Studio", "Installer", "vswhere.exe",
    )
    if not os.path.isfile(vswhere):
        return tools

    result = subprocess.run(
        [vswhere, "-latest", "-property", "installationPath"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return tools

    vs_path = result.stdout.strip()
    # Find the latest MSVC toolset under VC/Tools/MSVC/*/bin/Hostx64/x64/
    msvc_bin_pattern = os.path.join(
        vs_path, "VC", "Tools", "MSVC", "*", "bin", "Hostx64", "x64",
    )
    msvc_dirs = sorted(glob.glob(msvc_bin_pattern), reverse=True)
    for msvc_dir in msvc_dirs:
        dumpbin = os.path.join(msvc_dir, "dumpbin.exe")
        lib_exe = os.path.join(msvc_dir, "lib.exe")
        if os.path.isfile(dumpbin) and os.path.isfile(lib_exe):
            tools["dumpbin"] = dumpbin
            tools["lib"] = lib_exe
            break

    return tools


def find_dll(lib_dir: str) -> str | None:
    for name in ("opentui.dll", "libopentui.dll"):
        path = os.path.join(lib_dir, name)
        if os.path.isfile(path):
            return path
    return None


def generate_implib(dll_path: str, lib_dir: str) -> None:
    def_path = os.path.join(lib_dir, "opentui.def")
    lib_path = os.path.join(lib_dir, "opentui.lib")

    tools = find_msvc_tools()
    if "dumpbin" not in tools or "lib" not in tools:
        print("Could not find MSVC dumpbin/lib tools", file=sys.stderr)
        print("Ensure Visual Studio with C++ workload is installed", file=sys.stderr)
        sys.exit(1)

    print(f"Using dumpbin: {tools['dumpbin']}")
    print(f"Using lib: {tools['lib']}")

    # Extract exports with dumpbin
    result = subprocess.run(
        [tools["dumpbin"], "/EXPORTS", dll_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"dumpbin failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Parse export names from dumpbin output
    symbols: list[str] = []
    in_exports = False
    for line in result.stdout.splitlines():
        if re.match(r"\s+ordinal\s+hint\s+RVA\s+name", line):
            in_exports = True
            continue
        if in_exports:
            if not line.strip():
                break
            m = re.match(r"\s+\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\S+)", line)
            if m:
                symbols.append(m.group(1))

    if not symbols:
        print("No exports found in DLL", file=sys.stderr)
        sys.exit(1)

    # Write .def file
    with open(def_path, "w") as f:
        f.write("EXPORTS\n")
        for sym in symbols:
            f.write(f"    {sym}\n")

    print(f"Found {len(symbols)} exports, wrote {def_path}")

    # Generate .lib
    result = subprocess.run(
        [tools["lib"], f"/DEF:{def_path}", f"/OUT:{lib_path}", "/MACHINE:X64"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"lib failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Generated {lib_path}")


def main() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lib_dir = os.path.join(project_root, "src", "opentui", "opentui-libs")

    dll_path = find_dll(lib_dir)
    if not dll_path:
        print(f"No DLL found in {lib_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Generating import library from {dll_path}")
    generate_implib(dll_path, lib_dir)


if __name__ == "__main__":
    main()
