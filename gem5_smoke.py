import sys

import m5
from m5.objects import (
    AddrRange, Cache, DDR3_1600_8x8, MemCtrl, Process, Root, SEWorkload,
    SrcClockDomain, System, SystemXBar, VoltageDomain, X86O3CPU,
)

binary = sys.argv[1]
system = System()
system.clk_domain = SrcClockDomain(clock="2GHz", voltage_domain=VoltageDomain())
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MiB")]
system.cpu = X86O3CPU()
system.membus = SystemXBar()
system.cpu.addPrivateSplitL1Caches(
    Cache(size="32KiB", assoc=2, tag_latency=2, data_latency=2,
          response_latency=2, mshrs=4, tgts_per_mshr=8),
    Cache(size="32KiB", assoc=2, tag_latency=2, data_latency=2,
          response_latency=2, mshrs=4, tgts_per_mshr=8),
)
system.cpu.createInterruptController()
system.cpu.connectBus(system.membus)
system.system_port = system.membus.cpu_side_ports
system.mem_ctrl = MemCtrl(dram=DDR3_1600_8x8(range=system.mem_ranges[0]))
system.mem_ctrl.port = system.membus.mem_side_ports
system.workload = SEWorkload.init_compatible(binary)
system.cpu.workload = Process(cmd=[binary])
system.cpu.createThreads()
root = Root(full_system=False, system=system)
m5.instantiate()
event = m5.simulate()
if event.getCode() or event.getCause() != "exiting with last active thread context":
    raise SystemExit(f"Unexpected simulation exit: {event.getCause()}")
