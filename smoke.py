from math import isfinite, sqrt
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

here = Path(__file__).resolve().parent
output = Path.cwd()


def run(args, log):
    try:
        with log.open("w") as stream:
            result = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
    except subprocess.TimeoutExpired as error:
        raise SystemExit(f"Timed out: {args[0]}. See {log}.") from error
    report = log.read_text()
    if result.returncode:
        raise SystemExit(f"Failed: {args[0]}. See {log}.\n{report[-2000:]}")
    return report


run(["gcc", "-nostdlib", "-static", "-o", str(output / "loop"), str(here / "smoke.S")],
    output / "gcc.log")
run(["/opt/gem5/build/X86/gem5.opt", "-d", str(output / "gem5"),
     str(here / "gem5_smoke.py"), str(output / "loop")], output / "gem5.log")

stats = (output / "gem5/stats.txt").read_text()


def count(name):
    match = re.search(rf"^{re.escape(name)}\s+(\d+)\s", stats, re.MULTILINE)
    if not match or int(match[1]) <= 0:
        raise SystemExit(f"Missing or invalid gem5 counter: {name}")
    return match[1]


# Use the small ARM fixture to check transport of the two counters.
xml = ET.parse("/opt/mcpat/ProcessorDescriptionFiles/ARM_A9_2GHz.xml")
system = xml.find(".//component[@id='system']")
core = system.find("component[@id='system.core0']")
cycles = count("system.cpu.numCycles")
instructions = count("simInsts")
for component, field, value in [
    (system, "total_cycles", cycles),
    (core, "total_cycles", cycles),
    (core, "total_instructions", instructions),
    (core, "committed_instructions", instructions),
]:
    node = component.find(f"stat[@name='{field}']")
    if node is None:
        raise SystemExit(f"Missing McPAT field: {field}")
    node.set("value", value)

mcpat_input = output / "mcpat.xml"
xml.write(mcpat_input, encoding="utf-8", xml_declaration=True)
report = run(["/opt/mcpat/mcpat", "-infile", str(mcpat_input), "-print_level", "1"],
             output / "mcpat.log")
summary = re.search(r"^Processor:[ \t]*\n((?:[^\n]+\n)+)", report, re.MULTILINE)
if summary is None:
    raise SystemExit("Missing McPAT processor summary.")


def metric(name, unit):
    match = re.search(rf"^\s*{re.escape(name)}\s*=\s*(\S+)\s+{unit}\s*$",
                      summary[1], re.MULTILINE)
    if not match or not isfinite(float(match[1])) or float(match[1]) < 0:
        raise SystemExit(f"Missing or invalid McPAT metric: {name}")
    return float(match[1])


power = sum(metric(name, "W") for name in
            ("Runtime Dynamic", "Subthreshold Leakage", "Gate Leakage"))
side = sqrt(metric("Area", r"mm\^2")) / 1000
if side <= 0 or power <= 0:
    raise SystemExit("McPAT must produce positive area and power.")

floorplan = output / "chip.flp"
trace = output / "chip.ptrace"
steady = output / "chip.steady"
floorplan.write_text(f"chip\t{side:.12g}\t{side:.12g}\t0\t0\n")
trace.write_text(f"chip\n{power:.12g}\n")
steady.unlink(missing_ok=True)
run(["/opt/HotSpot/hotspot", "-model_type", "block", "-f", str(floorplan),
     "-p", str(trace), "-steady_file", str(steady)], output / "hotspot.log")
match = re.search(r"^chip\s+(\S+)", steady.read_text(), re.MULTILINE)
if not match or not isfinite(float(match[1])):
    raise SystemExit("Missing HotSpot steady-state chip temperature.")
print(f"Smoke test: gem5 {cycles} cycles, McPAT {power:.3f} W, "
      f"HotSpot {float(match[1]) - 273.15:.2f} °C (sample model)")
