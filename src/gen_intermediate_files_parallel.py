### 逐年生成中间文件，逐年分割gml文件，脉络树文件，点熵树熵文件，树深文件
""" 并行执行 years"""
import networkx as nx
import time
import json
import random
import os
import sys
import datetime
from readgml import readgml
from tqdm import tqdm
from multiprocessing.pool import Pool # 确保 Pool 被导入

# from gen_source_gml_by_year import gen_year_by_year_source_gml
from gen_source_gml_by_year_scc import gen_year_by_year_source_gml
# from gen_reduction_v3 import gen_reduction
from gen_reduction_v2 import gen_reduction
from gen_skeleton_tree import gen_skeleton_tree
from gen_tree_node_deep import gen_tree_node_deep
from gen_node_and_tree_entropy import gen_entropy
from gen_idea_tree_attributed_and_detail_file import gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail
from gen_KE_and_VD_evolution_pics import top_knowledge_entropy_evolution, visible_depth_evoluation
from get_delta_D_for_specific_topic import delta_d_evolution


def process_year_task(args):
    """
    用于并行处理单个年份的工作函数。
    """
    pid, year = args  # 解包参数
    try:
        start_time = time.time()
        INPUT_FILE_PATH = '../temp_files/source_gml_by_year/'+str(pid)+'/'+str(year)+'.gml'

        if not os.path.exists(INPUT_FILE_PATH):
            print(f"# [{pid}-{year}] 警告: 输入文件 {INPUT_FILE_PATH} 未找到，跳过。")
            return (year, False, 0)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{pid}-{year}] [{timestamp}] process begin.")

        pid2reduction = gen_reduction(pid, INPUT_FILE_PATH)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{pid}-{year}] [{timestamp}] reduction finish.")
        
        skeleton_tree = gen_skeleton_tree(pid, pid2reduction, INPUT_FILE_PATH)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{pid}-{year}] [{timestamp}] skeleton_tree finish.")
        
        deep2node = gen_tree_node_deep(pid, skeleton_tree)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{pid}-{year}] [{timestamp}] tree_node_deep finish.")
        
        EntropyIndex, EntropyCutIndex = gen_entropy(pid, skeleton_tree, deep2node, INPUT_FILE_PATH)  # EntropyIndex: 树熵，EntropyCutIndex：点熵
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{pid}-{year}] [{timestamp}] gen_entropy finish.")
        
        json.dump(skeleton_tree, open('../temp_files/skeleton_tree_by_year/'+str(pid)+'/'+str(year), 'w'))
        json.dump(deep2node, open('../temp_files/tree_deep_by_year/'+str(pid)+'/'+str(year), 'w'))
        json.dump(EntropyIndex, open('../temp_files/subtree_entropy_by_year/'+str(pid)+'/'+str(year), 'w'))
        json.dump(EntropyCutIndex, open('../temp_files/node_entropy_by_year/'+str(pid)+'/'+str(year), 'w'))
        
        # 要求3：保持注释状态
        # gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail(pid, year) 
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"# [{pid}-{year}] 运行时间: {elapsed_time:.2f} 秒")
        return (year, True, elapsed_time) # 返回成功状态和年份
    except Exception as e:
        print(f"!! [{pid}-{year}] 处理失败: {e}")
        return (year, False, 0) # 返回失败状态和年份


def gen_intermediate_files(pid):
    # 逐年生成脉络树，树深，各个节点的点熵树熵等
    
    # =================================================================
    # Barrier 1: 必须首先串行执行 (要求2)
    # =================================================================
    print(f"--- [Barrier 1] {pid}: 开始执行 gen_year_by_year_source_gml ---")
    start_time = time.time()
    gen_year_by_year_source_gml(pid) #按年份切分出该主题的引文网络，生成每年一个 .gml 文件（当前年份2025设置在这个函数中）
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"# 函数 gen_year_by_year_source_gml 运行时间: {elapsed_time:.2f} 秒")
    
    try:
        files_list = os.listdir('../temp_files/source_gml_by_year/'+str(pid)) #存储每年的.gml 文件
    except FileNotFoundError:
        print(f"!! 错误: 目录 ../temp_files/source_gml_by_year/{pid} 未找到。")
        print("!! gen_year_by_year_source_gml 可能未成功生成文件。")
        return # 提前退出

    years_list = sorted([int(file.split('.')[0]) for file in files_list])
    # years_list = [year for year in years_list if year >= 1992 and year <= 2010]
    print(f"[{pid}] 准备处理年份: {years_list}")
    
    # 串行创建所有需要的目录
    if not os.path.exists('../temp_files/skeleton_tree_by_year/'+str(pid)):
        os.makedirs('../temp_files/skeleton_tree_by_year/'+str(pid))
    if not os.path.exists('../temp_files/node_entropy_by_year/'+str(pid)):
        os.makedirs('../temp_files/node_entropy_by_year/'+str(pid))
    if not os.path.exists('../temp_files/subtree_entropy_by_year/'+str(pid)):
        os.makedirs('../temp_files/subtree_entropy_by_year/'+str(pid))
    if not os.path.exists('../temp_files/tree_deep_by_year/'+str(pid)):
        os.makedirs('../temp_files/tree_deep_by_year/'+str(pid))
    if not os.path.exists('../temp_files/attributed_idea_tree_by_year/'+str(pid)):
        os.makedirs('../temp_files/attributed_idea_tree_by_year/'+str(pid))
    if not os.path.exists('../output/final_topic_portrait/'+str(pid)):
        os.makedirs('../output/final_topic_portrait/'+str(pid))
    
    print(f"--- [Barrier 1] {pid}: 串行任务完成 ---")

    # =================================================================
    # Part 2: 并行处理 (要求1)
    # =================================================================
    print(f"--- [Parallel Start] {pid}: 开始并行处理 {len(years_list)} 个年份 ---")
    start_time_parallel = time.time()

    # 准备任务参数列表，每个元素是 (pid, year) 元组
    tasks = [(pid, year) for year in years_list]
    
    # 设置并行数为10
    num_processes = 5

    # 使用 Pool.map 来执行并行任务
    # pool.map 会阻塞，直到所有任务完成
    with Pool(processes=num_processes) as pool:
        # 使用 tqdm 显示进度
        results = list(tqdm(pool.map(process_year_task, tasks), total=len(tasks), desc=f"Processing {pid}"))

    # (可选) 检查并行处理的结果
    success_count = sum(1 for r in results if r[1])
    failed_years = [r[0] for r in results if not r[1]]

    end_time_parallel = time.time()
    elapsed_time_parallel = end_time_parallel - start_time_parallel
    print(f"--- [Parallel End] {pid}: 并行处理完成 ---")
    print(f"# 并行处理总运行时间: {elapsed_time_parallel:.2f} 秒")
    print(f"# 成功: {success_count}, 失败: {len(failed_years)}")
    if failed_years:
        print(f"!! 失败的年份: {failed_years}")

    # =================================================================
    # Barrier 2: 必须在并行任务全部完成后执行 (要求4)
    # =================================================================
    # print(f"--- [Barrier 2] {pid}: 开始执行 visible_depth_evoluation 和 delta_d_evolution ---")
    # start_time = time.time()
    # visible_depth_evoluation(pid)
    # delta_d_evolution(pid)
    # end_time = time.time()
    # elapsed_time = end_time - start_time
    # print(f"# 函数 visible_depth_evoluation 和 delta_d_evolution 运行时间: {elapsed_time:.2f} 秒")
    # print(f"--- [Barrier 2] {pid}: 串行任务完成 ---")
    
    print(f"Topic {pid} finish!")


if __name__=="__main__":
    if len(sys.argv) < 2:
        print("Usage: python gen_intermediate_files_parallel.py <pid>")
        sys.exit(1)
    
    pid = sys.argv[1]  # 读取命令行传入的 pid
    gen_intermediate_files(pid)