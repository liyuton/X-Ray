## 使用es获取论文的引文网络（包含所有引用pid的论文和他们之间的引用关系）
import os
from tqdm import tqdm
import time
from elasticsearch import Elasticsearch


hosts = [
    "http://10.10.10.0:9200",
    "http://elastic:ai8WoTKcmzUC9AW$@10.10.12.1:9200",  # dev
    "http://readonly:readonly@10.10.12.1:9201"          # web
]
client = Elasticsearch(hosts[2])


def find_one_paper_info(paper_id):
    query = {
        "from": 0,
        "size": 1,
        "query": {
            "bool": {
                "must": [
                    {
                        "match": {
                            "_id": paper_id
                        }
                    }
                ]
            }
        },
        "_source": ["title", "publication_date"]
    }

    paper_res = client.search(index="acemap.works", body=query)
    print("leading paper information done!")

    if paper_res['hits']['hits']:  # 确认有结果
        source = paper_res['hits']['hits'][0]['_source']
        paper_title = source.get('title', '')
        paper_date = source.get('publication_date', '')
        paper_id = paper_id.replace("https://openalex.org/W", "")
        return (paper_id, paper_title, paper_date)
    else:
        return (paper_id, None, None)  # 没查到


def find_all_papers_citing_id(input_id):
    """
    查询所有参考文献列表里包含pid的论文（即引用了pid的论文），并返回这些论文的详细信息。
        使用 Scroll API 查找所有引用了某篇特定论文（通过 input_id）的其他论文。
        - 解决了 term 查询在 text 字段上不生效的问题。
        - 解决了获取全部结果的需求。

    :param input_id: 被引用的论文ID (完整的URL字符串)
    :return: 包含所有结果文档的列表
    """
    all_results = []
    scroll_id = None

    try:
        # 0. 准备初始查询
        # - 使用 "referenced_works.keyword" 进行精确匹配
        # - 增加了 "scroll='1m'" 参数，启动一个滚动查询，游标保留1分钟
        query = {
            "query": {
                "term": {
                    "referenced_works.keyword": input_id
                }
            },
            "_source": ["title", "publication_date", "referenced_works"]
        }

        # 1. 发起第一次 search 请求，同时获取第一个 scroll_id
        print("正在发起初始查询...")
        response = client.search(
            index="acemap.works",
            body=query,
            scroll='1m', # 设置 scroll 上下文的保留时间
            size=1000   # 每次 scroll 拉取的数据量，最大10000，推荐1000
        )

        scroll_id = response.get('_scroll_id')
        hits = response['hits']['hits']
        print(f"初步查询命中 {response['hits']['total']['value']} 条，开始滚动获取...")

        # 2. 循环使用 scroll API 拉取剩余数据
        while scroll_id and hits:
            # 将当前批次的结果存入列表
            for hit in hits:
                source_data = hit['_source']
                source_data['_id'] = hit['_id']
                all_results.append(source_data)
            
            # 发起下一次 scroll 请求
            response = client.scroll(scroll_id=scroll_id, scroll='1m')
            
            scroll_id = response.get('_scroll_id')
            hits = response['hits']['hits']
            if hits:
                print(f"已获取 {len(all_results)} 条...")

        return all_results

    except Exception as e:
        print(f"查询 Elasticsearch 时出错: {e}")
        return []
    finally:
        # 3. 查询结束后，清除 scroll 上下文，释放 ES 资源
        if scroll_id:
            try:
                client.clear_scroll(scroll_id=scroll_id)
                print("Scroll上下文已清除。")
            except Exception as e:
                print(f"清除Scroll上下文时出错: {e}")


def gen_source_gml(pid):
    # 添加openalex.org/W前缀，构造完整的ES查询ID
    es_pid = "https://openalex.org/W" + pid
    all_results = find_all_papers_citing_id(es_pid)

    # 存储需要保留的节点id列表，同时去除了信息不全的论文id
    paper_id_all_set = set()
    paper_id_all_set.add(pid)
    for paper in all_results:
        try:
            paper_id = paper["_id"]
            paper_id = paper_id.replace("https://openalex.org/W", "")
            paper_title = paper["title"]
            paper_date = paper["publication_date"]
            paper_referenced_works = paper["referenced_works"]
            paper_id_all_set.add(paper_id)
        except KeyError as e:
            # print(f"文档 {paper.get('_id')} 缺少字段: {e}，跳过。")
            continue


    nodes_list, edges_list = [], []
    # 在节点列表中加入pid对应的论文信息（即使它不在all_results中，因为它可能没有被引用过）
    nodes_list.append(find_one_paper_info(es_pid))

    for paper in tqdm(all_results):
        try:
            paper_id = paper["_id"]
            paper_id = paper_id.replace("https://openalex.org/W", "")
            paper_title = paper["title"]
            paper_date = paper["publication_date"]
            paper_referenced_works = paper["referenced_works"]
        except KeyError as e:
            # print(f"# step 2: 文档 {paper.get('_id')} 缺少字段: {e}，跳过。")
            continue

        nodes_list.append((paper_id, paper_title, paper_date))

        for referenced_id in paper_referenced_works:
            referenced_id = referenced_id.replace("https://openalex.org/W", "")
            # 保留在节点列表内的ref_id（去除了信息不全的节点以及参考的论文在节点列表外的论文）
            if referenced_id in paper_id_all_set:
                edges_list.append((paper_id, referenced_id))
        
    print("all paper information done!")

    iteration = 0
    graph_info = 'graph [\n  directed 1\n'

    if not os.path.exists("../input/source_gml"):
        os.makedirs("../input/source_gml")
    with open(f"../input/source_gml/{pid}.gml", "w+", encoding="utf-8") as f:
        f.write(graph_info)
        for node in nodes_list:
            iteration += 1
            node_info = '  node' + '\n' + '  [\n    id ' + str(node[0]) + '\n' + '    label ' + str(node[1]).replace('"', "").replace(":", "") + '\n'+'    date ' + str(node[2]) + '\n  ]\n'
            f.write(node_info)
        for edge in edges_list:
            edge_info = '  edge' + '\n' + '  [\n    source ' + str(edge[0]) + '\n' + '    target ' + str(edge[1]) + '\n  ]\n'
            f.write(edge_info)
        f.write("]")



if __name__ == "__main__":
    # pids = ["https://openalex.org/W2896457183"]       # BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding
    # pids = ["https://openalex.org/W4294558607"]     # Inductive Representation Learning on Large Graphs
    # pids = ["2038356993","2036453317","3101479050","1513911404"]
    # pid入口
    pids = ['2113233457']




    for pid in tqdm(pids):
        time1 = time.time()
        gen_source_gml(pid)
        print("-" * 50)
        time2 = time.time()
        print(f"### process {pid} finished, time {time2-time1}s ###")

        