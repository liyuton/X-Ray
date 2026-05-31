# 生成逐年增量的引文网络gml文件（清洗时使用SCC找环切环）
import networkx as nx
import time
import json
import random
import os
import datetime
from readgml import readgml
# from tqdm import tqdm_notebook as tqdm
from multiprocessing.pool import Pool


# In[16]:
import datetime
import time
import networkx as nx

def clean_reference_data(nodes, edges, top_id):
    """
    优化版：
    - 批量过滤时间异常节点/边（用 list comprehension）
    - 用 strongly_connected_components 定位含环子图
    - 在每个 SCC 内：先删除违反时间顺序的边（target_time >= source_time）
      若仍有环，按时间降序排序打分，贪心删除反向边直到变为 DAG
    返回更新后的 nodes, edges（与原接口一致）
    """
    source_nodes_len = len(nodes)
    source_edges_len = len(edges)

    # 时间边界
    # today = datetime.date.today()
    # time_stamp_flag = int(time.mktime(time.strptime(today.strftime('%Y-%m-%d'), '%Y-%m-%d')))
    time_stamp_flag = int(time.mktime(time.strptime('2025-05-30', '%Y-%m-%d')))

    # 先找到 top paper 的时间戳（如果存在）
    top_paper_time_stamp = 0
    id2time_stamp = {}
    for node in nodes:
        if node['id'] == top_id:
            try:
                top_paper_time_stamp = int(time.mktime(time.strptime(node['date'], '%Y-%m-%d')))
            except Exception:
                top_paper_time_stamp = 0

    # 计算每个节点的时间戳并找出时间异常节点集合（去除在top_paper之前的论文和在设定当前时间之后的论文）
    out_date_id_set = set()
    for node in nodes:
        try:
            node_ts = int(time.mktime(time.strptime(node['date'], '%Y-%m-%d')))
        except Exception:
            # 若日期解析失败也视为异常
            node_ts = time_stamp_flag + 1
        id2time_stamp[node['id']] = node_ts
        if node_ts > time_stamp_flag or node_ts < top_paper_time_stamp:
            out_date_id_set.add(node['id'])

    # 批量过滤异常节点和与其关联的边（避免逐个 remove 导致 O(n^2)）
    nodes_copy = [node for node in nodes if node['id'] not in out_date_id_set]
    edges_copy = [edge for edge in edges
                  if edge['source'] not in out_date_id_set
                  and edge['target'] not in out_date_id_set
                  and edge['source'] != top_id]  # 移除 top_paper 指向他人的边

    # 构建 DiGraph（批量添加）
    G = nx.DiGraph()
    G.add_nodes_from([node['id'] for node in nodes_copy])
    G.add_edges_from([(e['source'], e['target']) for e in edges_copy])

    need_cut_edge = []  # list of tuples (u,v) 表示要移除的边

    # 若已经是 DAG，则直接跳过找环步骤
    if not nx.is_directed_acyclic_graph(G):
        # 遍历每个强连通分量（只处理 size>1 的）
        for scc in nx.strongly_connected_components(G):
            if len(scc) <= 1:
                continue
            sub_nodes = set(scc)
            subG = G.subgraph(sub_nodes).copy()

            # 首先：删除每个强连通分量子图内明显违反时间顺序的边（target 时间 >= source 时间）
            for (u, v) in list(subG.edges()):
                if id2time_stamp.get(v, 0) >= id2time_stamp.get(u, 0):
                    need_cut_edge.append((u, v))
                    G.remove_edge(u, v)
                    subG.remove_edge(u, v)

            # 如果子图仍然有环，使用基于时间的启发式贪心删除边直到变为 DAG
            # 排序规则：时间降序（最新的排在前），时间相同按 node id 作为次级键
            while not nx.is_directed_acyclic_graph(subG) and subG.number_of_edges() > 0:
                order = sorted(subG.nodes(), key=lambda n: (-id2time_stamp.get(n, 0), n))
                rank = {n: i for i, n in enumerate(order)}  # 为每个节点分配一个 rank（整数索引）越小越新

                removed = False
                # 找到第一条“逆序边”并删除：如果 rank[u] > rank[v] 表示 u 比 v 更旧（不应该引用更新的）
                for (u, v) in list(subG.edges()):
                    if rank.get(u, 0) > rank.get(v, 0) or (rank.get(u, 0) == rank.get(v, 0) and u > v):
                        need_cut_edge.append((u, v))
                        G.remove_edge(u, v)
                        subG.remove_edge(u, v)
                        removed = True
                        break

                if not removed:
                    # 极端情况：没有找到基于 rank 的逆序边（理论上极少），退化为删除任意一条边（选择度小的边更稳妥）
                    # 选择出度或入度较小的边以尽量保留“重要”连通性
                    min_score = None
                    candidate = None
                    for (u, v) in subG.edges():
                        score = subG.out_degree(u) + subG.in_degree(v)
                        if min_score is None or score < min_score:
                            min_score = score
                            candidate = (u, v)
                    if candidate is None:
                        break
                    need_cut_edge.append(candidate)
                    G.remove_edge(candidate[0], candidate[1])
                    subG.remove_edge(candidate[0], candidate[1])

    # 根据 need_cut_edge 从 edges_copy 中删除对应边，生成最终边集
    need_cut_set = set(need_cut_edge)
    edges_result = []
    remed_edge = []
    for edge in edges_copy:
        tup = (edge['source'], edge['target'])
        if tup in need_cut_set:
            remed_edge.append(edge)
        else:
            edges_result.append(edge)

    nodes_result = nodes_copy

    # 简单一致性检查（可选）
    try:
        if len(nodes_result) + len(out_date_id_set) != source_nodes_len or \
           len(edges_result) + len(need_cut_edge) + sum(1 for e in edges if e['source'] == top_id) != source_edges_len:
            # 注意：原代码中 cut_edge_num 统计了被 out-date 或 top_id 引起的删除数，这里用更保守的检查或记录日志即可
            # print('warning: inconsistent counts after cleaning')
            pass
    except Exception:
        pass

    return nodes_result, edges_result



# In[13]:



def gen_year_by_year_source_gml(pid, max_year=2025):
    
    allowed_min_nodes_num = 5  # 所允许的领域内最少paper数
    nodes, edges = readgml.read_gml(f"../input/source_gml/{pid}.gml")
    # print(type(nodes), type(edges))
    # print(len(nodes), len(edges))
    # print(nodes[:3])
    # print(edges[:3])
    # print("-" * 50)
    nodes, edges = clean_reference_data(nodes, edges, int(pid))
    # nodes, edges = clean_reference_data(nodes, edges, pid)
    # print(type(nodes), type(edges))
    # print(len(nodes), len(edges))
    # print("-" * 50)
    pid2label = {}
    pid2date = {}
    for node in nodes:
        # pid2label[int(node['id'])] = node['label']
        # pid2date[int(node['id'])] = node['date']
        pid2label[node['id']] = node['label']
        pid2date[node['id']] = node['date']
    min_year = min([int(node['date'][0:4]) for node in nodes])
    # max_year = int(datetime.datetime.now().year)
    year2nodes = {}
    year2edges = {}
    for i in range(max_year-min_year+1):
        year2nodes[min_year+i] = set()
        for node in nodes:
            if int(node['date'][0:4]) <= (min_year+i):
                year2nodes[min_year+i].add(node['id'])
    for year in year2nodes:
        if len(year2nodes[year]) < allowed_min_nodes_num: # 当前年份内paper数过少，不分析
            continue
        else:
            year2edges[year] = []
            for edge in edges:
                if edge['source'] in year2nodes[year] and edge['target'] in year2nodes[year]:
                    year2edges[year].append((edge['source'], edge['target']))
                    
    if not os.path.exists(f"../temp_files/source_gml_by_year/{pid}"):
        os.makedirs(f"../temp_files/source_gml_by_year/{pid}")
        
    for year in year2edges:
        nodes_list = year2nodes[year]
        edges_list = year2edges[year]
        graph_info = 'graph [\n  directed 1\n'
        with open(f"../temp_files/source_gml_by_year/{pid}/{year}.gml", "w+", encoding="utf-8") as f:
            f.write(graph_info)
            for node in nodes_list:
                node_info = '  node' + '\n' + '  [\n    id ' + str(node) + '\n' + '    label ' + str(pid2label[node]).replace('"', "").replace(":", "") + '\n'+'    date ' + str(pid2date[node]) + '\n  ]\n'
                f.write(node_info)
            for edge in edges_list:
                edge_info = '  edge' + '\n' + '  [\n    source ' + str(edge[0]) + '\n' + '    target ' + str(
                    edge[1]) + '\n  ]\n'
                f.write(edge_info)
            f.write("]")