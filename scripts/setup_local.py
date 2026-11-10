#!/usr/bin/env python3
"""Build pinned native tools and save their paths; no sudo or Docker required.

Install OS compiler/Python development dependencies first (see LOCAL.md).
Existing source directories are reused only when their HEAD matches the pin.
Build outputs stay in those source directories and are reused by make/SCons.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "gem5": ("https://github.com/gem5/gem5.git", "v26.0.0.0", "fed0e07e930fecf1e73dce94dd44e69a5bf70c46"),
    "mcpat": ("https://github.com/HewlettPackard/mcpat.git", None, "74d4759f3ba2dff8f5a69e07a68efdb46b42fb8c"),
    "hotspot": ("https://github.com/uvahotspot/HotSpot.git", None, "f18831e48cef5d62580585cca0d7fab6c71bc3cc"),
}


def run(command, cwd=None, env=None):
    print("+", " ".join(map(str, command)), flush=True)
    subprocess.run([str(x) for x in command], cwd=cwd, env=env, check=True)


def source(name, path):
    url, tag, sha = PINS[name]
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone"] + (["--depth", "1", "--branch", tag] if tag else []) + [url, path])
        if not tag:
            run(["git", "checkout", "--detach", sha], cwd=path)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    if actual != sha:
        raise RuntimeError(f"{name}: expected {sha}, found {actual}; refusing to reset existing sources")
    return path


def mcpat_clang_fix(path):
    # Upstream places a default argument on an out-of-class constructor
    # definition. Move it to the declaration for modern Clang; no model change.
    cpp, header = path / "cacti/nuca.cc", path / "cacti/nuca.h"
    text = cpp.read_text()
    declaration = header.read_text()
    old = "TechnologyParameter::DeviceType *dt = &(g_tp.peri_global)"
    if old in text:
        cpp.write_text(text.replace(old, "TechnologyParameter::DeviceType *dt", 1))
    if "TechnologyParameter::DeviceType *dt);" in declaration:
        header.write_text(declaration.replace("TechnologyParameter::DeviceType *dt);",
                          "TechnologyParameter::DeviceType *dt = &(g_tp.peri_global));", 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=ROOT / ".tools")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--python-config")
    for name in PINS:
        parser.add_argument(f"--{name}-source", type=Path)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if platform.system() not in ("Darwin", "Linux"):
        parser.error("Use macOS, Linux, or Ubuntu under WSL2")
    for program in ("git", "make", "m4"):
        if not shutil.which(program):
            parser.error(f"Missing {program}; install dependencies from LOCAL.md")
    try:
        import SCons  # noqa: F401
    except ImportError:
        parser.error("Install requirements-local.txt in this Python environment first")
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    py_config = args.python_config or shutil.which(f"python{version}-config")
    if not py_config:
        parser.error(f"Missing python{version}-config; install matching Python development headers")
    paths = {n: source(n, (getattr(args, n + "_source") or args.prefix / n).resolve()) for n in PINS}
    env = os.environ.copy()
    env["PYTHON_CONFIG"] = str(Path(py_config).resolve())
    if platform.system() == "Darwin":
        # Apple Clang's SDK and linker agree with the system C++ runtime.
        env.setdefault("CC", "/usr/bin/clang")
        env.setdefault("CXX", "/usr/bin/clang++")
    else:
        env.setdefault("CC", "gcc")
        env.setdefault("CXX", "g++")
    # PYTHON_CONFIG/CC/CXX are environment variables in gem5 v26, not SCons
    # command-line assignments. Passing assignments silently selects defaults.
    run([sys.executable, "-m", "SCons", "build/X86/gem5.opt", f"-j{args.jobs}", "--ignore-style"],
        cwd=paths["gem5"], env=env)
    mcpat_clang_fix(paths["mcpat"])
    # Native 64-bit build: omit upstream's hardcoded -m32 and x86-only SSE flags.
    flags = "-O2 -DNTHREADS=1 -Icacti -Wno-deprecated-register"
    marker = paths["mcpat"] / ".native-build-settings.json"
    settings = json.dumps({"CC": env["CC"], "CXX": env["CXX"], "flags": flags,
                           "host": platform.machine()}, sort_keys=True)
    # Make does not track compiler-option changes; discard incompatible objects.
    if not marker.is_file() or marker.read_text() != settings:
        run(["make", "clean_opt"], cwd=paths["mcpat"])
    run(["make", f"-j{args.jobs}", f"CC={env['CC']}", f"CXX={env['CXX']}",
         f"CXXFLAGS={flags}"], cwd=paths["mcpat"])
    marker.write_text(settings)
    run(["make", f"-j{args.jobs}", "hotspot", f"CC={env['CC']}"], cwd=paths["hotspot"])
    tools = {"gem5": str(paths["gem5"] / "build/X86/gem5.opt"),
             "mcpat": str(paths["mcpat"] / "mcpat"), "hotspot": str(paths["hotspot"] / "hotspot"),
             "source_commits": {n: p[2] for n, p in PINS.items()},
             "host": f"{platform.system()} {platform.machine()}"}
    (ROOT / ".local-tools.json").write_text(json.dumps(tools, indent=2) + "\n")
    print("Tools registered. Run: python -m problem1.run check --output local-check", flush=True)


if __name__ == "__main__":
    main()
