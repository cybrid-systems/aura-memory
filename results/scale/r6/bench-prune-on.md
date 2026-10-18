seeds [0, 1, 2, 3, 4], 600 events per stream (shift at 300), diagnosis noise 0.0

| mode | accuracy (mean, min–max) | window 1 / 2 / 3 | stale-answer rate | user corrections | memory size (final / mean) | proposals | KEEP / ROLLBACK |
|---|---|---|---|---|---|---|---|
| append | 78.0% (72.6%–83.1%) | 80.4% / 81.3% / 71.3% | 11.2% | 33.4 | 215 / 110 | 0.0 | 0.0 / 0.0 |
| fixed | 80.0% (74.1%–84.0%) | 90.8% / 81.0% / 65.9% | 17.3% | 29.0 | 96 / 45 | 0.0 | 0.0 / 0.0 |
| adaptive | 95.9% (93.5%–97.5%) | 94.0% / 94.9% / 99.3% | 2.6% | 6.0 | 32 / 26 | 3.4 | 3.0 / 0.4 |
| adaptive-nogate | 95.2% (90.9%–97.5%) | 93.8% / 94.2% / 97.9% | 3.1% | 6.6 | 32 / 26 | 3.6 | 3.6 / 0.0 |

accuracy by category

| mode | pref | fact | project | episodic |
|---|---|---|---|---|
| append | 74.3% | 77.9% | 71.5% | 100.0% |
| fixed | 74.1% | 100.0% | 39.6% | 100.0% |
| adaptive | 95.7% | 100.0% | 81.7% | 100.0% |
| adaptive-nogate | 94.2% | 100.0% | 81.7% | 100.0% |

latency (host round trip over pipes)

| mode | query µs p50 / p99 | write µs p50 | policy mutation ms p50 / max (GATE or APPLY) | startup ms | wall s |
|---|---|---|---|---|---|
| append | 1100 / 2173 | 1000 | – | 54 | 1 |
| fixed | 917 / 1946 | 797 | – | 59 | 1 |
| adaptive | 1063 / 4007 | 988 | 135 / 231 | 53 | 1 |
| adaptive-nogate | 1064 / 3834 | 998 | 2 / 3 | 51 | 1 |
