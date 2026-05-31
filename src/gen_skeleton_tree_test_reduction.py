#=====================================================================================
#title  : gen_skeleton_tree.py
#author  : Li Qi
#e-mail  : liqilcn@sjtu.edu.cn or qili_xidian@163.com
#date  : 20200711
#=====================================================================================
# 对比使用不同的reduction计算方法获得的skeleton_tree的差异
import networkx as nx
import numpy as np
import treelib as tl
import queue
import math
import csv
import os
from graphviz import Digraph
from readgml import readgml
from tqdm import tqdm_notebook as tqdm
import json
import datetime
from multiprocessing.pool import Pool


class MyNode:
    def __init__(self,ID,label,year,cite=[],becited=[]):
        self.ID = ID
        self.Label = label
        self.Year = year
        self.Cite = cite[:]
        self.BeCited = becited[:]

    def AppendCite(self,paper):
        self.Cite.append(paper)

    def AppendBeCited(self,paper):
        self.BeCited.append(paper)

    def RemoveCite(self,paper):
        if (paper in self.Cite):
            self.Cite.remove(paper)

    def RemoveBeCited(self,paper):
        if (paper in self.BeCited):
            self.BeCited.remove(paper)

    def ReturnID(self):
        return self.ID

    def ReturnLabel(self,):
        return self.Label

    def ReturnYear(self):
        return self.Year

    def ReturnCite(self):
        return self.Cite

    def ReturnBeCited(self):
        return self.BeCited

    def ReturnCiteTimes(self):
        return len(self.Cite)

    def ReturnBeCitedTimes(self):
        return len(self.BeCited)

    def copy(self):
        # 修正: 原始代码中的 self.URL 不存在, 应该使用 self.Year
        NewNode = MyNode(self.ID,self.Label,self.Year,self.Cite,self.BeCited) 
        return NewNode

def clean_reference_data(nodes, edges, top_id):
    # 去除发表日期大于当前日期的论文及其引用关系,这种情况有可能出现，但对学术脉络发展来说，不会对后面的脉络产生太大影响
    # 去除两篇文章之间的互引
    # 去除网络中存在的有向环
    # 存在开山作发表前的文章
    # 开山作引用别的文章的边
    import time
    source_nodes_len = len(nodes)
    source_edges_len = len(edges)
    yyy = datetime.datetime.now().year
    mmm = datetime.datetime.now().month
    ddd = datetime.datetime.now().day
    time_stamp_flag = int(time.mktime(time.strptime(f'{yyy}-{mmm}-{ddd}', '%Y-%m-%d'))) # 只需更改这个flag值即可更改论文的最新年份的界限
    top_paper_time_stamp = 0
    out_date_id_set = set()
    id2time_stamp = {}
    G = nx.DiGraph()
    
    # **新增变量**：记录因日期/Top-paper 剪除的边
    initial_cut_edges_list = [] 

    for node in nodes:
        if node['id'] == top_id:
            top_paper_time_stamp = int(time.mktime(time.strptime(node['date'], '%Y-%m-%d')))
    for node in nodes:
        id = node['id']
        date = node['date']
        node_time_stamp = int(time.mktime(time.strptime(date, '%Y-%m-%d')))
        id2time_stamp[id] = node_time_stamp
        # 将出版日期异常的点加入集合中
        if node_time_stamp > time_stamp_flag or node_time_stamp < top_paper_time_stamp:
            out_date_id_set.add(id)

    # 去除日期异常的节点
    nodes_copy = nodes[:]
    for node in nodes:
        if node['id'] in out_date_id_set:
            nodes_copy.remove(node)
    
    # 去除含有异常日期的边
    edges_copy = edges[:]
    # cut_edge_num = 0 # 此变量用于检查，不再使用
    
    edges_to_keep = []
    for edge in edges:
        source, target = edge['source'], edge['target']
        is_cut = False
        
        # 1. 去掉时间不在演进范围内节点相关的边
        if source in out_date_id_set or target in out_date_id_set:
            initial_cut_edges_list.append((source, target))
            is_cut = True
        
        # 2. 去掉top_paper引用别人的边
        if source == top_id:
            if not is_cut: # 避免重复记录
                initial_cut_edges_list.append((source, target))
            is_cut = True
        
        if not is_cut:
            edges_to_keep.append(edge)

    edges_copy = edges_to_keep # 更新 edges_copy
    
    for node in nodes_copy:
        G.add_node(node['id'])
    for edge in edges_copy:
        G.add_edge(edge['source'], edge['target'])
        
    # **新增变量**：记录因环结构剪除的边
    cycle_cut_edges_list = [] 
    
    try:
        Data = nx.find_cycle(G)
        ii = 0
        iii = 0
        while (Data):
            if len(Data) == 2:
                # 两篇paper互引的情况，根据两篇文章的发表顺序修复
                node_id_0 = Data[0][0]
                node_id_1 = Data[0][1]

                node_0_time_stamp = id2time_stamp[node_id_0]
                node_1_time_stamp = id2time_stamp[node_id_1]

                if node_0_time_stamp >= node_1_time_stamp:
                    cut_edge = (node_id_1, node_id_0)
                    G.remove_edge(node_id_1,node_id_0)
                    ii += 1
                else:
                    cut_edge = (node_id_0, node_id_1)
                    G.remove_edge(node_id_0,node_id_1)
                    iii += 1
                cycle_cut_edges_list.append(cut_edge) # **记录**
            else:
                # 有向环去除，根据论文的发表顺序
                cut_flag = 0
                for ed in Data:
                    if id2time_stamp[ed[1]] >= id2time_stamp[ed[0]]:
                        cut_flag = 1
                        cycle_cut_edges_list.append(ed) # **记录**
                        G.remove_edge(ed[0],ed[1])
                if cut_flag == 0:
                    pass
            try:
                Data = nx.find_cycle(G) # 切断一个环，继续寻找
            except:
                break
    except:
        pass
        
    # 将因日期/Top-paper剪除的边 和 因环结构剪除的边 合并
    all_initial_cut_edges = initial_cut_edges_list + cycle_cut_edges_list
    
    # 重新构建最终的 edges 列表，确保只包含 G 中仍然存在的边
    final_edges = []
    for edge in edges_copy:
        if G.has_edge(edge['source'], edge['target']):
             final_edges.append(edge)

    nodes = nodes_copy[:] 
    edges = final_edges[:]
    
    # 原始的错误检查逻辑被简化，因为我们已经清晰地追踪了被移除的边
    # if len(nodes) + len(out_date_id_set) != source_nodes_len or len(edges) + len(need_cut_edge) + cut_edge_num != source_edges_len:
    #     print('error')
    
    # **修改返回值**：返回清洗后的节点、边以及所有因清洗过程移除的边集
    return nodes, edges, all_initial_cut_edges

# 反复检测环，并按“简化指数差值最大优先切边”的策略剪边，直到无环。
def gen_skeleton_tree(id, Distance1Index, INPUT_FILE_PATH):

    nodes, edges = readgml.read_gml(INPUT_FILE_PATH)
    # **接收**清洗阶段移除的边集
    nodes, edges, clean_cut_edges = clean_reference_data(nodes, edges, int(id))

    NodeList = []
    NodeIDList = {}

    G=nx.DiGraph()

    NodeCount = 0
    for node in nodes:
        NodeCount = NodeCount + 1
        label = node.get('label', '')
        ID = node['id']
        year = node['date']
        labelnew = ''
        for i in label: # 去除异常编码
            if ((0 <= ord(i)) and (ord(i) <= 127)): # ord函数，输入一个字符输出一个ascii或者unicode编码
                labelnew = labelnew + i
        NewNode = MyNode(ID,labelnew,year)
        if ID in NodeIDList:
            pass
        else:
            NodeList.append(NewNode)
            NodeIDList[ID] = len(NodeList)-1
            G.add_node(ID,label = label)

    for ID in NodeIDList.keys():
        if (ID != NodeList[NodeIDList[ID]].ReturnID()):
            print ('Error!')

    EdgeCount = 0
    for edge in edges:
        EdgeCount = EdgeCount + 1
        Source = edge['source']
        Target = edge['target']
        G.add_edge(Source,Target)
        if (Source in NodeIDList) and (Target in NodeIDList):
            # 将引用和被引写入节点对象
            NodeList[NodeIDList[Source]].AppendCite(NodeList[NodeIDList[Target]])
            NodeList[NodeIDList[Target]].AppendBeCited(NodeList[NodeIDList[Source]])

    CiteCount,BeCitedCount = 0,0
    for ID in NodeIDList.keys():
        # 总引用量和总被引量
        CiteCount = CiteCount + NodeList[NodeIDList[ID]].ReturnCiteTimes()
        BeCitedCount = BeCitedCount + NodeList[NodeIDList[ID]].ReturnBeCitedTimes()


    if ((CiteCount != EdgeCount) or (BeCitedCount != EdgeCount)):
        print ('Error!')

    try:
        Data = nx.find_cycle(G,orientation='ignore') 
    except:
        Data = []

    # **新增变量**：记录因简化指数差异剪除的边集
    reduction_cut_edges = []
    
    i = 0
    while (Data):
        EdgeIndexList = []
        # 1. 计算环中每条边的简化指数差异
        for EdgeNow in Data:
            EdgeIndexList.append(abs(float(Distance1Index[EdgeNow[0]])-float(Distance1Index[EdgeNow[1]])))
        EdgeIndexListCopy = EdgeIndexList[:]

        while (True):
            if (EdgeIndexListCopy.count(-1) == len(EdgeIndexListCopy)):
                CutEdgeIndex = EdgeIndexList.index(max(EdgeIndexList))
                Node1 = NodeList[NodeIDList[Data[CutEdgeIndex][0]]]
                Node2 = NodeList[NodeIDList[Data[CutEdgeIndex][1]]]
                for edge in Data:
                    print(edge)
                break

            CutEdgeIndex = EdgeIndexListCopy.index(max(EdgeIndexListCopy))
            EdgeIndexListCopy[CutEdgeIndex] = -1
            
            Node1 = NodeList[NodeIDList[Data[CutEdgeIndex][0]]]
            Node2 = NodeList[NodeIDList[Data[CutEdgeIndex][1]]]
            
            # 原始代码中的错误检查和条件判断
            if (Data[CutEdgeIndex][0] != Node1.ReturnID()):
                print ('Error!1')
            if (Data[CutEdgeIndex][1] != Node2.ReturnID()):
                print ('Error!2')
                
            # 检查引用和被引关系
            if ((Node2 in Node1.ReturnBeCited()) and (Node1 in Node2.ReturnCite())):
                if (Node2.ReturnCiteTimes() > 1):
                    break
            elif ((Node1 in Node2.ReturnBeCited()) and (Node2 in Node1.ReturnCite())):
                if (Node1.ReturnCiteTimes() > 1):
                    break
            else:
                print ('Error!3')

        # 记录被剪除的边 (Node1 -> Node2)
        cut_source_id = Node1.ReturnID()
        cut_target_id = Node2.ReturnID()
        reduction_cut_edges.append((cut_source_id, cut_target_id)) 
        
        # 移除节点对象中的引用关系
        Node1.RemoveCite(Node2)
        # 原始代码中错误的移除逻辑 (Node1 引用 Node2, Node1 不会被 Node2 引用)
        # Node1.RemoveBeCited(Node2) 
        # Node2.RemoveCite(Node1)
        Node2.RemoveBeCited(Node1) # 移除 Node2 被 Node1 引用的关系

        # 移除图中的边
        G.remove_edge(cut_source_id, cut_target_id)
        
        # 尝试移除反向边 (如果存在) - 可能是互引导致的复杂情况
        try:
            G.remove_edge(Node2.ReturnID(),Node1.ReturnID()) 
            # 如果存在反向边并被移除，也应该记录
            reduction_cut_edges.append((Node2.ReturnID(),Node1.ReturnID())) 
            i += 1
        except:
            pass
            
        try:
            Data = nx.find_cycle(G,orientation='ignore') # 切断一个环，继续寻找
        except:
            break

    node_detail = {}
    for node in NodeList:
        if node.ReturnID() not in node_detail:
            node_detail[str(node.ReturnID())] = {}
        node_detail[str(node.ReturnID())]['label'] = node.ReturnLabel()
        node_detail[str(node.ReturnID())]['year'] = node.ReturnYear()[0:4]
        node_detail[str(node.ReturnID())]['cite'] = [node.ReturnID() for node in node.ReturnCite()]
        node_detail[str(node.ReturnID())]['becited'] = [node.ReturnID() for node in node.ReturnBeCited()]

    # **修改返回值**：返回节点详情和两个剪除边集
    return node_detail, clean_cut_edges, reduction_cut_edges





def run_comparison(pid, year):
    """
    加载两种 Reduction Index，两次调用 gen_skeleton_tree 函数，
    并存储对比结果。

    Args:
        pid (int): 目标论文 ID (例如 4294558607)。
        year (int): 目标年份 (例如 2025)。
    """
    
    # --- 1. 定义文件路径 ---
    
    # 假设你的代码文件运行在 'scientific_x_ray-github/src/' 目录下
    BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
    
    # Reduction 1: Sparse Index (相对路径)
    REDUCTION_1_PATH = os.path.join(
        BASE_DIR, 
        'single_reduction_results', 
        f'reduction_index_sparse_{pid}_{year}.json'
    )
    
    # Reduction 2: Dense Index (绝对路径，根据你提供的路径进行修正)
    REDUCTION_2_PATH = f'/home/liyutong1117/jupyter/scientific_x_ray-github/src/single_reduction_results_dense_output/reduction_index_{pid}_{year}.json'
    
    # GML 输入文件路径（假设 GML 文件路径和你的 gen_skeleton_tree 内部逻辑一致）
    # 注意：gen_skeleton_tree 内部使用了 readgml.read_gml(INPUT_FILE_PATH)，
    # 它的输入参数是 INPUT_FILE_PATH。
    INPUT_FILE_PATH = os.path.join(
        BASE_DIR, '..', 'temp_files', 'source_gml_by_year', str(pid), f'{year}.gml'
    )
    
    OUTPUT_DIR = os.path.join(BASE_DIR, 'comparison_output')
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    OUTPUT_FILE_PATH = os.path.join(
        OUTPUT_DIR, 
        f'reduction_comparison_results_{pid}_{year}.json'
    )
    
    # --- 2. 加载 Reduction Index 字典 ---
    
    def load_reduction_index(file_path, name):
        """加载 JSON 文件中的 reduction index 字典。"""
        if not os.path.exists(file_path):
            print(f"❌ 错误：{name} 文件未找到: {file_path}")
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 注意：JSON 中的键通常是字符串，需要确保它们能正确匹配 ID (int/str)
                data = json.load(f)
                # 假设 reduction index 的字典是以 ID (str) 为键
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"❌ 错误：加载 {name} 文件失败: {e}")
            return None

    index_sparse = load_reduction_index(REDUCTION_1_PATH, "Sparse Index")
    index_dense = load_reduction_index(REDUCTION_2_PATH, "Dense Index")

    if index_sparse is None or index_dense is None:
        print("终止比较过程。")
        return

    # --- 3. 调用 gen_skeleton_tree 并记录结果 ---
    
    comparison_results = {
        "PID": pid,
        "Year": year,
        "Clean_Cut_Edges": {},
        "Reduction_Cut_Edges": {}
    }
    
    # 第一次调用：使用 Sparse Index
    print(f"\n🚀 正在运行 Reduction 1 (Sparse Index) ...")
    node_detail_1, clean_cut_edges_1, reduction_cut_edges_1 = gen_skeleton_tree(
        pid, index_sparse, INPUT_FILE_PATH
    )
    
    # 第二次调用：使用 Dense Index
    print(f"\n🚀 正在运行 Reduction 2 (Dense Index) ...")
    # 注意：由于 gen_skeleton_tree 会修改其内部状态，这里假设它返回的是一个全新的结构。
    # 理想情况下，我们应该重新加载 GML 或重置状态，但这里我们依赖 gen_skeleton_tree 的内部逻辑。
    # 为了保证对比公平，我们传入同样的 INPUT_FILE_PATH。
    node_detail_2, clean_cut_edges_2, reduction_cut_edges_2 = gen_skeleton_tree(
        pid, index_dense, INPUT_FILE_PATH
    )
    
    # --- 4. 存储结果 ---
    
    # Clean Cut Edges (理论上两次运行应该一致)
    comparison_results["Clean_Cut_Edges"] = {
        "Sparse_Run": list(clean_cut_edges_1),
        "Dense_Run": list(clean_cut_edges_2)
    }
    
    # Reduction Cut Edges (这是我们想要对比的核心)
    comparison_results["Reduction_Cut_Edges"] = {
        "Sparse_Index": list(reduction_cut_edges_1),
        "Dense_Index": list(reduction_cut_edges_2)
    }
    
    # Jaccard Index 对比（可选，但强烈建议）
    set_a = set(reduction_cut_edges_1)
    set_b = set(reduction_cut_edges_2)
    intersection_size = len(set_a.intersection(set_b))
    union_size = len(set_a.union(set_b))
    jaccard_index = intersection_size / union_size if union_size > 0 else 1.0

    comparison_results["Comparison_Metrics"] = {
        "Total_Cuts_Sparse": len(set_a),
        "Total_Cuts_Dense": len(set_b),
        "Intersection_Size": intersection_size,
        "Union_Size": union_size,
        "Jaccard_Overlap_Rate": jaccard_index
    }
    
    with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(comparison_results, f, indent=4)
        
    print(f"\n✅ 比较完成。结果已保存到：{OUTPUT_FILE_PATH}")
    print(f"📊 Reduction Cut Edges Jaccard 重叠率: {jaccard_index:.4f}")

# --- 主程序入口 ---

if __name__ == '__main__':
    # 你的目标参数
    TARGET_PID = 4294558607
    TARGET_YEAR = 2025
    
    # 注意：为了让这个脚本能运行，你需要确保
    # 1. gen_skeleton_tree 函数在此处可用 (例如，确保它被导入或定义在同一文件中)。
    # 2. 两个 reduction index JSON 文件存在于指定路径。
    # 3. GML 输入文件存在于 gen_skeleton_tree 内部预期的路径。
    
    # ⚠️ 确保 gen_skeleton_tree 在此处可用，否则会报错 NameError
    try:
        run_comparison(TARGET_PID, TARGET_YEAR)
    except NameError:
        print("\nFATAL ERROR: gen_skeleton_tree 函数未定义。请确保已将 gen_skeleton_tree 放入此脚本或已正确导入。")