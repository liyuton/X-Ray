# import MySQLdb
# import MySQLdb.cursors
import pymysql
from pymysql.cursors import SSCursor
import json
import os
import datetime
import random
from tqdm import tqdm
import time

def getName_by_pid(pid):
    # 0.准备sql语句
    sql = "SELECT title FROM `am_paper`.`am_paper` WHERE paper_id = {}".format(pid)
    # 1.找到cursor
    cursor = db.cursor()
    # 2.执行sql并拿到结果
    cursor.execute(sql)
    result = cursor.fetchall()
    return result[0][0]




def gen_source_gml(pid):
    # 找到所有引用ID为PaperID的文章的ID
    start_time = time.time()
    cursor = db.cursor()
    sql = "select paper_id from `am_paper_reference` where reference_id = {}".format(pid)
    cursor.execute(sql)
    end_time = time.time()
    print(f"# 第一个sql运行时间: {end_time-start_time:.2f} 秒")

    IDList = [i[0] for i in cursor]
    IDList.append(pid)
    nodeList = []
    edgeList = []
    start_time = time.time()
    sql = "select paper_id, title, date from `am_paper` where paper_id IN {};".format(repr(tuple(IDList)))
    cursor.execute(sql)
    end_time = time.time()
    print(f"# 第二个sql运行时间: {end_time-start_time:.2f} 秒")
    for paid, title, date in cursor:
        nodeList.append((paid, title, date))
        
    start_time = time.time()
    sql = """SELECT paper_id, reference_id FROM am_paper_reference 
    WHERE reference_id IN {} AND paper_id IN {};""".format(repr(tuple(IDList)),repr(tuple(IDList)))
    cursor.execute(sql)
    end_time = time.time()
    print(f"# 第三个sql运行时间: {end_time-start_time:.2f} 秒")
    for paid, refid in cursor:
        edgeList.append((paid, refid))
                
    nodes_list = nodeList
    edges_list = edgeList
    iteration = 0
    graph_info = 'graph [\n  directed 1\n'
    start_time = time.time()
    title = getName_by_pid(pid).replace('"', "")
    title = title.replace(":", "")
    end_time = time.time()
    print(f"# 第四个sql运行时间: {end_time-start_time:.2f} 秒")

    if not os.path.exists("../input/source_gml"):
        os.makedirs("../input/source_gml")
    with open(f"../input/source_gml/{pid}.gml", "w+", encoding="utf-8") as f:
        f.write(graph_info)
        for node in nodes_list:
            iteration += 1
            node_info = '  node' + '\n' + '  [\n    id ' + str(node[0]) + '\n' + '    label ' + str(node[1]).replace('"', "").replace(":", "") + '\n'+'    date ' + str(node[2]) + '\n  ]\n'
            f.write(node_info)
        for edge in edges_list:
            edge_info = '  edge' + '\n' + '  [\n    source ' + str(edge[0]) + '\n' + '    target ' + str(
                edge[1]) + '\n  ]\n'
            f.write(edge_info)
        f.write("]")



if __name__ == "__main__":
    start_time_main = time.time() 
    # 根据当前已经生成好的各种中间文件来随机生成不重复的pid列表用于继续生成主题的x-ray
    # top_pids = json.load(open('top_paper_list.json', 'r'))
    # finished_pids = []
    # candidates_pids = os.listdir('../temp_files/node_entropy_by_year')
    # for cpid in candidates_pids:
    #     years = os.listdir(f'../temp_files/node_entropy_by_year/{cpid}')
    #     if '2021' in years:
    #         finished_pids.append(cpid)
    # unfinished_all_pids = list(set(top_pids).difference(finished_pids))
    # pids = []
    # if len(unfinished_all_pids) >= 2000:
    #     pids = random.sample(unfinished_all_pids, 2000)
    # else:
    #     pids = unfinished_all_pids
    # json.dump(pids, open('pids2process.json', 'w'))

    # pids = json.load(open('cccf_pids_1.json', 'r'))
    # pids = ['113768329']    # bert论文
    # pids = ['314384100'] #sentence-bert论文

        
    # db = MySQLdb.connect(
    #     host = '10.10.12.1',
    #     user = 'readonly_ampaper',
    #     password = 'readonly@ampaper1',
    #     db = 'am_paper',
    #     port = 3306,
    #     charset = 'utf8mb4',
    #     cursorclass=MySQLdb.cursors.SSCursor
    # )

        
    db = pymysql.connect(
        host='10.10.12.1',
        user='readonly_ampaper',
        password='readonly@ampaper1',
        db='am_paper',
        port=3306,
        charset='utf8mb4',
        cursorclass=SSCursor
    )
        
    # pids = ['107234871', '151483314', '369508772']
    # pids = json.load(open('12_28_pids.json', 'r'))
    # pids = ['107234871', '151483314', '369508772']
    # pids = ['380546090']
    pids = ['2047040143',
        '2051518078',
        '2138058376',
        '2089850899',
        '1978185779',
        '3088610511',
        '2943740841',
        ]
    for pid in tqdm(pids):
        gen_source_gml(str(pid))
        print("-" * 50)
        print(f"### process {pid} finished ###")

    # pids = json.load(open('cccf_pids_2.json', 'r'))
    
    # for pid in tqdm(pids):
    #     gen_source_gml(str(pid))
    end_time_main = time.time()  # 计时结束
    elapsed_time = end_time_main - start_time_main
    print(f"总运行时间: {elapsed_time:.2f} 秒")