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
