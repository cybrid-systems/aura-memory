seeds [0, 1, 2, 3, 4], 600 events per stream (shift at 300), diagnosis noise 1.0

| mode | accuracy (mean, min–max) | window 1 / 2 / 3 | stale-answer rate | user corrections | memory size (final / mean) | proposals | KEEP / ROLLBACK |
|---|---|---|---|---|---|---|---|
| adaptive | 80.0% (74.1%–84.0%) | 90.8% / 81.0% / 65.9% | 17.3% | 29.0 | 31 / 25 | 8.2 | 1.0 / 7.2 |

accuracy by category

| mode | pref | fact | project | episodic |
|---|---|---|---|---|
| adaptive | 74.1% | 100.0% | 39.6% | 100.0% |

latency (host round trip over pipes)

| mode | query µs p50 / p99 | write µs p50 | policy mutation ms p50 / max (GATE or APPLY) | startup ms | wall s |
|---|---|---|---|---|---|
| adaptive | 1055 / 3424 | 873 | 95 / 274 | 55 | 2 |

