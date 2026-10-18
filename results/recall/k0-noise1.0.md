seeds [0, 1, 2, 3, 4], 1200 events per stream (shift at 600), diagnosis noise 1.0

| mode | accuracy (mean, min–max) | window 1 / 2 / 3 | stale-answer rate | user corrections | memory size (final / mean) | proposals | KEEP / ROLLBACK |
|---|---|---|---|---|---|---|---|
| append | 81.4% (76.8%–85.1%) | 86.1% / 85.9% / 70.8% | 13.3% | 53.8 | 367 / 184 | 0.0 | 0.0 / 0.0 |
| fixed | 82.7% (80.2%–85.3%) | 92.2% / 82.0% / 71.4% | 16.2% | 51.6 | 180 / 82 | 0.0 | 0.0 / 0.0 |
| adaptive | 76.6% (71.7%–84.8%) | 91.0% / 74.4% / 61.3% | 16.2% | 69.0 | 55 / 46 | 14.4 | 1.4 / 13.0 |
| adaptive-nogate | 73.3% (70.5%–76.4%) | 91.0% / 69.0% / 55.9% | 16.2% | 78.8 | 43 / 37 | 24.0 | 24.0 / 0.0 |

accuracy by category

| mode | pref | fact | project | episodic |
|---|---|---|---|---|
| append | 72.3% | 87.0% | 53.0% | 100.0% |
| fixed | 71.3% | 100.0% | 41.7% | 100.0% |
| adaptive | 71.3% | 100.0% | 41.7% | 78.8% |
| adaptive-nogate | 71.3% | 100.0% | 41.7% | 66.6% |

latency (host round trip over pipes)

| mode | query µs p50 / p99 | write µs p50 | policy mutation ms p50 / max (GATE or APPLY) | startup ms | wall s |
|---|---|---|---|---|---|
| append | 1039 / 2502 | 890 | – | 51 | 1 |
| fixed | 916 / 2053 | 737 | – | 54 | 1 |
| adaptive | 1002 / 3570 | 821 | 96 / 244 | 56 | 3 |
| adaptive-nogate | 1018 / 3647 | 790 | 3 / 7 | 50 | 2 |

