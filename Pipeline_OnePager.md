# Scientific X-ray 一页执行手册（给同事直接照着跑）

适用范围：快速跑通单个或多个 pid 的标准流程。

## 0. 先决条件（1 分钟检查）

1. 进入项目目录：

```bash
cd /home/liyutong1117/jupyter/scientific_x_ray-github/src
```

2. 安装依赖（首次）：

```bash
pip install -r ../requirements.txt
```

3. 确认关键目录存在（没有就自动创建）：

- `../input/source_gml`
- `../temp_files`
- `../output`

## 1. 标准流程（单 pid）

### 步骤1：标题检索候选 pid（人工确认）

```bash
python test_pid.py
```

### 步骤2：生成主题引文网络

在 `gen_source_gml.py` 里配置 `pids` 后运行：

```bash
python gen_source_gml.py
```

期望产物：`../input/source_gml/<pid>.gml`

### 步骤3：中间文件主流程（推荐）

```bash
python gen_intermediate_files_v2_param.py <pid>
```

期望产物：
- `../temp_files/source_gml_by_year/<pid>/`
- `../temp_files/skeleton_tree_by_year/<pid>/`
- `../temp_files/tree_deep_by_year/<pid>/`
- `../temp_files/node_entropy_by_year/<pid>/`
- `../temp_files/subtree_entropy_by_year/<pid>/`
- `../temp_files/year2visible_depth/<pid>.json`
- `../temp_files/year2delta_d/<pid>.json`

### 步骤4：补算属性树与高 KE 细节（可选）

```bash
python run_only_gen_visible_depth.py
```

### 步骤5：DOT 演化图（可选）

```bash
python render_simplified_tree_v2.py --pid <pid> --year <year>
```

### 步骤6：总结（主线）

```bash
python dpi_summary_v6.py
```

## 2. 默认命令模板（按规模）

### 模板A：单 pid（默认推荐）

```bash
cd /home/liyutong1117/jupyter/scientific_x_ray-github/src

# 1) 先在 test_pid.py 里确认标题候选
python test_pid.py

# 2) 在 gen_source_gml.py 里填好 pids=["<pid>"]
python gen_source_gml.py

# 3) 生成中间文件
python gen_intermediate_files_v2_param.py <pid>

# 4) 可选：补算属性
python run_only_gen_visible_depth.py

# 5) 可选：渲染 DOT
python render_simplified_tree_v2.py --pid <pid> --year 2025

# 6) 生成总结
python dpi_summary_v6.py
```

### 模板B：多 pid（串行稳妥版）

```bash
cd /home/liyutong1117/jupyter/scientific_x_ray-github/src

for pid in 2100837269 2105934661 3090704166; do
  python gen_intermediate_files_v2_param.py "$pid"
done
```

### 模板C：多 pid（并行提速版，建议服务器）

```bash
cd /home/liyutong1117/jupyter/scientific_x_ray-github/src

# 每个 pid 启一个后台任务，日志独立输出
for pid in 2100837269 2105934661 3090704166; do
  nohup python gen_intermediate_files_parallel_v2.py "$pid" > "../output/run_${pid}.log" 2>&1 &
done

# 查看进度
tail -f ../output/run_2100837269.log
```

注：并行版常假设已存在 `source_gml_by_year`，若缺失先跑一次 v2_param 或启用对应脚本里的切片步骤。

## 3. 30 秒验收清单

1. `../input/source_gml/<pid>.gml` 存在。
2. `../temp_files/source_gml_by_year/<pid>/` 有多年 gml。
3. `../temp_files/node_entropy_by_year/<pid>/` 与 `tree_deep_by_year/<pid>/` 年份基本对齐。
4. `../temp_files/year2visible_depth/<pid>.json` 与 `year2delta_d/<pid>.json` 存在。
5. 总结结果写入 `../output`。

## 4. 快速故障定位（关键词）

- 关键词：`FileNotFoundError: ../temp_files/source_gml_by_year/...`
  - 含义：按年切片未生成。
  - 处理：先跑 `gen_intermediate_files_v2_param.py <pid>`，或打开并行脚本中的切片步骤。

- 关键词：`Killed` / `MemoryError`
  - 含义：常见于 reduction_v2 内存顶满。
  - 处理：改用 `gen_intermediate_files_parallel_v2.py` 或 `parallel_v3.py`（reduction_v3 路线）。

- 关键词：`graphviz.backend.execute.ExecutableNotFound`
  - 含义：系统未安装 dot。
  - 处理：安装 graphviz 可执行并确认 `dot -V` 可用。

- 关键词：`ConnectionError` / `AuthenticationException`（ES）
  - 含义：Elasticsearch 地址或凭据不可用。
  - 处理：检查脚本内 `es_hosts`，切换可访问节点。

---

维护建议：本手册只保留“最短可执行路径”，算法对比与细节说明请看 `Pipeline_PlanMode.md`。