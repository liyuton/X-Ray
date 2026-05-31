#!/usr/bin/env python3
# coding: utf-8

"""
filter_citation_gt50.py

从 es_search_selected.json 中筛选所有 cited_by_count > 50 的 paper，
输出 pid 列表（自动去重）。

Usage:
    python filter_citation_gt50.py input_selected.json
默认输入:
    es_search_selected.json

输出:
    pid_list.json
    pid_list.txt
"""

import json
import sys
import os

THRESHOLD = 50

def to_number(x):
    if x is None:
        return 0
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return 0

def main():
    if len(sys.argv) >= 2:
        input_json = sys.argv[1]
    else:
        input_json = "/home/liyutong1117/jupyter/scientific_x_ray-github/src/es_search_selected.json"

    if not os.path.exists(input_json):
        raise FileNotFoundError(input_json)

    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    pid_set = set()
    detailed_list = []

    for topic, entries in data.items():
        for entry in entries:
            sel = entry.get("selected_result")
            if not sel:
                continue

            citation = to_number(sel.get("cited_by_count"))
            if citation > THRESHOLD:
                pid = sel.get("numeric_id") or sel.get("id")
                if pid:
                    pid_set.add(str(pid))
                    detailed_list.append({
                        "pid": str(pid),
                        "citation": citation,
                        "title": sel.get("title"),
                        "publication_year": sel.get("publication_year"),
                        "topic": topic,
                        "query_title": entry.get("query_title")
                    })

    pid_list = sorted(pid_set)

    # ===== 输出 JSON =====
    with open("pid_list.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "threshold": THRESHOLD,
                "num_papers": len(pid_list),
                "pid_list": pid_list,
                "details": detailed_list
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    # ===== 输出 TXT =====
    with open("/home/liyutong1117/jupyter/scientific_x_ray-github/src/pid_list.txt", "w", encoding="utf-8") as f:
        for pid in pid_list:
            f.write(pid + "\n")

    print(f"筛选完成：citation > {THRESHOLD}")
    print(f"论文数量：{len(pid_list)}")
    print("输出文件：")
    print("  - pid_list.json")
    print("  - pid_list.txt")

if __name__ == "__main__":
    main()
