# #4946 aura-memory：v0.2 evo 组合策略的 held-out 验证（声明 → 测试 → 结果）

状态：**EoH-S 选择链路已跑通并留档；验收指标未达到（最差分布增益 0.0%，要求 ≥5%）。**
本文按“声明 → 测试 → 结果”写，失败项照实列出，并给出为什么在该候选族/流族内 5% 不可达的上界证据。

- 仓库：/home/dev/code/downstream/aura-memory，分支 v0.2-evo
- Aura：aura dev (99ddc81c9)，即 aura 仓库 HEAD 99ddc81c9（v0.2 开发线；尚无 v0.2.0-rc tag）
- 数据：全部合成、按 seed 可复现；无客户数据

## 0. 结论摘要

1. 现有单目标 KEEP 学习器在 15 条 dev 流上收敛到 4 个不同策略；其中最优的 P03（trio：resolve pref latest + admit project teammate + ttl episodic 60）在 3 个流分布（clean / recall80 / recall120）× 5 个 held-out seed 上的最差分布得分是 0.8067。
2. std/proposer 的 EoH-S（prop:set-select，k=3）选出 {P03, P16, P09}，覆盖度 12.308（15 条 dev 流之和）。按租户/流分布分配后：clean→P16（紧凑策略），recall80/recall120→P03。
3. held-out 上，组合把 clean 从 0.8293 提到 0.8549（+3.1%，5 个 seed 全部一致），但最差分布（recall120 0.8067 / recall80 0.8096）完全不变，**最差分布比值 1.0000，验收失败**。
4. 不是权重挑出来的结论：把存储目标权重调到 0（只看纠错召回与陈旧率）时，单一最优 0.9750、组合 0.9750；把整个 24 策略池按分布取 oracle 也只能到 +2.56%。在 1/3 与 1/2 权重下，池 oracle 的相对增益分别是 0.0% 与 +0.86%。**任何权重下都到不了 +5%。**
5. 原因不是搜索没找到互补，而是该策略族里没有能抬高最差分布的互补对：唯一在 clean 上更好的紧凑策略 P16（ttl 20）在 recall 流上掉 4–5 分；唯一在 recall 流上更准的 P09（ttl 120 + promote 3）因存储变大在等权得分上反而更低。最差分布恰好是单策略已经最强的分布。

## 1. 声明（要证明什么）

- C1 基线：现有单目标 KEEP 的 held-out 表现可复现，且作为“单一最优策略”参与比较。
- C2 搜索：候选生成/记录走 std/evo-core 的 ask/tell 与 evo log；互补集合选择走 std/proposer 的 EoH-S（prop:set-select），k ≤ 3；没有另写搜索算法。
- C3 分布：按租户/流分布评估。每个分布是一个可复现的流族，dev 与 held-out 的 seed 不相交。
- C4 验收：held-out 上，互补集合的最差分布得分比单一最优策略高 ≥5%（5 个 seed）。
- C5 审计/回滚：策略 KEEP/ROLLBACK 仍走原有 worldline（mutate:rebind / ast:snapshot / ast:restore），并补上 evo:record! 的谱系；回滚后源码逐字节一致。
- C6 可复现：固定 Aura、固定 seed、固定候选文件；结果目录含原始 JSON 与 evo log。

## 2. 方法

### 2.1 流分布（租户口径）

同一条合成流，三个分布只改回放窗口的读法（stream(seed, n=600, recall=...)）：

| 分布 | recall | 含义 |
|---|---:|---|
| clean | 0 | 只读 ≤15 事件内的 episodic 笔记；ttl 看起来免费 |
| recall80 | 80 | 每隔 80 事件一个回放块，问 30–150 事件前的笔记；短 ttl 会丢 |
| recall120 | 120 | 同上，回放块更稀疏、跨度更大 |

dev seed = 0,1,2,3,4（15 条流）；held-out seed = 5,6,7,8,9（15 条流），两组不相交。5 个 held-out seed 即验收要求的 5 seed。

### 2.2 候选策略族

候选必须是学习器自己能写出的策略，规则只含 admit / resolve / ttl / promote（闭语法）：

- 20 个语法候选（P00–P19）：seed；resolve pref latest；三个学习器 KEEP 的组合（ttl 60/120/240/0）；keep-both；promote 1/3；被 gate 拒绝过的 admit pref assistant；resolve project keep-first；以及 ttl 20/30 的“紧凑探针”等。
- 4 个真实学习器产物：在 dev 流上跑 adaptive（单目标 KEEP + worldline replay gate），取最终策略源码，去重后得到 L00–L03。
- 共 24 个候选（P00–P19、L00–L03），每个都是一份可加载的策略文件（results/evo/policies/）。

候选不是随机网格：P16/P17 的 ttl 20/30 只在“存储”目标上不同，用来检验组合是否有互补空间；其余都来自学习器的变异词表或其直接邻域。

### 2.3 指标与得分

每条 (策略, 流) 关闭学习、固定策略回放，测三件事：

- 纠错召回 correction-recall：用户纠正过某 key 之后，该 key 后续查询答对的比例（无后续查询的纠正跳过）。
- 陈旧事实率 stale-rate：答成历史真值的查询比例（stream 自带 stale 标记）。
- 存储条数 size：流结束时的 item 数。

主得分（预注册，等权三项）：

    score = ( correction-recall + (1 - stale-rate) + 30/(30+size) ) / 3

30/(30+size) 是严格递减的存储项：size 15→0.67，30→0.50，60→0.33，93→0.24。

为证明结论不依赖权重，报告同时给出存储权重 w = 0、1/3、1/2 的敏感性表（w=0 即只看正确性）。

### 2.4 搜索与选择（std，不自建）

- Python 侧只做“域评估”：对每个候选×dev 流真实启动 Aura memory server 回放，写矩阵。
- aura/evo_select.aura：
  - evo:search(algo="eoh-s") + evo:ask/evo:tell! 逐候选记账；每个候选一条 v=2 evo:record!（objectives = mean/worst，behavior = 分布标签）。
  - prop:set-select-report(ordered, rows, 3) 做 EoH-S 贪心集合选择（覆盖度 = 每个 dev 流取集合内最大值之和；单调子模，1-1/e 近似）。
  - 集合本身再写一条 evo:record!（candidate=set-k3，parents=选中的三个候选）。
- 没有另写贪心/进化/选择算法。

### 2.5 部署式分配

集合选出来后，按分布分配策略：若某候选在该分布的 dev 均值比单一最优高 >0.01 才替换，否则回退到单一最优（防止 3–5 条 dev 流上的选择噪声）。这是“租户画像已知”的可部署规则，不是按 held-out 逐条挑最优。

## 3. 测试与结果

复现命令（在仓库根目录）：

    export AURA_BIN=/home/dev/code/aura/build/aura AURA_LIB=/home/dev/code/aura/lib
    python3 scripts/evo_portfolio.py --jobs 8
    python3 scripts/evo_summary.py
    python3 -m unittest discover -s tests -v

### T1 基线：单目标 KEEP 的 held-out 表现

15 条 dev 流跑 adaptive，得到 4 个不同最终策略（L00–L03）；去重后与语法候选一起评估。dev 上单一最优是 P03（trio，ttl 60），其行为与学习器产物 L00 相同。

held-out（5 seed 均值）：

| 分布 | 单一最优 P03 |
|---|---:|
| clean | 0.8293 |
| recall80 | 0.8096 |
| recall120 | 0.8067 |
| **最差分布** | **0.8067** |

P03 的原始指标：clean acc 1.000 / recall 1.000 / stale 0 / size 31.6；recall80 acc 0.907 / recall 1.000 / size 40.4；recall120 acc 0.929 / recall 0.950 / size 34.0。

说明：学习器在 15 条 dev 流上并没有学到不同的“流派”，而是收敛到同一组三条规则（ttl 只分 60/120 两支），这本身就是后面互补性不足的第一个信号。

### T2 EoH-S 选择

- 选中：P03（trio ttl60）、P16（ttl 20 紧凑）、P09（ttl 120 + promote 3）
- 覆盖度：12.308（15 条 dev 流；单策略最好 P03 = 12.173，集合 +1.1%）
- 分配：clean→P16，recall80→P03，recall120→P03
- evo log：results/evo/log.jsonl；每个候选一条 SCORED，集合一条 KEEP（parents=P03/P16/P09）

### T3 验收：held-out 最差分布

| 分布 | 单一最优 | 组合（按租户分配） | 差 |
|---|---:|---:|---:|
| clean | 0.8293 | 0.8549 | +0.0256（+3.1%） |
| recall80 | 0.8096 | 0.8096 | 0 |
| recall120 | 0.8067 | 0.8067 | 0 |
| **最差分布** | **0.8067** | **0.8067** | **0.0000** |

最差分布比值 = 0.8067 / 0.8067 = **1.0000**；门槛 1.05 → **不通过**。

每个 held-out seed（score，括号内为组合 / 单策略的最差分布）：

| seed | clean 单/组 | recall80 单/组 | recall120 单/组 | 最差 单/组 | 最差增量 |
|---|---:|---:|---:|---:|---:|
| 5 | 0.831 / 0.863 | 0.802 / 0.802 | 0.818 / 0.818 | 0.802 / 0.802 | 0.0000 |
| 6 | 0.821 / 0.848 | 0.804 / 0.804 | 0.816 / 0.816 | 0.804 / 0.804 | 0.0000 |
| 7 | 0.825 / 0.845 | 0.821 / 0.821 | 0.825 / 0.825 | 0.821 / 0.821 | 0.0000 |
| 8 | 0.828 / 0.855 | 0.797 / 0.797 | 0.735 / 0.735 | 0.735 / 0.735 | 0.0000 |
| 9 | 0.842 / 0.863 | 0.825 / 0.825 | 0.839 / 0.839 | 0.825 / 0.825 | 0.0000 |

5 个 seed 的 clean 增益分别是 +3.9% / +3.4% / +2.4% / +3.3% / +2.4%，方向一致；最差分布 5 个 seed 全部零增益。这不是“在噪声内”，而是结构性 0。

### T4 上界：整个候选池也到不了 5%

对 24 个策略在 held-out 上逐分布取 oracle（完美的按租户选择，任何集合的上界）：

| 存储权重 w | 单一最优最差 | 组合最差 | 池 oracle 最差 | oracle 相对增益 |
|---:|---:|---:|---:|---:|
| 0（只看正确性） | 0.9750 | 0.9750 | 1.0000 | +2.56% |
| 1/3（预注册等权） | 0.8067 | 0.8067 | 0.8067 | 0.0% |
| 1/2 | 0.7144 | 0.7144 | 0.7205 | +0.86% |

即：即使允许每个租户都挑整个池里最好的策略，最差分布也只能提高 2.56%（正确性口径），远低于 5%。**验收指标在该候选族/流族内不可达，不是 EoH-S 选择得不好。**

### T5 审计与回滚

- aura/server.aura 的 log-version! 现在同时写 evo:record!：target=候选，decision=KEEP/ROLLBACK，evidence={why, version, chosen, scores}，v=2 成员含 algo=memory-policy、gen=版本号、candidate、parents（上一个 KEEP 的 candidate id）、behavior={tenant, phase}、objectives={correct, labeled, size}。
- 谱系链：同一个 tenant 的第二次 KEEP 的 parent 等于第一次 KEEP 的 candidate id；第一个是 root（parents=null）。
- 回滚：仍用 ast:snapshot + ast:restore（gate 原有逻辑），tests/test_control.py 的 test_rollback_restores_source_byte_identical 通过。
- 验证命令：

    aura evo log --log results/evo/log.jsonl --run last
    aura evo log --log results/evo/log.jsonl --lineage <keep-id>
    aura evo report --html results/evo/evo-report --log results/evo/log.jsonl --all

  输出见 results/evo/log.jsonl（329 行 / 137 KB，含 15 条学习流的 KEEP/ROLLBACK 与选择流的 26 条 v=2 记录：24 SCORED + 1 PROPOSE + 1 KEEP）。
- 新测试 tests/test_evo_lineage.py：KEEP 父子链、每个 KEEP 带 objectives、集合记录带成员 parents；tests 总计 24 项全通过。

### T6 可复现性

- 流、候选、评估全部固定 seed；候选策略文件在 results/evo/policies/，矩阵在 results/evo/matrix.json，原始测量在 results/evo/cache_eval.json。
- 评估在关闭学习的固定策略上做；同一 (策略, 分布, seed) 键可缓存重放。
- control.py 新增读超时（select + timeout_s=120）：server 死掉/卡住会报错而不是把 harness 挂死（本次调试中实际用到）。

## 4. 失败项（如实）

1. **验收 C4 未通过**：最差分布增益 0.0000（要求 ≥5%），5 个 held-out seed 全部为 0；clean 有 +3.1% 但 clean 不是最差分布。
2. 互补集合只在“已经最强的分布之外”有效：P16 抬 clean、P09 抬 recall 的 acc（0.907/0.929 → 0.972/0.989），但 P09 的存储从 31.6/34.0 涨到 39.8/45.6，等权得分反而降到 0.7985/0.8004；w=0 时 P09 才能到 1.0。
3. 单一最优策略不是“折中策略”，而是 recall 流上的最优策略，所以“组合修最差分布”的前提不成立。这是本仓库流族的结构，不是搜索 bug。

## 5. 如果要把这条验收做成可通过

按优先级：

1. 换指标口径：把验收写成“正确性口径下的最差分布提升 ≥5%”。本次正确性口径上界是 +2.56%，仍不够，但至少方向对。
2. 扩策略族到 rank/src-weight 与 keep-both 的组合，制造“正确性 vs 正确性”的互补，而不是“正确性 vs 存储”的互补；当前闭语法里没有两个策略在 recall 流上同时接近 1.0 且在 clean 上不互相拖累。
3. 换分布：当前 3 个流族的差异只在旧笔记回读，单一策略的 trio 恰好全部覆盖。要出现 ≥5% 的最差分布缺口，需要一个单策略明显失手的租户族（例如 20k 条目、长回读窗口、或强噪声诊断下学习器会误 KEEP 的流），并把“学习过程”也纳入评估，而不只是固定策略回放。
4. 若保留等权指标，则验收门槛应改成“组合不劣于单策略，且在至少一个分布上严格更好”，这与本次数据一致（clean +3.1%，其余持平）。

## 6. 产物

- docs/4946-aura-memory-v0.2-evo.md（本文）
- results/evo/report.json、summary.md、matrix.json、selection.json、cache_eval.json、cache_learn.json
- results/evo/policies/*.aura（24 个候选策略源码）
- results/evo/log.jsonl（evo log，v=2）、logs/（每条学习流与选择流）
- results/evo/evo-report/（aura evo report 生成的 HTML/SVG，可重建）
- aura/evo_select.aura、aura_memory/eval.py、aura_memory/policy_gen.py、scripts/evo_portfolio.py、scripts/evo_summary.py
- tests/test_evo_lineage.py
