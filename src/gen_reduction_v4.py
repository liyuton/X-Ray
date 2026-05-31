#使用稀疏矩阵+减小k值+稀疏图上的dijistra
# 导入必要的库
import scipy.sparse as sp
import scipy.sparse.linalg as splinalg
import scipy.sparse.csgraph as csgraph # 用于稀疏图算法
import numpy as np
import networkx as nx
import queue
import datetime
import time
import math
import json
import csv
import os
from readgml import readgml
# from tqdm import tqdm_notebook as tqdm # 注释掉，避免依赖问题
from multiprocessing.pool import Pool

# 设置稀疏特征向量的数量限制，在大规模网络下推荐使用小 k
K_EIGEN_VECTORS = 512

# --- MyNode Class (保持不变) ---
class MyNode:
    def __init__(self,ID,year):
        self.ID = ID
        self.Year = year
        self.Cite = []
        self.BeCited = []

    def AppendCite(self,paper):
        self.Cite.append(paper)

    def AppendBeCited(self,paper):
        self.BeCited.append(paper)

    def ReturnID(self):
        return self.ID

    def ReturnYear(self):
        return self.Year

    def ReturnCite(self):
        return set(self.Cite)

    def ReturnBeCited(self):
        return set(self.BeCited)

    def ReturnCiteTimes(self):
        return len(set(self.Cite))

    def ReturnBeCitedTimes(self):
        return len(set(self.BeCited))

# --- 稀疏化函数 1: 拉普拉斯矩阵计算 ---
# 替换原有的 GetLaplacianMatrix
def GetLaplacianMatrix_Sparse(Matrix_Sparse):
    """
    计算归一化稀疏拉普拉斯矩阵 L_sym = I - D^(-0.5) * A * D^(-0.5)
    Matrix_Sparse 必须是稀疏矩阵 (CSR 格式)
    """
    # 1. 计算度矩阵 D 的对角线元素 d
    d = np.array(Matrix_Sparse.sum(axis=1)).flatten()
    
    # 2. 构建 D^(-0.5) 的对角线元素 d_inv_sqrt
    d_inv_sqrt = np.power(d, -0.5)
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0 # 避免除以 0
    
    # 3. 构建对角稀疏矩阵 Dn = D^(-0.5)
    Dn = sp.diags(d_inv_sqrt, format='csr')
    
    # 4. 计算 L_sym = I - Dn * A * Dn
    LaplacianMatrix = sp.eye(Matrix_Sparse.shape[0], format='csr') - Dn.dot(Matrix_Sparse).dot(Dn)
    
    return LaplacianMatrix

# --- 稀疏化函数 2: 特征值求解 ---
# 替换原有的 getKSmallestEigVec
def getKSmallestEigVec_Sparse(LaplacianMatrix, k):
    """
    使用稀疏求解器计算 K 个最小实部特征值和特征向量。
    """
    N = LaplacianMatrix.shape[0]
    
    # 检查 k 是否过大，并限制其值
    k_effective = min(k, N - 1) 
    if k_effective > 512:
        print(f"Warning: k={k_effective} is large. Resetting to 100 for performance.")
        k_effective = 512
    
    if k_effective < 1:
         k_effective = 1

    # 使用针对稀疏矩阵的求解器，which='SR' 表示最小实部
    try:
        EigenValue, EigenVector = splinalg.eigs(LaplacianMatrix, k=k_effective, which='SR')
    except splinalg.ArpackNoConvergence as e:
        print(f"Warning: Arpack failed to converge for k={k_effective}. Returning results anyway.")
        EigenValue, EigenVector = e.eigenvalues, e.eigenvectors
    
    # 返回实部
    return EigenValue.real, EigenVector.real

# --- clean_reference_data 函数 (保持不变) ---
def clean_reference_data(nodes, edges, top_id):
    import time
    source_nodes_len = len(nodes)
    source_edges_len = len(edges)
    yyy = datetime.datetime.now().year
    mmm = datetime.datetime.now().month
    ddd = datetime.datetime.now().day
    time_stamp_flag = int(time.mktime(time.strptime(f'{yyy}-{mmm}-{ddd}', '%Y-%m-%d'))) 
    top_paper_time_stamp = 0
    out_date_id_set = set()
    id2time_stamp = {}
    G = nx.DiGraph()

    for node in nodes:
        if node['id'] == top_id:
            top_paper_time_stamp = int(time.mktime(time.strptime(node['date'], '%Y-%m-%d')))

    for node in nodes:
        id = node['id']
        date = node['date']
        node_time_stamp = int(time.mktime(time.strptime(date, '%Y-%m-%d')))
        id2time_stamp[id] = node_time_stamp
        if node_time_stamp > time_stamp_flag or node_time_stamp < top_paper_time_stamp:
            out_date_id_set.add(id)

    nodes_copy = nodes[:]
    for node in nodes:
        if node['id'] in out_date_id_set:
            nodes_copy.remove(node)
            
    edges_copy = edges[:]
    cut_edge_num = 0
    for edge in edges:
        if edge['source'] in out_date_id_set or edge['target'] in out_date_id_set:
            edges_copy.remove(edge)
            cut_edge_num += 1
        if edge['source'] == top_id:
            try:
                edges_copy.remove(edge)
                cut_edge_num += 1
            except:
                pass
    
    for node in nodes_copy:
        G.add_node(node['id'])
    for edge in edges_copy:
        G.add_edge(edge['source'], edge['target'])
    need_cut_edge = []
    try:
        Data = nx.find_cycle(G)
        ii = 0
        iii = 0
        while (Data):
            if len(Data) == 2:
                node_id_0 = Data[0][0]
                node_id_1 = Data[0][1]

                node_0_time_stamp = id2time_stamp[node_id_0]
                node_1_time_stamp = id2time_stamp[node_id_1]

                if node_0_time_stamp >= node_1_time_stamp:
                    need_cut_edge.append((node_id_1, node_id_0))
                    G.remove_edge(node_id_1,node_id_0)
                    ii += 1
                else:
                    need_cut_edge.append((node_id_0, node_id_1))
                    G.remove_edge(node_id_0,node_id_1)
                    iii += 1
            else:
                cut_flag = 0
                for ed in Data:
                    if id2time_stamp[ed[1]] >= id2time_stamp[ed[0]]:
                        cut_flag = 1
                        need_cut_edge.append(ed)
                        G.remove_edge(ed[0],ed[1])
                if cut_flag == 0:
                    pass
            try:
                Data = nx.find_cycle(G) 
            except:
                break
    except:
        pass
    nodes = []
    nodes = nodes_copy[:] 
    edges = []
    edges = edges_copy[:]
    
    remed_edge = []
    for edge in edges_copy:
        for nd_cut_edge in need_cut_edge:
            if edge['source'] == nd_cut_edge[0] and edge['target'] == nd_cut_edge[1]:
                remed_edge.append(edge)
                edges.remove(edge)

    if len(nodes) + len(out_date_id_set) != source_nodes_len or len(edges) + len(need_cut_edge) + cut_edge_num != source_edges_len:
        print('error')
    
    return nodes, edges
    
# --- gen_reduction 函数 (主要修改部分) ---
def gen_reduction(paper_id, INPUT_FILE_PATH):
    NodeList = []
    NodeIDList = {}
    Node_ID = set()
    G = nx.DiGraph()
    nodes, edges = readgml.read_gml(INPUT_FILE_PATH)
    nodes, edges = clean_reference_data(nodes, edges, int(paper_id))
    
    NodeCount = 0
    yearflag = int(datetime.datetime.now().year)
    for node in nodes:
        ID = node['id']
        year = int(node['date'][0:4])
        if year <= yearflag:
            NodeCount = NodeCount + 1
            NewNode = MyNode(ID,year)
            if ID in NodeIDList:
                pass
            else:
                NodeList.append(NewNode)
                NodeIDList[ID] = len(NodeList)-1
                G.add_node(ID)
                Node_ID.add(ID)
    
    for ID in NodeIDList.keys():
        if (ID != NodeList[NodeIDList[ID]].ReturnID()):
            print ('Error1!')
            
    EdgeCount = 0
    for edge in edges:
        Source = edge['source']
        Target = edge['target']
        if (Source != Target) and (Source in NodeIDList) and (Target in NodeIDList):
            NodeList[NodeIDList[Source]].AppendCite(NodeList[NodeIDList[Target]])
            NodeList[NodeIDList[Target]].AppendBeCited(NodeList[NodeIDList[Source]])
            EdgeCount = EdgeCount + 1

    CiteCount,BeCitedCount = 0,0
    for ID in NodeIDList.keys():
        CiteCount = CiteCount + NodeList[NodeIDList[ID]].ReturnCiteTimes()
        BeCitedCount = BeCitedCount + NodeList[NodeIDList[ID]].ReturnBeCitedTimes()

    if ((len(NodeList) != NodeCount) or (len(NodeIDList) != NodeCount)):
        pass
    if ((CiteCount != EdgeCount) or (BeCitedCount != EdgeCount)):
        print ('Error3!')

    # === 稀疏化修改 1：构建稀疏邻接矩阵 ===
    N = len(NodeIDList)
    row_indices = []
    col_indices = []
    data = []

    for NodeNow in NodeList:
        i = NodeIDList[NodeNow.ReturnID()]
        
        # 对角线元素 (自连接或权重为 1)
        if NodeNow.ReturnID() == int(paper_id):
            row_indices.append(i)
            col_indices.append(i)
            data.append(1)
            
        # 邻接元素 (A[i][j] = 1)
        for NodeLinked in NodeNow.ReturnCite():
            j = NodeIDList[NodeLinked.ReturnID()]
            row_indices.append(i)
            col_indices.append(j)
            data.append(1)
            
    # 创建稀疏矩阵 (CSR 格式)
    AdjacencyMatrix_Sparse = sp.csr_matrix((data, (row_indices, col_indices)), shape=(N, N))
    
    # 检查邻接矩阵的总和
    if (AdjacencyMatrix_Sparse.sum() != EdgeCount+1):
        print('存在与开山作的互引!')

    # === 稀疏化修改 2：使用稀疏拉普拉斯矩阵和稀疏特征值求解器 ===
    # K_EIGEN_VECTORS 设为全局变量 512
    LaplacianMatrix = GetLaplacianMatrix_Sparse(AdjacencyMatrix_Sparse)
    print(INPUT_FILE_PATH, datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"), '>>> LaplacianMatrix calculated!')

    EigenValue, EigenVector = getKSmallestEigVec_Sparse(LaplacianMatrix, k=K_EIGEN_VECTORS)
    print(INPUT_FILE_PATH, datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"), '>>> EigenVector calculated!')

    MaxDistance = 0
    
    # 准备构建稀疏权重矩阵的数据结构
    source_indices = []
    target_indices = []
    weights = []

    for NodeNow in NodeList:
        i = NodeIDList[NodeNow.ReturnID()]
        for NodeLinked in NodeNow.ReturnCite():
            j = NodeIDList[NodeLinked.ReturnID()]
            # 特征向量距离作为权重
            distance = np.linalg.norm(EigenVector[i] - EigenVector[j])
            G.add_edge(NodeNow.ReturnID(),NodeLinked.ReturnID(),weight = distance)
            
            source_indices.append(i)
            target_indices.append(j)
            weights.append(distance)
            
            if (distance > MaxDistance):
                MaxDistance = distance
    
    # === 稀疏化修改 3：构建稀疏权重矩阵用于 Dijkstra ===
    WeightMatrix_Sparse = sp.csr_matrix((weights, (source_indices, target_indices)), shape=(N, N))
    
    # --- 移除 all_pairs_dijkstra_path_length 调用 ---
    # all_pairs_lengths = dict(nx.all_pairs_dijkstra_path_length(G)) # REMOVED

    NodeBeCitedTimesList = []
    NodeBeCitedTimesIDList = []
    for i in NodeList:
        NodeBeCitedTimesList.append(i.ReturnBeCitedTimes())

    if (len(NodeBeCitedTimesList) != len(NodeIDList)):
        print ('Error5!')

    # (MaxIndex 循环逻辑保持不变，用于排序)
    MaxIndex = NodeBeCitedTimesList.index(max(NodeBeCitedTimesList))
    while (NodeBeCitedTimesList[MaxIndex] != -1):
        if (NodeList[MaxIndex].ReturnBeCitedTimes() != NodeBeCitedTimesList[MaxIndex]):
            print ('Error6!')
        else:
            NodeBeCitedTimesIDList.append(NodeIDList[NodeList[MaxIndex].ReturnID()])
            NodeBeCitedTimesList[MaxIndex] = -1
            MaxIndex = NodeBeCitedTimesList.index(max(NodeBeCitedTimesList))

    if (sum(NodeBeCitedTimesList) != -1*len(NodeBeCitedTimesList)):
        print ('Error7!')

    NodeBeCitedTimesIDList.reverse()
    for i in NodeBeCitedTimesIDList:
        NodeBeCitedTimesList.append(NodeList[i])

    # --- 补回原版语义：先统计平均层级步长，用于不可达惩罚项 ---
    sumstep = 0
    sumpath = 0

    for i in NodeBeCitedTimesIDList:
        NodeNow = NodeList[i]
        for NodeLinked in NodeNow.ReturnCite():
            if (not(NodeNow in NodeLinked.ReturnBeCited())):
                print ('Error8!')
            else:
                MyQueueNow = queue.Queue()
                MyQueueNext = queue.Queue()
                ReferenceDictionary = {}
                for k in NodeLinked.ReturnCite():
                    MyQueueNext.put(k)
                Step = 0
                while (not(MyQueueNext.empty())):
                    Step = Step + 1
                    MyQueueNow = MyQueueNext
                    MyQueueNext = queue.Queue()
                    while (not(MyQueueNow.empty())):
                        NodeOperateNow = MyQueueNow.get()
                        if NodeOperateNow.ReturnID() in ReferenceDictionary:
                            pass
                        else:
                            ReferenceDictionary[NodeOperateNow.ReturnID()] = Step
                            sumstep = sumstep + Step
                            sumpath = sumpath + 1
                            for k in NodeOperateNow.ReturnCite():
                                if k.ReturnID() in ReferenceDictionary:
                                    pass
                                else:
                                    MyQueueNext.put(k)

    # --- Distance Index 初始化 (保持不变) ---
    
    Distance1Index_init = {}
    Distance2Index_init = {}
    Distance3Index_init = {}
    
    avg_step_path_ratio = MaxDistance * 1.0 * sumstep / sumpath if sumpath != 0 else MaxDistance
    
    for j in NodeList:
        Distance1Index_init[j.ReturnID()] = 0
        Distance2Index_init[j.ReturnID()] = 0
        # 如果不可达，使用惩罚值
        Distance3Index_init[j.ReturnID()] = avg_step_path_ratio 
        
    Distance1Index = Distance1Index_init.copy()
    # 缓存同一 source 的 SSSP 结果，避免重复调用 dijkstra
    sssp_cache = {}
    
    # --- 循环内部：按需 SSSP 计算 ---
    for i in NodeBeCitedTimesIDList:
        NodeNow = NodeList[i]
        Distance2Index = Distance2Index_init.copy()
        for NodeLinked in NodeNow.ReturnCite():
            
            # --- 关键修改：单源最短路径计算 (SSSP) ---
            source_id = NodeLinked.ReturnID()
            source_index = NodeIDList[source_id] 

            # 使用缓存复用同一 source_index 的最短路结果
            if source_index in sssp_cache:
                SSSP_distances = sssp_cache[source_index]
            else:
                # 使用 scipy.sparse.csgraph.dijkstra 计算从 source_index 到所有点的最短路径
                SSSP_distances = csgraph.dijkstra(
                    csgraph=WeightMatrix_Sparse,
                    indices=[source_index],
                    directed=True,
                    unweighted=False
                ).flatten()
                sssp_cache[source_index] = SSSP_distances
            # 结果 SSSP_distances[k] 即为从源点到索引 k 的最短距离

            # ... (队列和距离初始化)
            MyQueueNow = queue.Queue()
            MyQueueNext = queue.Queue()
            Distance3Index = Distance3Index_init.copy()
            Distance3Index_flag = {}
            for k in NodeLinked.ReturnCite():
                MyQueueNext.put(k)
                
            # --- 循环：使用 SSSP 结果替换 BFS/Dijkstra 步骤 ---
            while (not(MyQueueNext.empty())):
                MyQueueNow = MyQueueNext
                MyQueueNext = queue.Queue()
                while (not(MyQueueNow.empty())):
                    NodeOperateNow = MyQueueNow.get()
                    if NodeOperateNow.ReturnID() in Distance3Index_flag:
                        pass
                    else:
                        target_id = NodeOperateNow.ReturnID()
                        target_index = NodeIDList[target_id] 
                        
                        length = SSSP_distances[target_index]
                        
                        # csgraph.dijkstra 使用 np.inf 表示不可达
                        if np.isinf(length):
                            # 路径不可达，使用 Distance3Index_init 中的惩罚值，并跳过后续节点
                            pass 
                        else:
                            # 路径可达
                            Distance3Index[target_id] = length
                            Distance2Index[target_id] += Distance3Index[target_id]
                            Distance3Index_flag[target_id] = 1
                            
                            # 继续广度优先搜索
                            for k in NodeOperateNow.ReturnCite():
                                if k.ReturnID() not in Distance3Index_flag:
                                    MyQueueNext.put(k)

            # ... (Work set 逻辑保持不变)
            Distance3Index_flag_key = set(Distance3Index_flag.keys())
            work_set = Node_ID.difference(Distance3Index_flag_key)
            for j_id in work_set:
                Distance2Index[j_id] = Distance2Index[j_id] + Distance3Index[j_id]

        for j in NodeList:
            Distance1Index[j.ReturnID()] = Distance1Index[j.ReturnID()] + Distance2Index[j.ReturnID()]
    
    # ... (SolutionList 排序逻辑保持不变)
    SolutionList = []
    SolutionIDList = []
    SolutionIndexList = []
    for s in NodeBeCitedTimesIDList:
        SolutionIDList.append(NodeList[s].ReturnID())
        SolutionIndexList.append(Distance1Index[NodeList[s].ReturnID()])
        
    MaxIndex = max(SolutionIndexList)
    while (MaxIndex != -1):
        SolutionList.append(SolutionIDList[SolutionIndexList.index(MaxIndex)])
        SolutionIndexList[SolutionIndexList.index(MaxIndex)] = -1
        MaxIndex = max(SolutionIndexList)
    
    if (sum(SolutionIndexList) != -1*len(SolutionIndexList)):
        print ('Error--!')
    
    print(INPUT_FILE_PATH, '>>> Reduction calculated!')
    
    return Distance1Index

def save_distance_to_json(data, file_path):
    """
    将计算结果 (字典) 保存为 JSON 文件。
    """
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            # 键必须是字符串，因此显式转换为字符串
            data_to_save = {str(k): v for k, v in data.items()}
            json.dump(data_to_save, f, indent=4)
        print(f"✅ Distance1Index 成功保存到 {file_path}")
    except Exception as e:
        print(f"❌ 保存 JSON 文件时出错: {e}")


def process_single_paper(pid, year, output_dir='./temp_files/reduction_results'):
    """
    主函数：处理单个论文 ID 和年份，计算 Distance1Index 并保存。

    Args:
        pid (int/str): 待处理论文的 ID。
        year (int/str): 对应的年份。
        output_dir (str): 结果 JSON 文件存储的根目录。
    """
    
    try:
        pid = int(pid)
        year = int(year)
    except ValueError:
        print("❌ 错误: pid 和 year 必须是有效的数字。")
        return

    # 1. 构造 GML 文件路径
    INPUT_FILE_PATH = os.path.join(
        '..', 'temp_files', 'source_gml_by_year', str(pid), f'{year}.gml'
    )
    
    if not os.path.exists(INPUT_FILE_PATH):
        print(f"⚠️ 文件未找到: {INPUT_FILE_PATH}。无法进行计算。")
        return

    start_time = time.time()
    print(f"--- 开始处理 Paper ID: {pid} (Year: {year}) ---")
    
    try:
        # 2. 调用核心计算函数
        # gen_reduction 返回的是 Distance1Index 字典
        distance1_index = gen_reduction(pid, INPUT_FILE_PATH)
        
        # 3. 保存结果到 JSON 文件
        output_filename = f'reduction_index_{pid}_{year}.json'
        output_file_path = os.path.join(output_dir, output_filename)
        
        save_distance_to_json(distance1_index, output_file_path)
        
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"🎉 Paper ID: {pid} 所有计算完成，总耗时: {elapsed:.2f} 秒。")
        
    except Exception as e:
        print(f"❌ Paper ID: {pid} 计算失败。错误: {e}")
        # 打印详细错误信息，方便调试
        # import traceback; traceback.print_exc() 


if __name__ == '__main__':
    # --- 脚本调用示例区 ---
    # 假设你希望处理 Paper ID 1001, Year 2005
    
    TARGET_PID = 4294558607
    TARGET_YEAR = 2025
    
    # 定义结果输出目录
    RESULTS_OUTPUT_DIR = './single_reduction_results' 
    
    # 调用单论文处理函数
    process_single_paper(TARGET_PID, TARGET_YEAR, RESULTS_OUTPUT_DIR)