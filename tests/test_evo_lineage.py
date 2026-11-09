"""v0.2-evo / #4946: the learner's verdicts land in the evo worldline with lineage.

Needs AURA_BIN (skipped otherwise). Two checks:
  * a stream with one ROLLBACK and several KEEPs writes v=2 evo:record! entries with algo=memory-policy,
    and every KEEP after the first has the previous KEEP's candidate id as its parent (the lineage chain);
  * the set-selection program (aura/evo_select.aura) selects the complementary pair on a hand-built
    matrix and records the set with its members as v=2 parents.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aura_memory.agent import run

ROOT = Path(__file__).resolve().parents[1]
NEED = unittest.skipUnless(os.environ.get("AURA_BIN") and os.environ.get("AURA_LIB"), "AURA_BIN/AURA_LIB not set")


def records(path):
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


@NEED
class LineageTest(unittest.TestCase):
    def test_keep_chain_is_parented(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "evo.jsonl"
            run("adaptive", 0, n=600,
                extra_env={"AURA_EVO_LOG": str(log), "AURA_EVO_RUN": "test-lineage"})
            recs = [r for r in records(log) if r.get("v") == 2 and r.get("kind") == "record"]
            mine = [r for r in recs if r.get("algo") == "memory-policy"]
            self.assertTrue(mine, "no memory-policy records")
            decisions = {r["decision"] for r in mine}
            self.assertIn("KEEP", decisions)
            self.assertIn("ROLLBACK", decisions)
            keeps = [r for r in mine if r["decision"] == "KEEP"]
            self.assertGreaterEqual(len(keeps), 2)
            # the first KEEP is a root; each later one names the previous KEEP's candidate id as its parent
            self.assertEqual(keeps[0]["parents"], None)
            for prev, cur in zip(keeps, keeps[1:]):
                self.assertEqual(cur["parent"], prev["candidate"])
                self.assertEqual(cur["parents"], [prev["candidate"]])
            # every KEEP carried objectives measured by the gate
            for r in keeps:
                self.assertIn("correct", r["objectives"])
                self.assertIn("size", r["objectives"])

    def test_set_selection_records_members(self):
        matrix = {
            "k": 2,
            "instances": ["a", "b", "c"],
            "candidates": [
                {"id": "P0", "genome": "g0", "note": "seed", "rows": [0.6, 0.7, 0.5]},
                {"id": "P1", "genome": "g1", "note": "recall", "rows": [0.9, 0.8, 0.4]},
                {"id": "P2", "genome": "g2", "note": "compact", "rows": [0.5, 0.6, 0.9]},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            mp, log = Path(td) / "m.json", Path(td) / "e.jsonl"
            mp.write_text(json.dumps(matrix))
            env = os.environ.copy()
            env.update({"MATRIX": str(mp), "AURA_EVO_LOG": str(log), "AURA_EVO_RUN": "test-set",
                        "AURA_SANDBOX": "off", "AURA_PIPELINE_STRICT": "0"})
            env["AURA_PATH"] = os.environ["AURA_LIB"] + ":" + env.get("AURA_PATH", "")
            p = subprocess.run([os.environ["AURA_BIN"], str(ROOT / "aura" / "evo_select.aura")],
                               cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            out = json.loads(p.stdout.strip().splitlines()[-1])
            self.assertEqual(sorted(out["selected"]), ["P1", "P2"])
            self.assertAlmostEqual(out["coverage"], 2.6, places=6)
            sets = [r for r in records(log) if r.get("candidate", "").startswith("set-k")]
            self.assertEqual(len(sets), 1)
            self.assertEqual(sets[0]["decision"], "KEEP")
            self.assertEqual(sorted(sets[0]["parents"]), sorted(out["selected"]))


if __name__ == "__main__":
    unittest.main()
