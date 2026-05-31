# -*- coding: utf-8 -*-
"""
只运行 gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail()
假设前置计算（reduction、skeleton_tree、entropy 等）已完成。
"""

import os
import time
from tqdm import tqdm
from gen_idea_tree_attributed_and_detail_file import gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail


def run_visible_depth_only(pid):
    """
    针对指定主题ID (pid)，逐年执行 gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail。
    """
    base_path = f"../temp_files/source_gml_by_year/{pid}"
    if not os.path.exists(base_path):
        print(f"[错误] 未找到路径: {base_path}")
        return

    # 获取年份列表
    files_list = os.listdir(base_path)
    years_list = sorted([int(file.split('.')[0]) for file in files_list if file.endswith('.gml')])

    print(f"开始执行 gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail() for {pid}")
    print(f"检测到年份列表: {years_list}")

    for year in tqdm(years_list, desc=f"Processing {pid}"):
        start_time = time.time()
        try:
            gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail(pid, year)
            print(f"{pid} - {year} 完成")
        except Exception as e:
            print(f"{pid} - {year} 出错: {e}")
        elapsed = time.time() - start_time
        print(f"运行时间: {elapsed:.2f} 秒\n")

    print(f"所有年份处理完成: {pid}")


if __name__ == "__main__":
    pids = ["2113233457","2137775453"]

    for pid in pids:
        run_visible_depth_only(pid)
