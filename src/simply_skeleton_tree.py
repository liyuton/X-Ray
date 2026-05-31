import json
import os
import queue

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

    def ReturnLabel(self):
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
        NewNode = MyNode(self.ID,self.Label,self.URL,self.Cite,self.BeCited)
        return NewNode

TREE_JSON_FILE_PATH = '../temp_files/skeleton_tree_by_year/'
TREE_DEEP_PATH = '../temp_files/tree_deep_by_year/'
SIMPLIED_TREE_JSON_FILE_PATH = '../temp_files/simplied_skeleton_tree_by_year/'
# THRESHOLD = 10

def subtree_node_num(Node):
    # 获取根节点A的子树内的节点数量
    NodeList = []
    MyQueue = queue.Queue()
    MyQueue.put(Node)
    while (not(MyQueue.empty())):
        NodeNow = MyQueue.get()
        NodeList.append(NodeNow)
        for NodeLinked in NodeNow.ReturnBeCited():
            MyQueue.put(NodeLinked)
    return len(NodeList)

def get_subtree_pids(Node):
    NodeIDList = [Node.ReturnID()]
    MyQueue = queue.Queue()
    MyQueue.put(Node)
    while (not(MyQueue.empty())):
        NodeNow = MyQueue.get()
        NodeIDList.append(NodeNow.ReturnID())
        for NodeLinked in NodeNow.ReturnBeCited():
            MyQueue.put(NodeLinked)
    return NodeIDList

def get_nodes_in_path2seminal_paper(node):
    # 包含node节点的id，但不包含seminal_paper的id
    selected_pids = []
    selected_pids.append(node.ReturnID())
    while (not node.ReturnCiteTimes() == 0):
        selected_pids.append(str(node.ReturnCite()[0].ReturnID()))
        node = node.ReturnCite()[0]
    return selected_pids




def simply_skeleton_tree_2(pid, yr, THRESHOLD, rescale_len=25):
    # 第二种简化脉络树的方法
    # 根据最近年份最宽的层来rescale以往年份所有的层，且保留原始idea tree的shape
    # 先保留当前的所有高知识熵节点，以及通往seminal paper的路径上的所有节点，保持连通性
    pid2node_entropy = json.load(open('../temp_files/node_entropy_by_year/'+str(pid)+'/{}'.format(yr), 'r'))
    all_high_ke_nodes = [] # 不包含seminal_paper
    for p_id in pid2node_entropy:
        if str(pid) == str(p_id):
            continue
        if pid2node_entropy[p_id] >= THRESHOLD:
            all_high_ke_nodes.append(str(p_id))

    node_detail = json.load(open(TREE_JSON_FILE_PATH+str(pid)+'/'+str(yr), 'r'))
    id2node = {}
    NodeList = []
    for node in node_detail:
        ID = node
        node = str(node)
        label = node_detail[node]['label']
        year = node_detail[node]['year']
        NewNode = MyNode(ID,label,year)
        id2node[node] = NewNode
    for node in id2node:
        for nd in node_detail[node]['cite']:
            id2node[node].AppendCite(id2node[str(nd)])
        for nd in node_detail[node]['becited']:
            id2node[node].AppendBeCited(id2node[str(nd)])
        NodeList.append(id2node[node])

    all_path_pids = []
    for p_id in all_high_ke_nodes:
        all_path_pids += get_nodes_in_path2seminal_paper(id2node[p_id])

    all_path_pids = list(set(all_path_pids))
    all_path_pids_set = set(all_path_pids)

    max_year = 2025
    last_tree_deep = json.load(open(TREE_DEEP_PATH+str(pid)+'/'+str(max_year), 'r'))
    max_tree_width = 0
    for dp in last_tree_deep:
        if len(last_tree_deep[dp]) >= max_tree_width:
            max_tree_width = len(last_tree_deep[dp])
    rescale_factor = rescale_len/max_tree_width  # 至此，将所有idea树都归一化到最大宽度为rescale_len

    tree_deep = json.load(open(TREE_DEEP_PATH+str(pid)+'/'+str(yr), 'r'))

    # 筛选最终保留的pids
    selected_pids = [str(pid)]
    for depth in range(0,len(tree_deep)):
        if depth == 0:
            next_layer_pids = []
            next_layer_selected_pids = []
            for node in id2node[str(tree_deep[str(depth)][0])].ReturnBeCited():
                if str(node.ReturnID()) in all_path_pids_set:
                    selected_pids.append(str(node.ReturnID()))
                    next_layer_selected_pids.append(str(node.ReturnID()))
                    continue
                next_layer_pids.append(str(node.ReturnID()))
            p_id2subtree_node_num = {}
            for p_id in next_layer_pids:
                p_id2subtree_node_num[str(p_id)] = subtree_node_num(id2node[str(p_id)])
            sorted_tuple = sorted(p_id2subtree_node_num.items(), key=lambda item:item[1], reverse=True)
            
            for i in range(int(len(sorted_tuple)*rescale_factor)):
                next_layer_selected_pids.append(sorted_tuple[i][0])
                selected_pids.append(sorted_tuple[i][0])
        else:
            current_layer_pids = next_layer_selected_pids
            next_layer_pids = []
            next_layer_selected_pids = []
            for p_id in current_layer_pids:
                for node in id2node[p_id].ReturnBeCited():
                    if str(node.ReturnID()) in all_path_pids_set:
                        selected_pids.append(str(node.ReturnID()))
                        next_layer_selected_pids.append(str(node.ReturnID()))
                        continue
                    next_layer_pids.append(str(node.ReturnID())) 
            p_id2subtree_node_num = {}
            for p_id in next_layer_pids:
                p_id2subtree_node_num[str(p_id)] = subtree_node_num(id2node[str(p_id)])
            sorted_tuple = sorted(p_id2subtree_node_num.items(), key=lambda item:item[1], reverse=True)
            
            for i in range(int(len(sorted_tuple)*rescale_factor)):
                next_layer_selected_pids.append(sorted_tuple[i][0])
                selected_pids.append(sorted_tuple[i][0])

    print(len(selected_pids), len(pid2node_entropy))
    new_node_list = []
    new_id2node = {}
    
    for node in node_detail:
        if str(node) in selected_pids:
            ID = node
            node = str(node)
            label = node_detail[node]['label']
            year = node_detail[node]['year']
            NewNode = MyNode(ID,label,year)
            new_id2node[node] = NewNode
            
    for node in new_id2node:
        for nd in node_detail[node]['cite']:
            if str(node) in selected_pids and str(nd) in selected_pids:
                new_id2node[node].AppendCite(new_id2node[str(nd)])
        for nd in node_detail[node]['becited']:
            if str(node) in selected_pids and str(nd) in selected_pids:
                new_id2node[node].AppendBeCited(new_id2node[str(nd)])
        if len(new_id2node[node].ReturnCite()) == 0 and new_id2node[node].ReturnID() != str(pid):
            continue
        new_node_list.append(new_id2node[node])
    
    node_detail = {}
    for node in new_node_list:
        if node.ReturnID() not in node_detail:
            node_detail[str(node.ReturnID())] = {}
        node_detail[str(node.ReturnID())]['label'] = node.ReturnLabel()
        node_detail[str(node.ReturnID())]['year'] = node.ReturnYear()[0:4]
        node_detail[str(node.ReturnID())]['cite'] = [node.ReturnID() for node in node.ReturnCite()]
        node_detail[str(node.ReturnID())]['becited'] = [node.ReturnID() for node in node.ReturnBeCited()]
    print(len(node_detail))
    if not os.path.exists(SIMPLIED_TREE_JSON_FILE_PATH+str(pid)):
        os.makedirs(SIMPLIED_TREE_JSON_FILE_PATH+str(pid))
    json.dump(node_detail, open(SIMPLIED_TREE_JSON_FILE_PATH+str(pid)+'/'+str(yr), 'w'))


def simply_skeleton_tree_3(pid, yr, THRESHOLD, rescale_len=25, intersect_pids=[]):
    """
    基于 simply_skeleton_tree_2 改进：
    增加 intersect_pids 参数（两棵树的交汇节点ID列表）。
    在简化过程中，强制保留这些交汇节点以及它们通往根节点（Seminal Paper）的完整路径，
    防止因层级剪枝导致演化路径断裂。
    """
    
    # 1. 加载知识熵数据，筛选高熵节点
    pid2node_entropy = json.load(open('../temp_files/node_entropy_by_year/'+str(pid)+'/{}'.format(yr), 'r'))
    all_high_ke_nodes = [] # 不包含seminal_paper
    for p_id in pid2node_entropy:
        if str(pid) == str(p_id):
            continue
        if pid2node_entropy[p_id] >= THRESHOLD:
            all_high_ke_nodes.append(str(p_id))

    # 2. 加载当前年份的树结构并构建 MyNode 对象图
    node_detail = json.load(open(TREE_JSON_FILE_PATH+str(pid)+'/'+str(yr), 'r'))
    id2node = {}
    NodeList = []
    for node in node_detail:
        ID = node
        node = str(node)
        label = node_detail[node]['label']
        year = node_detail[node]['year']
        NewNode = MyNode(ID,label,year)
        id2node[node] = NewNode
    
    # 构建引用关系链接
    for node in id2node:
        for nd in node_detail[node]['cite']:
            # 确保引用的节点也在当前树中才添加，防止KeyError
            if str(nd) in id2node: 
                id2node[node].AppendCite(id2node[str(nd)])
        for nd in node_detail[node]['becited']:
            if str(nd) in id2node:
                id2node[node].AppendBeCited(id2node[str(nd)])
        NodeList.append(id2node[node])

    # 3. 收集“强制保留名单” (all_path_pids)
    all_path_pids = []

    # 3.1 处理高知识熵节点：保留节点及其到根的路径
    for p_id in all_high_ke_nodes:
        # 确保节点在当前年份存在
        if str(p_id) in id2node:
            all_path_pids += get_nodes_in_path2seminal_paper(id2node[p_id])

    # ==================== 新增逻辑开始 ====================
    # 3.2 处理交汇节点 (Intersection Nodes)
    # 如果 intersect_pids 为空，则跳过此步，逻辑与 simply_skeleton_tree_2 完全一致
    if intersect_pids:
        for p_id in intersect_pids:
            p_id_str = str(p_id)
            # 关键检查：交汇节点必须存在于当前年份的树中
            # (因为交汇点列表可能基于2025年生成，但当前处理的是较早年份，该节点可能尚未发表)
            if p_id_str in id2node:
                # 不仅保留交汇点，还保留其通往根节点的路径，确保连通性
                path_nodes = get_nodes_in_path2seminal_paper(id2node[p_id_str])
                all_path_pids += path_nodes
    # ==================== 新增逻辑结束 ====================

    # 去重，转为集合以便快速查找
    all_path_pids = list(set(all_path_pids))
    all_path_pids_set = set(all_path_pids)

    # 4. 计算 Rescale 因子 (基于 2025 年最大宽度)
    max_year = 2025
    last_tree_deep = json.load(open(TREE_DEEP_PATH+str(pid)+'/'+str(max_year), 'r'))
    max_tree_width = 0
    for dp in last_tree_deep:
        if len(last_tree_deep[dp]) >= max_tree_width:
            max_tree_width = len(last_tree_deep[dp])
    
    # 防止除零错误，虽然理论上最大宽度不应为0
    if max_tree_width == 0: 
        max_tree_width = 1
        
    rescale_factor = rescale_len/max_tree_width 

    # 5. 开始按层级筛选节点
    tree_deep = json.load(open(TREE_DEEP_PATH+str(pid)+'/'+str(yr), 'r'))

    selected_pids = [str(pid)] # 始终保留根节点
    
    # 遍历每一层
    for depth in range(0, len(tree_deep)):
        # 确定下一层待筛选的候选节点池
        if depth == 0:
            # 第0层是根节点，其 becited 就是第1层候选
            current_root = id2node[str(tree_deep[str(depth)][0])]
            candidates = current_root.ReturnBeCited()
        else:
            # 非第0层，候选节点来自于上一层被选中节点的 becited
            # 注意：这里的逻辑沿用了原代码风格。
            # 原代码逻辑：current_layer_pids 是上一层被选中的节点 ID
            # 下一层候选是这些节点的 becited 集合
            # 这里为了保持一致性，复用 next_layer_selected_pids 作为下一轮的 current
            current_layer_pids = next_layer_selected_pids
            candidates = []
            seen_candidates = set()
            for p_id in current_layer_pids:
                if p_id in id2node:
                    for node in id2node[p_id].ReturnBeCited():
                        if node.ReturnID() not in seen_candidates:
                            candidates.append(node)
                            seen_candidates.add(node.ReturnID())

        next_layer_pids = []          # 需要参与排序竞争的节点
        next_layer_selected_pids = [] # 本层最终被选中的节点

        for node in candidates:
            node_id = str(node.ReturnID())
            
            # 【关键判别】
            # 如果节点在“强制保留名单”中（包含高熵路径节点 OR 交汇路径节点）
            # 直接保留，不参与子树大小竞争
            if node_id in all_path_pids_set:
                selected_pids.append(node_id)
                next_layer_selected_pids.append(node_id)
                continue
            
            # 否则，加入竞争队列
            next_layer_pids.append(node_id)

        # 对非强制保留的节点，按子树大小排序并截断
        p_id2subtree_node_num = {}
        for p_id in next_layer_pids:
            p_id2subtree_node_num[str(p_id)] = subtree_node_num(id2node[str(p_id)])
        
        sorted_tuple = sorted(p_id2subtree_node_num.items(), key=lambda item:item[1], reverse=True)
        
        # 计算保留数量
        keep_num = int(len(sorted_tuple) * rescale_factor)
        for i in range(keep_num):
            p_id_to_keep = sorted_tuple[i][0]
            next_layer_selected_pids.append(p_id_to_keep)
            selected_pids.append(p_id_to_keep)

    # 6. 重构并保存简化后的 JSON
    print(f"Original Nodes: {len(pid2node_entropy)}, Selected Nodes: {len(selected_pids)}")
    
    new_node_list = []
    new_id2node = {}
    
    # 仅创建被选中的节点
    for node in node_detail:
        if str(node) in selected_pids:
            ID = node
            node = str(node)
            label = node_detail[node]['label']
            year = node_detail[node]['year']
            NewNode = MyNode(ID,label,year)
            new_id2node[node] = NewNode
            
    # 重建引用关系（仅限于被选中的节点内部）
    for node in new_id2node:
        # 原数据中的引用关系
        raw_cite = node_detail[node]['cite']
        raw_becited = node_detail[node]['becited']
        
        for nd in raw_cite:
            # 如果引用对象也在选中列表中，才添加连接
            if str(node) in selected_pids and str(nd) in selected_pids:
                new_id2node[node].AppendCite(new_id2node[str(nd)])
        
        for nd in raw_becited:
            if str(node) in selected_pids and str(nd) in selected_pids:
                new_id2node[node].AppendBeCited(new_id2node[str(nd)])
        
        # 清理孤立节点：如果没有引用别人（且不是根节点），原逻辑似乎会跳过
        # 但如果是交汇点，即使看起来孤立（因为父节点被剪了？但在本逻辑中路径被保留，不应孤立），也应保留。
        # 原逻辑保留：
        if len(new_id2node[node].ReturnCite()) == 0 and new_id2node[node].ReturnID() != str(pid):
            # 这里有一个风险：如果路径中间断了，这里会过滤掉。
            # 但由于我们在前面强制保留了 path2seminal_paper，理论上 ReturnCite 不会为空。
            continue
            
        new_node_list.append(new_id2node[node])
    
    # 格式化输出数据
    output_detail = {}
    for node in new_node_list:
        node_id_str = str(node.ReturnID())
        if node_id_str not in output_detail:
            output_detail[node_id_str] = {}
        output_detail[node_id_str]['label'] = node.ReturnLabel()
        output_detail[node_id_str]['year'] = node.ReturnYear()[0:4]
        output_detail[node_id_str]['cite'] = [node.ReturnID() for node in node.ReturnCite()]
        output_detail[node_id_str]['becited'] = [node.ReturnID() for node in node.ReturnBeCited()]

    print(f"Final Output Nodes: {len(output_detail)}")
    
    # 写入文件
    output_dir = SIMPLIED_TREE_JSON_FILE_PATH + str(pid)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    json.dump(output_detail, open(output_dir + '/' + str(yr), 'w'))

## 保留高知识熵节点topk个子树结构（子树仅保留一层）
def simply_skeleton_tree_2_B(pid, yr, THRESHOLD, rescale_len=25, TOPK_DESC=6):
    """
    tree_2 + 方案B：
    在原有高知识熵路径保护基础上，
    额外保留每个高熵节点下 top-k 最大子树分支
    """

    # ===== 1. 高知识熵节点 =====
    pid2node_entropy = json.load(open('../temp_files/node_entropy_by_year/'+str(pid)+'/{}'.format(yr), 'r'))
    all_high_ke_nodes = []
    for p_id in pid2node_entropy:
        if str(pid) != str(p_id) and pid2node_entropy[p_id] >= THRESHOLD:
            all_high_ke_nodes.append(str(p_id))

    # ===== 2. 构建节点图 =====
    node_detail = json.load(open(TREE_JSON_FILE_PATH+str(pid)+'/'+str(yr), 'r'))
    id2node = {}
    for node in node_detail:
        NewNode = MyNode(node,
                         node_detail[str(node)]['label'],
                         node_detail[str(node)]['year'])
        id2node[str(node)] = NewNode

    for node in id2node:
        for nd in node_detail[node]['cite']:
            if str(nd) in id2node:
                id2node[node].AppendCite(id2node[str(nd)])
        for nd in node_detail[node]['becited']:
            if str(nd) in id2node:
                id2node[node].AppendBeCited(id2node[str(nd)])

    # ===== 3. 强制保留集合 =====
    all_path_pids = []
    high_ke_descendant_pids = set()

    # 3.1 高熵节点 → seminal 路径
    for p_id in all_high_ke_nodes:
        if p_id in id2node:
            all_path_pids += get_nodes_in_path2seminal_paper(id2node[p_id])

    # 3.2 【方案B】高熵节点下 top-k 子树
    for p_id in all_high_ke_nodes:
        if p_id not in id2node:
            continue
        children = id2node[p_id].ReturnBeCited()
        if not children:
            continue

        child_sizes = []
        for ch in children:
            child_sizes.append((str(ch.ReturnID()), subtree_node_num(ch)))

        child_sizes.sort(key=lambda x: x[1], reverse=True)
        for cid, _ in child_sizes[:TOPK_DESC]:
            high_ke_descendant_pids.add(cid)

    all_path_pids_set = set(all_path_pids) | high_ke_descendant_pids

    # ===== 4. rescale 因子 =====
    # 自动获取最大年份
    entropy_dir = f"/home/liyutong1117/jupyter/scientific_x_ray-github/temp_files/node_entropy_by_year/{pid}"
    year_files = [f for f in os.listdir(entropy_dir) if f.isdigit()]
    max_year = max([int(y) for y in year_files]) if year_files else 2025
    # print(f"当前论文最大年份: {max_year}")
    last_tree_deep = json.load(open(TREE_DEEP_PATH+str(pid)+f'/{max_year}', 'r'))
    max_tree_width = max(len(last_tree_deep[d]) for d in last_tree_deep)
    rescale_factor = rescale_len / max(1, max_tree_width)

    tree_deep = json.load(open(TREE_DEEP_PATH+str(pid)+'/'+str(yr), 'r'))

    # ===== 5. 分层筛选 =====
    selected_pids = [str(pid)]
    next_layer_selected_pids = []

    for depth in range(len(tree_deep)):
        candidates = []

        if depth == 0:
            root = id2node[str(tree_deep[str(depth)][0])]
            candidates = root.ReturnBeCited()
        else:
            for pid_ in next_layer_selected_pids:
                for node in id2node[pid_].ReturnBeCited():
                    candidates.append(node)

        next_layer_selected_pids = []
        competition = []

        for node in candidates:
            nid = str(node.ReturnID())
            if nid in all_path_pids_set:
                selected_pids.append(nid)
                next_layer_selected_pids.append(nid)
            else:
                competition.append(nid)

        scored = [(nid, subtree_node_num(id2node[nid])) for nid in competition]
        scored.sort(key=lambda x: x[1], reverse=True)

        keep_num = int(len(scored) * rescale_factor)
        for nid, _ in scored[:keep_num]:
            selected_pids.append(nid)
            next_layer_selected_pids.append(nid)

    # ===== 6. 输出 =====
    new_nodes = {}
    for nid in selected_pids:
        node = id2node[nid]
        new_nodes[nid] = {
            'label': node.ReturnLabel(),
            'year': node.ReturnYear()[0:4],
            'cite': [],
            'becited': []
        }

    for nid in new_nodes:
        for c in id2node[nid].ReturnCite():
            if str(c.ReturnID()) in new_nodes:
                new_nodes[nid]['cite'].append(c.ReturnID())
        for b in id2node[nid].ReturnBeCited():
            if str(b.ReturnID()) in new_nodes:
                new_nodes[nid]['becited'].append(b.ReturnID())

    out_dir = SIMPLIED_TREE_JSON_FILE_PATH + str(pid)
    os.makedirs(out_dir, exist_ok=True)
    json.dump(new_nodes, open(out_dir+'/'+str(yr), 'w'))


def simply_skeleton_tree(pid, yr, simply_ratio=0.05):
    # 根据上述三个原则对脉络树进行精简
    node_detail = json.load(open(TREE_JSON_FILE_PATH+str(pid)+'/'+str(yr), 'r'))
    id2node = {}
    NodeList = []
    for node in node_detail:
        ID = node
        node = str(node)
        label = node_detail[node]['label']
        year = node_detail[node]['year']
        NewNode = MyNode(ID,label,year)
        id2node[node] = NewNode
    for node in id2node:
        for nd in node_detail[node]['cite']:
            id2node[node].AppendCite(id2node[str(nd)])
        for nd in node_detail[node]['becited']:
            id2node[node].AppendBeCited(id2node[str(nd)])
        NodeList.append(id2node[node])
    tree_deep = json.load(open(TREE_DEEP_PATH+str(pid)+'/'+str(yr), 'r'))

    selected_pids = set(list(id2node.keys()))
    for depth in range(1,len(tree_deep)):
        p_id2subtree_node_num = {}
        for p_id in tree_deep[str(depth)]:
            p_id = str(p_id)
            if p_id in selected_pids:
                p_id2subtree_node_num[p_id] = subtree_node_num(id2node[p_id])
        sorted_tuple = sorted(p_id2subtree_node_num.items(), key=lambda item:item[1], reverse=True)
        for i in range(int(simply_ratio*len(sorted_tuple)), len(sorted_tuple)): #留下前三个子树  佛光普照型取140个子树
            s_pids = get_subtree_pids(id2node[sorted_tuple[i][0]])
            for p_id in s_pids:
                if p_id in selected_pids:
                    selected_pids.remove(p_id)
    
    new_node_list = []
    new_id2node = {}
    
    for node in node_detail:
        if str(node) in selected_pids:
            ID = node
            node = str(node)
            label = node_detail[node]['label']
            year = node_detail[node]['year']
            NewNode = MyNode(ID,label,year)
            new_id2node[node] = NewNode
            
    for node in new_id2node:
        for nd in node_detail[node]['cite']:
            if str(node) in selected_pids and str(nd) in selected_pids:
                new_id2node[node].AppendCite(new_id2node[str(nd)])
        for nd in node_detail[node]['becited']:
            if str(node) in selected_pids and str(nd) in selected_pids:
                new_id2node[node].AppendBeCited(new_id2node[str(nd)])
        if len(new_id2node[node].ReturnCite()) == 0 and new_id2node[node].ReturnID() != str(pid):
            continue
        new_node_list.append(new_id2node[node])
    
    node_detail = {}
    for node in new_node_list:
        if node.ReturnID() not in node_detail:
            node_detail[str(node.ReturnID())] = {}
        node_detail[str(node.ReturnID())]['label'] = node.ReturnLabel()
        node_detail[str(node.ReturnID())]['year'] = node.ReturnYear()[0:4]
        node_detail[str(node.ReturnID())]['cite'] = [node.ReturnID() for node in node.ReturnCite()]
        node_detail[str(node.ReturnID())]['becited'] = [node.ReturnID() for node in node.ReturnBeCited()]
    
    print(len(node_detail))
    if not os.path.exists(SIMPLIED_TREE_JSON_FILE_PATH+str(pid)):
        os.makedirs(SIMPLIED_TREE_JSON_FILE_PATH+str(pid))
    json.dump(node_detail, open(SIMPLIED_TREE_JSON_FILE_PATH+str(pid)+'/'+str(yr), 'w'))

def simply_skeleton_tree_combined(pid, yr, THRESHOLD,
                                  rescale_len=25,
                                  TOPK_DESC=6,
                                  intersect_pids=None):
    """
    合并版：
    - 保留高知识熵节点到 seminal 的路径
    - 对每个高知识熵节点保留其下 top-k 最大子分支（仅保留一层子节点）
    - 如果给定 intersect_pids，则将这些交汇节点及其通向 seminal 的路径也强制保留
    - 按层做子树大小竞争式裁剪（使用 rescale_len / max_tree_width 计算保留比例）

    参数:
      pid: 根论文 id
      yr: 处理的年份（对应树 JSON 文件名）
      THRESHOLD: 知识熵阈值
      rescale_len: 用于计算保留比例的目标宽度
      TOPK_DESC: 每个高熵节点下保留的 top-k 子分支数（只保留子节点本身，不递归整棵子树）
      intersect_pids: 可选，交汇节点 id 列表（或 None）
    """

    # 1. load high-ke data
    pid2node_entropy = json.load(open(f'../temp_files/node_entropy_by_year/{pid}/{yr}', 'r'))
    all_high_ke_nodes = []
    for p_id, ent in pid2node_entropy.items():
        if str(p_id) == str(pid):
            continue
        if ent >= THRESHOLD:
            all_high_ke_nodes.append(str(p_id))

    # 2. load tree JSON for this year and build MyNode graph
    node_detail = json.load(open(f'{TREE_JSON_FILE_PATH}{pid}/{yr}', 'r'))
    id2node = {}
    for node_id in node_detail:
        nid = str(node_id)
        NewNode = MyNode(nid,
                         node_detail[nid]['label'],
                         node_detail[nid]['year'])
        id2node[nid] = NewNode

    for nid in id2node:
        raw = node_detail[nid]
        for nd in raw.get('cite', []):
            nds = str(nd)
            if nds in id2node:
                id2node[nid].AppendCite(id2node[nds])
        for nd in raw.get('becited', []):
            nds = str(nd)
            if nds in id2node:
                id2node[nid].AppendBeCited(id2node[nds])

    # 3. 强制保留集合：高熵路径节点 + 高熵子分支（top-k） + 交汇节点路径
    forced_keep_paths = []         # 存路径节点（列表合并，后面会去重）
    high_ke_child_pids = set()     # 存 top-k 子分支的 node id

    # 3.1 高熵节点到 seminal 路径
    for hk in all_high_ke_nodes:
        if hk in id2node:
            forced_keep_paths += get_nodes_in_path2seminal_paper(id2node[hk])

    # 3.2 对每个高熵节点，取其 direct children 中 subtree_size 最大的 top-k（只加入 child id）
    for hk in all_high_ke_nodes:
        if hk not in id2node:
            continue
        children = id2node[hk].ReturnBeCited()
        if not children:
            continue
        child_sizes = [(str(ch.ReturnID()), subtree_node_num(ch)) for ch in children]
        child_sizes.sort(key=lambda x: x[1], reverse=True)
        for cid, _ in child_sizes[:TOPK_DESC]:
            high_ke_child_pids.add(cid)

    # 3.3 交汇节点：保留交汇节点及其到 seminal 的路径
    if intersect_pids:
        for p in intersect_pids:
            pstr = str(p)
            if pstr in id2node:
                forced_keep_paths += get_nodes_in_path2seminal_paper(id2node[pstr])

    # 合并强制保留集合
    all_path_pids_set = set(forced_keep_paths) | high_ke_child_pids

    # 4. 计算 rescale 因子（基于 2025 年的最大宽度，沿用原逻辑）
    max_year = 2025
    last_tree_deep = json.load(open(f'{TREE_DEEP_PATH}{pid}/{max_year}', 'r'))
    max_tree_width = 0
    for d in last_tree_deep:
        max_tree_width = max(max_tree_width, len(last_tree_deep[d]))
    if max_tree_width == 0:
        max_tree_width = 1
    rescale_factor = rescale_len / max_tree_width

    tree_deep = json.load(open(f'{TREE_DEEP_PATH}{pid}/{yr}', 'r'))

    # 5. 按层筛选
    selected_pids = [str(pid)]   # 始终保留根
    # next_layer_selected_pids 保存上一层被保留的节点 id（字符串形式）
    next_layer_selected_pids = [str(pid)]

    for depth in range(len(tree_deep)):
        # 计算候选节点（这一层的所有 child）
        candidates = []
        if depth == 0:
            # 根的第1层候选
            root_id = str(tree_deep[str(depth)][0])
            if root_id in id2node:
                candidates = id2node[root_id].ReturnBeCited()
            else:
                candidates = []
        else:
            seen = set()
            for p_id in next_layer_selected_pids:
                if p_id in id2node:
                    for node in id2node[p_id].ReturnBeCited():
                        nid = str(node.ReturnID())
                        if nid not in seen:
                            candidates.append(node)
                            seen.add(nid)

        # 重置下一层候选
        next_layer_selected_pids = []
        competition = []

        # 先把强制保留的节点直接加入（不参与竞争）
        for node in candidates:
            nid = str(node.ReturnID())
            if nid in all_path_pids_set:
                selected_pids.append(nid)
                next_layer_selected_pids.append(nid)
            else:
                competition.append(nid)

        # 对竞争者按 subtree 大小排序并切取比例
        scored = [(nid, subtree_node_num(id2node[nid])) for nid in competition]
        scored.sort(key=lambda x: x[1], reverse=True)

        keep_num = int(len(scored) * rescale_factor)
        # keep_num 可能为 0，保留原语义。如果你希望每层至少保留 1 个，可改为: keep_num = max(1, keep_num) when len(scored)>0
        for nid, _ in scored[:keep_num]:
            selected_pids.append(nid)
            next_layer_selected_pids.append(nid)

    # 去重并保证字符串格式
    selected_pids = list(dict.fromkeys([str(x) for x in selected_pids]))  # 保持顺序且去重

    # 6. 构造输出节点 JSON（只包含被选中的节点及其内部引用关系）
    new_nodes = {}
    for nid in selected_pids:
        if nid not in id2node:
            # 有可能被选中的节点并不在当前年份树中（路径来自 later-year），跳过
            continue
        node = id2node[nid]
        new_nodes[nid] = {
            'label': node.ReturnLabel(),
            'year': node.ReturnYear()[0:4],
            'cite': [],
            'becited': []
        }

    for nid in list(new_nodes.keys()):
        node = id2node.get(nid)
        if not node:
            continue
        for c in node.ReturnCite():
            cid = str(c.ReturnID())
            if cid in new_nodes:
                new_nodes[nid]['cite'].append(c.ReturnID())
        for b in node.ReturnBeCited():
            bid = str(b.ReturnID())
            if bid in new_nodes:
                new_nodes[nid]['becited'].append(b.ReturnID())

    # 写出文件
    out_dir = SIMPLIED_TREE_JSON_FILE_PATH + str(pid)
    os.makedirs(out_dir, exist_ok=True)
    json.dump(new_nodes, open(out_dir+'/'+str(yr), 'w'))

    print(f"[simply_skeleton_tree_combined] year={yr} original_nodes={len(node_detail)} selected={len(new_nodes)} "
          f"high_ke_count={len(all_high_ke_nodes)} forced_keep_count={len(all_path_pids_set)}")

