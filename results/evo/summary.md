# #4946 aura-memory: EoH-S policy set (machine summary)

aura: aura dev (99ddc81c9) | n=600 | dev seeds [0, 1, 2, 3, 4] | held-out seeds [5, 6, 7, 8, 9] | k=3

selected: ['P03', 'P16', 'P09'] (coverage 12.308)
assignment: {'clean': 'P16', 'recall120': 'P03', 'recall80': 'P03'}
single best: P03 (trio (seed0-4 final))
acceptance: ratio 1.0000, pass False

## Held-out means per distribution

| policy | clean | recall80 | recall120 | worst |
|---|---:|---:|---:|---:|
| single best P03 | 0.8293 | 0.8096 | 0.8067 | 0.8067 |
| portfolio | 0.8549 | 0.8096 | 0.8067 | 0.8067 |
| set oracle | 0.8549 | 0.8096 | 0.8067 | 0.8067 |
| pool oracle (all 24 policies) | 0.8549 | 0.8096 | 0.8067 | 0.8067 |

## Per held-out seed (score; worst = min over distributions)

| seed | single clean/recall80/recall120 | worst | portfolio clean/recall80/recall120 | worst | delta worst |
|---|---|---:|---|---|---:|
| 5 | 0.831 / 0.802 / 0.818 | 0.8018 | 0.863 / 0.802 / 0.818 | 0.8018 | +0.0000 |
| 6 | 0.821 / 0.804 / 0.816 | 0.8037 | 0.848 / 0.804 / 0.816 | 0.8037 | +0.0000 |
| 7 | 0.825 / 0.821 / 0.825 | 0.8205 | 0.845 / 0.821 / 0.825 | 0.8205 | +0.0000 |
| 8 | 0.828 / 0.797 / 0.735 | 0.7348 | 0.855 / 0.797 / 0.735 | 0.7348 | +0.0000 |
| 9 | 0.842 / 0.825 / 0.839 | 0.8254 | 0.863 / 0.825 / 0.839 | 0.8254 | +0.0000 |

## Score-weight sensitivity (size objective weight)

| size weight | single worst | portfolio worst | pool oracle worst | portfolio ratio | passes 5% |
|---:|---:|---:|---:|---:|---|
| 0.000 | 0.9750 | 0.9750 | 1.0000 | 1.0000 | False |
| 0.333 | 0.8067 | 0.8067 | 0.8067 | 1.0000 | False |
| 0.500 | 0.7144 | 0.7144 | 0.7205 | 1.0000 | False |

## Selected policies, held-out metrics

| policy | dist | score | accuracy | correction-recall | stale | size |
|---|---|---:|---:|---:|---:|---:|
| P03 | clean | 0.8293 | 1.0000 | 1.0000 | 0.0000 | 31.6 |
| P03 | recall80 | 0.8096 | 0.9067 | 1.0000 | 0.0000 | 40.4 |
| P03 | recall120 | 0.8067 | 0.9294 | 0.9500 | 0.0000 | 34.0 |
| P09 | clean | 0.8107 | 1.0000 | 1.0000 | 0.0000 | 39.8 |
| P09 | recall80 | 0.7985 | 0.9720 | 1.0000 | 0.0000 | 46.6 |
| P09 | recall120 | 0.8004 | 0.9889 | 1.0000 | 0.0000 | 45.6 |
| P16 | clean | 0.8549 | 1.0000 | 1.0000 | 0.0000 | 23.2 |
| P16 | recall80 | 0.7763 | 0.8189 | 0.7996 | 0.0000 | 26.8 |
| P16 | recall120 | 0.7639 | 0.8587 | 0.7207 | 0.0000 | 22.6 |

## Single best, held-out metrics

| dist | score | accuracy | correction-recall | stale | size |
|---|---:|---:|---:|---:|---:|
| clean | 0.8293 | 1.0000 | 1.0000 | 0.0000 | 31.6 |
| recall80 | 0.8096 | 0.9067 | 1.0000 | 0.0000 | 40.4 |
| recall120 | 0.8067 | 0.9294 | 0.9500 | 0.0000 | 34.0 |
