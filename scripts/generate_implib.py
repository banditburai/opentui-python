"""Generate a .lib import library from opentui.dll using MSVC tools.

Extracts extern "C" function declarations from the C++ binding source files
to build a .def file, then uses MSVC lib.exe to create the import library.
This avoids depending on dumpbin parsing (Zig DLLs may have non-standard
export table formats).
"""

import glob
import os
import re
import subprocess
import sys


def find_msvc_lib() -> str | None:
    """Locate lib.exe via vswhere + MSVC directory structure."""
    # Check if already on PATH
    try:
        subprocess.run(["lib", "/?"], capture_output=True, timeout=5)
        return "lib"
    except FileNotFoundError:
        pass

    # Use vswhere to find Visual Studio installation
    vswhere = os.path.join(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        "Microsoft Visual Studio", "Installer", "vswhere.exe",
    )
    if not os.path.isfile(vswhere):
        return None

    result = subprocess.run(
        [vswhere, "-latest", "-property", "installationPath"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None

    vs_path = result.stdout.strip()
    msvc_bin_pattern = os.path.join(
        vs_path, "VC", "Tools", "MSVC", "*", "bin", "Hostx64", "x64",
    )
    for msvc_dir in sorted(glob.glob(msvc_bin_pattern), reverse=True):
        lib_exe = os.path.join(msvc_dir, "lib.exe")
        if os.path.isfile(lib_exe):
            return lib_exe

    return None


def extract_symbols_from_source(bindings_dir: str) -> list[str]:
    """Extract function names from extern "C" blocks in C++ source files."""
    symbols: set[str] = set()

    for cpp_file in sorted(glob.glob(os.path.join(bindings_dir, "*.cpp"))):
        with open(cpp_file) as f:
            content = f.read()

        # Find all extern "C" blocks
        for match in re.finditer(r'extern\s+"C"\s*\{', content):
            start = match.end()
            # Find matching closing brace (handle nested braces)
            depth = 1
            pos = start
            while pos < len(content) and depth > 0:
                if content[pos] == "{":
                    depth += 1
                elif content[pos] == "}":
                    depth -= 1
                pos += 1
            block = content[start : pos - 1]

            # Extract function declarations (lines with return_type name(...))
            for line in block.splitlines():
                line = line.strip()
                if not line or line.startswith("//") or line.startswith("/*"):
                    continue
                # Match function declarations: [const] type [*] name(args...)
                m = re.match(r"(?:const\s+)?(?:\w+)\s*\*?\s+(\w+)\s*\(", line)
                if m:
                    symbols.add(m.group(1))

    return sorted(symbols)


def find_dll(lib_dir: str) -> str | None:
    for name in ("opentui.dll", "libopentui.dll"):
        path = os.path.join(lib_dir, name)
        if os.path.isfile(path):
            return path
    return None


def main() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lib_dir = os.path.join(project_root, "src", "opentui", "opentui-libs")
    bindings_dir = os.path.join(project_root, "src", "opentui_bindings")
    def_path = os.path.join(lib_dir, "opentui.def")
    lib_path = os.path.join(lib_dir, "opentui.lib")

    dll_path = find_dll(lib_dir)
    if not dll_path:
        print(f"No DLL found in {lib_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"DLL: {dll_path}")

    # Extract symbols from C++ source
    symbols = extract_symbols_from_source(bindings_dir)
    if not symbols:
        print("No extern C symbols found in binding source files", file=sys.stderr)
        sys.exit(1)

    # Write .def file
    with open(def_path, "w") as f:
        f.write("EXPORTS\n")
        for sym in symbols:
            f.write(f"    {sym}\n")

    print(f"Extracted {len(symbols)} symbols from source, wrote {def_path}")

    # Find lib.exe
    lib_exe = find_msvc_lib()
    if not lib_exe:
        print("Could not find MSVC lib.exe", file=sys.stderr)
        sys.exit(1)

    print(f"Using lib: {lib_exe}")

    # Generate .lib
    result = subprocess.run(
        [lib_exe, f"/DEF:{def_path}", f"/OUT:{lib_path}", "/MACHINE:X64"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"lib.exe failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Generated {lib_path}")


if __name__ == "__main__":
    main()
