seeds [0, 1, 2, 3, 4], 600 events per stream (shift at 300), diagnosis noise 0.3

| mode | accuracy (mean, min–max) | window 1 / 2 / 3 | stale-answer rate | user corrections | memory size (final / mean) | proposals | KEEP / ROLLBACK |
|---|---|---|---|---|---|---|---|
| adaptive | 95.2% (93.5%–96.8%) | 94.0% / 92.8% / 99.0% | 2.7% | 6.6 | 32 / 26 | 3.4 | 3.0 / 0.4 |

accuracy by category

| mode | pref | fact | project | episodic |
|---|---|---|---|---|
| adaptive | 95.7% | 100.0% | 75.0% | 100.0% |

latency (host round trip over pipes)

| mode | query µs p50 / p99 | write µs p50 | policy mutation ms p50 / max (GATE or APPLY) | startup ms | wall s |
|---|---|---|---|---|---|
| adaptive | 1084 / 4301 | 991 | 241 / 319 | 51 | 2 |

