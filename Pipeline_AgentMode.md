# Scientific X-ray 项目流程与脚本版本对比指南

本文档在你已有梳理基础上，结合当前仓库实现，补齐了以下内容：
- 端到端执行流程（从 title 到最终总结）
- 关键脚本职责拆分（不仅列文件名，还说明输入/输出与调用关系）
- 多版本脚本差异（特别是 reduction、按年切分、并行中间文件、summary）
- 产物路径总表
- clean_reference_data 重复实现的复用优化建议

## 1. 全流程总览（建议执行顺序）

1. 标题检索候选 pid
   - 脚本: src/test_pid.py
   - 作用: 基于 ES 检索 title，返回若干候选（含标题、摘要、年份、引用数）
   - 说明: 需人工筛选最合适的开山论文 pid

2. 生成主题引文网络（source gml）
   - 脚本: src/gen_source_gml.py
   - 输入: 选定 pid
   - 输出: input/source_gml/{pid}.gml
   - 核心逻辑: 拉取所有“引用了开山作”的论文，并保留其内部引用关系

3. 生成逐年中间文件（核心流水线）
   - 主脚本（常用）: src/gen_intermediate_files_v2_param.py <pid>
   - 实际阶段:
     1) 按年切片引文网络: gen_year_by_year_source_gml
     2) 计算 reduction 指数: gen_reduction*
     3) 生成脉络树: gen_skeleton_tree
     4) 计算树深: gen_tree_node_deep
     5) 计算点熵/树熵: gen_entropy
     6) 生成 VD 与 delta-D 演化数值: visible_depth_evoluation + delta_d_evolution

4. 生成“带属性脉络树 + 高 KE 节点细节图”
   - 脚本: src/run_only_gen_visible_depth.py
   - 调用: gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail
   - 作用: 在已有中间结果基础上补齐可视化属性和高 KE 节点细节图

5. DOT 渲染演化图
   - 脚本: src/render_simplified_tree_v2.py
   - 输出: temp_files/dot_output/{pid}/...

6. 总结生成
   - 当前主用脚本: src/dpi_summary_v6.py
   - 输入: 多年份树结构 + 节点摘要/标题
   - 输出: 文本报告（通常写到 output 下对应文件）


## 2. 中间文件流水线细化（阶段职责 + 产物）

### 2.1 按年切分引文网络

- 入口调用位置:
  - src/gen_intermediate_files.py（老）
  - src/gen_intermediate_files_v2.py / src/gen_intermediate_files_v2_param.py（常用）
  - src/gen_intermediate_files_parallel*.py（并行版）

- 两个版本:
  - src/gen_source_gml_by_year.py
    - 传统 clean + find_cycle 循环切环
    - 逻辑直接，适合较小图
  - src/gen_source_gml_by_year_scc.py
    - 先用 strongly_connected_components 定位强连通分量，再做时间序切边与贪心去环
    - 批量过滤方式更高效，通常比原版更稳健

- 输出路径:
  - temp_files/source_gml_by_year/{pid}/{year}.gml


### 2.2 计算 reduction（最关键版本差异）

- 统一接口: gen_reduction(paper_id, INPUT_FILE_PATH)
- 在中间流水线中产物以内存 dict 形式传给 skeleton_tree，不单独落盘

- 版本对比:

1) src/gen_reduction.py（原版）
   - 邻接矩阵: 稠密
   - 特征分解: 全量稠密 eig
   - 最短路: 深层循环中反复调用点到点 dijkstra
   - 特点: 小图可用；图一大后速度瓶颈明显

2) src/gen_reduction_v2.py
   - 保留稠密矩阵与全量 eig
   - 优化点: 预计算 all_pairs_dijkstra_path_length，后续查表
   - 优势: 比 v1 快
   - 瓶颈: all-pairs 路径字典非常吃内存，中等图以上容易顶内存

3) src/gen_reduction_v3.py
   - 稀疏邻接矩阵 + 稀疏归一化拉普拉斯
   - 稀疏特征求解（限制 k，默认上限 512）
   - 最短路改为稀疏图单源 dijkstra（按 source 求 SSSP）
   - 适用: 中大规模稀疏图，时间/内存综合最均衡

4) src/gen_reduction_v4.py
   - 在 v3 基础上补回原语义中的不可达惩罚项（avg step/path 比例）
   - 增加 SSSP 缓存，避免同一 source 重复 dijkstra
   - 适用: 追求 v3 性能同时更贴近原公式语义
   - 状态: 建议先做小批量回归验证再大规模替换


### 2.3 生成脉络树 skeleton_tree

- 版本:
  - src/gen_skeleton_tree.py
    - 重复检测环，按环上边两端 reduction 差值最大优先切边
    - 直到图无环，形成树化结构
  - src/gen_skeleton_tree_test_reduction.py
    - 用于对比不同 reduction 方案导致的切边差异
    - 额外返回清洗切边与 reduction 切边，方便做归因分析

- 输出路径:
  - temp_files/skeleton_tree_by_year/{pid}/{year}


### 2.4 计算树深

- 脚本: src/gen_tree_node_deep.py
- 逻辑: 从 seminal pid 做广度优先层次展开，得到 depth -> nodes 映射
- 输出路径:
  - temp_files/tree_deep_by_year/{pid}/{year}


### 2.5 计算点熵/树熵

- 脚本: src/gen_node_and_tree_entropy.py
- 逻辑: 结合原始引文边与 skeleton_tree 结构，计算 subtree entropy 与 node entropy（含互熵项）
- 输出路径:
  - 节点知识熵: temp_files/node_entropy_by_year/{pid}/{year}
  - 子树熵: temp_files/subtree_entropy_by_year/{pid}/{year}


### 2.6 VD 与 delta-D 演化

- VD:
  - 函数: visible_depth_evoluation
  - 脚本: src/gen_KE_and_VD_evolution_pics.py
  - 数值输出: temp_files/year2visible_depth/{pid}.json
  - 曲线图输出: temp_files/skeleton_evolution_related_jpg/{pid}/max_visible_depth.jpg

- delta-D:
  - 函数: delta_d_evolution
  - 脚本: src/get_delta_D_for_specific_topic.py
  - 数值输出: temp_files/year2delta_d/{pid}.json


## 3. 中间流水线脚本家族（gen_intermediate_files*）对比

### 3.1 串行主线

1) src/gen_intermediate_files.py
   - 老版本
   - 使用 gen_source_gml_by_year + gen_reduction（v1）
   - 默认 max_year 参数常见到 2021（早期设置）

2) src/gen_intermediate_files_v2.py
   - 升级版
   - 使用 gen_source_gml_by_year_scc + gen_reduction_v2
   - 包含 VD 与 delta-D 后处理

3) src/gen_intermediate_files_v2_param.py
   - 推荐命令行入口
   - 用法: python gen_intermediate_files_v2_param.py <pid>
   - 更适合多 screen 手工并行多个 pid

4) src/gen_intermediate_files_v2_copy.py / src/gen_intermediate_files_v2_copy2.py
   - 主要是不同 pid 清单的运行副本
   - 核心逻辑基本与 v2 类同


### 3.2 按年份并行主线

1) src/gen_intermediate_files_parallel.py
   - 年份维度并行（Pool）
   - 默认 reduction_v2
   - 分成 Barrier 1（切片与建目录）-> 并行年份 -> Barrier 2（可选后处理）

2) src/gen_intermediate_files_parallel_v2.py / src/gen_intermediate_files_parallel_v3.py
   - 默认切到 reduction_v3
   - 增加年份过滤策略（例如 2008-2010 或 2011+）
   - 适合分区间拆任务、分机或分时段运行

3) src/gen_intermediate_files_parallel_T4_2025.py
   - 面向特定年份窗口（示例里常见 2025 或 2011+）
   - 可跳过重新切片，直接复用已有 source_gml_by_year


## 4. 可视化与属性增强脚本对比

1) src/run_only_gen_visible_depth.py
   - 仅补跑属性树和高 KE 节点细节
   - 适合中间文件已算完但属性图漏跑的补算场景

2) src/gen_idea_tree_attributed_and_detail_file.py
   - 生成属性化脉络树 gml、高 KE 节点细节图等
   - 会依赖简化树文件，不存在时尝试调用 simply_skeleton_tree_2 生成
   - 典型细节图路径: temp_files/high_KE_node_detail_png/{seminal_pid}/{year}.jpg

3) src/render_simplified_tree_v2.py
   - 读取简化树、熵和深度信息，用 Graphviz 产出紧凑 DOT 布局图
   - 输出路径: temp_files/dot_output/{pid}/


## 5. 总结脚本（dpi_summary*）版本演进

1) src/dpi_summary_v1.py
   - 早期方案，依赖 MySQL 老库，模型偏早期（gpt-4o-mini）

2) src/dpi_summary_v2.py
   - 切到 ES，开始修复 GML 解析与节点信息提取

3) src/dpi_summary_v3.py
   - 在 v2 上增加“关键节点外的其他节点信息”输入，prompt 信息更全

4) src/dpi_summary_v4.py
   - 保持多年度结构分析框架，替换模型/提示策略（如 deepseek-reasoner）做对比

5) src/dpi_summary_simplified.py
   - 只用最后一年，面向快速摘要而非完整演化叙事

6) src/dpi_summary_v6.py（当前主线）
   - 强化多年度结构化 prompt、引用关系解释和参考文献输出格式
   - 默认模型可见为 gpt-5-mini（以脚本当前配置为准）

7) src/dpi_summary_compare.py / src/dpi_summary_compare_v2.py
   - 用于多模型/多策略横向对比评测


## 6. 你关心的 clean_reference_data 复用问题

### 6.1 现状

clean_reference_data 目前至少在以下脚本重复定义（9 处）：
- src/gen_source_gml_by_year.py
- src/gen_source_gml_by_year_scc.py
- src/gen_reduction.py
- src/gen_reduction_v2.py
- src/gen_reduction_v3.py
- src/gen_reduction_v4.py
- src/gen_skeleton_tree.py
- src/gen_skeleton_tree_test_reduction.py
- src/gen_node_and_tree_entropy.py

### 6.2 影响

- 维护成本高: 修一个 bug 需要改多处
- 行为不一致风险: 不同模块“清洗后网络”可能有细微差异
- 版本对比时噪声变大: 你以为是 reduction 差异，实际可能混入清洗差异

### 6.3 推荐优化写法

1. 抽公共模块
   - 新建 src/common/reference_cleaning.py
   - 提供统一接口: clean_reference_data(nodes, edges, top_id, strategy='classic'|'scc', max_date='2025-05-30')

2. 把策略参数化
   - classic: 兼容旧版 find_cycle 行为
   - scc: 使用强连通分量切环
   - 由调用方选择，避免复制粘贴

3. 统一时间边界配置
   - 现在代码里有多处硬编码 2025 或当天日期混用
   - 建议统一从配置文件读取（例如 src/config.py）

4. 做最小回归测试
   - 选 3-5 个不同规模 pid
   - 比对节点数、边数、是否 DAG、VD 和 delta-D 变化


## 7. 按图规模的版本选择建议

1. 小规模/中小规模图
   - 可用: gen_reduction.py
   - 优点: 与最原始论文实现语义最接近

2. 中等规模图
   - 可用: gen_reduction_v2.py
   - 注意: all-pairs 内存可能成为上限

3. 中大规模稀疏图（当前首选）
   - 可用: gen_reduction_v3.py
   - 若希望更接近原惩罚语义并减少重复 SSSP: gen_reduction_v4.py（先小样本验证）

4. 多年大量任务批处理
   - 推荐: gen_intermediate_files_parallel_v3.py 或 gen_intermediate_files_parallel_T4_2025.py
   - 可按年份分段并行（比如 2008-2010 / 2011+）


## 8. 关键产物路径速查

- 原始引文网络: input/source_gml/{pid}.gml
- 年度切片: temp_files/source_gml_by_year/{pid}/{year}.gml
- skeleton tree: temp_files/skeleton_tree_by_year/{pid}/{year}
- tree depth: temp_files/tree_deep_by_year/{pid}/{year}
- node entropy: temp_files/node_entropy_by_year/{pid}/{year}
- subtree entropy: temp_files/subtree_entropy_by_year/{pid}/{year}
- 属性化树与细节: temp_files/attributed_idea_tree_by_year/{pid}/... 与 temp_files/high_KE_node_detail_png/{pid}/{year}.jpg
- VD 数值: temp_files/year2visible_depth/{pid}.json
- delta-D 数值: temp_files/year2delta_d/{pid}.json
- VD/KE 曲线: temp_files/skeleton_evolution_related_jpg/{pid}/...
- DOT 渲染: temp_files/dot_output/{pid}/...
- 汇总报告: output/ 下各 final_report*.txt 或自定义输出目录


## 9. 推荐执行模板（与你当前习惯一致）

1. 检索并人工选 pid
   - python src/test_pid.py

2. 生成 source gml
   - python src/gen_source_gml.py

3. 生成中间文件（单 pid）
   - python src/gen_intermediate_files_v2_param.py <pid>

4. 补跑属性化与高 KE 细节
   - python src/run_only_gen_visible_depth.py

5. DOT 演化图
   - python src/render_simplified_tree_v2.py

6. 生成总结
   - python src/dpi_summary_v6.py

注: 多 pid 时，建议你继续用多个 screen 并行 pid；单 pid 内部按年份并行可切到 parallel 系列脚本。
