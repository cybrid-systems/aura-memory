seeds [0, 1, 2, 3, 4], 1200 events per stream (shift at 600), diagnosis noise 0.0

| mode | accuracy (mean, min–max) | window 1 / 2 / 3 | stale-answer rate | user corrections | memory size (final / mean) | proposals | KEEP / ROLLBACK |
|---|---|---|---|---|---|---|---|
| append | 81.4% (76.8%–85.1%) | 86.1% / 85.9% / 70.8% | 13.3% | 53.8 | 367 / 184 | 0.0 | 0.0 / 0.0 |
| fixed | 82.7% (80.2%–85.3%) | 92.2% / 82.0% / 71.4% | 16.2% | 51.6 | 180 / 82 | 0.0 | 0.0 / 0.0 |
| adaptive | 96.6% (95.8%–97.8%) | 96.2% / 94.2% / 99.5% | 1.3% | 9.6 | 79 / 52 | 4.8 | 4.4 / 0.4 |
| adaptive-nogate | 95.9% (94.8%–96.9%) | 95.7% / 92.6% / 99.8% | 1.4% | 11.2 | 94 / 56 | 5.6 | 5.6 / 0.0 |

accuracy by category

| mode | pref | fact | project | episodic |
|---|---|---|---|---|
| append | 72.3% | 87.0% | 53.0% | 100.0% |
| fixed | 71.3% | 100.0% | 41.7% | 100.0% |
| adaptive | 97.5% | 100.0% | 89.5% | 95.0% |
| adaptive-nogate | 97.0% | 100.0% | 89.5% | 93.4% |

latency (host round trip over pipes)

| mode | query µs p50 / p99 | write µs p50 | policy mutation ms p50 / max (GATE or APPLY) | startup ms | wall s |
|---|---|---|---|---|---|
| append | 1092 / 2671 | 946 | – | 59 | 2 |
| fixed | 924 / 2242 | 758 | – | 57 | 1 |
| adaptive | 1048 / 3956 | 964 | 160 / 275 | 57 | 2 |
| adaptive-nogate | 1065 / 4247 | 969 | 2 / 5 | 51 | 2 |

