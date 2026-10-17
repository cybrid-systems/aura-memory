seeds [0, 1, 2, 3, 4], 600 events per stream (shift at 300), diagnosis noise 0.3

| mode | accuracy (mean, min–max) | window 1 / 2 / 3 | stale-answer rate | user corrections | memory size (final / mean) | proposals | KEEP / ROLLBACK |
|---|---|---|---|---|---|---|---|
| append | 78.0% (72.6%–83.1%) | 80.4% / 81.3% / 71.3% | 11.2% | 33.4 | 215 / 110 | 0.0 | 0.0 / 0.0 |
| fixed | 80.0% (74.1%–84.0%) | 90.8% / 81.0% / 65.9% | 17.3% | 29.0 | 96 / 45 | 0.0 | 0.0 / 0.0 |
| adaptive | 95.2% (93.5%–96.8%) | 94.0% / 92.8% / 99.0% | 2.7% | 6.6 | 32 / 26 | 3.4 | 3.0 / 0.4 |
| adaptive-nogate | 94.5% (90.9%–96.8%) | 93.8% / 92.2% / 97.6% | 3.2% | 7.2 | 32 / 26 | 3.6 | 3.6 / 0.0 |

accuracy by category

| mode | pref | fact | project | episodic |
|---|---|---|---|---|
| append | 74.3% | 77.9% | 71.5% | 100.0% |
| fixed | 74.1% | 100.0% | 39.6% | 100.0% |
| adaptive | 95.7% | 100.0% | 75.0% | 100.0% |
| adaptive-nogate | 94.2% | 100.0% | 75.0% | 100.0% |

latency (host round trip over pipes)

| mode | query µs p50 / p99 | write µs p50 | policy mutation ms p50 / max (GATE or APPLY) | startup ms | wall s |
|---|---|---|---|---|---|
| append | 57394 / 403575 | 31564 | – | 114 | 40 |
| fixed | 23934 / 180844 | 14024 | – | 118 | 17 |
| adaptive | 19696 / 79514 | 10502 | 3695 / 5889 | 113 | 24 |
| adaptive-nogate | 19627 / 79318 | 11195 | 12 / 17 | 116 | 12 |
