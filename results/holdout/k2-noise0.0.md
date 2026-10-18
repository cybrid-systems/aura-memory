seeds [0, 1, 2, 3, 4], 600 events per stream (shift at 300), diagnosis noise 0.0

| mode | accuracy (mean, min–max) | window 1 / 2 / 3 | stale-answer rate | user corrections | memory size (final / mean) | proposals | KEEP / ROLLBACK |
|---|---|---|---|---|---|---|---|
| adaptive | 95.9% (93.5%–97.5%) | 94.0% / 94.9% / 99.3% | 2.6% | 6.0 | 32 / 26 | 3.4 | 3.0 / 0.4 |

accuracy by category

| mode | pref | fact | project | episodic |
|---|---|---|---|---|
| adaptive | 95.7% | 100.0% | 81.7% | 100.0% |

latency (host round trip over pipes)

| mode | query µs p50 / p99 | write µs p50 | policy mutation ms p50 / max (GATE or APPLY) | startup ms | wall s |
|---|---|---|---|---|---|
| adaptive | 1047 / 3760 | 968 | 292 / 369 | 54 | 2 |

