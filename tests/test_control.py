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

    def assert_index_ok(self):
        for c in self.m.call("INDEX")["cats"] or []:
            self.assertEqual(c["cnt"], c["cnt_full"], c)
            self.assertEqual(c["dead"], c["dead_full"], c)
            self.assertLessEqual(c["tq"], 2 * c["cnt"] + 64 + 1, c)
            self.assertLessEqual(c["young"], 2 * c["cnt"] + 64 + 1, c)

    def test_category_index_consistent_under_churn(self):
        # writes / queries / corrections / pins, white-box edit / delete / pin / unpin, and kept ttls (sweeps):
        # the per-category counters must always equal a full recompute and the queues must stay bounded
        import random
        m, r = self.m, random.Random(7)
        cats = ["pref", "fact", "project", "episodic"]
        ids = []
        for i in range(900):
            k = f"k{r.randrange(90)}"; c = cats[int(k[1:]) % 4]; x = r.random()
            if x < 0.5: res = m.obs(k, f"v{r.randrange(5)}", c, r.choice(["user", "teammate"]))
            elif x < 0.75: res = m.query(k, c)
            elif x < 0.82: res = m.correct(k, f"v{r.randrange(5)}", c)
            elif x < 0.84: res = m.pin_key(k, c)
            else:
                if not ids: continue
                op, iid = r.choice(["edit", "delete", "pin", "unpin"]), r.choice(ids)
                try:
                    {"edit": lambda: m.edit(iid, "w"), "delete": lambda: m.delete(iid), "pin": lambda: m.pin(iid),
                     "unpin": lambda: m.unpin(iid)}[op]()
                except RuntimeError:
                    pass                      # deleted / decayed id
                continue
            if res.get("id", -1) != -1: ids.append(res["id"])
            if res.get("propose"): m.apply()
            if i % 100 == 99: self.assert_index_ok()
        self.assert_index_ok()

    def test_ttl_expiry_exact(self):
        # 15 episodic items; one pinned, one retrieved. The size check proposes ttl episodic 60; once kept, the next
        # sweep drops exactly the 13 untouched unpinned items; the unpinned one and the retrieved one (60+ events
        # stale by then) go at the following sweep
        m = self.m
        ids = {f"e{i}": m.obs(f"e{i}", "v", "episodic", "user")["id"] for i in range(15)}
        m.pin(ids["e3"])
        res, ts = None, 15
        while True:
            res = m.query("e5" if ts == 40 else "nothing", "pref" if ts != 40 else "episodic"); ts = res["ts"]
            if res.get("propose"): break
        self.assertIn("ttl\tepisodic\t60", res["propose"]["candidates"])
        self.assertEqual(m.apply()["chosen"], "ttl\tepisodic\t60")
        decays = []
        while ts < 200:
            res = m.query("nothing", "pref"); ts = res["ts"]
            if res["decayed"]: decays.append((ts, res["decayed"]))
            if ts == 105: m.unpin(ids["e3"])
        self.assertEqual(decays, [(100, 13), (110, 2)])   # 110: e3 (unpinned at 105) + e5 (retrieved at ts 40)
        self.assertEqual(m.list("episodic"), [])
        self.assert_index_ok()

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


def _with_env(**kv):
    """Start an AuraMemory with temporary server env overrides."""
    def start(*a, **k):
        old = {n: os.environ.get(n) for n in kv}
        os.environ.update(kv)
        try:
            return AuraMemory(*a, **k)
        finally:
            for n, v in old.items():
                if v is None: os.environ.pop(n, None)
                else: os.environ[n] = v
    return start


def _ttl_run(m):
    """15 episodic items, ttl episodic 60 kept, then the bulk expiry; returns every white-box view."""
    for i in range(15):
        m.obs(f"e{i}", "v", "episodic", "user")
    ts = 15
    while True:
        res = m.query("nothing", "pref"); ts = res["ts"]
        if res.get("propose"): break
    m.apply()
    decays = []
    while ts < 130:
        res = m.query("nothing", "pref"); ts = res["ts"]
        if res["decayed"]: decays.append((ts, res["decayed"]))
    st = m.stats()
    return decays, [m.get(f"e{i}") for i in range(15)], m.list(), st


@NEED
class EquivalenceTest(unittest.TestCase):
    def test_decay_batches_match_per_item_log(self):
        # a bulk expiry is logged as one batch record; GET must still show the same per-key obs/prov records
        runs = []
        for b in ("1", "0"):
            m = _with_env(AURA_MEMORY_DECAY_BATCH=b)(policy="seed", learn=True, min_evidence=1)
            try:
                runs.append(_ttl_run(m))
            finally:
                m.close()
        (d1, g1, l1, s1), (d0, g0, l0, s0) = runs
        self.assertEqual(d1, [(100, 15)])
        self.assertEqual((d1, g1, l1), (d0, g0, l0))
        self.assertIn("decay", [o["outcome"] for o in g1[0]["observations"]] + [p["op"] for p in g1[0]["provenance"]])

    def test_gate_prune_does_not_change_verdicts(self):
        out = []
        for p in ("1", "0"):
            m = _with_env(AURA_MEMORY_GATE_PRUNE=p)(policy="seed", learn=True, min_evidence=1)
            try:
                m.obs("user.theme", "dark", "pref", "user")
                m.obs("user.theme", "light", "pref", "chatter")
                m.query("user.theme", "pref")
                m.correct("user.theme", "light", "pref")
                v1 = m.gate()
                m.obs("user.coffee", "latte", "pref", "user")
                m.obs("user.coffee", "flat white", "pref", "user")
                m.query("user.coffee", "pref")
                r = m.correct("user.coffee", "flat white", "pref")
                v2 = m.gate() if r.get("propose") else {}
                out.append([(v.get("verdict"), v.get("chosen"), v.get("version")) for v in (v1, v2)]
                           + [m.policy()["source"]])
            finally:
                m.close()
        self.assertEqual(out[0], out[1])
