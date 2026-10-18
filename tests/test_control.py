"""Control-plane tests against a real Aura process (need AURA_BIN; skipped otherwise)."""
import os
import unittest

from aura_memory.control import AuraMemory

NEED = unittest.skipUnless(os.environ.get("AURA_BIN"), "AURA_BIN not set")


@NEED
class WhiteBoxTest(unittest.TestCase):
    def setUp(self):
        self.m = AuraMemory(policy="seed", learn=True, min_evidence=1)

    def tearDown(self):
        self.m.close()

    def test_admit_list_get_provenance(self):
        m = self.m
        self.assertEqual(m.obs("user.theme", "dark", "pref", "user")["outcome"], "added")
        self.assertEqual(m.obs("user.theme", "light", "pref", "chatter")["outcome"], "rejected")
        items = m.list()
        self.assertEqual([(i["key"], i["val"], i["src"], i["policy_version"]) for i in items],
                         [("user.theme", "dark", "user", 0)])
        g = m.get("user.theme")
        self.assertEqual([o["outcome"] for o in g["observations"]], ["rejected", "added"])
        self.assertEqual([p["op"] for p in g["provenance"]], ["rejected", "added"])
        self.assertEqual(m.query("user.theme", "pref")["answer"], "dark")

    def test_store_index_matches_model(self):
        # 600 keys over 4096 buckets (many sharing a bucket), keep-first conflicts, a delete, a pin; LIST must stay
        # newest-first and GET/STATS must agree with a plain Python model of the old list store.
        m = self.m
        m.call("LEARN", "0")
        model = {}
        for i in range(600):
            k = f"user.k{i % 400}"          # keys 0..199 written twice: second write is lost to keep-first
            r = m.obs(k, f"v{i}", "fact", "user")
            if k in model:
                self.assertEqual(r["outcome"], "lost-conflict")
            else:
                self.assertEqual(r["outcome"], "added")
                model[k] = (r["id"], f"v{i}")
        for k in ("user.k0", "user.k199", "user.k200", "user.k399"):
            self.assertEqual(m.query(k, "fact")["answer"], model[k][1])
        self.assertEqual(m.query("user.missing", "fact")["answer"], "")
        gone = model.pop("user.k7")
        self.assertTrue(m.delete(gone[0])["ok"])
        self.assertEqual(m.get("user.k7")["items"], [])
        items = m.list()
        self.assertEqual([i["id"] for i in items], sorted((v[0] for v in model.values()), reverse=True))
        self.assertEqual({i["key"]: i["val"] for i in items}, {k: v[1] for k, v in model.items()})
        st = m.stats()
        self.assertEqual(st["size"], len(model))
        self.assertEqual(dict(st["by_cat"])["fact"], len(model))
        self.assertTrue(m.pin(model["user.k8"][0])["item"]["pinned"])
        self.assertTrue(m.get("user.k8")["items"][0]["pinned"])
        self.assertEqual(m.obs("user.k8", "other", "fact", "user")["outcome"], "lost-conflict")
        self.assertEqual(m.query("user.k8", "fact")["answer"], model["user.k8"][1])

    def test_edit_pin_delete_are_recorded(self):
        m = self.m
        iid = m.obs("user.pet", "cat:Mochi", "fact", "user")["id"]
        self.assertEqual(m.edit(iid, "dog:Doudou")["item"]["val"], "dog:Doudou")
        self.assertTrue(m.pin(iid)["item"]["pinned"])
        self.assertEqual(m.query("user.pet", "fact")["answer"], "dog:Doudou")
        self.assertTrue(m.delete(iid)["ok"])
        self.assertEqual(m.list(), [])
        ops = [(p["op"], p["actor"]) for p in m.get("user.pet")["provenance"]]
        self.assertEqual(ops[:3], [("delete", "user"), ("retrieve", "agent"), ("pin", "user")])
        self.assertIn(("edit", "user"), ops)

    def test_pinned_value_survives_non_user_write(self):
        m = AuraMemory(policy="append", learn=False)
        try:
            m.obs("user.allergy", "peanuts", "fact", "user")
            m.pin_key("user.allergy", "fact")
            self.assertEqual(m.obs("user.allergy", "pollen", "fact", "chatter")["outcome"], "lost-pinned")
            self.assertEqual(m.query("user.allergy", "fact")["answer"], "peanuts")
            self.assertEqual(m.obs("user.allergy", "none", "fact", "user")["outcome"], "added")
        finally:
            m.close()

    def test_append_only_keeps_everything(self):
        m = AuraMemory(policy="append", learn=False)
        try:
            m.obs("user.theme", "dark", "pref", "user")
            m.obs("user.theme", "light", "pref", "chatter")
            self.assertEqual(len(m.list()), 2)
            self.assertEqual(m.query("user.theme", "pref")["answer"], "light")   # newest mention wins
        finally:
            m.close()


@NEED
class LearnerGateTest(unittest.TestCase):
    def test_keep_rewrites_policy_and_logs_version(self):
        m = AuraMemory(policy="seed", learn=True, min_evidence=1)
        try:
            src0 = m.policy()["source"]
            m.obs("user.theme", "dark", "pref", "user")
            self.assertEqual(m.obs("user.theme", "light", "pref", "user")["outcome"], "lost-conflict")
            self.assertEqual(m.query("user.theme", "pref")["answer"], "dark")
            r = m.correct("user.theme", "light", "pref")
            self.assertEqual(r["propose"]["candidates"], ["resolve\tpref\tlatest", "resolve\tpref\tkeep-both"])
            v = m.gate()
            self.assertEqual((v["verdict"], v["chosen"], v["version"]), ("KEEP", "resolve\tpref\tlatest", 1))
            src1 = m.policy()["source"]
            self.assertNotEqual(src0, src1)
            self.assertIn('"latest"', src1.split("define resolve")[1].split("define ttl")[0])
            self.assertTrue(m.call("CHECK")["agree"])
            vs = m.versions()
            self.assertEqual([x["verdict"] for x in vs], ["KEEP"])
            self.assertEqual(m.obs("user.theme", "solarized", "pref", "user")["outcome"], "replaced")
            self.assertEqual(m.get("user.theme")["items"][0]["policy_version"], 1)
        finally:
            m.close()

    def test_rollback_restores_source_byte_identical(self):
        m = AuraMemory(policy="seed", learn=True, min_evidence=1)
        try:
            src0 = m.policy()["source"]
            m.obs("user.theme", "dark", "pref", "user")
            m.obs("user.theme", "light", "pref", "chatter")          # rejected
            m.query("user.theme", "pref")
            r = m.correct("user.theme", "light", "pref")
            self.assertEqual(r["propose"]["candidates"], ["admit\tpref\tchatter\t1"])
            v = m.gate()        # admitting chatter cannot help: keep-first still drops it
            self.assertEqual(v["verdict"], "ROLLBACK")
            self.assertEqual(m.policy()["source"], src0)
            self.assertTrue(m.call("CHECK")["agree"])
            self.assertEqual(m.obs("user.coffee", "latte", "pref", "chatter")["outcome"], "rejected")
        finally:
            m.close()

    def test_noop_candidates_are_not_proposed(self):
        m = AuraMemory(policy="seed", learn=True, min_evidence=1)
        try:
            m.obs("proj.alpha.owner", "li", "project", "teammate")
            m.query("proj.alpha.owner", "project")
            m.correct("proj.alpha.owner", "li", "project")
            self.assertEqual(m.gate()["verdict"], "KEEP")       # admit project/teammate
            m.obs("proj.beta.status", "build", "project", "user")
            m.obs("proj.beta.status", "review", "project", "teammate")
            self.assertEqual(m.query("proj.beta.status", "project")["answer"], "review")
            self.assertFalse(m.correct("proj.beta.status", "review", "project")["propose"])
        finally:
            m.close()


if __name__ == "__main__":
    unittest.main()
