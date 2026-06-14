# 生成中间文件脚本分析 Prompt 与计划汇总

本文档整理关于“生成中间文件”脚本分析与优化建议的五个版本：

1. `prompt v0`：初始需求描述。
2. `prompt v1`：完善后的详细任务 prompt。
3. `plan prompt`：执行计划 prompt。
4. `plan detailed`：详细分析报告。
5. `plan concise`：简洁分析报告。

---

## prompt v0

```text
帮忙深入理解分析一下各种 [生成中间文件] 的脚本，目标是给出介绍和加速优化建议，
方便下一步理解和优化代码，首先分析其工作流程，确认其关键模块/主要函数等等，
其他给出现有的并行维度分析，然后分析其关键函数是否可以继续优化加速，
目前对于超大网络比如 20w+ 节点的初始引文网络，其关键函数运行时间都各有一两个月，
请先分析一下确认需求和任务，给出更完善更详细的这个的任务需求的 prompt。
```

---

## prompt v1

```text
请在仓库 /home/liyutong1117/jupyter/scientific_x_ray-github 中，深入分析“生成中间文件”相关脚本，目标是形成一份面向后续代码优化的技术分析报告和加速建议。当前背景是：对于超大初始引文网络，例如 20w+ 节点规模，关键函数单次运行可能达到一两个月，需要系统理解现有流程、并行方式、瓶颈函数和可优化空间。

请不要先改代码。先做只读分析，必要时可以运行非破坏性的统计/小样本检查。Python 命令如需运行，优先使用 conda xray 环境。

分析范围：
1. 七个中间文件入口脚本：
   - src/gen_intermediate_files.py
   - src/gen_intermediate_files_v2.py
   - src/gen_intermediate_files_v2_param.py
   - src/gen_intermediate_files_parallel.py
   - src/gen_intermediate_files_parallel_v2.py
   - src/gen_intermediate_files_parallel_v3.py
   - src/gen_intermediate_files_parallel_T4_2025.py

2. 这些入口调用的关键模块和函数：
   - 年度 GML 切片：gen_source_gml_by_year.py、gen_source_gml_by_year_scc.py
   - reduction 计算：gen_reduction.py、gen_reduction_v2.py、gen_reduction_v3.py、如相关也分析 gen_reduction_v4.py
   - 脉络树：gen_skeleton_tree.py
   - 树深：gen_tree_node_deep.py
   - 点熵/树熵：gen_node_and_tree_entropy.py
   - VD/DPI：gen_KE_and_VD_evolution_pics.py、get_delta_D_for_specific_topic.py、gen_vd_and_dpi.py

请输出一份结构化报告，至少包含：

一、总体工作流程
- 从 input/source_gml/{pid}.gml 到 temp_files/source_gml_by_year/{pid}/{year}.gml 的年度累计切片流程。
- 每个年份切片如何依次生成：
  - skeleton_tree_by_year
  - tree_deep_by_year
  - subtree_entropy_by_year
  - node_entropy_by_year
  - year2visible_depth
  - year2delta_d
- 用流程图或分步骤列表说明数据依赖关系，明确哪些步骤必须串行，哪些步骤理论上可并行。

二、七个脚本变体对比
请用表格比较七个入口脚本，至少包括：
- 使用的 source_gml 生成版本：普通版还是 SCC 清洗版。
- 使用的 reduction 版本：原版、v2、v3 等。
- 是否从命令行接收 pid。
- 并行维度：PID 间并行、年份内并行、单年份串行。
- 是否生成年度 GML，还是依赖已有年度 GML。
- 是否计算 VD/DPI。
- 是否限制年份范围，例如 2008-2010、2011+、2025+。
- 适用场景和主要风险。

三、关键函数和复杂度分析
重点分析以下函数的算法结构、时间复杂度、空间复杂度和瓶颈：
- clean_reference_data：重复清洗、找环、SCC 版本差异。
- gen_year_by_year_source_gml：年度累计切片是否重复扫描节点/边，是否可增量化。
- gen_reduction / v2 / v3 / v4：
  - 稠密矩阵 vs 稀疏矩阵。
  - 全量特征分解 vs 稀疏 eigs。
  - 反复 Dijkstra、all-pairs shortest paths、按需单源最短路的区别。
  - 在 20w+ 节点下的内存和时间不可行点。
- gen_skeleton_tree：反复 find_cycle 和按 reduction 剪边的瓶颈。
- gen_tree_node_deep：BFS 树深计算是否轻量。
- gen_entropy：树熵/点熵计算中的组合、遍历、重复读 GML 和重复清洗问题。
- VD/DPI 计算：是否主要是读取年度熵和深度文件后的轻量后处理。

四、现有并行维度分析
请区分并分析：
- PID 级并行：多个主题并行，适合多小图，但对单个超大图帮助有限。
- 年份级并行：单个 PID 内各年度并行，当前 parallel 系列采用的方式。
- 函数内部并行：目前基本缺失，尤其是 reduction、cycle removal、entropy 内部。
- I/O 和缓存维度：年度 GML、清洗结果、图结构、最短路结果是否重复计算。
- 对 20w+ 节点图，现有并行为什么仍可能跑一两个月。

五、加速优化建议
请按优先级给出建议，分为短期、中期、长期：
- 短期：不大改算法的优化，例如减少重复 clean_reference_data、缓存年度图对象、避免重复读写 GML、跳过已完成年份、断点续跑、明确日志和 profiling。
- 中期：重构 pipeline，例如统一七个入口、参数化年份范围和 reduction 版本、增量生成年度切片、统一输出目录、把年度任务变成可调度 job。
- 长期：算法级替换，例如避免全图 all-pairs shortest paths，使用稀疏/近似/局部子图、限制候选边、图数据库或 CSR 表示、批量/向量化熵计算、GPU/多机/任务队列。
- 每条建议说明预期收益、实现风险、对结果一致性的影响、需要验证的指标。

六、建议的下一步优化路线
请给出一个可以落地的实施路线：
1. 先做 profiling 和基线统计，记录每个阶段的耗时、节点数、边数、内存峰值。
2. 统一入口脚本，避免七个变体继续分叉。
3. 优先消除重复读取/重复清洗/重复构图。
4. 再优化 reduction 核心算法。
5. 最后考虑更激进的近似算法或分布式方案。

输出要求：
- 使用中文。
- 用清晰标题、表格和分层列表。
- 结论要直接指出当前最大瓶颈和最值得优先优化的位置。
- 不要泛泛建议“加并行”或“用 GPU”，必须结合当前代码中的具体函数和数据流说明。
- 如果发现某些优化会改变科学指标含义或结果一致性，请明确标注。
- 不要修改代码，除非后续明确要求进入实现阶段。
```

---

## plan prompt

```text
# 中间文件脚本分析报告执行计划

## Summary
- 产出一份中文技术分析报告，覆盖七个 gen_intermediate_files* 入口、关键模块链路、现有并行维度、主要复杂度瓶颈，以及面向 20w+ 节点超大图的分阶段加速建议。
- 全程只读分析，不修改仓库代码；必要时仅运行非破坏性统计、静态检查或小样本读取。
- 报告会明确指出当前最优先优化位置：gen_reduction*、重复 read_gml + clean_reference_data、gen_skeleton_tree 反复找环、gen_entropy 子树集合/互熵组合计算。

## Key Analysis Work
- 梳理总体数据流：
  input/source_gml/{pid}.gml -> 年度累计 GML -> reduction -> skeleton_tree -> tree_deep -> node/subtree_entropy -> VD/DPI。
- 对比七个入口脚本：
  使用普通/SCC 年度切片、reduction 版本、PID/年份并行、是否生成年度 GML、是否补算 VD/DPI、年份范围限制、适用场景和风险。
- 深入分析关键函数：
  clean_reference_data、gen_year_by_year_source_gml、gen_reduction/v2/v3/v4、gen_skeleton_tree、gen_tree_node_deep、gen_entropy、visible_depth_evoluation、delta_d_evolution。
- 明确复杂度和不可行点：
  稠密矩阵/全量特征分解/all-pairs Dijkstra 对 20w+ 节点不可行；v3/v4 虽转稀疏和 SSSP，但仍存在大量源点最短路、全量字典累加和重复构图问题。

## Output Structure
- 第一部分：总体流程和数据依赖，包含可并行/必须串行边界。
- 第二部分：七个脚本变体对比表。
- 第三部分：关键函数复杂度与瓶颈分析。
- 第四部分：现有并行维度分析，包括 PID 级、年份级、函数内部、I/O 缓存维度。
- 第五部分：短期/中期/长期加速建议，每条说明收益、风险、结果一致性影响和验证指标。
- 第六部分：下一步落地路线，按 profiling、统一入口、去重复计算、优化 reduction、考虑近似/分布式的顺序推进。

## Validation Plan
- 用静态代码引用支撑结论，避免泛泛建议。
- 如运行命令，仅做只读统计，例如入口脚本差异、函数调用关系、已有样本文件规模、输出目录结构。
- 不运行完整 pipeline，不生成新中间文件，不改动任何 repo-tracked 文件。
- 对可能改变科学指标语义的建议单独标注，例如近似最短路、候选边剪枝、局部子图替代全图计算。

## Assumptions
- 本轮交付物是分析报告和优化建议，不进入代码实现。
- 优先关注超大单主题网络的加速，而不是多个小主题的批量吞吐。
- 保持现有指标语义为默认目标；任何近似化或算法替换都作为长期方案单独评估。
```

---

## plan detailed

### 结论先行

当前最大瓶颈不是“并行数不够”，而是核心算法和重复计算结构对 20w+ 节点不成立：

- `gen_reduction.py` / `gen_reduction_v2.py` 的稠密矩阵、全量特征分解、all-pairs shortest path 在该规模基本不可行。
- `gen_reduction_v3.py` / `gen_reduction_v4.py` 改成稀疏后仍会做大量单源最短路和全量节点字典累加。
- 第二优先瓶颈是每个年度、每个阶段反复 `read_gml + clean_reference_data + 构图`。

### 一、总体流程

数据链路如下：

```text
input/source_gml/{pid}.gml
  -> gen_year_by_year_source_gml(pid)
  -> temp_files/source_gml_by_year/{pid}/{year}.gml
  -> gen_reduction(pid, yearly_gml)
  -> gen_skeleton_tree(pid, reduction, yearly_gml)
  -> gen_tree_node_deep(pid, skeleton_tree)
  -> gen_entropy(pid, skeleton_tree, deep2node, yearly_gml)
  -> skeleton_tree_by_year / tree_deep_by_year / subtree_entropy_by_year / node_entropy_by_year
  -> visible_depth_evoluation + delta_d_evolution
  -> year2visible_depth / year2delta_d
```

每个年度切片内部依赖是串行的：

- `reduction` 必须先于 `skeleton_tree`。
- `skeleton_tree` 必须先于 `tree_deep` 和 `entropy`。
- 不同年份理论上可以并行。
- 年度 GML 生成必须先完成。
- VD/DPI 必须等所有年度的 `node_entropy` 和 `tree_deep` 完成后再做。

### 二、七个入口脚本对比

| 脚本 | GML 切片 | reduction | PID 输入 | 并行维度 | 年份范围 | VD/DPI | 侧重点 |
|---|---|---|---|---|---|---|---|
| `src/gen_intermediate_files.py` | 普通版 | 原版 | 写死列表 | PID 间并行 | 到 2021 | 注释 | 旧版基线 |
| `src/gen_intermediate_files_v2.py` | SCC 版 | v2 | 写死列表 | PID 间并行 | 到 2025 | 是 | 更新批处理 |
| `src/gen_intermediate_files_v2_param.py` | SCC 版 | v2 | CLI 单 pid | 单 PID 包一层 Pool | 到 2025 | 是 | 单主题调度 |
| `src/gen_intermediate_files_parallel.py` | SCC 版 | v2 | CLI 单 pid | 年份并行 5 | 全部 | 注释 | 快速生成核心中间文件 |
| `src/gen_intermediate_files_parallel_v2.py` | 依赖已有 | v3 | CLI 单 pid | 年份并行 5 | `>=2011` | 是 | T4 后期年份 |
| `src/gen_intermediate_files_parallel_v3.py` | 依赖已有 | v3 | CLI 单 pid | 年份并行 5 | `2008-2010` | 是 | T4 早期补算 |
| `src/gen_intermediate_files_parallel_T4_2025.py` | 依赖已有 | v3 | CLI 单 pid | 年份并行 1 | `>=2025` | 是 | 最新年份补算 |

`gen_reduction_v4.py` 没有接入这七个入口，但它在 v3 基础上增加了 `sssp_cache`，是值得纳入下一步优化的实验版本。

### 三、关键函数瓶颈

`gen_year_by_year_source_gml`：

- 普通版和 SCC 版都按年份重复扫描全量节点和边。
- `year2nodes` 是 `O(Y*N)`。
- `year2edges` 是 `O(Y*E)`。
- 对累计年度网络，这是可增量化的。

`clean_reference_data`：

- 普通版反复 `find_cycle` 切环。
- SCC 版用 `strongly_connected_components` 定位环子图，方向是对的。
- 主要问题是它在年度切片、reduction、skeleton、entropy 中反复执行。

`gen_reduction`：

- 原版构造 `N*N` 稠密矩阵并全量特征分解。
- 循环里反复 `nx.dijkstra_path_length`。
- 20w 节点仅稠密 `float64` 矩阵约 320GB，实际特征分解远超可用资源。

`gen_reduction_v2`：

- 仍然是稠密矩阵。
- 额外使用 `all_pairs_dijkstra_path_length`。
- 内存和时间都不可行。

`gen_reduction_v3/v4`：

- 改成稀疏矩阵和 `eigs(k=512)`，明显比前两版合理。
- 但仍对大量 `source_index` 做 `csgraph.dijkstra`。
- v4 加了缓存，但缓存全量距离数组会有 `unique_sources * N` 的内存风险。

`gen_skeleton_tree`：

- 通过 `nx.find_cycle(..., orientation='ignore')` 找一个环、切一条边、再找下一轮。
- 如果环很多，近似 `O(C*(N+E))`。
- NetworkX 对 20w+ 图本身开销较高。

`gen_entropy`：

- 先构造每个子树的节点集合和边集合。
- 再对每个节点的孩子做两两组合互熵。
- 高分叉节点会触发组合爆炸。
- 集合复制和 `union` 也很重。

VD/DPI：

- 相对轻量。
- 主要读取 `node_entropy_by_year` 和 `tree_deep_by_year` 后做阈值扫描。
- 但 DPI 当前会按候选节点反复扫描多年熵文件，仍可缓存年度熵矩阵。

### 四、并行维度分析

- PID 级并行适合多个小主题；对单个 20w+ 超大主题帮助有限。
- 年份级并行是 parallel 系列的主要改进，但每个年份内部仍可能跑数周。
- 函数内部并行基本缺失，尤其是 reduction 的 SSSP、skeleton 的切环、entropy 的节点互熵。
- I/O/cache 未充分利用：年度 GML 已写盘，但后续每个函数又重新读、重新清洗、重新构建对象图。

### 五、加速建议

短期优先：

- 增加 profiling 和阶段日志：记录每年 `read/clean/reduction/skeleton/depth/entropy/write` 耗时、N/E、内存峰值。
- 跳过已完成输出：四类核心 JSON 都存在且可读时跳过该年。
- 合并重复 `read_gml + clean_reference_data`：年度任务内只清洗一次，把 `nodes/edges/graph/index` 传给后续函数。
- 默认使用 `gen_reduction_v4` 的 SSSP 缓存思想，但限制缓存规模，避免内存爆。

中期重构：

- 合并七个入口为一个参数化 runner：`pid`、年份范围、是否生成年度 GML、reduction 版本、年份并行数、是否 VD/DPI。
- 年度 GML 生成改为增量：按年份排序节点/边，逐年追加，而不是每年扫全量节点/边。
- 用轻量 CSR/邻接表作为内部主表示，GML 只作为输入/兼容输出，不作为阶段间主要交换格式。
- 将 `clean_reference_data` 统一为一次性预处理结果，避免多个模块各自维护一份清洗逻辑。

长期算法级：

- reduction 需要重新定义可计算版本：限制候选边/候选源点、局部子图、近似最短路、多源批量最短路或基于拓扑 DAG 的动态规划替代全图最短路。
- skeleton 切环不应每次全图 `find_cycle`；可用一次性生成 DAG/最大保留边策略，或按 SCC 局部处理。
- entropy 可用子树区间、bitset/roaring bitmap、稀疏边索引替代 Python set of `"u|v"` 字符串。
- 近似算法会影响科学指标一致性，必须和小图原算法做 ranking correlation、top-K KE 节点重合率、VD/DPI 曲线差异验证。

### 六、落地路线

1. 先做 profile runner，不改算法，只采集每阶段耗时、N/E、内存峰值。
2. 统一入口脚本，消除七个变体分叉，保留参数化行为。
3. 去掉重复读 GML、重复清洗、重复构图，这是最低风险收益点。
4. 将默认 reduction 切到受控缓存版，并测 v3/v4 在同一 PID/年份上的结果一致性和内存。
5. 再做算法替换实验：先在小图上保证结果接近，再扩展到 20w+ 网络。

当前最值得先动的是：统一年度任务内的数据对象和清洗结果，然后 profile `gen_reduction_v3/v4` 的 SSSP 次数、唯一 source 数、缓存内存和单年耗时。这个位置最可能把“一两个月”降到可诊断、可分解的量级。

---

## plan concise

### 1. 现有流程

`gen_intermediate_files*` 系列脚本的核心作用是：把一个主题论文 `pid` 的原始引文网络，按年份生成后续 X-ray 分析需要的中间文件。

流程如下：

```text
input/source_gml/{pid}.gml
  -> 按年份切片 source_gml_by_year/{pid}/{year}.gml
  -> reduction 计算
  -> 生成 skeleton_tree 脉络树
  -> 计算 tree_deep 树深
  -> 计算 subtree_entropy 树熵、node_entropy 点熵
  -> 基于点熵和树深计算 VD / DPI
```

主要输出：

```text
temp_files/source_gml_by_year/{pid}/{year}.gml
temp_files/skeleton_tree_by_year/{pid}/{year}
temp_files/tree_deep_by_year/{pid}/{year}
temp_files/subtree_entropy_by_year/{pid}/{year}
temp_files/node_entropy_by_year/{pid}/{year}
temp_files/year2visible_depth/{pid}.json
temp_files/year2delta_d/{pid}.json
```

七个入口脚本本质上是同一条 pipeline 的不同运行版本：有的跑旧算法，有的换了 SCC 清洗，有的按 PID 并行，有的按年份并行，有的只补算特定年份段。

### 2. 关键函数

| 模块 | 作用 | 关键函数 |
|---|---|---|
| 年度切片 | 从原始 GML 生成逐年累计网络 | `gen_year_by_year_source_gml` |
| 数据清洗 | 删除异常日期节点、去掉开山作外引、处理环 | `clean_reference_data` |
| reduction | 计算节点/边保留依据，是最重的核心步骤 | `gen_reduction / v2 / v3 / v4` |
| 脉络树 | 根据 reduction 剪边，生成树结构 | `gen_skeleton_tree` |
| 树深 | BFS 计算每层节点 | `gen_tree_node_deep` |
| 熵指标 | 计算树熵和点熵 | `gen_entropy` |
| VD/DPI | 基于点熵和树深做后处理 | `visible_depth_evoluation`、`delta_d_evolution` |

### 3. 主要瓶颈

最大瓶颈是 `gen_reduction*`。

原版和 v2 的问题最严重：

- 使用 `N*N` 稠密矩阵。
- 做全量特征分解。
- 原版反复调用 Dijkstra。
- v2 预计算 all-pairs shortest path。

对 20w+ 节点来说，这基本不可行。仅稠密矩阵内存就是数百 GB 级别，还不算特征分解和最短路。

v3/v4 已经改进：

- 使用稀疏矩阵。
- 使用 `scipy.sparse.linalg.eigs`。
- 使用 `scipy.sparse.csgraph.dijkstra` 做单源最短路。
- v4 还加了 SSSP 缓存。

但 v3/v4 仍然很重，因为它们仍可能对大量源点做单源最短路，并对全体节点做字典累加。

第二类瓶颈是重复计算：

- 每个年份都会重新读 GML。
- `gen_reduction`、`gen_skeleton_tree`、`gen_entropy` 内部又各自 `read_gml + clean_reference_data`。
- 同一个年度图被反复清洗、反复构图。

第三类瓶颈是 `gen_skeleton_tree`：

- 它通过 `find_cycle` 找一个环、切一条边、再重新找环。
- 如果环很多，会反复全图扫描。

第四类瓶颈是 `gen_entropy`：

- 构造子树节点集合和边集合。
- 对每个节点的孩子节点做两两组合互熵。
- 高分叉节点会出现组合爆炸。

VD/DPI 相对轻量，主要是读已有熵和树深文件做阈值扫描。

### 4. 现有并行情况

目前主要有两种并行：

- PID 级并行：多个主题同时跑。适合很多小图，不解决单个超大图。
- 年份级并行：一个主题内多个年份同时跑。parallel 系列就是这样做的。

但核心问题是：单个年份内部仍然非常重。对于 20w+ 网络，年份并行只能让多个重任务同时跑，不能降低每个年度任务本身的复杂度，还可能加剧内存压力。

目前几乎没有函数内部并行，也缺少缓存复用。

### 5. 优化建议

短期优先做这些，风险最低：

1. 加 profiling  
   记录每个年份的节点数、边数、`read/clean/reduction/skeleton/entropy/write` 耗时和内存峰值。

2. 支持断点续跑  
   如果某年四类核心输出已经存在且可读，直接跳过。

3. 消除重复读取和清洗  
   一个年度任务中只读一次 GML、只清洗一次，把 `nodes/edges/graph/index` 传给 `reduction/skeleton/entropy`。

4. 默认使用更合理的 reduction 版本  
   优先评估 `gen_reduction_v4`，但要限制 SSSP 缓存规模，避免内存爆炸。

中期建议：

1. 合并七个入口脚本  
   改成一个参数化 runner：`pid`、年份范围、是否生成年度 GML、reduction 版本、并行数、是否计算 VD/DPI。

2. 年度切片增量化  
   当前每年重复扫描全量节点和边，可以改为按年份追加节点和边。

3. 使用统一图结构  
   内部用邻接表或 CSR，不要在阶段之间反复 GML 读写和 NetworkX 构图。

4. 统一 `clean_reference_data`  
   现在多个模块各有一份类似逻辑，应统一成一次预处理结果。

长期建议：

1. 重做 reduction 算法  
   避免全图 all-pairs 或大量 SSSP，考虑候选边筛选、局部子图、近似最短路、DAG 动态规划等。

2. 优化 skeleton 切环  
   不要反复全图 `find_cycle`，改为 SCC 局部处理或一次性生成 DAG。

3. 优化 entropy  
   用 bitset/稀疏索引替代 Python set 和 `"u|v"` 字符串，减少集合 union 和组合计算成本。

4. 近似算法单独验证  
   如果使用近似或剪枝，需要比较点熵排名、top-K 节点、VD/DPI 曲线是否保持一致。

### 6. 优先级结论

最优先不是继续简单增加并行，而是：

1. profile 定位每个阶段真实耗时。
2. 消除重复 `read_gml + clean_reference_data + 构图`。
3. 统一入口脚本，减少七个版本分叉。
4. 重点优化 `gen_reduction_v3/v4`。
5. 再考虑替换 reduction 和 entropy 的核心算法。

对于 20w+ 节点网络，`gen_reduction` 是第一瓶颈，`gen_entropy` 和 `gen_skeleton_tree` 是第二梯队瓶颈，VD/DPI 不是主要问题。
