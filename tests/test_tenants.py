"""Multi-tenant server (R12): interleaved tenants must reply exactly like one dedicated server per stream."""
import os
import unittest

from aura_memory.control import AuraMemory
from aura_memory.tenants import TenantView, check, run_tenants

NEED = unittest.skipUnless(os.environ.get("AURA_BIN"), "AURA_BIN not set")


@NEED
class TenantTest(unittest.TestCase):
    def test_interleaved_equals_dedicated(self):
        for order in ("rr", "random"):
            m = run_tenants("adaptive", [0, 1, 2], n=300, order=order, order_seed=7)
            self.assertTrue(any(r["verdicts"] for r in m["results"].values()), "no learner verdict to compare")
            c = check("adaptive", [0, 1, 2], 300, 0.0, m)
            self.assertEqual(c["diffs"], {0: [], 1: [], 2: []}, order)

    def test_isolation_and_default_tenant(self):
        shared = AuraMemory(policy="seed", learn=True, min_evidence=1)
        shared.cur = ""
        try:
            a, b, root = TenantView(shared, "a"), TenantView(shared, "b"), TenantView(shared, "")
            a.obs("user.theme", "dark", "pref", "user")
            b.obs("user.theme", "light", "pref", "user")
            root.obs("user.theme", "solarized", "pref", "user")
            self.assertEqual(a.query("user.theme", "pref")["answer"], "dark")
            self.assertEqual(b.query("user.theme", "pref")["answer"], "light")
            self.assertEqual(root.query("user.theme", "pref")["answer"], "solarized")
            self.assertEqual([s["size"] for s in (a.stats(), b.stats(), root.stats())], [1, 1, 1])
            info = shared.call("TENANTS")
            self.assertEqual(info["count"], 3)
        finally:
            shared.close()

    def test_policy_isolation_across_switches(self):
        """a KEEPs resolve pref latest in its workspace; b stays on the seed. Both switch modes."""
        for se in ("0", "1"):
            old = os.environ.get("AURA_MEMORY_SWITCH_EVAL")
            os.environ["AURA_MEMORY_SWITCH_EVAL"] = se
            shared = AuraMemory(policy="seed", learn=True, min_evidence=1)
            shared.cur = ""
            try:
                a, b = TenantView(shared, "a"), TenantView(shared, "b")
                for t in (a, b):
                    t.obs("user.theme", "dark", "pref", "user")
                    self.assertEqual(t.obs("user.theme", "light", "pref", "user")["outcome"], "lost-conflict")
                a.query("user.theme", "pref")
                a.correct("user.theme", "light", "pref")
                self.assertEqual(a.gate()["chosen"], "resolve\tpref\tlatest")
                for i in range(5):
                    v = f"v{i}"
                    self.assertEqual(a.obs("user.music", v, "pref", "user")["outcome"], "added" if i == 0 else "replaced", se)
                    self.assertEqual(b.obs("user.music", v, "pref", "user")["outcome"], "added" if i == 0 else "lost-conflict", se)
                    self.assertTrue(a.call("CHECK")["agree"])
                    self.assertTrue(b.call("CHECK")["agree"])
                self.assertIn('"latest"', a.policy()["source"].split("define resolve")[1].split("define ttl")[0])
                self.assertIn('(equal? cat "pref") "keep-first"', b.policy()["source"])
                self.assertNotIn('(equal? cat "pref") "keep-first"', a.policy()["source"])
            finally:
                shared.close()
                if old is None:
                    os.environ.pop("AURA_MEMORY_SWITCH_EVAL", None)
                else:
                    os.environ["AURA_MEMORY_SWITCH_EVAL"] = old


if __name__ == "__main__":
    unittest.main()
