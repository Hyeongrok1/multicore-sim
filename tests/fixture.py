"""Synthetic v26 config/stat schema, NOT measured PARSEC experiment results."""
from problem1.model import Configuration


def fixture(cores=4, width=4):
    cfg = Configuration(cores, width)
    manifest = {"schema": 1, "configuration": cfg.to_dict(), "workload": "blackscholes", "input": "simsmall",
                "roi": {"begin_tick": 500000, "end_tick": 1500000}, "cpu_paths": [],
                "l1i_paths": [], "l1d_paths": [], "l2_path": "board.cache_hierarchy.l2cache",
                "bus_paths": ["board.cache_hierarchy.l2bus", "board.cache_hierarchy.membus"],
                "memory_paths": ["board.memory.mem_ctrls0", "board.memory.mem_ctrls1"]}
    config = {"children": []}
    stats = {"simTicks": 1000000, "finalTick": 1500000, "simFreq": 1e12}

    def cache(path, size, assoc, latency):
        config["children"].append({"type": "Cache", "path": path, "size": size,
                                    "assoc": assoc, "tag_latency": latency, "data_latency": latency,
                                    "mshrs": 20, "write_buffers": 8})
        stats.update({path+".ReadReq.accesses::total": 100, path+".ReadReq.misses::total": 5,
                      path+".WriteReq.accesses::total": 40, path+".WriteReq.misses::total": 2,
                      path+".WritebackDirty.accesses::total": 10})

    for i in range(cores):
        p = f"board.processor.cores{i}.core"
        manifest["cpu_paths"].append(p)
        cpu = {"type": "X86O3CPU", "path": p, "numROBEntries": 192, "numPhysIntRegs": 256,
               "numPhysFloatRegs": 256, "LQEntries": 32, "SQEntries": 32,
               "fetchBufferSize": 64, "fetchQueueSize": 32,
               "instQueues": [{"numEntries": 64, "fuPool": {"FUList": [
                   {"type": "FUDesc", "count": n, "opList": [{"opClass": op} for op in ops]}
                   for ops, n in ((("IntAlu",), 6), (("IntMult", "IntDiv"), 2),
                   (("FloatAdd",), 4), (("FloatMult",), 2), (("SimdAdd",), 4),
                   (("MemRead", "MemWrite"), 4))]}}],
               "branchPred": {"type": "BranchPredictor", "conditionalBranchPred": {
                   "type": "TournamentBP", "localPredictorSize": 2048, "localCtrBits": 2,
                   "localHistoryTableSize": 2048, "globalPredictorSize": 8192, "globalCtrBits": 2,
                   "choicePredictorSize": 8192, "choiceCtrBits": 2},
                   "ras": {"numEntries": 16}, "btb": {"numEntries": 4096, "associativity": 1}},
               "mmu": {}}
        for field in ("fetchWidth", "decodeWidth", "renameWidth", "dispatchWidth", "issueWidth", "wbWidth", "commitWidth"):
            cpu[field] = width
        for name in ("itb", "dtb"):
            path = p+".mmu."+name
            cpu["mmu"][name] = {"path": path, "size": 64}
            for op in ("rd", "wr", "ex"):
                stats[path+"."+op+"Accesses"] = 100
                stats[path+"."+op+"Misses"] = 2
        config["children"].append(cpu)
        values = {"numCycles": 1000-i*50, "commitStats0.numInsts": 500+i*10,
                  "commitStats0.numOps": 600+i*20, "commitStats0.numIntInsts": 400,
                  "commitStats0.numFpInsts": 70, "commitStats0.numVecInsts": 10,
                  "commitStats0.numLoadInsts": 80, "commitStats0.numStoreInsts": 40,
                  "commitStats0.functionCalls": 5, "commitStats0.committedControl::IsControl": 30,
                  "rob.reads": 600, "rob.writes": 650,
                  "rename.intLookups": 800, "rename.fpLookups": 120, "rename.vecLookups": 20,
                  "intInstQueueReads": 600, "intInstQueueWrites": 650, "intInstQueueWakeupAccesses": 900,
                  "fpInstQueueReads": 70, "fpInstQueueWrites": 75, "fpInstQueueWakeupAccesses": 80,
                  "vecInstQueueReads": 10, "vecInstQueueWrites": 12, "vecInstQueueWakeupAccesses": 15,
                  "intAluAccesses": 450, "fpAluAccesses": 70, "vecAluAccesses": 10,
                  "issuedInstType_0::IntMult": 20, "issuedInstType_0::IntDiv": 5,
                  "branchPred.BTBLookups": 50, "branchPred.BTBUpdates": 8}
        stats.update({p+"."+k: v for k, v in values.items()})
        for prefix in ("l1i", "l1d"):
            path = f"board.cache_hierarchy.{prefix}caches{i}"
            manifest[prefix+"_paths"].append(path)
            cache(path, 32768, 8, 1)
    cache(manifest["l2_path"], 2097152, 16, 10)
    for p in manifest["bus_paths"]:
        config["children"].append({"type": "CoherentXBar", "path": p, "width": 32})
        stats[p+".pktCount::total"] = 300
    for p in manifest["memory_paths"]:
        stats[p+".readReqs"] = 10
        stats[p+".writeReqs"] = 4
    text = "---------- Begin Simulation Statistics ----------\n"
    text += "\n".join(f"{k} {v}" for k, v in stats.items())
    text += "\n---------- End Simulation Statistics   ----------\n"
    return config, manifest, text


def report(cores=4):
    # Each core = logic (2mm², 2W) + two L1 caches (0.5mm², 0.5W each).
    # All components have 80% dynamic, 10% subthreshold, 10% gate leakage.
    def section(label, area, power, indent=0):
        return (" "*indent + label + "\n" + f"  Area = {area} mm^2\n"
                f"  Runtime Dynamic = {power*.8} W\n  Subthreshold Leakage = {power*.1} W\n"
                f"  Gate Leakage = {power*.1} W\n\n")
    text = section("Processor:", cores*3+4, cores*3+4)
    for i in range(cores):
        text += section("Core:", 3, 3)
        text += section("Instruction Cache:", .5, .5, 8)
        text += section("Data Cache:", .5, .5, 8)
    text += section("L2", 2, 2)
    text += section("BUSES", .5, .5) * 2
    text += section("Memory Controller:", 1, 1)
    return text
