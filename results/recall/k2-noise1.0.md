seeds [0, 1, 2, 3, 4], 1200 events per stream (shift at 600), diagnosis noise 1.0

| mode | accuracy (mean, min–max) | window 1 / 2 / 3 | stale-answer rate | user corrections | memory size (final / mean) | proposals | KEEP / ROLLBACK |
|---|---|---|---|---|---|---|---|
| append | 81.4% (76.8%–85.1%) | 86.1% / 85.9% / 70.8% | 13.3% | 53.8 | 367 / 184 | 0.0 | 0.0 / 0.0 |
| fixed | 82.7% (80.2%–85.3%) | 92.2% / 82.0% / 71.4% | 16.2% | 51.6 | 180 / 82 | 0.0 | 0.0 / 0.0 |
| adaptive | 82.0% (79.7%–85.3%) | 92.2% / 81.3% / 69.7% | 16.2% | 53.6 | 135 / 68 | 12.6 | 0.4 / 12.2 |
| adaptive-nogate | 73.3% (70.5%–76.4%) | 91.0% / 69.0% / 55.9% | 16.2% | 78.8 | 43 / 37 | 24.0 | 24.0 / 0.0 |

accuracy by category

| mode | pref | fact | project | episodic |
|---|---|---|---|---|
| append | 72.3% | 87.0% | 53.0% | 100.0% |
| fixed | 71.3% | 100.0% | 41.7% | 100.0% |
| adaptive | 71.3% | 100.0% | 41.7% | 97.2% |
| adaptive-nogate | 71.3% | 100.0% | 41.7% | 66.6% |

latency (host round trip over pipes)

| mode | query µs p50 / p99 | write µs p50 | policy mutation ms p50 / max (GATE or APPLY) | startup ms | wall s |
|---|---|---|---|---|---|
| append | 1076 / 2547 | 936 | – | 53 | 2 |
| fixed | 935 / 2331 | 762 | – | 70 | 1 |
| adaptive | 1048 / 3233 | 832 | 102 / 494 | 53 | 3 |
| adaptive-nogate | 1042 / 4088 | 811 | 3 / 6 | 52 | 2 |

