import json
import os
from simply_skeleton_tree import simply_skeleton_tree_3

# ================== 配置区域 ==================
# 假设这是您的两篇论文 ID，请在此修改
PID_1 = "2113233457" 
PID_2 = "2137775453"

# 基础路径配置 (根据您提供的路径)
BASE_PATH = '/home/liyutong1117/jupyter/scientific_x_ray-github/temp_files'
TREE_JSON_FILE_PATH = os.path.join(BASE_PATH, 'skeleton_tree_by_year/')
# 注意：simply_skeleton_tree_3 函数内部可能也使用了全局变量 TREE_JSON_FILE_PATH
# 请确保上下文中的路径一致

# ================== 辅助函数 ==================

def load_json(path):
    """
    读取 JSON 文件并返回字典
    """
    if not os.path.exists(path):
        return None # 如果文件不存在返回 None，方便后续判断
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def find_common_ids(data1, data2):
    """
    找出两个数据集中重复出现的论文 ID（键为10位数字）
    """
    if data1 is None or data2 is None:
        return set() # 如果任一数据为空，交集为空

    ids1 = set(data1.keys())
    ids2 = set(data2.keys())

    common = ids1.intersection(ids2)
    return common

def get_sorted_year_list(pid1, pid2, base_path):
    """
    选取最长年份跨度的论文，读取其目录下的文件名作为year_list并排序
    """
    dir1 = os.path.join(base_path, str(pid1))
    dir2 = os.path.join(base_path, str(pid2))
    
    files1 = []
    files2 = []
    
    if os.path.exists(dir1):
        files1 = [f for f in os.listdir(dir1) if f.isdigit() or f.startswith('20')] # 简单的过滤，确保是年份文件
    
    if os.path.exists(dir2):
        files2 = [f for f in os.listdir(dir2) if f.isdigit() or f.startswith('20')]
        
    # 选取文件数量较多（跨度较长）的列表
    target_files = files1 if len(files1) >= len(files2) else files2
    
    # 排序（按数字大小排序）
    # 假设文件名就是年份，如 "2020", "2021"
    sorted_years = sorted(target_files, key=lambda x: int(x) if x.isdigit() else 0)
    
    return sorted_years

# ================== 主执行流程 ==================

def run_evolution_analysis(pid1, pid2):
    print(f"开始进行 PID: {pid1} 和 PID: {pid2} 的保留演化的简化...")
    
    # 1. 获取最长年份列表
    year_list = get_sorted_year_list(pid1, pid2, TREE_JSON_FILE_PATH)
    print(f"检测到的年份范围: {year_list[0]} -> {year_list[-1]} (共 {len(year_list)} 年)")
    
    # 2. 逐年遍历
    for year in year_list:
        print(f"\n>>> 正在处理年份: {year}")
        
        path1 = os.path.join(TREE_JSON_FILE_PATH, str(pid1), str(year))
        path2 = os.path.join(TREE_JSON_FILE_PATH, str(pid2), str(year))
        
        # 3. 读取数据并计算交集
        # 注意：simply_skeleton_tree_3 需要的是 ID 列表
        common_ids_list = []
        
        # 只有当两个文件都存在时，才有必要计算交集
        if os.path.exists(path1) and os.path.exists(path2):
            data1 = load_json(path1)
            data2 = load_json(path2)
            
            common_set = find_common_ids(data1, data2)
            if common_set:
                common_ids_list = list(common_set)
                print(f"   [交集] 发现 {len(common_ids_list)} 个重合节点")
            else:
                print("   [交集] 无重合节点")
        else:
            print(f"   [交集] 跳过计算 (某一方数据缺失: P1 exists? {os.path.exists(path1)}, P2 exists? {os.path.exists(path2)})")

        # 4. 分别对两篇论文调用简化函数
        # 即使交集为空，或者另一篇论文不存在，当前存在的论文仍需进行简化计算
        
        # 处理 PID 1
        if os.path.exists(path1):
            try:
                print(f"   [执行] 简化 {pid1} - {year} ...")
                simply_skeleton_tree_3(
                    pid=pid1, 
                    yr=year, 
                    THRESHOLD=10, 
                    intersect_pids=common_ids_list # 传入列表
                )
            except Exception as e:
                print(f"   [错误] 处理 {pid1} {year} 时出错: {e}")
        
        # 处理 PID 2
        if os.path.exists(path2):
            try:
                print(f"   [执行] 简化 {pid2} - {year} ...")
                simply_skeleton_tree_3(
                    pid=pid2, 
                    yr=year, 
                    THRESHOLD=10, 
                    intersect_pids=common_ids_list # 传入列表
                )
            except Exception as e:
                print(f"   [错误] 处理 {pid2} {year} 时出错: {e}")

    print("\n所有年份处理完毕。")

# ================== 启动脚本 ==================



if __name__ == "__main__":
    # 确保此处已经定义了 simply_skeleton_tree_3 函数
    # 如果 simply_skeleton_tree_3 在其他文件中，请先 import
    
    run_evolution_analysis(PID_1, PID_2)