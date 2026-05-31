###使用最后一年的脉络树和ES库生成总结###
# simplified_summary_keep_original_es_and_completion.py
"""
简化版：仅使用最后一年（最新）的 .gml 文件，忽略节点颜色/大小，只使用节点 id 与引用关系，
生成你要求的 prompt 格式并调用原始 completion()。

保留：原始的 es_hosts 列表、原始 completion() 函数实现、以及原始 imports 引入方式。
"""
import requests
from elasticsearch import Elasticsearch
from readgml import readgml
import os
import json
import re

# ---------------- 原始配置（保持不变） ----------------
es_hosts = [
    "http://10.10.10.0:9200",
    "http://elastic:ai8WoTKcmzUC9AW$@10.10.12.1:9200",
    "http://readonly:readonly@10.10.12.1:9201"
]
# 使用原始脚本中选择的 es_client（dev/read-only index）
es_client = Elasticsearch(es_hosts[2])
ES_INDEX = "acemap.works"

# -------------- 本地路径配置（可按需修改） --------------
BASE_GML_PATH = "../temp_files/attributed_idea_tree_by_year"
OUTPUT_DIR = "../output/final_report"

# ----------------- 辅助函数 -----------------
def find_latest_gml_path(base_path, pid):
    folder = os.path.join(base_path, str(pid))
    if not os.path.isdir(folder):
        raise FileNotFoundError(f"PID 文件夹不存在: {folder}")

    files = [f for f in os.listdir(folder) if f.lower().endswith('.gml')]
    if not files:
        raise FileNotFoundError(f"未在 {folder} 找到任何 .gml 文件")

    def extract_num(name):
        m = re.search(r'(\d{4})', name)
        if m:
            return int(m.group(1))
        return int(os.path.getmtime(os.path.join(folder, name)))

    files_sorted = sorted(files, key=lambda f: extract_num(f), reverse=True)
    latest = files_sorted[0]
    return os.path.join(folder, latest)

def flatten_nodes_edges(raw_nodes, raw_edges):
    nodes = []
    edges = []

    if isinstance(raw_nodes, list):
        for item in raw_nodes:
            if isinstance(item, dict) and 'id' in item:
                nodes.append(item)
            elif isinstance(item, (list, tuple)):
                for sub in item:
                    if isinstance(sub, dict) and 'id' in sub:
                        nodes.append(sub)
    elif isinstance(raw_nodes, dict) and 'id' in raw_nodes:
        nodes.append(raw_nodes)

    if isinstance(raw_edges, list):
        for item in raw_edges:
            if isinstance(item, dict) and 'source' in item and 'target' in item:
                edges.append(item)
            elif isinstance(item, (list, tuple)):
                for sub in item:
                    if isinstance(sub, dict) and 'source' in sub and 'target' in sub:
                        edges.append(sub)
    elif isinstance(raw_edges, dict) and 'source' in raw_edges and 'target' in raw_edges:
        edges.append(raw_edges)

    for n in nodes:
        n['id'] = str(n.get('id'))
    for e in edges:
        e['source'] = str(e.get('source'))
        e['target'] = str(e.get('target'))

    return nodes, edges

def get_paper_info_from_es(es_client_local, pid):
    try:
        openalex_id = f"https://openalex.org/W{pid}"
        query = {
            "query": {"term": {"_id": openalex_id}},
            "_source": ["title", "abstract"]
        }
        resp = es_client_local.search(index=ES_INDEX, body=query)
        hits = resp.get('hits', {}).get('hits', [])
        if hits:
            src = hits[0]['_source']
            return src.get('title', f'Paper_{pid}'), src.get('abstract', 'Abstract not available')
        # 备选：尝试直接以 pid 作为 _id
        query2 = {
            "query": {"term": {"_id": str(pid)}},
            "_source": ["title", "abstract"]
        }
        resp2 = es_client_local.search(index=ES_INDEX, body=query2)
        hits2 = resp2.get('hits', {}).get('hits', [])
        if hits2:
            src = hits2[0]['_source']
            return src.get('title', f'Paper_{pid}'), src.get('abstract', 'Abstract not available')
    except Exception:
        pass
    return f"Paper_{pid}", "Abstract not available"

def build_prompt(pid, leading_info, other_infos, edges):
    top_pid_info = leading_info

    other_paper_info = ""
    for oid, info in other_infos.items():
        other_paper_info += f"ID: {oid}\nTitle: {info[0]}\nAbstract: {info[1]}\n\n"

    reference_info = ""
    for e in edges:
        reference_info += f"{e['source']} -> {e['target']}\n"

    prompt = f"""Given the list of papers below and their citation relationships, write a concise and coherent analysis of these papers. 

### Leading Paper Information ###
Leading Paper ID: {pid}
Leading Paper Title: {top_pid_info[0]}
Leading Paper Abstract: {top_pid_info[1]}

### Other Paper Information ###
{other_paper_info}

### Reference Information (Note: A -> B means that A is cited by B!) ###
{reference_info}
"""
    return prompt

# ---------------- 原始 completion() 实现（保持不变） ----------------
def completion(user_prompt):
    dialogue = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_prompt},
    ]
    sjtu_temp = 'sk-o2ndZu1j0iWAg7LnJtsUzB957Zklec6mXnFDnDpA3gpOiSrt'

    response = requests.post(
        url='https://openai.acemap.cn/v1/chat/completions',
        headers={'Authorization': f'Bearer {sjtu_temp}'},
        # json={'model': 'gpt-5-mini', 'messages': dialogue},
        json={'model': 'gpt-5-mini', 'messages': dialogue},
        verify=False,
        timeout=600
    )
    return response.json()['choices'][0]['message']['content']

# ----------------- 主流程 -----------------
def summarize_from_latest_gml(pid, base_path=BASE_GML_PATH):
    gml_path = find_latest_gml_path(base_path, pid)
    print(f"Using GML file: {gml_path}")

    raw_nodes, raw_edges = readgml.read_gml(gml_path)
    nodes, edges = flatten_nodes_edges(raw_nodes, raw_edges)

    node_ids = [str(n.get('id')) for n in nodes]
    if str(pid) not in node_ids:
        node_ids.append(str(pid))

    leading_title, leading_abstract = get_paper_info_from_es(es_client, pid)

    other_ids = [nid for nid in node_ids if nid != str(pid)]
    other_infos = {}
    for oid in other_ids:
        title, abstract = get_paper_info_from_es(es_client, oid)
        other_infos[oid] = (title, abstract)

    prompt = build_prompt(pid, (leading_title, leading_abstract), other_infos, edges)
    print("Prompt built. Sending to completion API...")
    result = completion(prompt)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, f"simplified_prompt_{pid}.txt"), 'w', encoding='utf-8') as f:
        f.write(prompt)
    with open(os.path.join(OUTPUT_DIR, f"simpllified__result_{pid}.txt"), 'w', encoding='utf-8') as f:
        f.write(result)

    print("Summary generation complete. Results saved to:", OUTPUT_DIR)
    return prompt, result

if __name__ == '__main__':
    PID = 2105934661
    prompt, result = summarize_from_latest_gml(PID)
    print('\n===== Generated Summary =====\n')
    print(result)
