#!/usr/bin/env python3
# coding: utf-8

"""
batch_es_search_structured.py

从 JSON 文件读入 {topic: [title, ...]}，
对每个 title 调用 Elasticsearch 检索，
返回结果全部用「字典结构」存储，不做任何字符串拼接，
最终写入一个结构化 JSON 文件。
"""

import json
import sys
import os
from elasticsearch import Elasticsearch

# ================= ES 配置 =================
es_hosts = [
    "http://10.10.10.0:9200",
    "http://elastic:ai8WoTKcmzUC9AW$@10.10.12.1:9200",
    "http://readonly:readonly@10.10.12.1:9201"
]
es_client = Elasticsearch(es_hosts[2])
ES_INDEX = "acemap.works"

# ================= 查询函数 =================
def get_paper_id_from_es_by_title(title, size=5):
    """模糊匹配 title"""
    try:
        print(f"[fuzzy] {title}")
        query = {
            "query": {"match": {"title": title}},
            "_source": ["title", "abstract", "_id", "publication_year", "cited_by_count"],
            "size": size
        }
        response = es_client.search(index=ES_INDEX, body=query)
        hits = response.get("hits", {}).get("hits", [])

        results = []
        for hit in hits:
            src = hit.get("_source", {})
            pid = hit.get("_id", "")
            numeric_id = (
                pid.replace("https://openalex.org/W", "")
                if isinstance(pid, str) and pid.startswith("https://openalex.org/W")
                else pid
            )
            results.append({
                "id": pid,
                "numeric_id": numeric_id,
                "title": src.get("title"),
                "abstract": src.get("abstract"),
                "publication_year": src.get("publication_year"),
                "cited_by_count": src.get("cited_by_count")
            })
        return results
    except Exception as e:
        print(f"Fuzzy search error: {e}")
        return []

def get_exact_paper_id_from_es_by_title(title, size=5):
    """精确匹配 title.keyword"""
    try:
        print(f"[exact] {title}")
        query = {
            "query": {"term": {"title.keyword": title}},
            "_source": ["title", "abstract", "_id", "publication_year", "cited_by_count"],
            "size": size
        }
        response = es_client.search(index=ES_INDEX, body=query)
        hits = response.get("hits", {}).get("hits", [])

        results = []
        for hit in hits:
            src = hit.get("_source", {})
            pid = hit.get("_id", "")
            numeric_id = (
                pid.replace("https://openalex.org/W", "")
                if isinstance(pid, str) and pid.startswith("https://openalex.org/W")
                else pid
            )
            results.append({
                "id": pid,
                "numeric_id": numeric_id,
                "title": src.get("title"),
                "abstract": src.get("abstract"),
                "publication_year": src.get("publication_year"),
                "cited_by_count": src.get("cited_by_count")
            })
        return results
    except Exception as e:
        print(f"Exact search error: {e}")
        return []

# ================= 主处理逻辑 =================
def process_titles(input_dict, fuzzy_size=5, exact_size=5):
    """
    input_dict: {topic: [title1, title2, ...]}
    """
    output = {}

    for topic, titles in input_dict.items():
        print(f"\n=== Topic: {topic} ({len(titles)}) ===")
        topic_results = []

        for title in titles:
            item = {
                "query_title": title,
                "fuzzy_results": get_paper_id_from_es_by_title(title, fuzzy_size),
                "exact_results": get_exact_paper_id_from_es_by_title(title, exact_size)
            }
            topic_results.append(item)

        output[topic] = topic_results

    return output

# ================= CLI =================
def main():
    if len(sys.argv) >= 3:
        input_json = sys.argv[1]
        output_json = sys.argv[2]
    else:
        input_json = "/home/liyutong1117/jupyter/scientific_x_ray-github/paper_info.json"
        output_json = "/home/liyutong1117/jupyter/scientific_x_ray-github/src/es_search_results_structured.json"

    if not os.path.exists(input_json):
        raise FileNotFoundError(input_json)

    with open(input_json, "r", encoding="utf-8") as f:
        input_dict = json.load(f)

    results = process_titles(input_dict)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {output_json}")

if __name__ == "__main__":
    main()
