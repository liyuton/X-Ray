# Scientific X-ray 项目主流程与版本对比指南（v2）

本文档在既有梳理基础上，重点补齐以下内容：
- 端到端流程（从标题检索到报告生成）
- 关键 Python 脚本的职责边界（输入、输出、上下游依赖）
- 多版本脚本的差异与选型建议（reduction / intermediate / summary）
- 每个流程步骤后的优化建议与风险提示

适用对象：
- 需要快速上手跑通全流程的同学
- 需要做性能优化、版本迁移、并行提速的同学
- 需要定位某个中间产物来自哪个脚本的同学

---

## 1. 全流程总览（先看这个）

主流程（推荐顺序）
1. 标题检索候选 pid：test_pid.py
2. 生成主题引文网络：gen_source_gml.py
3. 生成逐年中间文件：gen_intermediate_files_v2_param.py <pid>
4. 生成属性树和高 KE 细节图：run_only_gen_visible_depth.py
5. 渲染 DOT 演化图：render_simplified_tree_v2.py
6. 生成总结报告：dpi_summary_v6.py

核心数据流
- 输入：论文标题 / seminal pid
- 中间产物：source_gml_by_year、skeleton_tree、tree_deep、node_entropy、subtree_entropy、year2visible_depth、year2delta_d
- 输出：属性化树图、DOT 图、文本总结

---

## 2. 流程视角（逐步说明 + 每步优化建议）

## 2.1 步骤1：标题检索候选 pid

脚本
- src/test_pid.py

主要作用
- 通过 Elasticsearch 用标题检索候选论文
- 输出候选的 id / numeric_id / title / abstract / publication_year / cited_by_count
- 支持模糊匹配与精确匹配两种方式

典型命令
- 在 src 目录运行：python test_pid.py

输入
- 论文标题（脚本内 test_titles，或改成你自己的标题列表）

输出
- 终端打印候选结果（需人工筛选最合适的 seminal paper）

依赖关系
- 下游步骤需要一个最终确认的 pid

优化建议与风险提示
- 建议把人工筛选标准固定化：年份、被引、标题语义一致性
- 建议落盘一个 pid 候选清单（json/csv），便于复现
- 风险：只看第 1 条命中可能拿错 pid，后续全流程都会偏离

---

## 2.2 步骤2：生成主题引文网络 source gml

脚本
- src/gen_source_gml.py

主要作用
- 查询“引用了 seminal paper”的论文集合
- 构建该集合内部的引用边
- 生成主题级原始引文图（GML）

典型命令
- 在 src 目录运行：python gen_source_gml.py
- 或在脚本中设置 pids 后批量跑

输入
- pid（数值字符串）

输出
- ../input/source_gml/{pid}.gml

依赖关系
- 步骤3按年切片依赖该文件

优化建议与风险提示
- 建议将步骤2和步骤1之间增加 pid 合法性校验（是否可查到标题与日期）
- 建议记录查询时间和命中总数，便于排查 ES 数据更新导致的波动
- 风险：ES 字段缺失会导致节点不完整，进而影响后续树结构

---

## 2.3 步骤3：生成逐年中间文件（核心）

主脚本（推荐）
- src/gen_intermediate_files_v2_param.py

典型命令
- 在 src 目录运行：python gen_intermediate_files_v2_param.py <pid>

本步骤分为 6 个子阶段：

### 2.3.a 逐年切分引文网络（gen_year_by_year_source_gml）

调用来源
- gen_intermediate_files_v2_param.py 导入：gen_source_gml_by_year_scc.gen_year_by_year_source_gml

版本差异
- src/gen_source_gml_by_year.py
  - 基于 find_cycle 的循环找环/切环
- src/gen_source_gml_by_year_scc.py（当前主用）
  - 基于强连通分量（SCC）定位环，再执行切边策略
  - 在环较多时通常更稳

输出
- ../temp_files/source_gml_by_year/{pid}/{year}.gml

优化建议与风险提示
- 建议优先使用 _scc 版本
- parallel_v2 / v3 / T4_2025 中常把此步骤注释掉（复用已有切片）
- 风险：若复用旧切片而源数据已变，会造成结果过期

### 2.3.b 计算简化指数 reduction（gen_reduction）

输入
- 年度 gml：../temp_files/source_gml_by_year/{pid}/{year}.gml

输出
- 内存对象 pid2reduction（通常不单独落盘）

版本详细对比

1) src/gen_reduction.py（v1 原版）
- 稠密矩阵 + 全量特征分解
- 适合小规模图
- 大图时间开销明显

2) src/gen_reduction_v2.py
- 仍为稠密框架
- 通过 all-pairs dijkstra 预计算提升速度
- 但 all-pairs 路径字典内存压力较大

3) src/gen_reduction_v3.py（当前中大图推荐）
- 稀疏矩阵 + 稀疏特征求解（k 有上限）
- 单源最短路方式，整体更平衡
- 面向中大规模稀疏图更友好

4) src/gen_reduction_v4.py（实验增强）
- 在 v3 基础上补充不可达惩罚语义
- 增加单源最短路缓存，减少重复 dijkstra
- 建议先做回归验证再全面替换

优化建议与风险提示
- 默认建议：生产优先 v3，v4 先小样本 A/B
- 风险：v2 在图规模上来后可能出现内存瓶颈
- 风险：v4 如果未充分回归，可能带来结果偏移

### 2.3.c 生成脉络树 skeleton_tree（gen_skeleton_tree）

脚本
- src/gen_skeleton_tree.py
- 对照脚本：src/gen_skeleton_tree_test_reduction.py

主要作用
- 在有向图上反复检测环并切边，直到无环
- 形成可用于后续深度与熵计算的树化结构

输出
- ../temp_files/skeleton_tree_by_year/{pid}/{year}

优化建议与风险提示
- 对比不同 reduction 版本时，建议用 test_reduction 版本追踪切边差异
- 风险：如果只看最终树，不记录切边过程，难以解释版本差异来源

### 2.3.d 计算每个节点树深（gen_tree_node_deep）

脚本
- src/gen_tree_node_deep.py

主要作用
- 计算树深分层（deep -> nodes）

输出
- ../temp_files/tree_deep_by_year/{pid}/{year}

优化建议与风险提示
- 建议加入结果完整性检查：根节点必须在 depth 0
- 风险：上游树结构异常会放大到后续 VD 与 delta-D

### 2.3.e 计算点熵与树熵（gen_entropy）

脚本
- src/gen_node_and_tree_entropy.py

主要作用
- 结合树结构与引用信息计算 node entropy / subtree entropy

输出
- ../temp_files/node_entropy_by_year/{pid}/{year}
- ../temp_files/subtree_entropy_by_year/{pid}/{year}

优化建议与风险提示
- 建议在每年计算后做简单统计（max/min/缺失键）
- 风险：若节点 id 类型不一致（int/str），可能出现键缺失

### 2.3.f 生成 VD 与 delta-D 演化

脚本与函数
- src/gen_KE_and_VD_evolution_pics.py：visible_depth_evoluation
- src/get_delta_D_for_specific_topic.py：delta_d_evolution

输出
- VD 数值：../temp_files/year2visible_depth/{pid}.json
- VD 曲线：../temp_files/skeleton_evolution_related_jpg/{pid}/max_visible_depth.jpg
- delta-D 数值：../temp_files/year2delta_d/{pid}.json

版本注意
- gen_intermediate_files.py（老版）中这两步是注释状态
- v2 / v2_param / parallel_v2 / parallel_v3 / T4_2025 中通常启用
- parallel.py 中该步骤为注释状态

优化建议与风险提示
- 建议将“是否生成 VD/delta-D”做成显式参数，避免脚本间行为不一致
- 风险：老脚本跑完后可能缺 year2visible_depth/year2delta_d，影响后续分析

---

## 2.4 步骤4：补算属性树与高 KE 节点细节

脚本
- src/run_only_gen_visible_depth.py
- 其核心调用：src/gen_idea_tree_attributed_and_detail_file.py

主要作用
- 在前置中间文件已存在时，补跑属性化脉络树与高 KE 节点细节图

典型输入依赖
- source_gml_by_year / node_entropy_by_year / tree_deep_by_year / simplied_skeleton_tree_by_year

典型输出
- ../temp_files/attributed_idea_tree_by_year/{pid}/...
- ../temp_files/high_KE_node_detail_png/{seminal_pid}/{year}.jpg

优化建议与风险提示
- 建议作为“补算工具”保留，不与主流程强耦合
- 风险：simplied_skeleton_tree 缺失时会触发自动生成，需确认依赖函数可用

---

## 2.5 步骤5：生成 DOT 布局演化图

脚本
- src/render_simplified_tree_v2.py

主要作用
- 读取简化树、树深、熵信息，构建 DOT 并渲染 PNG

典型输出
- ../temp_files/dot_output/{pid}/{pid}_{year}_tree.png

优化建议与风险提示
- 建议提前检查 graphviz dot 可执行是否可用
- 风险：简化树文件缺失时，若 fallback 生成函数不可导入会失败

---

## 2.6 步骤6：生成总结报告

主脚本
- src/dpi_summary_v6.py

主要作用
- 聚合多年结构信息，构造 prompt，调用模型生成领域演化总结

典型输出
- output/final_report_*.txt（按你的运行脚本命名）

优化建议与风险提示
- 建议将 prompt 与结果统一归档（便于复现实验）
- 风险：不同版本 summary 脚本模型配置不同，报告风格和结论会有差异

---

## 3. 脚本视角（家族化对比）

## 3.1 intermediate 家族对比（最实用）

| 脚本 | 逐年切分 | reduction 版本 | 按年份并行 | VD/delta-D | 典型场景 |
|---|---|---|---|---|---|
| src/gen_intermediate_files.py | gen_source_gml_by_year | v1 | 否 | 否（注释） | 历史基线，不推荐新任务 |
| src/gen_intermediate_files_v2.py | gen_source_gml_by_year_scc | v2 | 否 | 是 | 串行稳定跑 |
| src/gen_intermediate_files_v2_param.py | gen_source_gml_by_year_scc | v2 | 否 | 是 | 单 pid 常用入口（推荐） |
| src/gen_intermediate_files_parallel.py | gen_source_gml_by_year_scc | v2 | 是 | 否（注释） | 早期并行版 |
| src/gen_intermediate_files_parallel_v2.py | gen_source_gml_by_year_scc（默认注释复用） | v3 | 是 | 是 | 中大规模并行（推荐） |
| src/gen_intermediate_files_parallel_v3.py | gen_source_gml_by_year_scc（默认注释复用） | v3 | 是 | 是 | 并行复跑、阶段化任务 |
| src/gen_intermediate_files_parallel_T4_2025.py | gen_source_gml_by_year_scc（默认注释复用） | v3 | 是 | 是 | 特定年份窗口任务 |

选型建议
- 单个 pid、快速跑通：v2_param
- 多 pid 批处理且图较大：parallel_v2 或 parallel_v3
- 需要严控内存：优先 v3 reduction 路线

---

## 3.2 reduction 家族对比（算法与性能）

| 版本 | 核心实现 | 优势 | 风险 | 推荐度 |
|---|---|---|---|---|
| src/gen_reduction.py | 稠密矩阵 + 传统求解 | 实现直观 | 大图慢 | 低（仅小图验证） |
| src/gen_reduction_v2.py | 稠密 + all-pairs 思路 | 比 v1 更快 | all-pairs 内存容易涨 | 中（中小图） |
| src/gen_reduction_v3.py | 稀疏矩阵 + 稀疏特征 + 单源最短路 | 时间/内存更平衡 | 参数上限需关注 | 高（当前主推） |
| src/gen_reduction_v4.py | v3 + 不可达惩罚 + SSSP 缓存 | 语义更完整、减少重复最短路 | 尚需回归验证 | 中高（试点） |

建议
- 默认生产：v3
- v4：先在固定 pid 集上做对照，再决定是否切换

---

## 3.3 按年切分家族对比

| 版本 | 切环策略 | 性能/稳定性 | 推荐度 |
|---|---|---|---|
| src/gen_source_gml_by_year.py | find_cycle 逐步切环 | 逻辑直观，但环多时效率一般 | 中 |
| src/gen_source_gml_by_year_scc.py | SCC + 切环策略 | 对复杂环更稳，当前主流 | 高 |

建议
- 新流程优先 _scc
- 做历史复现实验时再使用旧版

---

## 3.4 summary 家族对比

| 脚本 | 模型配置（当前代码） | 主要定位 |
|---|---|---|
| src/dpi_summary_v1.py | gpt-4o-mini | 早期版本 |
| src/dpi_summary_v2.py | gpt-4o-mini | ES 化后早期改进 |
| src/dpi_summary_v3.py | gpt-4o-mini | 信息组织增强 |
| src/dpi_summary_v4.py | deepseek-reasoner | 推理风格对比 |
| src/dpi_summary_simplified.py | gpt-5-mini | 快速摘要 |
| src/dpi_summary_v6.py | gpt-5-mini | 当前主线总结 |
| src/dpi_summary_compare.py | gpt-5-mini | 比较评测 |
| src/dpi_summary_compare_v2.py | gpt-5-mini | 比较评测增强 |

建议
- 日常主线：v6
- 快速草稿：simplified
- 模型对比：compare / compare_v2

---

## 4. 关键问题：clean_reference_data 的复用与优化

当前现状
- clean_reference_data 在以下脚本中重复定义：
  - src/gen_source_gml_by_year.py
  - src/gen_source_gml_by_year_scc.py
  - src/gen_reduction.py
  - src/gen_reduction_v2.py
  - src/gen_reduction_v3.py
  - src/gen_reduction_v4.py
  - src/gen_skeleton_tree.py
  - src/gen_skeleton_tree_test_reduction.py
  - src/gen_node_and_tree_entropy.py

影响
- 维护成本高：修复一个清洗 bug 需改多处
- 一致性风险：不同模块清洗细节漂移会污染版本对比
- 性能浪费：同一年份同一输入可能被重复清洗多次

可执行优化路线（分层推进）

短期（低风险，优先）
1. 在主流程内做单次清洗缓存
2. reduction / skeleton / entropy 复用同一 cleaned nodes/edges

中期（结构优化）
1. 抽取统一模块：src/common/reference_cleaning.py
2. 提供统一入口：clean_reference_data(..., strategy=classic|scc)
3. 各脚本改为 import 同一实现

长期（进一步提速）
1. 增加按 pid-year 的清洗结果缓存（带输入指纹）
2. 与并行流程联动，减少重复 CPU 消耗

风险提示
- 清洗逻辑统一后，历史结果可能出现轻微差异，需回归验证

---

## 5. 关键产物路径速查

输入
- input/source_gml/{pid}.gml

中间产物
- temp_files/source_gml_by_year/{pid}/{year}.gml
- temp_files/skeleton_tree_by_year/{pid}/{year}
- temp_files/tree_deep_by_year/{pid}/{year}
- temp_files/node_entropy_by_year/{pid}/{year}
- temp_files/subtree_entropy_by_year/{pid}/{year}
- temp_files/year2visible_depth/{pid}.json
- temp_files/year2delta_d/{pid}.json
- temp_files/attributed_idea_tree_by_year/{pid}/...
- temp_files/high_KE_node_detail_png/{pid}/{year}.jpg
- temp_files/dot_output/{pid}/{pid}_{year}_tree.png

输出
- output/final_report*.txt
- output/summary*.txt
- output/phase*_result*.txt

---

## 6. 推荐执行策略（按场景）

场景A：单个主题，快速稳定跑通
1. test_pid.py 筛 pid
2. gen_source_gml.py 生成 source gml
3. gen_intermediate_files_v2_param.py <pid>
4. run_only_gen_visible_depth.py（如需补算）
5. render_simplified_tree_v2.py
6. dpi_summary_v6.py

场景B：多个主题并行 + 中大规模图
1. 优先 parallel_v2 / parallel_v3
2. reduction 走 v3
3. 对需要严格语义一致性的主题，抽样试跑 v4 对照

场景C：模型输出对照评测
1. 固定中间文件版本
2. 用 summary compare 脚本对同一输入做模型横向比较

---

## 7. 执行后核对清单（建议）

每次跑完至少检查：
1. source_gml_by_year 是否存在完整年份切片
2. skeleton_tree / tree_deep / node_entropy / subtree_entropy 是否同年份齐全
3. year2visible_depth 与 year2delta_d 是否生成
4. dot_output 是否有对应 pid-year 图
5. summary/final_report 是否与本次模型版本一致

---

## 8. 版本结论（可直接用于选型）

1. 当前主流程建议
- 单 pid：gen_intermediate_files_v2_param.py
- 多 pid 并行：gen_intermediate_files_parallel_v2.py 或 v3

2. reduction 建议
- 默认 v3
- v4 先小样本验证后再切换全量

3. summary 建议
- 默认 v6
- 快速试读可用 simplified
- 评测对比用 compare/compare_v2

4. clean_reference_data 优化建议
- 先做主流程缓存复用，再做统一模块重构

---

## 9. 一页执行手册（速用入口）

- 已提供独立文档：`Pipeline_OnePager.md`
- 推荐给新同事直接使用该手册跑首轮流程，再回看本 v2 文档做版本选型

---

## 10. 默认命令模板（写在文档末尾，便于复制）

说明
- 以下命令默认在仓库的 src 目录执行
- 单 pid 默认走 v2_param
- 多 pid 且图规模较大默认走 parallel_v2 / v3（reduction_v3 路线）

### 10.1 单 pid 默认模板（推荐）

```bash
cd /home/liyutong1117/jupyter/scientific_x_ray-github/src

# 1) 检索并人工确认 pid
python test_pid.py

# 2) 在 gen_source_gml.py 中设置 pids 后生成 source gml
python gen_source_gml.py

# 3) 主流程
python gen_intermediate_files_v2_param.py <pid>

# 4) 可选：补算属性图
python run_only_gen_visible_depth.py

# 5) 可选：DOT 演化图
python render_simplified_tree_v2.py --pid <pid> --year 2025

# 6) 总结报告
python dpi_summary_v6.py
```

### 10.2 多 pid 串行模板（稳妥）

```bash
cd /home/liyutong1117/jupyter/scientific_x_ray-github/src

for pid in 2100837269 2105934661 3090704166; do
  python gen_intermediate_files_v2_param.py "$pid"
done
```

### 10.3 多 pid 并行模板（提速）

```bash
cd /home/liyutong1117/jupyter/scientific_x_ray-github/src

for pid in 2100837269 2105934661 3090704166; do
  nohup python gen_intermediate_files_parallel_v2.py "$pid" > "../output/run_${pid}.log" 2>&1 &
done

# 观测日志
tail -f ../output/run_2100837269.log
```

使用提示
- 并行脚本常默认复用已有 `source_gml_by_year`，若目录缺失，请先跑一次 v2_param 或在并行脚本中启用切片步骤。

---

## 11. 故障排查章节（按报错关键词）

### 11.1 关键词：FileNotFoundError: ../input/source_gml/<pid>.gml

定位
- 脚本：gen_intermediate_files_* 家族
- 含义：步骤2未成功生成 source gml

处理
1. 先运行 gen_source_gml.py 确保 `../input/source_gml/<pid>.gml` 存在
2. 检查 pid 是否在脚本内 pids 列表中

### 11.2 关键词：FileNotFoundError: ../temp_files/source_gml_by_year/...

定位
- 脚本：gen_intermediate_files_parallel_v2.py / v3 / T4_2025
- 含义：并行版假设已存在按年切片

处理
1. 先跑 `python gen_intermediate_files_v2_param.py <pid>`
2. 或在并行脚本里启用 `gen_year_by_year_source_gml(pid)`

### 11.3 关键词：Killed / MemoryError

定位
- 脚本：gen_reduction_v2.py 路线（含老并行）
- 含义：all-pairs 路径缓存触发内存瓶颈

处理
1. 改用 reduction_v3 路线（parallel_v2 / parallel_v3）
2. 分批跑 pid，降低并发度

### 11.4 关键词：graphviz.backend.execute.ExecutableNotFound

定位
- 脚本：render_simplified_tree_v2.py
- 含义：Python 包存在，但系统 dot 不可执行

处理
1. 安装系统 graphviz
2. 终端验证 `dot -V`
3. 重跑渲染命令

### 11.5 关键词：ConnectionError / AuthenticationException（Elasticsearch）

定位
- 脚本：test_pid.py、gen_source_gml.py、dpi_summary_* 部分流程
- 含义：ES 地址不可达或凭据失效

处理
1. 检查脚本中的 `es_hosts`
2. 切换到可访问节点
3. 再重跑检索或网络生成

### 11.6 关键词：KeyError（节点 id）/ JSONDecodeError

定位
- 脚本：gen_node_and_tree_entropy.py、gen_idea_tree_attributed_and_detail_file.py
- 含义：常见于中间文件不完整、id 类型不一致（str/int）、或文件写入中断

处理
1. 删除异常年份的中间文件后重算该年份
2. 确认 node_entropy/tree_deep/skeleton 的年份集合一致
3. 避免任务中断时读取半写入 JSON

### 11.7 关键词：No module named ...

定位
- 所有脚本
- 含义：依赖未安装或环境不一致

处理
1. 在项目根执行 `pip install -r requirements.txt`
2. 确认运行目录是 `src`（相对路径依赖较多）

### 11.8 关键词：无 year2visible_depth / year2delta_d 产物

定位
- 脚本：gen_intermediate_files.py、gen_intermediate_files_parallel.py（这些版本相关调用可能注释）

处理
1. 改用 v2/v2_param/parallel_v2/v3
2. 或手动调用 `visible_depth_evoluation(pid)` 与 `delta_d_evolution(pid)`

---

（完）
