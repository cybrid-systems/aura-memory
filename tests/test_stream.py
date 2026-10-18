import unittest

from aura_memory.stream import PROJECT, stream


class StreamTest(unittest.TestCase):
    def test_deterministic(self):
        a = [(e.kind, e.key, e.val, e.src) for e in stream(3, 300)]
        b = [(e.kind, e.key, e.val, e.src) for e in stream(3, 300)]
        c = [(e.kind, e.key, e.val, e.src) for e in stream(4, 300)]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_shift(self):
        s = stream(0, 600)
        self.assertEqual(len(s), 600)
        self.assertFalse([e for e in s[:300] if e.cat == "project"])
        self.assertTrue([e for e in s[300:] if e.cat == "project" and e.src == "teammate"])
        self.assertTrue(all(e.phase == "B" for e in s[300:]))

    def test_truth_is_latest_authoritative_statement(self):
        for seed in range(3):
            truth, hist = {}, {}
            for e in stream(seed, 600):
                if e.kind == "OBS" and (e.src == "user" or (e.src == "teammate" and e.key in PROJECT)):
                    if e.key in truth and truth[e.key] != e.val:
                        hist.setdefault(e.key, []).append(truth[e.key])
                    truth[e.key] = e.val
                if e.kind == "QUERY":
                    self.assertEqual(e.truth, truth[e.key])
                    self.assertEqual(list(e.stale), hist.get(e.key, []))

    def test_noise_sources_never_change_truth(self):
        s = stream(1, 600)
        for i, e in enumerate(s):
            if e.kind == "QUERY":
                for prev in reversed(s[:i]):
                    if prev.kind == "OBS" and prev.key == e.key and prev.src in ("user", "teammate"):
                        self.assertEqual(prev.val, e.truth)
                        break


if __name__ == "__main__":
    unittest.main()


class RecallRegimeTest(unittest.TestCase):
    def test_off_by_default(self):
        a, b = stream(3, 600), stream(3, 600, recall=0)
        self.assertEqual([vars(e) for e in a], [vars(e) for e in b])

    def test_recall_queries_are_old_episodic_notes(self):
        from aura_memory.stream import RECALL_AGE, in_recall
        evs = stream(0, 1200, recall=100)
        first = {}
        for e in evs:
            if e.kind == "OBS" and e.cat == "episodic" and e.src == "user":
                first.setdefault(e.key, e.ts)
        old = [e for e in evs if e.kind == "QUERY" and e.cat == "episodic" and in_recall(e.ts, 100)]
        self.assertGreater(len(old), 30)
        for e in old:
            self.assertTrue(RECALL_AGE[0] <= e.ts - first[e.key] <= RECALL_AGE[1], (e.key, e.ts, first[e.key]))
        recent = [e for e in evs if e.kind == "QUERY" and e.cat == "episodic" and not in_recall(e.ts, 100)]
        self.assertTrue(all(e.ts - first[e.key] <= 15 for e in recent))
