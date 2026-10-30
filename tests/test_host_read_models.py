import json
import os
from pathlib import Path
import re
import tempfile
import unittest

from adapters import host_read_models as hrm

ROOT = Path(__file__).resolve().parent.parent


def clock():
    return 1_800_000_000


class HostReadModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.paths = hrm.HostPaths(state=str(base / "state"), sessions=str(base / "sessions"), codex_pool=str(base / "pool"),
                                   jobs_glob=str(base / "jobs" / "*" / "conductor" / "state.json"), cstack_state=str(base / "ak"))
        self.base = base

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = self.base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def test_gpu_queue_lanes_from_ticket_names(self):
        self.write("state/gpu-queue/0-1700000000000000000-1.ticket", json.dumps({"name": "a", "est": 60}))
        self.write("state/gpu-queue/1-1700000000500000000-2.ticket", json.dumps({"name": "b", "est": 900}))
        self.write("state/gpu-queue/history.jsonl", json.dumps({"lane": "long", "ran": 5, "rc": 0}) + "\n")
        p = hrm.gpu_queue(self.paths, clock)
        self.assertEqual((p.summary["short"], p.summary["long"]), (1, 1))
        self.assertEqual(p.confidence.level, "complete")

    def test_capacity_absent_file_means_full(self):
        self.assertEqual(hrm.capacity(self.paths, clock).summary, {"percent": 100, "draining": None})
        self.write("state/fleet/CAPACITY", "40 reboot\n")
        self.write("state/fleet/DRAIN", "maintenance\n")
        self.assertEqual(hrm.capacity(self.paths, clock).summary, {"percent": 40, "draining": "maintenance"})

    def test_session_files_yield_counts_only(self):
        secret = "PROMPT TEXT THAT MUST NOT LEAK"
        self.write("sessions/a/b/local_1.json", json.dumps({"title": secret, "scratchPromptRecents": [secret], "isArchived": False,
                                                            "lastActivityAt": clock() * 1000 - 1000,
                                                            "postTurnSummary": {"status_category": "blocked"}}))
        p = hrm.agent_sessions(self.paths, clock)
        self.assertEqual(p.summary, {"total": 1, "live": 1, "blocked": 1, "review_ready": 0})
        self.assertNotIn(secret, json.dumps(p.to_dict()))

    def test_codex_pool_reports_only_future_cooldowns(self):
        self.write("pool/cooldown/acct1", str((clock() + 60) * 1000))
        self.write("pool/cooldown/acct2", str((clock() - 60) * 1000))
        self.assertEqual(hrm.codex_pool(self.paths, clock).summary["cooling_until"], {"acct1": clock() + 60})

    def test_missing_poodo_root_is_partial_with_reason(self):
        p = hrm.poodo_state(self.paths, clock)
        self.assertEqual(p.confidence.level, "partial")
        self.assertIn("no POODO state root", p.confidence.reason)

    def test_conductor_job_counts_atoms(self):
        self.write("jobs/j1/conductor/state.json", json.dumps({"job": "j1", "phase": "streaming", "atoms": {
            "a": {"status": "launched", "lane": {"engine": "codex"}}, "b": {"status": "locked"}}}))
        row = hrm.conductor_jobs(self.paths, clock).rows[0]
        self.assertEqual((row["job"], row["atoms"], row["engines"]), ("j1", {"launched": 1, "locked": 1}, ["codex"]))

    def test_a_failing_source_becomes_a_stale_projection(self):
        def broken(argv, timeout=5.0):
            raise TimeoutError("slow")
        out = {p.name: p for p in hrm.project_all(self.paths, clock, broken)}
        self.assertEqual(out["workers"].confidence.level, "stale")
        self.assertIn("TimeoutError", out["workers"].confidence.reason)
        self.assertEqual(out["capacity"].confidence.level, "complete")

    def fake_proc(self):
        """A /proc with two processes and a meminfo, and a heavy.slice with one scope."""
        self.write("proc/loadavg", "13.25 17.7 15.3 10/4757 1\n")
        self.write("proc/meminfo", "MemTotal: 130000000 kB\nMemAvailable: 70000000 kB\nSwapTotal: 10000000 kB\nSwapFree: 4000000 kB\n")
        self.write("proc/101/comm", "blender\n"); self.write("proc/101/statm", "100 262144 0\n")
        self.write("proc/102/comm", "claude\n"); self.write("proc/102/statm", "100 131072 0\n")
        self.write("proc/102/cmdline", "claude\0SECRET PROMPT\0")
        self.write("heavy/heavy-mid-pipegen-7.scope/cgroup.procs", "101\n")
        self.write("heavy/heavy-mid-pipegen-7.scope/memory.current", str(2 * 1024 ** 3))
        return hrm.HostPaths(state=str(self.base / "state"), proc=str(self.base / "proc"), heavy_cgroup=str(self.base / "heavy"),
                             mounts=("/",))

    @staticmethod
    def smi(argv, timeout=5.0):
        if "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw" in argv:
            return "NVIDIA GeForce RTX 4080, 53, 9216, 16376, 47, 157.2\n"
        if "--query-compute-apps=pid,used_memory" in argv:
            return "101, 8396\n"
        if argv[1:] == ["-q", "-d", "MEMORY"]:
            return "FB Memory Usage\n    Total : 16376 MiB\nBAR1 Memory Usage\n    Total : 16384 MiB\n    Used : 56 MiB\n    Free : 16328 MiB\n"
        raise AssertionError(argv)

    def test_host_resources_reads_load_memory_gpu_and_disk(self):
        p = hrm.host_resources(self.fake_proc(), clock, self.smi)
        s = p.summary
        self.assertEqual(s["load"], [13.2, 17.7, 15.3])
        self.assertEqual(s["mem_gib"]["total"], round(130000000 * 1024 / 1024 ** 3, 1))
        self.assertEqual(s["swap_gib"]["used"], round(6000000 * 1024 / 1024 ** 3, 1))
        self.assertEqual((s["gpus"][0]["util"], s["gpus"][0]["vram_gib"]["used"], s["gpus"][0]["bar1_mib"]), (53, 9.0, {"used": 56, "total": 16384}))
        self.assertEqual([d["mount"] for d in s["disks"]], ["/"])
        self.assertEqual(p.confidence.level, "complete")

    def test_host_resources_without_a_gpu_is_partial(self):
        def no_smi(argv, timeout=5.0):
            raise FileNotFoundError("nvidia-smi")
        p = hrm.host_resources(self.fake_proc(), clock, no_smi)
        self.assertEqual((p.summary["gpus"], p.confidence.level), ([], "partial"))

    def test_running_work_names_jobs_and_families_never_arguments(self):
        p = hrm.running_work(self.fake_proc(), clock, self.smi)
        self.assertEqual(p.summary["heavy_jobs"], [{"unit": "heavy-mid-pipegen-7", "commands": ["blender"], "mem_gib": 2.0}])
        self.assertEqual(p.summary["gpu_processes"], [{"pid": 101, "command": "blender", "vram_gib": 8.2}])
        self.assertEqual(p.summary["families"]["Claude Code"]["processes"], 1)
        self.assertNotIn("SECRET", json.dumps(p.to_dict()))

    def test_gpu_queue_tells_running_from_waiting(self):
        paths = self.fake_proc()
        self.write("state/gpu-queue/2-1700000000000000000-101.ticket", json.dumps({"name": "render"}))
        self.write("state/gpu-queue/2-1700000001000000000-102.ticket", json.dumps({"name": "next"}))
        self.write("proc/101/task/101/children", "555 ")          # the waiter launched its job
        self.write("proc/102/task/102/children", "")
        s = hrm.gpu_queue(paths, clock).summary
        self.assertEqual((s["running"], s["waiting"]), (1, 1))
        self.assertEqual(s["jobs"], [{"name": "render", "state": "running"}, {"name": "next", "state": "waiting"}])

    def test_runner_refuses_commands_off_the_read_list(self):
        for argv in (["codex-pool", "status"], ["gpu-queue.py", "--stats"], ["sh", "-c", "true"]):
            with self.assertRaises(PermissionError):
                hrm.run_read(argv)

    def test_module_opens_nothing_for_writing(self):
        src = (ROOT / "adapters" / "host_read_models.py").read_text()
        self.assertFalse(re.search(r"open\([^)]*[\"'][wax+]", src))
        self.assertNotIn("--stats", src.replace('"--stats"', "").replace("`--stats`", "").replace("--stats` (it deletes", ""))
        for word in ("unlink", "rmtree", "os.remove", ".write("):
            self.assertNotIn(word, src)


if __name__ == "__main__":
    unittest.main()
