# Modeling contract

This flow implements Problem 1 experiments, not a calibrated physical CPU.
No PARSEC measurements are shipped. Synthetic tests are not experiment results.
The separate `check` command uses small independent SE processes to validate
the hardware/ROI/postprocessing connection. Its `__smoke__` results are not
PARSEC measurements and do not enter the experiment sweeps below.

## Performance and ROI

- gem5 v26.0.0.0 `X86O3CPU`, one hardware thread per core.
- Core sweep: 1/4/8 at width 4. Width sweep: 2/4/8 on four cores.
- Fetch/decode/rename/dispatch/issue/writeback/commit widths change together.
  ROB=192, IQ=64, physical integer/FP registers=256 each, LQ/SQ=32 each,
  default functional-unit counts and latencies stay fixed. This is a width
  sweep, not a sweep that also enlarges every structure.
- Classic coherent private 32 KiB 8-way L1I/L1D and shared 2 MiB 16-way L2;
  the gem5 standard-library cache defaults, including L1/L2 stride prefetching,
  are retained. Page walkers connect to L2 bus; no separate walker caches.
- CPU and cache clock 2 GHz, 64-byte lines, dual-channel DDR4-2400, 3 GiB RAM.
- Full-system OS threads run on actual simulated cores; this is not several
  unrelated syscall-emulation processes. Thread count follows core count.
- One global PARSEC hooks ROI is required. Reset stats at workbegin; dump at
  workend. Boot/preparation are excluded, OS work inside the ROI is included.
  Stop at workend, so post-ROI application validation is not performed.
- Speedup = baseline ROI simulated time / current ROI simulated time, for
  each workload independently. Width baseline is **4 cores, width 2**; core
  baseline is **1 core, width 4**. Never normalize by IPC or host time.

## Power mapping

`mcpat-template.xml` comes from HewlettPackard/mcpat's Xeon.xml at commit
`74d4759f3ba2dff8f5a69e07a68efdb46b42fb8c`. See `problem1/MCPAT-LICENSE`.
It supplies the McPAT schema and physical-model defaults, not activity data.
Every template statistic is cleared, including disabled components, before
measured/derived counters are populated. Cores are explicitly enumerated with
`homogeneous_cores=0`: do not multiply core 0's activity by the core count.
The legacy McPAT parser requires positional components and lowercase `noc`
names; disabled directory/L3 placeholders are retained in its required order.

| McPAT field | Source |
|---|---|
| core widths, ROB, IQ, physical registers, queues, FU counts | gem5 config.json |
| cache capacity, associativity, MSHRs, write buffers, latency | config.json |
| predictor, BTB, RAS, TLB sizes | config.json |
| total_cycles for every core | ROI ticks / simFreq × CPU Hz |
| busy/idle cycles | active numCycles / remaining ROI cycles |
| x86 committed instructions | commitStats0.numOps (micro-ops) |
| instruction mix, branch, loads/stores | commitStats0 counters |
| ROB, IQ, wakeup, rename lookups, register-file accesses | corresponding O3 statistics |
| integer multiply/divide | issuedInstType_0::IntMult/IntDiv |
| cache activity | command-specific accesses/misses, including prefetch/writebacks |
| TLB activity | rd/wr/ex accesses and misses |
| buses | each coherent crossbar's pktCount |
| memory controller | readReqs/writeReqs across memory channels |

Strictly required missing or non-finite counters fail conversion. Fields
known to be suppressed when zero (gem5 `nozero`/`prereq`) can be zero; their
names are recorded in `mapping.json`. The parser selects only dumps whose
`simTicks` and `finalTick` match the recorded ROI, ignoring boot/shutdown dumps.

Explicit approximations / fixed physical parameters:

- 45 nm, 1.0 V, 350 K leakage reference, no power gating or long-channel mode.
  The physical parameters not represented in gem5 retain the documented Xeon
  schema defaults. Pipeline depth is modeled as 14 integer/FP stages. Fetch
  buffer bytes are converted to modeled 4-byte instruction slots.
- McPAT does not directly model every x86 vector structure: SIMD execution and
  register/IQ activity are folded into the FP model. Functional-unit counts
  are classified by `FUDesc.opList`, not Python subclass names. Physical FP
  registers remain a proxy; this is not a bit-accurate SIMD register model.
- McPAT's unified-IQ abstraction uses the configured size for its integer/FP
  fields. Rename destination writes use committed integer/FP+vector counts;
  source lookups use measured speculative counters. CDB accesses use execution
  counts. These are documented activity proxies, not independent measurements.
- Unobservable optional fields such as context_switches/conflicts are zero;
  they are never example workload counts. Peak-duty factors are 1; reported
  experiment power uses **Runtime Dynamic**, not Peak Dynamic/Peak Power.
- Cache banks=1, throughput=1 cycle, modeled latency=tag+data, output width=64;
  fill buffers use MSHR count and prefetch buffers use four entries. These
  CACTI buffer/timing abstractions are not exact gem5 queue structures.
- Crossbars are represented by two McPAT bus models at their configured byte
  width. Packet counts approximate transfers; snoop/control layout and
  multi-flit serialization are not transistor-level models.
- One dual-channel on-chip controller with PHY is modeled at DDR4-2400's
  1200 MHz interface clock, 19200 MB/s per channel, 64-bit channel data bus.
  Its circuit implementation uses McPAT's generic controller model.
- Chip boundary: cores (including L1/TLB/predictor), L2, modeled interconnect,
  on-chip memory controller/PHY. Off-chip DRAM, disks, board devices, and the
  gem5 functional platform's tiny I/O cache are excluded. This is modeled
  processor-die power, not wall-socket system power.

`Runtime Dynamic + Subthreshold Leakage + Gate Leakage` is used consistently.
L1 cache power/area is subtracted from its parent core before creating separate
blocks, preventing double counting. Component sums must agree with McPAT's
processor totals within rounding tolerance. Negative/NaN/missing values fail.

## Thermal assumptions

- One constant power sample per ROI: average-power **steady-state** temperature,
  not a transient trace or transient peak-temperature estimate.
- Each core's logic, each L1, shared L2, both buses, and controller receive their
  own nonoverlapping rectangular HotSpot block. All blocks have equal height;
  widths are chosen to preserve modeled areas, giving a square overall die.
  This deterministic strip floorplan is an architectural approximation, not
  a floorplan optimized for physical placement. Layout impacts temperature.
- Package/cooling is fixed across sweeps in `problem1/hotspot.config`:
  ambient 318.15 K (45 °C), convection resistance 0.1 K/W, 30 mm spreader,
  60 mm sink, silicon thickness 0.15 mm. Other settings are explicit or the
  pinned HotSpot defaults. If a modeled die exceeds package dimensions,
  HotSpot should fail rather than silently resize the package.
- Leakage is evaluated at fixed 350 K; no iterative temperature/leakage feedback.
- Main temperature metric is maximum chip-block steady-state Celsius; also
  emit all block temperatures and area-weighted average. Package nodes are
  excluded from these statistics.

## Upstream references used for implementation

- gem5 v26 APIs and statistic names: https://github.com/gem5/gem5/tree/v26.0.0.0
- Official PARSEC image/command and ROI workflow example:
  https://github.com/gem5/gem5/blob/v24.1.0.3/configs/example/gem5_library/x86-parsec-benchmarks.py
  (resource/guest-command reference only; this implementation uses v26 APIs).
- McPAT model/schema: https://github.com/HewlettPackard/mcpat
- HotSpot interface/thermal model: https://github.com/uvahotspot/HotSpot
