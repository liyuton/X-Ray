###用老数据库和引文网络生成总结###
import requests
import pymysql
from readgml import readgml
from pymysql.cursors import SSCursor


# 调用 API 补全对话
def completion(user_prompt):
    dialogue = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_prompt},
        {"role": "assistant", "content": ""},
    ]
    sjtu_temp = 'sk-hBzYhO9CB1r1bZJf7407DcF261Af46A8Ad5eF71fB4C102F2'  # 令牌

    response = requests.post(
        url='https://openai.acemap.cn/v1/chat/completions',
        headers={'Authorization': f'Bearer {sjtu_temp}'},
        json={'model': 'gpt-4o-mini', 'messages': dialogue},
        verify=False,
    )
    return response.json()['choices'][0]['message']['content']


# 对于更复杂的引文网络，需要使用 networkx 建图，并搜索一跳节点
def graph_search(pid):
    pass


# 给定单个 pid，从老的 mysql 库中搜索 title 和 abstract
def get_info_by_pid(pid):
    sql = "SELECT title FROM `am_paper`.`am_paper` WHERE paper_id = {}".format(pid)
    cursor = db.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    title = result[0][0]

    sql = "SELECT abstract FROM `am_paper`.`am_paper_abstract` WHERE paper_id = {}".format(pid)
    cursor = db.cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    abstract = result[0][0]

    return title, abstract


# 给定 pid 列表，多次调用 get_info_by_pid
def db_search(pid_ls):
    paper_info_ls = []
    for pid in pid_ls:
        title, abstract = get_info_by_pid(pid)
        paper_info = [title, abstract]
        paper_info_ls.append(paper_info)
    
    return paper_info_ls


# 最终的总结函数：1. 构造prompt，2. 调用 api 总结
def summary(pid, cited_pid_ls, top_pid_info, cited_pid_info, reference_ls):
    other_paper_info = ""
    for paper_id, paper_info in zip(cited_pid_ls, cited_pid_info):
        cur_paper_info = f"""Paper ID: {paper_id}
Paper Title: {paper_info[0]}
Paper Abstract: {paper_info[1]}\n
"""
        other_paper_info += cur_paper_info
    
    reference_info = ""
    for reference in reference_ls:
        cur_ref_info = f"""Paper {reference[0]} cited Paper {reference[1]}\n
"""
        reference_info += cur_ref_info
    
    prompt = f"""Given the list of papers below and their citation relationships, write a concise, coherent development narrative of the research area. 
The paragraph should include: background and starting point, key developments in chronological order, main contributions and methods of each work, causal/influence relations between works (who extended or improved whom), and the current state plus likely future directions. 
Inline parenthetical markers for key papers are requested (e.g., author surname, year or paper ID). Please use clear, objective, and scholarly language suitable for researchers.

### Leading Paper Information ###
Leading Paper ID: {pid}
Leading Paper Title: {top_pid_info[0]}
Leading Paper Abstract: {top_pid_info[1]}

### Other Paper Information ###
{other_paper_info}

### Reference Information ###
{reference_info}
"""

    response = completion(prompt)

    return prompt, response

        
db = pymysql.connect(
    host='10.10.12.1',
    user='readonly_ampaper',
    password='readonly@ampaper1',
    db='am_paper',
    port=3306,
    charset='utf8mb4',
    cursorclass=SSCursor
)

pid = 470780090
gml_path = "../temp_files/attributed_idea_tree_by_year/470780090/2021.gml"
nodes, edges = readgml.read_gml(gml_path)

reference_ls = [[edge["source"], edge["target"]] for edge in edges]


# cited_pid_ls = graph_search(pid)
cited_pid_ls = [node["id"] for node in nodes]
# top_pid_info = db_search(pid)
top_pid_info = get_info_by_pid(pid)
cited_pid_info = db_search(cited_pid_ls)


prompt, final_summary = summary(pid, cited_pid_ls, top_pid_info, cited_pid_info, reference_ls)

print(prompt)
print("-" * 50)
print(final_summary)


# 将 prompt 和 summary 结果保存到本地 txt 文件
with open("../output/prompt.txt", "w", encoding="utf-8") as f:
    f.write(prompt)

with open("../output/summary.txt", "w", encoding="utf-8") as f:
    f.write(final_summary)