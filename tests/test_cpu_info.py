from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "components"
    / "nanoos-cpu-info"
    / "nanoos_cpu_info.py"
)
SPEC = importlib.util.spec_from_file_location("nanoos_cpu_info", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
cpu_info = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cpu_info)


class ParseCpuInfoTests(unittest.TestCase):
    def test_parses_amd_cpu_block(self) -> None:
        sample = """processor : 0
vendor_id : AuthenticAMD
cpu family : 26
model : 68
model name : AMD Ryzen 9 Example
stepping : 1
flags : fpu sse sse2 avx2 avx512f

processor : 1
vendor_id : AuthenticAMD
model name : AMD Ryzen 9 Example
"""
        result = cpu_info.parse_cpuinfo(sample)
        self.assertEqual(result["vendor_id"], "AuthenticAMD")
        self.assertEqual(result["model_name"], "AMD Ryzen 9 Example")
        self.assertEqual(result["family"], "26")
        self.assertIn("avx512f", result["flags"])

    def test_empty_cpuinfo_is_safe(self) -> None:
        result = cpu_info.parse_cpuinfo("")
        self.assertIsNone(result["vendor_id"])
        self.assertIsNone(result["model_name"])
        self.assertEqual(result["flags"], [])


class SnapshotTests(unittest.TestCase):
    def test_reads_fake_policy_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cpuinfo = root / "cpuinfo"
            cpuinfo.write_text(
                "processor : 0\nvendor_id : AuthenticAMD\n"
                "model name : Test CPU\nflags : sse avx2\n",
                encoding="utf-8",
            )
            cpufreq = root / "cpufreq"
            policy = cpufreq / "policy0"
            policy.mkdir(parents=True)
            (policy / "scaling_driver").write_text("amd-pstate-epp\n", encoding="utf-8")
            (policy / "scaling_governor").write_text("powersave\n", encoding="utf-8")
            (policy / "scaling_available_governors").write_text(
                "powersave performance\n", encoding="utf-8"
            )
            (policy / "energy_performance_preference").write_text(
                "balance_performance\n", encoding="utf-8"
            )
            (policy / "energy_performance_available_preferences").write_text(
                "default performance balance_performance balance_power power\n",
                encoding="utf-8",
            )

            snapshot = cpu_info.collect_snapshot(cpuinfo, cpufreq)
            self.assertEqual(snapshot["cpu"]["model_name"], "Test CPU")
            self.assertEqual(snapshot["cpufreq"]["policy_count"], 1)
            self.assertTrue(snapshot["cpufreq"]["any_epp_available"])
            self.assertFalse(snapshot["access"]["writes_sysfs"])

    def test_missing_sysfs_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cpuinfo = root / "missing-cpuinfo"
            cpufreq = root / "missing-cpufreq"
            snapshot = cpu_info.collect_snapshot(cpuinfo, cpufreq)
            self.assertEqual(snapshot["cpufreq"]["policy_count"], 0)
            self.assertFalse(snapshot["cpufreq"]["any_epp_available"])


if __name__ == "__main__":
    unittest.main()
