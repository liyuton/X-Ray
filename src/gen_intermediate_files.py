# ### 逐年生成相关科学主题的所需文件，逐年分割gml文件，脉络树文件，点熵树熵文件，树深文件
import networkx as nx
import time
import json
import random
import os
from readgml import readgml
from tqdm import tqdm
from multiprocessing.pool import Pool

from gen_source_gml_by_year import gen_year_by_year_source_gml
from gen_reduction import gen_reduction
from gen_skeleton_tree import gen_skeleton_tree
from gen_tree_node_deep import gen_tree_node_deep
from gen_node_and_tree_entropy import gen_entropy
from gen_idea_tree_attributed_and_detail_file import gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail
from gen_KE_and_VD_evolution_pics import top_knowledge_entropy_evolution, visible_depth_evoluation
from get_delta_D_for_specific_topic import delta_d_evolution


def gen_intermediate_files(pid):
    # 逐年生成脉络树，树深，各个节点的点熵树熵等
    start_time = time.time()
    gen_year_by_year_source_gml(pid, 2021) #按年份切分出该主题的引文网络，生成每年一个 .gml 文件
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"# 函数 gen_year_by_year_source_gml 运行时间: {elapsed_time:.2f} 秒")
    files_list = os.listdir('../temp_files/source_gml_by_year/'+str(pid)) #存储每年的.gml 文件
    years_list = sorted([int(file.split('.')[0]) for file in files_list])
    print(years_list)
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
    for year in tqdm(years_list): #依次处理每年的引文网络
        start_time = time.time()
        INPUT_FILE_PATH = '../temp_files/source_gml_by_year/'+str(pid)+'/'+str(year)+'.gml'
        pid2reduction = gen_reduction(pid, INPUT_FILE_PATH)
        print(year,"reduction finish.")
        skeleton_tree = gen_skeleton_tree(pid, pid2reduction, INPUT_FILE_PATH)
        print(year,"skeleton_tree finish.")
        deep2node = gen_tree_node_deep(pid, skeleton_tree)
        print(year,"tree_node_deep finish.")
        EntropyIndex, EntropyCutIndex = gen_entropy(pid, skeleton_tree, deep2node, INPUT_FILE_PATH)  # EntropyIndex: 树熵，EntropyCutIndex：点熵
        print(year,"gen_entropy finish.")
        json.dump(skeleton_tree, open('../temp_files/skeleton_tree_by_year/'+str(pid)+'/'+str(year), 'w'))
        json.dump(deep2node, open('../temp_files/tree_deep_by_year/'+str(pid)+'/'+str(year), 'w'))
        json.dump(EntropyIndex, open('../temp_files/subtree_entropy_by_year/'+str(pid)+'/'+str(year), 'w'))
        json.dump(EntropyCutIndex, open('../temp_files/node_entropy_by_year/'+str(pid)+'/'+str(year), 'w'))
        # gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail(pid, year)
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"# year: {year}, 运行时间: {elapsed_time:.2f} 秒")
    
    # start_time = time.time()
    # visible_depth_evoluation(pid)
    # delta_d_evolution(pid)
    # end_time = time.time()
    # elapsed_time = end_time - start_time
    # print(f"函数 visible_depth_evoluation 和 delta_d_evolution 运行时间: {elapsed_time:.2f} 秒")
    print(f"Topic {pid} finish!")

if __name__=="__main__":
    # pids = ['314384100']
    # pids = ['107234871', '151483314', '369508772']
    # pids = ['470780090',
    #         '187139104',
    #         '242975836',
    #         '193690222',
    #         '200599618',
    #         '219704643',
    #         '76205213',
    #         '477291171',
    #         '298754821',
    #         '496604792'
    #     ]
    # pids = ['380546090']
    pids = ['303083533', '233671985', '135613275', '284362347', '165012411', '235050912']
    process_num = len(pids) if len(pids) <= 50 else 50

    with Pool(process_num) as pool:
        pool.map(gen_intermediate_files, pids)
