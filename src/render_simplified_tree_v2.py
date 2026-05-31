#!/usr/bin/env python3
## 紧凑布局，保留高知识熵节点子树
"""

生成并渲染简化脉络树的 DOT->PNG 图。

用法:
    python render_simplified_tree.py --pid 62270017 --year 2019

说明:
 - 脚本会按你原有项目路径约定寻找 JSON 文件：
   ../temp_files/node_entropy_by_year/{pid}/{year}
   ../temp_files/tree_deep_by_year/{pid}/{year}
   ../temp_files/simplied_skeleton_tree_by_year/{pid}/{year}
 - 如果简化树文件缺失，会尝试调用 simply_skeleton_tree(pid, year)（如果可用）。
 - 依赖: graphviz 可执行程序（dot）在 PATH 中；python 包 graphviz, networkx, PIL, numpy, pandas 等（脚本会在运行时打印友好提示）。

此脚本包含：
 - gen_node_size: 将节点的熵映射为可视化尺寸的函数（从你的代码改写）render
 - get_edge_color_by_mixe_node_color: 将两个十六进制颜色平均得到边颜色
 - render_simplified_tree_dot: 主函数（读取 JSON、构造 DOT、渲染 PNG）

返回值：在 ../temp_files/dot_output/{pid}_{year}_tree.png

"""

import os
import json
import argparse
import math
import logging
from graphviz import Digraph

# 如果你的项目中有这些函数/模块，可以直接导入；否则脚本会继续并使用本地实现
try:
    from simply_skeleton_tree import simply_skeleton_tree_2_B
except Exception:
    simply_skeleton_tree_2_B = None

# 常量
THRESHOLD = 10

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def wrap_label(s, width=15):
    if s is None:
        return ""
    s = str(s)
    parts = [s[i:i+width] for i in range(0, len(s), width)]
    return "\n".join(parts)


def gen_node_size(id2entropy):
    """将节点熵映射到 10-200 的尺寸区间（与原脚本一致）。"""
    if not id2entropy:
        return {}
    # 保护性处理并计算上限
    max_entropy = 0.0
    for pid, v in id2entropy.items():
        try:
            val = float(v)
        except Exception:
            val = 0.0
        # 仿照原逻辑对极大值做平滑
        if val > 1000:
            val = 1000 + math.log(max(1.0, val - 1000)) * 10.0
        if val > max_entropy:
            max_entropy = val
        id2entropy[pid] = val

    if max_entropy <= 0:
        # fallback: 给所有节点默认尺寸
        return {str(pid): 10 for pid in id2entropy}

    factor = 190.0 / max_entropy
    id2size = {}
    for pid, val in id2entropy.items():
        try:
            id2size[str(pid)] = factor * float(val) + 10.0
        except Exception:
            id2size[str(pid)] = 10.0
    return id2size


def get_edge_color_by_mixe_node_color(source_color, target_color):
    """平均颜色：#RRGGBB -> 平均 -> 返回 #RRGGBB"""
    def to_int(hex_pair):
        try:
            return int(hex_pair, 16)
        except Exception:
            return 128

    sc = source_color if source_color and isinstance(source_color, str) else '#808080'
    tc = target_color if target_color and isinstance(target_color, str) else '#808080'
    sc = sc if sc.startswith('#') else '#' + sc
    tc = tc if tc.startswith('#') else '#' + tc
    r = (to_int(sc[1:3]) + to_int(tc[1:3])) // 2
    g = (to_int(sc[3:5]) + to_int(tc[3:5])) // 2
    b = (to_int(sc[5:7]) + to_int(tc[5:7])) // 2
    return '#{0:02x}{1:02x}{2:02x}'.format(r, g, b)


def render_simplified_tree_dot(seminal_pid, year,
                              output_dir="../temp_files/dot_output",
                              view=False,
                              size_scale=1.0):
    seminal_pid = str(seminal_pid)
    year = str(year)

    node_entropy_path = f'../temp_files/node_entropy_by_year/{seminal_pid}/{year}'
    tree_deep_path = f'../temp_files/tree_deep_by_year/{seminal_pid}/{year}'
    simplied_path = f"../temp_files/simplied_skeleton_tree_by_year/{seminal_pid}/{year}"

    # 检查
    if not os.path.exists(node_entropy_path):
        raise FileNotFoundError(f"node_entropy not found: {node_entropy_path}")
    if not os.path.exists(tree_deep_path):
        raise FileNotFoundError(f"tree_deep not found: {tree_deep_path}")

    if not os.path.exists(simplied_path):
        logging.info("simplified skeleton json missing, attempting to generate via simply_skeleton_tree_2_B()")
        if simply_skeleton_tree_2_B is None:
            raise FileNotFoundError(f"simplified skeleton missing and simply_skeleton_tree_2 not available to generate: {simplied_path}")
        simply_skeleton_tree_2_B(seminal_pid, year, THRESHOLD)
        if not os.path.exists(simplied_path):
            raise FileNotFoundError(f"after generation attempt, still missing: {simplied_path}")

    # 读取 JSON 文件
    with open(node_entropy_path, 'r') as f:
        pid2node_entropy = json.load(f)
    with open(tree_deep_path, 'r') as f:
        tree_node_deep = json.load(f)
    with open(simplied_path, 'r') as f:
        node_detail = json.load(f)

    # 计算可视深度与颜色映射
    depth2color = {
        'root': '#ff0000',
        'invisible': '#959595',
        '1': '#ffe306','2': '#ff723a','3': '#f81463','4': '#9d126f','5': '#6c48aa','6': '#0a0da7','7': '#0000ff',
        '8': '#0000ff','9': '#0000ff','10': '#0000ff'
    }
    visible_depths = set()
    for deep, nodes in tree_node_deep.items():
        if not isinstance(nodes, (list, tuple)):
            continue
        for p_id in nodes:
            key = str(p_id)
            if key not in pid2node_entropy:
                continue
            try:
                ke_val = float(pid2node_entropy[key])
            except Exception:
                continue
            if ke_val >= THRESHOLD:
                visible_depths.add(str(deep))

    if '0' in visible_depths:
        visible_depths.discard('0')

    pid2color = {}
    for deep, nodes in tree_node_deep.items():
        for p_id in nodes:
            pid2color[str(p_id)] = depth2color['invisible']
    pid2color[seminal_pid] = depth2color['root']

    sorted_visible_depths = sorted(list(visible_depths), key=lambda x: int(x))
    for i, d in enumerate(sorted_visible_depths):
        color_for_depth = depth2color.get(str(i+1), depth2color['invisible'])
        for p_id in tree_node_deep.get(d, []):
            pid2color[str(p_id)] = color_for_depth

    # 计算尺寸
    id2size = gen_node_size(dict(pid2node_entropy))

    # 填充 Graphviz
    os.makedirs(f"{output_dir}/{pid}", exist_ok=True)
    out_basename = os.path.join(f"{output_dir}/{pid}", f"{seminal_pid}_{year}_tree")
    
    # --- 修改点 1: 初始化 Graph 时设置 newrank 和 splines 使得布局更对称 ---
    u = Digraph('G', filename=out_basename + '.gv')
    u.attr(rankdir='TB')  # Top to Bottom
    u.attr(newrank='true') # 有助于对齐
    u.attr(splines='true') # 使用曲线，有时能缓解视觉上的不对称
    # ----------------------------------------------------------------
    
    u.attr(size='10,10')
    u.node_attr.update(style='filled')

    # 添加节点
    for nid, ndinfo in node_detail.items():
        nid = str(nid)
        size_val = id2size.get(nid, id2size.get(int(nid) if nid.isdigit() else nid, 10))
        size_val = float(size_val) * float(size_scale)
        width = max(0.1, min(5.0, size_val / 40.0))
        color = pid2color.get(nid, '#959595')

        # 去掉 label，仅显示节点形状和颜色
        u.node(nid,
               label="",
               color=color,
               width=str(width),
               shape='circle',
               style='filled')


    # 添加边
    for nid, ndinfo in node_detail.items():
        nid = str(nid)
        cites = ndinfo.get('cite', []) or []
        for src in cites:
            src = str(src)
            if src not in node_detail:
                continue
            sc = pid2color.get(src, '#959595')
            tc = pid2color.get(nid, '#959595')
            try:
                ecolor = get_edge_color_by_mixe_node_color(sc, tc)
            except Exception:
                ecolor = '#808080'
            
            # --- 修改点 2: 动态设置边的权重 (weight) ---
            # Graphviz 中 weight 越大，边越直、越短。
            # 我们强制让根节点发出的边具有极高的权重，这样根节点会被“钉”在子节点的中心。
            edge_weight = "1"
            if src == seminal_pid:
                edge_weight = "10" 
            
            u.edge(src, nid, color=ecolor, weight=edge_weight)
            # ----------------------------------------

    # 渲染
    try:
        logging.info(f"Rendering DOT -> PNG to {out_basename}.png")
        u.render(out_basename, format='png', view=view, cleanup=False)
        png_path = out_basename + '.png'
        if not os.path.exists(png_path):
            raise RuntimeError(f"render finished but png not found: {png_path}")
        logging.info(f"Saved PNG: {png_path}")
        return png_path
    except Exception as e:
        raise RuntimeError(f"Graphviz render failed: {e}")

def main(pid):
    year_list = sorted([int(file) for file in os.listdir('../temp_files/node_entropy_by_year/'+str(pid))])
    for year in year_list:
        render_simplified_tree_dot(pid, year)



if __name__ == '__main__':
    # pids = [
    #     2045435533
    #     ]
    # pids = ['2045435533','1989561469','2174335611']

    pids = ["2100837269"]

    for pid in pids:
        main(pid)
    


        
