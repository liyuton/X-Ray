#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import math
import csv
import logging
import subprocess
from graphviz import Digraph, Source
from elasticsearch import Elasticsearch
from simply_skeleton_tree import simply_skeleton_tree_2_B

# ================= logging =================
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# ================= 工具函数 =================
def gen_node_size(pid2entropy):
    """根据熵值生成节点大小"""
    if not pid2entropy: return {}
    max_entropy = 0.0
    processed_entropy = {}
    for pid, v in pid2entropy.items():
        try: val = float(v)
        except: val = 0.0
        # 对超大熵值进行平滑处理
        if val > 1000: val = 1000 + math.log(max(1.0, val - 1000)) * 10.0
        max_entropy = max(max_entropy, val)
        processed_entropy[str(pid)] = val
    
    if max_entropy <= 0: return {str(pid): 10 for pid in processed_entropy}
    factor = 190.0 / max_entropy
    return {pid: factor * v + 10.0 for pid, v in processed_entropy.items()}

def get_edge_color_by_mixe_node_color(source_color, target_color):
    """混合起始节点颜色生成边颜色"""
    def to_int(hex_pair):
        try: return int(hex_pair, 16)
        except: return 128
    sc = source_color if source_color and source_color.startswith('#') else '#808080'
    tc = target_color if target_color and target_color.startswith('#') else '#808080'
    r = (to_int(sc[1:3]) + to_int(tc[1:3])) // 2
    g = (to_int(sc[3:5]) + to_int(tc[3:5])) // 2
    b = (to_int(sc[5:7]) + to_int(tc[5:7])) // 2
    return '#{0:02x}{1:02x}{2:02x}'.format(r, g, b)

# ================= 坐标与位置计算 =================
def get_node_x_from_graphviz_plain(gv_path):
    """解析 Graphviz 生成的物理坐标"""
    if not os.path.exists(gv_path):
        logging.error(f"解析失败，找不到布局文件: {gv_path}")
        return {}
    try:
        cmd = ["dot", "-Tplain", gv_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        node_x = {}
        for line in proc.stdout.splitlines():
            parts = line.split()
            if parts and parts[0] == "node":
                pid = parts[1].strip('"')
                node_x[pid] = float(parts[2])
        return node_x
    except Exception as e:
        logging.error(f"执行 dot 命令失败: {e}")
        return {}

def compute_visual_positions(gv_path, tree_deep, visible_pids):
    """计算节点在图片中的排名 (基于物理 X 坐标)"""
    node_x = get_node_x_from_graphviz_plain(gv_path)
    pos_map = {}
    for depth, pids in tree_deep.items():
        try: d_int = int(depth)
        except: continue
        # 仅对图中出现的节点进行该层内的排序
        layer_visible = []
        for pid in pids:
            p_str = str(pid)
            if p_str in visible_pids:
                x = node_x.get(p_str, 0.0)
                layer_visible.append({'pid': p_str, 'x': x})
        
        # 物理坐标排序
        layer_visible.sort(key=lambda n: (n['x'], n['pid']))
        for i, node in enumerate(layer_visible):
            pos_map[node['pid']] = (d_int, i + 1)
    return pos_map

# ================= ES & CSV 逻辑 =================
es_client = Elasticsearch(["http://readonly:readonly@10.10.12.1:9201"])

def get_paper_info(pid):
    try:
        query = {"query": {"term": {"_id": f"https://openalex.org/W{pid}"}}, "_source": ["title", "publication_year", "cited_by_count"]}
        res = es_client.search(index="acemap.works", body=query)
        hits = res.get("hits", {}).get("hits", [])
        if hits:
            s = hits[0]["_source"]
            return s.get("title"), s.get("publication_year"), s.get("cited_by_count")
    except: pass
    return None, None, None

def save_high_ke_csv(pid, year, pid2entropy, tree_deep, node_detail, threshold, out_dir, gv_path, cache):
    os.makedirs(out_dir, exist_ok=True)
    visible_nodes = set(str(k) for k in node_detail.keys())
    visible_nodes.add(str(pid))
    
    # 获取位置映射
    pos_map = compute_visual_positions(gv_path, tree_deep, visible_nodes)
    
    rows = []
    # 筛选高 KE 节点
    for pstr, ent in pid2entropy.items():
        if float(ent) >= threshold or pstr == str(pid):
            if pstr not in cache: cache[pstr] = get_paper_info(pstr)
            title, pubyr, cit = cache[pstr]
            d, pos = pos_map.get(pstr, (None, None))
            if d is not None:
                rows.append({"pid": pstr, "entropy": ent, "depth": d, "pos": pos, 
                             "in_simplified": pstr in node_detail, "year": pubyr, "title": title, "citation": cit})
    
    rows.sort(key=lambda x: (x["depth"], -x["entropy"]))
    csv_path = os.path.join(out_dir, f"{pid}_{year}_high_ke_nodes.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pid", "entropy", "depth", "pos", "in_simplified", "year", "title", "citation"])
        writer.writeheader()
        writer.writerows(rows)
    logging.info(f"CSV已生成: {csv_path}")

# ================= 渲染函数 (已修改着色逻辑) =================
def render_simplified_tree_dot(pid, year, base_output_dir, threshold=10, use_default_threshold_dir=False):
    pid, year = str(pid), str(year)
    base = "../temp_files"
    # simplied_path = f"../temp_files/simplied_skeleton_tree_by_year/{pid}/{year}"
    simply_skeleton_tree_2_B(pid, year, threshold)
    # if not os.path.exists(simplied_path):
    #     logging.info("simplified skeleton json missing, attempting to generate via simply_skeleton_tree_2_B()")
    #     if simply_skeleton_tree_2_B is None:
    #         raise FileNotFoundError(f"simplified skeleton missing and simply_skeleton_tree_2 not available to generate: {simplied_path}")
    #     simply_skeleton_tree_2_B(pid, year, threshold)
    #     if not os.path.exists(simplied_path):
    #         raise FileNotFoundError(f"after generation attempt, still missing: {simplied_path}")
    # 1. 加载原始数据
    pid2entropy = json.load(open(f"{base}/node_entropy_by_year/{pid}/{year}"))
    tree_deep = json.load(open(f"{base}/tree_deep_by_year/{pid}/{year}"))
    node_detail = json.load(open(f"{base}/simplied_skeleton_tree_by_year/{pid}/{year}"))

    # 2. 路径处理
    if use_default_threshold_dir:
        gv_dir = os.path.join(base, "tree_graphviz", pid)
        png_dir = os.path.join(base_output_dir, pid)
    else:
        gv_dir = os.path.join(base, "tree_graphviz", pid, f"threshold_{threshold}")
        png_dir = os.path.join(base_output_dir, pid, f"threshold_{threshold}")
    os.makedirs(gv_dir, exist_ok=True)
    os.makedirs(png_dir, exist_ok=True)

    gv_path = os.path.join(gv_dir, f"{pid}_{year}_tree.gv")
    png_base = os.path.join(png_dir, f"{pid}_{year}_tree")

    if os.path.exists(gv_path): os.remove(gv_path)

    # 3. 条件着色逻辑：可见层压缩后按排名渐变色，不可见层保持灰色
    depth2color = {
        'root': '#ff0000', 
        'invisible': '#959595',
        '1': '#ffe306', '2': '#ff723a', '3': '#f81463', '4': '#9d126f', '5': '#6c48aa', 
        '6': '#0a0da7', '7': '#0000ff', '8': '#0000ff', '9': '#0000ff', '10': '#0000ff'
    }

    # 3.1 找出哪些层级包含熵值 >= threshold 的节点
    visible_depths = set()
    for deep, nodes in tree_deep.items():
        if not isinstance(nodes, (list, tuple)): continue
        for p_id in nodes:
            key = str(p_id)
            # 获取该节点熵值
            try:
                ke_val = float(pid2entropy.get(key, 0.0))
            except:
                ke_val = 0.0
            
            # 只要有一个节点满足阈值，该层就被标记为“可见色”
            if ke_val >= threshold:
                visible_depths.add(str(deep))
                break # 该层已激活，无需继续检查同层其他节点

    # 根层不参与可见层排名映射
    if '0' in visible_depths:
        visible_depths.discard('0')

    # 3.2 构建 pid2color 映射（先全部灰色）
    pid2color = {}
    for deep, nodes in tree_deep.items():
        for p_id in nodes:
            pid2color[str(p_id)] = depth2color['invisible']

    # 可见层按深度排序后重新映射到颜色序号 1,2,3...
    sorted_visible_depths = sorted(list(visible_depths), key=lambda x: int(x))
    for i, d in enumerate(sorted_visible_depths):
        color_key = str(i + 1)
        color_for_depth = depth2color.get(color_key, depth2color['invisible'])
        for p_id in tree_deep.get(d, []):
            pid2color[str(p_id)] = color_for_depth

    # 3.3 强制根节点为红色
    pid2color[pid] = depth2color['root']

    # 4. 构建图
    g = Digraph("G", filename=gv_path)
    g.attr(rankdir="TB", splines="true")
    # 增加 newrank=true 可以在某些情况下帮助对齐
    g.attr(newrank='true') 
    g.node_attr.update(style="filled", label="")
    
    id2size = gen_node_size(pid2entropy)

    for nid in node_detail:
        nid_str = str(nid)
        size = id2size.get(nid_str, 10)
        # 大小缩放系数与原逻辑保持一致
        width = max(0.1, min(4.0, size / 45.0))
        # 颜色从 pid2color 获取，如果没有则默认灰色
        color = pid2color.get(nid_str, '#959595')
        g.node(nid_str, shape="circle", width=str(width), color=color)

    for nid, info in node_detail.items():
        for src in info.get('cite', []):
            src_str, nid_str = str(src), str(nid)
            if src_str in node_detail:
                # 边颜色混合
                c_src = pid2color.get(src_str, '#959595')
                c_tgt = pid2color.get(nid_str, '#959595')
                ec = get_edge_color_by_mixe_node_color(c_src, c_tgt)
                
                # 边权重处理（参考逻辑中根节点的边加粗逻辑）
                w = "1"
                if src_str == pid: w = "10"
                
                g.edge(src_str, nid_str, color=ec, weight=w)

    # 5. 保存并渲染
    g.save(gv_path)
    Source(g.source).render(filename=png_base, format="png", cleanup=True)
    
    return gv_path, pid2entropy, tree_deep, node_detail

# ================= 主程序 =================
def main(target_pid, thresholds, output_root):
    cache = {}
    y_dir = f"../temp_files/node_entropy_by_year/{target_pid}"
    use_default_threshold_dir = len(thresholds) == 1 and thresholds[0] == 10
    try:
        years = sorted(y for y in os.listdir(y_dir) if y.isdigit())
    except FileNotFoundError:
        logging.error(f"找不到目录: {y_dir}")
        return

    for th in thresholds:
        for yr in years:
            try:
                gv, ent, deep, det = render_simplified_tree_dot(target_pid, yr, output_root, th, use_default_threshold_dir)
                if use_default_threshold_dir:
                    out_path = os.path.join(output_root, target_pid)
                else:
                    out_path = os.path.join(output_root, target_pid, f"threshold_{th}")
                save_high_ke_csv(target_pid, yr, ent, deep, det, th, out_path, gv, cache)
            except Exception as e:
                logging.error(f"Error at {yr}: {e}")

if __name__ == "__main__":
    pids = ["3177828909"]
    # pids = [
    # '4313324526',
    # '1575585006',
    # '1486722793',
    # '2094366129',
    # '2063264144',
    # '1538902372',
    # '2137590150',
    # '2129319296',
    # '2033541702']
    thresholds = [10]

    output_root = '../output/20260607_alphafold' 

    for pid in pids:
        main(pid, thresholds, output_root)
