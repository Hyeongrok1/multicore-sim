import copy
import math
import unittest
from problem1.model import WORKLOADS, configurations, guest_command
from problem1.stats import Stats
from problem1.mcpat import convert
from problem1.thermal import parse_report, floorplan, temperatures
from problem1.run import normalized_rows
from tests.fixture import fixture, report


class FlowTests(unittest.TestCase):
    def test_matrix_and_guest(self):
        self.assertEqual(len(configurations())*len(WORKLOADS), 20)
        self.assertEqual({c.key for c in configurations()}, {"c1-w4", "c4-w4", "c8-w4", "c4-w2", "c4-w8"})
        for workload in WORKLOADS:
            command = guest_command(workload, 8)
            self.assertIn("-i simsmall -n 8", command)
            self.assertIn("OMP_NUM_THREADS=8", command)
            self.assertIn("gcc-hooks", command)

    def test_each_configuration_maps_real_activity(self):
        for c in configurations():
            config, manifest, text = fixture(c.cores, c.width)
            tree, audit = convert(config, manifest, text)
            system = tree.find(".//component[@id='system']")
            cores = [x for x in system.findall("component") if x.get("id").startswith("system.core")]
            self.assertEqual(len(cores), c.cores)
            self.assertAlmostEqual(audit["roi_seconds"], 1e-6)
            self.assertEqual(audit["roi_cycles"], 2000)
            for i, core in enumerate(cores):
                value = lambda name: float(core.find(f"stat[@name='{name}']").get("value"))
                self.assertEqual(value("committed_instructions"), 600+i*20)
                self.assertEqual(value("total_cycles"), 2000)  # includes idle time
                self.assertEqual(value("ROB_reads"), 600)
                self.assertEqual(value("mul_accesses"), 25)  # actual v26 2D naming
                self.assertEqual(value("context_switches"), 0)  # seed value cleared
                self.assertEqual(value("branch_instructions"), 30)
                self.assertEqual(core.find("param[@name='issue_width']").get("value"), str(c.width))
            l2 = tree.find(".//component[@id='system.L20']")
            self.assertEqual(float(l2.find("stat[@name='write_accesses']").get("value")), 50)
            self.assertEqual(tree.find(".//component[@id='system.NoC0']").get("name"), "noc0")
            self.assertEqual(float(cores[0].find("param[@name='ALU_per_core']").get("value")), 6)
            order = [x.get("id") for x in system.findall("component")]
            self.assertLess(order.index("system.NoC1"), order.index("system.mc"))

    def test_roi_dump_selection_and_missing_stat_fail(self):
        config, manifest, text = fixture()
        boot = text.replace("simTicks 1000000", "simTicks 500000").replace("finalTick 1500000", "finalTick 500000")
        first = text.replace("simFreq 1000000000000.0", "simFreq 1000000000000.0\nhostSeconds 10")
        duplicate = first.replace("hostSeconds 10", "hostSeconds 11")
        stats = Stats.roi(boot+first+duplicate, manifest["roi"])
        self.assertEqual(stats.get("simTicks"), 1000000)
        with self.assertRaisesRegex(ValueError, "No statistics block"):
            Stats.roi(boot, manifest["roi"])
        broken = text.replace("board.processor.cores0.core.rob.reads 600\n", "")
        with self.assertRaisesRegex(ValueError, "Required.*rob.reads"):
            convert(config, manifest, broken)
        config["children"][0]["issueWidth"] = 8
        with self.assertRaisesRegex(ValueError, "does not match"):
            convert(config, manifest, text)

    def test_power_no_double_count_and_geometry(self):
        power = parse_report(report(), 4)
        self.assertEqual(len(power["blocks"]), 16)
        self.assertAlmostEqual(sum(x["power_w"] for x in power["blocks"]), 16)
        flp, trace = floorplan(power)
        x_end = 0
        area = 0
        for line in flp.splitlines():
            _, width, height, x, y = line.split()
            width, height, x, y = map(float, (width, height, x, y))
            self.assertAlmostEqual(x, x_end, places=10)
            self.assertEqual(y, 0)
            area += width*height
            x_end = x+width
        self.assertAlmostEqual(area*1e6, 16)
        self.assertEqual(len(trace.splitlines()[0].split()), 16)
        steady = "\n".join(f"{b['name']} 350" for b in power["blocks"])
        thermal = temperatures(steady+"\nspreader 999\n", power)
        self.assertAlmostEqual(thermal["peak_c"], 76.85)
        with self.assertRaises(ValueError):
            temperatures("core0 nan\n", power)
        with self.assertRaisesRegex(ValueError, "component sum mismatch"):
            parse_report(report().replace("Area = 16 mm^2", "Area = 20 mm^2"), 4)

    def test_unused_rename_classes_are_zero_suppressed(self):
        config, manifest, text = fixture()
        text = "\n".join(line for line in text.splitlines()
                         if ".rename.fpLookups " not in line and ".rename.vecLookups " not in line)
        tree, audit = convert(config, manifest, text)
        for index in range(manifest["configuration"]["cores"]):
            core = tree.find(f".//component[@id='system.core{index}']")
            self.assertEqual(float(core.find("stat[@name='fp_rename_reads']").get("value")), 0)
        self.assertTrue(any(key.endswith("rename.fpLookups") for key in audit["zero_suppressed_stats"]))

    def test_normalization_is_per_sweep_and_workload(self):
        results = []
        for w in WORKLOADS:
            for c in configurations():
                results.append({"workload": w, "configuration": c.to_dict(),
                                "roi_seconds": 100/(c.cores*c.width),
                                "power": {"processor": {"power_w": 10, "dynamic_w": 8, "static_w": 2}},
                                "temperature": {"peak_c": 80, "area_weighted_c": 70}})
        rows = normalized_rows(results)
        self.assertEqual(len(rows), 24)  # common baseline reused in two sweeps
        for r in rows:
            self.assertEqual(r["speedup"], r["cores"] if r["sweep"] == "cores" else r["width"]/2)
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            normalized_rows(results[:-1])


if __name__ == "__main__":
    unittest.main()
