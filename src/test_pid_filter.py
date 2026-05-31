#!/usr/bin/env python3
# coding: utf-8
"""
select_best_matches.py

从结构化的 ES 检索结果 JSON（格式见前一版脚本输出）中，
为每个 query_title 选择一个“最佳匹配”：
  - 优先从 exact_results 中选择 cited_by_count 最大的；
  - 若 exact_results 为空，则从 fuzzy_results 中选择 cited_by_count 最大的；
  - 若都为空，selected_result 为 None。

输出格式:
{
  "Topic A": [
    {
      "query_title": "...",
      "selected_from": "exact" | "fuzzy" | None,
      "selected_result": { ... } | None,
      "selected_rank": int | None
    },
    ...
  ],
  ...
}

Usage:
    python select_best_matches.py input_structured.json output_selected.json
"""
import json
import sys
import os

def to_number(x):
    """尝试把 cited_by_count 转为整数；出错返回 0"""
    if x is None:
        return 0
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return 0

def pick_best_from_list(results_list):
    """
    results_list: list of dicts, each dict 包含 'cited_by_count' 字段（可能为 None / str / int）
    返回 (best_item, best_index) 或 (None, None) 如果列表为空
    选择依据：cited_by_count 最大，若相同选择第一个出现的
    """
    if not results_list:
        return None, None
    best_idx = None
    best_item = None
    best_score = -1
    for i, item in enumerate(results_list):
        score = to_number(item.get('cited_by_count', 0))
        if score > best_score:
            best_score = score
            best_item = item
            best_idx = i
    return best_item, best_idx

def process_input_file(input_path):
    """
    读取结构化 ES 输出（topic -> list of query entries）
    为每个 query 选择一个 best match，返回新的字典结构
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    output = {}
    for topic, entries in data.items():
        out_entries = []
        for entry in entries:
            query_title = entry.get('query_title')
            exact = entry.get('exact_results', []) or []
            fuzzy = entry.get('fuzzy_results', []) or []

            # 优先 exact
            selected = None
            selected_from = None
            selected_rank = None

            if exact:
                best, idx = pick_best_from_list(exact)
                if best is not None:
                    selected = best
                    selected_from = "exact"
                    selected_rank = idx
            elif fuzzy:
                best, idx = pick_best_from_list(fuzzy)
                if best is not None:
                    selected = best
                    selected_from = "fuzzy"
                    selected_rank = idx
            else:
                selected = None
                selected_from = None
                selected_rank = None

            out_entries.append({
                "query_title": query_title,
                "selected_from": selected_from,
                "selected_rank": selected_rank,
                "selected_result": selected
            })
        output[topic] = out_entries
    return output

def main(argv):
    if len(argv) >= 3:
        input_json = argv[1]
        output_json = argv[2]
    else:
        input_json = "/home/liyutong1117/jupyter/scientific_x_ray-github/src/es_search_results_structured.json"
        output_json = "/home/liyutong1117/jupyter/scientific_x_ray-github/src/es_search_selected.json"
        print(f"Using defaults: input={input_json}, output={output_json}")

    if not os.path.exists(input_json):
        print(f"Input file not found: {input_json}")
        sys.exit(1)

    selected = process_input_file(input_json)

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(selected, f, ensure_ascii=False, indent=2)

    print(f"Saved selected matches to: {output_json}")

if __name__ == "__main__":
    main(sys.argv)
