import matplotlib.pyplot as plt
import networkx as nx
from PIL import Image, ImageDraw, ImageFont
from readgml import readgml
from networkx.drawing.nx_agraph import graphviz_layout

import os
import re
import csv
import json
import math
import random
import queue
# import MySQLdb
# import MySQLdb.cursors
import pymysql
from pymysql.cursors import SSCursor
import matplotlib
matplotlib.use('Agg')
from multiprocessing.pool import Pool
import datetime
import matplotlib.pyplot as plt
from graphviz import Digraph
from tqdm import tqdm
from PIL import Image
from matplotlib import cm
import numpy as np
import seaborn as sns
import networkx as nx
import treelib as tl
import pandas as pd
from matplotlib.ticker import MaxNLocator
from networkx.utils import is_string_like

from entropy_tree_layout2gml import gen_entropy_tree_visual_gml, gen_citation_entropy_tree_visual_gml # 传递参数较多，集成的模块从函数内部进行配置传参
from gen_tree_analysis_data import get_max_bias_subtree_entropy, get_max_bias_node_entropy
# from simply_skeleton_tree import simply_skeleton_tree, simply_skeleton_tree_2
from simply_skeleton_tree import simply_skeleton_tree_2
from gml2jpg import gml2png # 传递的参数较少，集成模块时直接从函数调用时传参
from get_sub_field_entropy import get_sub_field_entropy

THRESHOLD = 10

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


def generate_gml(G):
    # gml图生成器直接将networkx源代码进行修改
    # recursively make dicts into gml brackets
    def listify(d,indent,indentlevel):
        result='[ \n'
        for k,v in d.items():
            if type(v)==dict:
                v=listify(v,indent,indentlevel+1)
            result += (indentlevel+1)*indent + string_item(k,v,indentlevel*indent)+'\n'
        return result+indentlevel*indent+"]"

    def string_item(k,v,indent):
        # try to make a string of the data
        if type(v)==dict: 
            v=listify(v,indent,2)
        elif is_string_like(v):
            v='"%s"'%v
        elif type(v)==bool:
            v=int(v)
        return "%s %s"%(k,v)

    # check for attributes or assign empty dict
    if hasattr(G,'graph_attr'):
        graph_attr=G.graph_attr
    else:
        graph_attr={}
    if hasattr(G,'node_attr'):
        node_attr=G.node_attr
    else:
        node_attr={}

    indent=2*' '
    count=iter(range(len(G)))
    node_id={}

    yield "graph ["
    if G.is_directed():
        yield indent+"directed 1"
    # write graph attributes 
    for k,v in G.graph.items():
        if k == 'directed':
            continue
        yield indent+string_item(k,v,indent)
    # write nodes
    for n in G:
        yield indent+"node ["
        # get id or assign number
        #nid=G.node[n].get('id',next(count))
        #node_id[n]=nid
        nid = n
        node_id[n]=n
        # 上两行对原代码进行修改，以原始输入的id作为输出图文件的id
        yield 2*indent+"id %s"%nid
        label=G.node[n]['L']
        node_json = G.node[n]['JSON']
        if is_string_like(label):
            label='"%s"'%label
        yield 2*indent+'label %s'%label
        if n in G:
          for k,v in G.node[n].items():
              if k=='id' or k == 'label' or k == 'L' or k == 'JSON': continue
              yield 2*indent+string_item(k,v,indent)
        yield indent+"]"
    # write edges
    for u,v,edgedata in G.edges(data=True):
        source_color = G.node[u]['graphics']['fill']
        target_color = G.node[v]['graphics']['fill']
        yield indent+"edge ["
        yield 2*indent+"source %s"%u
        yield 2*indent+"target %s"%v
        yield 2*indent+"value 1.0"
        yield 2*indent+"color "+ get_edge_color_by_mixe_node_color(source_color, target_color)
        yield indent+"]"
    yield "]"


def gen_node_size(id2entropy):
    # 此函数对于节点尺寸的可视化效果不佳，未能凸显不同节点的知识熵差异，弃用
    id2size = {pid:5 for pid in id2entropy}
    for pid in id2entropy:
        if id2entropy[pid] >= THRESHOLD:
            id2size[pid] = ((math.log(float(id2entropy[pid])))** 2) + 10
    return id2size

def gen_node_size(id2entropy):
    # 将所有节点的大小严格限制在10-200之间
    max_entropy = 0
    max_entropy_id = ''
    for pid in id2entropy:
        if id2entropy[pid] > 1000:
            id2entropy[pid] = 1000 + math.log(id2entropy[pid] - 1000)*10
        if id2entropy[pid] > max_entropy:
            max_entropy = id2entropy[pid]
            max_entropy_id = str(pid)
    factor = 190/max_entropy
    id2size = {}
    for pid in id2entropy:
        id2size[pid] = factor*id2entropy[pid] + 10
    return id2size

def get_edge_color_by_mixe_node_color(source_color, target_color):
    # 用于将节点颜色进行混合，进而得到边的颜色
    r = str(hex(int((int(source_color[1:3], 16) + int(target_color[1:3], 16)) / 2)))
    g = str(hex(int((int(source_color[3:5], 16) + int(target_color[3:5], 16)) / 2)))
    b = str(hex(int((int(source_color[5:7], 16) + int(target_color[5:7], 16)) / 2)))
    if len(r.split('x')[1]) == 1:
        r = '0' + r.split('x')[1]
    else:
        r = r.split('x')[1]
    if len(g.split('x')[1]) == 1:
        g = '0' + g.split('x')[1]
    else:
        g = g.split('x')[1]
    if len(b.split('x')[1]) == 1:
        b = '0' + b.split('x')[1]
    else:
        b = b.split('x')[1]
    return '#' + r + g + b


def gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail(seminal_pid, year):
    """
    更安全的实现：加入大量检查/日志，避免 NoneType/键错误，并在关键点抛出带上下文的异常。
    """
    try:
        print(f"[DEBUG] start gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail pid={seminal_pid}, year={year}")
        # 配色/参数保持不变
        depth2color = {
            'root': '#ff0000',
            'invisible': '#959595',
            '1': '#ffe306','2': '#ff723a','3': '#f81463','4': '#9d126f','5': '#6c48aa','6': '#0a0da7','7': '#0000ff'
        }
        depth2color_half_trans = {'1': "#fff396",'2': '#ffb89c','3': '#fb89b1','4': '#ce88b7','5': '#b5a3d4','6': '#5355c1'}
        pid2simply_ratio = {
            '62270017': 0.3, '142612150': 0.05, '214435441': 0.05, '255866650': 0.05,
            '1842472': 0.05, '356008829': 0.05, '71305135': 0.1, '379075697': 0.05,
            '252195446': 0.07, '174864895': 0.1, '175773368': 0.15, '329258602': 0.05,
            '457139010': 0.3, '1587314': 0.35, '81075167': 0.14, '38572377': 0.00001,
            '252470610': 0.001, '166247013': 0.001, '445475439': 0.01, '166725067': 0.001, '457139010': 0.001
        }
        simply_ratio = pid2simply_ratio.get(str(seminal_pid), 0.2)

        # 检查并加载必要文件（存在性`和类型检查）
        node_entropy_path = f'../temp_files/node_entropy_by_year/{seminal_pid}/{year}'
        tree_deep_path = f'../temp_files/tree_deep_by_year/{seminal_pid}/{year}'
        simplied_path = f"../temp_files/simplied_skeleton_tree_by_year/{seminal_pid}/{year}"

        # Step 1. 检查前置依赖（node_entropy 与 tree_deep）
        for p in (node_entropy_path, tree_deep_path):
            if not os.path.exists(p):
                raise FileNotFoundError(f"[ERR] required file not found: {p} (pid={seminal_pid}, year={year})")

        # Step 2. 检查并确保简化脉络树存在（如果没有则生成）
        simplied_path = f"../temp_files/simplied_skeleton_tree_by_year/{seminal_pid}/{year}"
        if not os.path.exists(simplied_path):
            print(f"[INFO] simplied skeleton tree missing, generating via simply_skeleton_tree_2()...")
            try:
                simply_skeleton_tree_2(seminal_pid, year, THRESHOLD)
                # 生成后再检查一次
                if not os.path.exists(simplied_path):
                    raise FileNotFoundError(f"[ERR] simply_skeleton_tree_2 did not produce expected file: {simplied_path}")
                else:
                    print(f"[INFO] successfully generated simplified skeleton tree for pid={seminal_pid}, year={year}")
            except Exception as e:
                raise RuntimeError(f"[ERR] failed to generate simplified skeleton tree for pid={seminal_pid}, year={year}: {e}")


        pid2node_entropy = json.load(open(node_entropy_path, 'r'))
        if not isinstance(pid2node_entropy, dict):
            raise TypeError(f"[ERR] pid2node_entropy is not dict: {type(pid2node_entropy)} (path={node_entropy_path})")

        tree_node_deep = json.load(open(tree_deep_path, 'r'))
        if not isinstance(tree_node_deep, dict):
            raise TypeError(f"[ERR] tree_node_deep is not dict: {type(tree_node_deep)} (path={tree_deep_path})")

        # 识别高 KE 节点（注意 keys 可能为 str）
        visible_depths = set()
        all_high_KE_node = []
        high_KE_node2deep = {}
        high_KE_node2KE = {}

        for deep, nodes in tree_node_deep.items():
            if not isinstance(nodes, (list, tuple)):
                continue
            for p_id in nodes:
                key = str(p_id)
                if key not in pid2node_entropy:
                    # 记录并跳过缺失的键，而不是直接 crash
                    print(f"[WARN] pid {key} missing in pid2node_entropy (pid={seminal_pid}, year={year})")
                    continue
                try:
                    ke_val = float(pid2node_entropy[key])
                except Exception as e:
                    print(f"[WARN] cannot parse ke for {key}: {e}; value={pid2node_entropy.get(key)}")
                    continue
                if ke_val >= THRESHOLD:
                    visible_depths.add(str(deep))
                    all_high_KE_node.append(key)
                    high_KE_node2deep[key] = str(deep)
                    high_KE_node2KE[key] = ke_val

        if '0' in visible_depths:
            visible_depths.discard('0')

        # 预设颜色映射，先把不可视层设为 invisible
        pid2color = {}
        for deep, nodes in tree_node_deep.items():
            for p_id in nodes:
                pid2color[str(p_id)] = depth2color['invisible']
        pid2color[str(seminal_pid)] = depth2color['root']

        # 按可视深度排序并着色
        sorted_visible_depths = sorted(list(visible_depths), key=lambda x: int(x))
        tree_deep2visible_depth = {}
        for i, d in enumerate(sorted_visible_depths):
            tree_deep2visible_depth[d] = str(i+1)
            for p_id in tree_node_deep.get(d, []):
                pid2color[str(p_id)] = depth2color.get(str(i+1), depth2color['invisible'])

        # # 调用简化脉络树函数（保持原有调用）
        # try:
        #     simply_skeleton_tree_2(seminal_pid, year)
        # except Exception as e:
        #     print(f"[WARN] simply_skeleton_tree_2 raised {e} (pid={seminal_pid}, year={year}); continuing")

        # 加载简化后生成的节点详情文件
        node_detail = json.load(open(simplied_path, 'r'))
        if not isinstance(node_detail, dict):
            raise TypeError(f"[ERR] node_detail not dict: {type(node_detail)} path={simplied_path}")

        # 构建图和 MyNode 实例
        id2node = {}
        G = nx.DiGraph()
        for node_key, ndinfo in node_detail.items():
            nid = str(node_key)
            # 确保 ndinfo 是 dict 并含有 label/year
            label = ndinfo.get('label', '')
            nyear = ndinfo.get('year', '')
            G.add_node(nid, graphics={'w': 0, 'h': 0, 'd': 0, 'fill': ''}, L='', JSON='')
            id2node[nid] = MyNode(nid, label, nyear)

        # 添加边和引用关系（对缺失字段做保护）
        for node_key, ndinfo in node_detail.items():
            nid = str(node_key)
            cites = ndinfo.get('cite', []) or []
            becited = ndinfo.get('becited', []) or []
            for nd in cites:
                nds = str(nd)
                if nds not in id2node:
                    print(f"[WARN] cite node {nds} not in id2node (pid={seminal_pid}, year={year})")
                    continue
                id2node[nid].AppendCite(id2node[nds])
                G.add_edge(str(nds), nid)
            for nd in becited:
                nds = str(nd)
                if nds not in id2node:
                    continue
                id2node[nid].AppendBeCited(id2node[nds])

        # 生成 id2size（注意 pid2node_entropy 的键类型）
        try:
            id2size = gen_node_size(pid2node_entropy)
        except Exception as e:
            raise RuntimeError(f"[ERR] gen_node_size failed: {e}")

        # 再次加载以确保 pid2node_entropy 可用（按原逻辑）
        pid2node_entropy = json.load(open(node_entropy_path, 'r'))

        # 将尺寸/颜色填回 G（使用安全的取值）
        for nid in list(G.nodes()):
            # id2size 的键可能为 str 或 int，尽量尝试多种形式
            size_val = None
            for k in (nid, int(nid) if nid.isdigit() else None):
                if k is None:
                    continue
                if k in id2size:
                    size_val = id2size[k]
                    break
            if size_val is None:
                # fallback 默认尺寸
                size_val = 10
                print(f"[WARN] size missing for {nid}, using default {size_val}")

            # 颜色
            color_val = pid2color.get(nid, depth2color['invisible'])

            # safe assignment
            node_attr = G.nodes[nid].setdefault('graphics', {'w': 0, 'h': 0, 'd': 0, 'fill': ''})
            node_attr['w'] = size_val
            node_attr['h'] = size_val
            node_attr['d'] = size_val
            node_attr['fill'] = color_val

        # 为高 KE 节点打标签：注意 high_KE_node2KE 的键均为 str
        # 如果 high_KE_node2KE 为空则跳过 DB 操作
        if len(high_KE_node2KE) == 0:
            high_KE_node2KE = {}

        # DB 连接及标签持久化操作（加保护）
        db = None
        try:
            db = pymysql.connect(
                host='10.10.12.1', user='readonly_ampaper', password='readonly@ampaper1',
                db='am_paper', port=3306, charset='utf8mb4', cursorclass=SSCursor)
        except Exception as e:
            print(f"[WARN] cannot connect to DB: {e}; skipping DB-dependent labeling (pid={seminal_pid}, year={year})")

        high_label_dir = f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}"
        os.makedirs(high_label_dir, exist_ok=True)
        high_label_path = os.path.join(high_label_dir, "high_KE_pid2label.json")

        # 如果 db 可用并且有高 KE 节点，则计算/更新标签映射；否则尽量从已有文件加载
        if db is not None and len(high_KE_node2KE) > 0:
            # prepare mapping high_KE_node -> year
            high_KE_node2year = {}
            with db.cursor() as cursor:
                for pid_key in high_KE_node2KE.keys():
                    try:
                        sql = f"SELECT year FROM `am_paper`.`am_paper` WHERE paper_id = {pid_key}"
                        cursor.execute(sql)
                        res = cursor.fetchone()
                        if res and res[0]:
                            high_KE_node2year[pid_key] = int(res[0])
                        else:
                            high_KE_node2year[pid_key] = 9999
                    except Exception as e:
                        print(f"[WARN] DB query failed for pid {pid_key}: {e}")
                        high_KE_node2year[pid_key] = 9999

            if not os.path.exists(high_label_path):
                sorted_high = sorted(high_KE_node2year.items(), key=lambda item: item[1])
                body = {str(sorted_high[i][0]): str(i+1) for i in range(len(sorted_high))}
                high_KE_pid2label = {'body': body, 'year': str(year)}
                json.dump(high_KE_pid2label, open(high_label_path, 'w'))
            else:
                # 更新现有文件（保守合并）
                try:
                    high_KE_pid2label = json.load(open(high_label_path, 'r'))
                    # ensure proper structure
                    if 'body' not in high_KE_pid2label:
                        high_KE_pid2label = {'body': {}, 'year': str(year)}
                    orig_len = len(high_KE_pid2label['body'])
                    unlabeled = [p for p in high_KE_node2KE.keys() if str(p) not in high_KE_pid2label['body']]
                    if unlabeled:
                        unlabeled_years = {}
                        with db.cursor() as cursor:
                            for pid_key in unlabeled:
                                try:
                                    sql = f"SELECT year FROM `am_paper`.`am_paper` WHERE paper_id = {pid_key}"
                                    cursor.execute(sql)
                                    res = cursor.fetchone()
                                    unlabeled_years[pid_key] = int(res[0]) if res and res[0] else 9999
                                except Exception as e:
                                    unlabeled_years[pid_key] = 9999
                        sorted_unl = sorted(unlabeled_years.items(), key=lambda item: item[1])
                        for i, (k, _) in enumerate(sorted_unl):
                            high_KE_pid2label['body'][str(k)] = str(orig_len + i + 1)
                        high_KE_pid2label['year'] = str(year)
                        json.dump(high_KE_pid2label, open(high_label_path, 'w'))
                except Exception as e:
                    print(f"[WARN] failed to load/update high label file: {e}")

        else:
            # 尝试加载已有的 label 文件（如果存在）
            if os.path.exists(high_label_path):
                try:
                    high_KE_pid2label = json.load(open(high_label_path, 'r'))
                except Exception as e:
                    print(f"[WARN] cannot load existing high label file: {e}")
                    high_KE_pid2label = {'body': {}, 'year': str(year)}
            else:
                high_KE_pid2label = {'body': {}, 'year': str(year)}

        # 给 G 中存在的节点设置 L 属性（字母标签）
        for p_id, labelnum in high_KE_pid2label.get('body', {}).items():
            try:
                if p_id in G.nodes():
                    G.nodes[p_id]['L'] = chr(int(labelnum) + 64)
            except Exception as e:
                print(f"[WARN] cannot set label for {p_id}: {e}")

        # 输出 gml（使用 generate_gml，但加 try 捕捉可能的 None）
        try:
            os.makedirs(os.path.dirname(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}/{year}.gml"), exist_ok=True)
            with open(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}/{year}.gml", 'w') as fp:
                for line in generate_gml(G):
                    fp.write(line + '\n')
        except Exception as e:
            print(f"[ERR] write gml failed: {e}")
            raise

        # 生成高 KE 节点 detail（从 high_KE_pid2label 中读取）
        high_KE_pid2year = {}
        high_KE_pid2title = {}
        high_KE_pid2KE = {}
        # 注意：high_KE_pid2label['body'] 的键是 str
        for pid in high_KE_pid2label.get('body', {}):
            if db is None:
                # 不能访问 DB 时，尽量从 pid2node_entropy / local 信息回退
                high_KE_pid2year[pid] = node_detail.get(pid, {}).get('year', '')
                high_KE_pid2title[pid] = node_detail.get(pid, {}).get('label', '')
                high_KE_pid2KE[pid] = float(pid2node_entropy.get(pid, 0.0))
                continue
            try:
                sql = f"SELECT year, title FROM `am_paper`.`am_paper` WHERE paper_id = {pid}"
                with db.cursor() as cursor:
                    cursor.execute(sql)
                    result = cursor.fetchone()
                if result:
                    high_KE_pid2year[pid] = int(result[0]) if result[0] else ''
                    high_KE_pid2title[pid] = result[1] if len(result) > 1 else ''
                else:
                    high_KE_pid2year[pid] = node_detail.get(pid, {}).get('year', '')
                    high_KE_pid2title[pid] = node_detail.get(pid, {}).get('label', '')
                high_KE_pid2KE[pid] = float(pid2node_entropy.get(pid, 0.0))
            except Exception as e:
                print(f"[WARN] failed to query title/year for {pid}: {e}")
                high_KE_pid2year[pid] = node_detail.get(pid, {}).get('year', '')
                high_KE_pid2title[pid] = node_detail.get(pid, {}).get('label', '')
                high_KE_pid2KE[pid] = float(pid2node_entropy.get(pid, 0.0))

        if db is not None:
            try:
                db.close()
            except Exception:
                pass

        # 构造高 KE 表格并写出（和原来一致）
        sorted_high = sorted(high_KE_pid2label.get('body', {}).items(), key=lambda item: int(item[1]))
        high_KE_node_detail = {'Label': [], 'Title': [], 'Knowledge Entropy': [], 'Published Year': []}
        for pid, _ in sorted_high:
            lab = chr(64 + int(high_KE_pid2label['body'].get(pid, '1')))
            high_KE_node_detail['Label'].append(lab)
            high_KE_node_detail['Title'].append(high_KE_pid2title.get(pid, ''))
            high_KE_node_detail['Knowledge Entropy'].append(high_KE_pid2KE.get(pid, 0.0))
            high_KE_node_detail['Published Year'].append(str(high_KE_pid2year.get(pid, '')))

        df = pd.DataFrame(high_KE_node_detail)
        pd.set_option('display.max_colwidth', 500)
        pd.set_option('display.width', 500)
        os.makedirs(f"../output/final_topic_portrait/{seminal_pid}", exist_ok=True)
        high_KE_node_detail_latex = df.to_latex(index=False, header=True, float_format="%.4f",
                                               column_format='p{1cm}p{7.5cm}p{3cm}p{2cm}')
        with open(f'../output/final_topic_portrait/{seminal_pid}/{year}.txt', 'w') as fp:
            fp.write(high_KE_node_detail_latex)

        # 导出图片表格（保留原逻辑）
        col = ['Label', 'Title', 'Knowledge Entropy', 'Published Year']
        vals = []
        for i in range(len(high_KE_node_detail['Label'])):
            vals.append([
                high_KE_node_detail['Label'][i],
                high_KE_node_detail['Title'][i],
                float('%.4f' % high_KE_node_detail['Knowledge Entropy'][i]),
                high_KE_node_detail['Published Year'][i]
            ])

        os.makedirs(f"../temp_files/high_KE_node_detail_png/{seminal_pid}", exist_ok=True)
        plt.figure(figsize=(20, 20), dpi=100)
        if len(vals) == 0:
            plt.savefig(f"../temp_files/high_KE_node_detail_png/{seminal_pid}/{year}.jpg")
            plt.close()
        else:
            tab = plt.table(cellText=vals, colLabels=col, loc='center', cellLoc='center', rowLoc='center')
            tab.auto_set_font_size(False)
            tab.set_fontsize(10)
            tab.scale(1.3, 1.3)
            plt.axis('off')
            plt.savefig(f"../temp_files/high_KE_node_detail_png/{seminal_pid}/{year}.jpg")
            plt.close()

        print(f"[DEBUG] finish gen_visible_depth... pid={seminal_pid}, year={year}")

    except Exception as e:
        # 捕获所有异常并打印上下文，便于定位
        print(f"[ERROR] Exception in gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail (pid={seminal_pid}, year={year}): {e}")
        raise

# 对每个领域生成逐年可视深度的演进图
def gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail_bk(seminal_pid, year):
    # 在简化的脉络树中标注出最大可视深度下的点熵超过10的节点，用深红色
    # 可视化思路：先筛选出所有不包含高知识熵节点的层，把这些节点上invisible这个颜色，然后将剩下的层按深度排序，分别上123456对应的颜色
    #配置部分
    depth2color = {
        'root': '#ff0000',
        'invisible': '#959595', # 只要不存在高知识熵节点的层都是invisible，用于高亮高知识熵节点
        '1': '#ffe306',
        '2': '#ff723a',
        '3': '#f81463',
        '4': '#9d126f',
        '5': '#6c48aa',
        '6': '#0a0da7',
        '7': '#0000ff'
    }
    depth2color_half_trans = { #  同一颜色降低透明度，用于标识相应高知识熵节点使得某一层可视的所有节点
        '1': "#fff396",
        '2': '#ffb89c',
        '3': '#fb89b1',
        '4': '#ce88b7',
        '5': '#b5a3d4',
        '6': '#5355c1',
    }
    pid2simply_ratio = { # 用于对特定pid的脉络树进行微调，调节剪枝的比率
        '62270017': 0.3, #
    #     477114443,
        '142612150': 0.05,
        '214435441': 0.05,
        '255866650': 0.05, #
    #     274480977,
        '1842472': 0.05, #
        '356008829': 0.05,
        '71305135': 0.1, #
        '379075697': 0.05,
        '252195446': 0.07, # 
        '174864895': 0.1, #
        '175773368': 0.15, #
        '329258602': 0.05,
        '457139010': 0.3,
        '1587314': 0.35,
        '81075167': 0.14,
        '38572377': 0.00001,
        '252470610': 0.001,
        '166247013': 0.001,
        '445475439': 0.01,
        '166725067': 0.001,
        '457139010': 0.001
    }
    #读取数据
    simply_ratio = pid2simply_ratio.get(seminal_pid, 0.2)
    
    pid2node_entropy = json.load(open('../temp_files/node_entropy_by_year/'+str(seminal_pid)+'/{}'.format(year), 'r'))

    tree_node_deep = json.load(open('../temp_files/tree_deep_by_year/'+str(seminal_pid)+'/{}'.format(year), 'r'))
    
    #找出高 KE 节点 & 可见层
    visible_depths = set()
    all_high_KE_node = []
    high_KE_node2deep = {}
    high_KE_node2KE = {}
    for deep in tree_node_deep:
        for p_id in tree_node_deep[deep]:
            if float(pid2node_entropy[str(p_id)]) >= THRESHOLD:
                visible_depths.add(deep)
                all_high_KE_node.append(p_id)
                high_KE_node2deep[p_id] = deep
                high_KE_node2KE[str(p_id)] = float(pid2node_entropy[str(p_id)])
    if '0' in visible_depths: # 删除seminal paper所在的层
        visible_depths.remove('0')

    #给节点上色
    pid2color = {}
    for deep in tree_node_deep: # 设置不可视层的颜色
        if deep not in visible_depths:
            for p_id in tree_node_deep[deep]:
                pid2color[str(p_id)] = depth2color['invisible']
    pid2color[str(seminal_pid)] = depth2color['root']  # seminal paper上色
    
    sorted_visible_depths = sorted(list(visible_depths))
    tree_deep2visible_depth = {}
    for i in range(len(sorted_visible_depths)):
        tree_deep2visible_depth[sorted_visible_depths[i]] = str(i+1)
        for p_id in tree_node_deep[sorted_visible_depths[i]]:
            pid2color[str(p_id)] = depth2color[str(i+1)]       
#     for p_id in all_high_KE_node:
#         if str(p_id) == str(seminal_pid):
#             continue
#         pid2color[str(p_id)] = depth2color[str(tree_deep2visible_depth[str(high_KE_node2deep[p_id])])]
    
    #生成简化的脉络树
    # simply_skeleton_tree(seminal_pid, year, simply_ratio) # 通过第上一个函数写文件，下一个函数读文件进行传递数据也是可行的
    simply_skeleton_tree_2(seminal_pid, year, THRESHOLD)

    yr = year
    node_detail = json.load(open(f"../temp_files/simplied_skeleton_tree_by_year/{seminal_pid}/{year}", "r"))
    id2node = {}
    NodeList = []
    G = nx.DiGraph()
    for node in node_detail:
        ID = node
        G.add_node(str(ID),graphics = {'w':0,'h':0,'d':0,'fill':''}, L = '', JSON='')
        node = str(node)
        label = node_detail[node]['label']
        year = node_detail[node]['year']
        NewNode = MyNode(ID,label,year)
        id2node[node] = NewNode
    for node in id2node:
        for nd in node_detail[node]['cite']:
            id2node[node].AppendCite(id2node[str(nd)])
            G.add_edge(str(nd), str(node)) # 脉络树的箭头方向为被引文献指向引用文献，以表示启发功能，与引文网络的方向相反
        for nd in node_detail[node]['becited']:
            id2node[node].AppendBeCited(id2node[str(nd)])
        NodeList.append(id2node[node])
    

    id2size = gen_node_size(pid2node_entropy)
    pid2node_entropy = json.load(open('../temp_files/node_entropy_by_year/'+str(seminal_pid)+'/{}'.format(yr), 'r'))
    
    for id in id2node:
        G.node[str(id)]['graphics']['w'] = id2size[id]
        G.node[str(id)]['graphics']['h'] = id2size[id]
        G.node[str(id)]['graphics']['d'] = id2size[id]
        G.node[str(id)]['graphics']['fill'] = pid2color[id]
    # 为高知识熵节点打标签
    if seminal_pid in high_KE_node2KE:
        ttt = high_KE_node2KE.pop(str(seminal_pid))
    # 读文件初始化已有标签
    db = pymysql.connect(
            host = '10.10.12.1',
            user = 'readonly_ampaper',
            password = 'readonly@ampaper1',
            db = 'am_paper',
            port = 3306,
            charset = 'utf8mb4',
            cursorclass=SSCursor
    )
    if not os.path.exists(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}/high_KE_pid2label.json"):
        high_KE_node2year = {}
        for pid in high_KE_node2KE:
            sql = f"SELECT year FROM `am_paper`.`am_paper` WHERE paper_id = {pid}"
            # cursor = db.cursor()
            with db.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchone()
                high_KE_node2year[pid] = int(result[0])
            
        sorted_high_KE_node2year = sorted(high_KE_node2year.items(), key = lambda item:item[1])
        high_KE_pid2label_body = {str(sorted_high_KE_node2year[i][0]):str(i+1) for i in range(len(sorted_high_KE_node2year))}
        high_KE_pid2label = {}
        high_KE_pid2label['body'] = high_KE_pid2label_body
        high_KE_pid2label['year'] = yr
        json.dump(high_KE_pid2label, open(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}/high_KE_pid2label.json", 'w'))
    else:
        high_KE_pid2label = json.load(open(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}/high_KE_pid2label.json", 'r'))
        if int(high_KE_pid2label['year']) > int(yr):
            high_KE_node2year = {}
            for pid in high_KE_node2KE:
                sql = f"SELECT year FROM `am_paper`.`am_paper` WHERE paper_id = {pid}"
                # cursor = db.cursor()
                with db.cursor() as cursor:
                    cursor.execute(sql)
                    result = cursor.fetchone()
                    high_KE_node2year[pid] = int(result[0])
            sorted_high_KE_node2year = sorted(high_KE_node2year.items(), key = lambda item:item[1])
            high_KE_pid2label_body = {str(sorted_high_KE_node2year[i][0]):str(i+1) for i in range(len(sorted_high_KE_node2year))}
            high_KE_pid2label['body'] = high_KE_pid2label_body
            high_KE_pid2label['year'] = yr
            json.dump(high_KE_pid2label, open(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}/high_KE_pid2label.json", 'w'))
        else:
            high_KE_pid2label = json.load(open(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}/high_KE_pid2label.json", 'r'))
            orig_len = len(high_KE_pid2label['body'])
            unlabeled_pids = []
            for pid in high_KE_node2KE:
                if str(pid) not in high_KE_pid2label['body']:
                    unlabeled_pids.append(str(pid))
            unlabeled_pid2year = {}
            for pid in unlabeled_pids:
                sql = f"SELECT year FROM `am_paper`.`am_paper` WHERE paper_id = {pid}"
                # cursor = db.cursor()
                with db.cursor() as cursor:
                    cursor.execute(sql)
                    result = cursor.fetchone()
                    unlabeled_pid2year[pid] = int(result[0])
            sorted_unlabeled_pid2year = sorted(unlabeled_pid2year.items(), key = lambda item:item[1])
            for i in range(len(sorted_unlabeled_pid2year)):
                high_KE_pid2label['body'][str(sorted_unlabeled_pid2year[i][0])] = str(orig_len + i + 1)
            high_KE_pid2label['year'] = yr
            json.dump(high_KE_pid2label, open(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}/high_KE_pid2label.json", 'w'))

    for p_id in high_KE_pid2label['body']: # 会有极少数主题前期的高知识节点在后期知识熵降为极低而被剪枝算法去掉，导致G里面不包含这个节点，从而导致这里报错, if str(p_id) in G.node为新加
        if str(p_id) in G.node:
            G.node[str(p_id)]['L'] = chr(int(high_KE_pid2label['body'][p_id])+64)  # 将数字label转化为大写字母
    
    if not os.path.exists(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}"):
            os.makedirs(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}")
    
    with open(f"../temp_files/attributed_idea_tree_by_year/{seminal_pid}/{yr}.gml", 'w') as fp:
        for line in generate_gml(G):
            line+='\n'
            fp.write(line)
    
    # 生成主题内部的高知识熵节点的detail
    high_KE_pid2year = {}
    high_KE_pid2title = {}
    high_KE_pid2KE = {}
    for pid in high_KE_pid2label['body']:
        sql = f"SELECT year, title FROM `am_paper`.`am_paper` WHERE paper_id = {pid}"
        # cursor = db.cursor()
        with db.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchone()
            high_KE_pid2year[pid] = int(result[0])
            high_KE_pid2title[pid] = result[1]
            high_KE_pid2KE[pid] = float(pid2node_entropy[pid])
    db.close()
    
    # print(pid2node_entropy)
    sorted_high_KE_pid2label = sorted(high_KE_pid2label['body'].items(), key=lambda item:int(item[1]))
    high_KE_node_detail = {'Label':[], 'Title':[], 'Knowledge Entropy':[], 'Published Year':[]}
    for pid, ke in sorted_high_KE_pid2label:
        high_KE_node_detail['Label'].append(chr(64+int(high_KE_pid2label['body'][pid]))) # 将数字label转化为大写字母
        high_KE_node_detail['Title'].append(high_KE_pid2title[pid])
        high_KE_node_detail['Knowledge Entropy'].append(high_KE_pid2KE[pid])
        high_KE_node_detail['Published Year'].append(str(high_KE_pid2year[pid]))
    df = pd.DataFrame(high_KE_node_detail)
    pd.set_option('display.max_colwidth',500)
    pd.set_option('display.width',500)
    high_KE_node_detail_latex = df.to_latex(index=False, header=True, float_format="%.4f", column_format='p{1cm}p{7.5cm}p{3cm}p{2cm}')
    if not os.path.exists(f"../output/final_topic_portrait/{seminal_pid}"):
        os.makedirs(f"../output/final_topic_portrait/{seminal_pid}")
    with open(f'../output/final_topic_portrait/{seminal_pid}/{yr}.txt', 'w') as fp:
        fp.write(high_KE_node_detail_latex)
    # 将表格转为图片
    col = ['Label', 'Title', 'Knowledge Entropy', 'Published Year']
    vals = []
    for i in range(len(high_KE_node_detail['Label'])):
        r = [high_KE_node_detail['Label'][i], high_KE_node_detail['Title'][i], float('%.4f' % high_KE_node_detail['Knowledge Entropy'][i]), high_KE_node_detail['Published Year'][i]]
        
        vals.append(r)

    plt.figure(figsize = (20, 20), dpi = 100)
    if len(vals) == 0:
        if not os.path.exists(f"../temp_files/high_KE_node_detail_png/{seminal_pid}"):
            os.makedirs(f"../temp_files/high_KE_node_detail_png/{seminal_pid}")
        plt.savefig(f"../temp_files/high_KE_node_detail_png/{seminal_pid}/{yr}.jpg")
        plt.close()
    else:
        tab = plt.table(cellText=vals, 
                        colLabels=col, 
                        loc='center', 
                        cellLoc='center',
                        rowLoc='center')
        tab.auto_set_font_size(False)
        tab.set_fontsize(10)
        tab.scale(1.3,1.3)
        plt.axis('off')
        if not os.path.exists(f"../temp_files/high_KE_node_detail_png/{seminal_pid}"):
            os.makedirs(f"../temp_files/high_KE_node_detail_png/{seminal_pid}")
        plt.savefig(f"../temp_files/high_KE_node_detail_png/{seminal_pid}/{yr}.jpg")
        plt.close()

        
if __name__=="__main__":
    pids = json.load(open('cccf_pids_1.json', 'r'))

    candidates_pids = os.listdir('../temp_files/node_entropy_by_year')
    all_pids = []
    year_now = datetime.datetime.now().year
    for cpid in candidates_pids:
        years = os.listdir(f'../temp_files/node_entropy_by_year/{cpid}')
        if str(year_now) in years:
            all_pids.append(cpid)

    pids = list(set(all_pids).intersection(set(pids)))
    pids = json.load(open('x_ray_geo_finished_pids.json', 'r'))
    pids = ['267126213', '457139010', '12014159', '162137477', '180782032', '372732296', '223164844', '1587314', '194520463', '351922417', '364638540', '263480625',
            '186736262', '3963681', '18869729', '144236702', '403862122', '404272823', '212067742', '239501141', '464101270'
     ]
    pids = ['403862122', '144236702']
    pids = ['18869729']
    pids = ['81075167']
    pids = [
            # '38572377', 
            # '252470610', 
            '166247013', 
            # '445475439', 
            # '166725067', 
            # '457139010'
            ]
    pids = ['372732296']
    pids = [
             # '262101246',
    #          '290257163',
    #          '3950247',
    #          '434239941',
             # '364638540',
             # '186736262',
             # '267126213',
             # '12014159',
             # '162137477',
             # '180782032',
             # '263480625',
             # '116579552',
             # '372732296',
             # '144236702',
             # '403862122',
             # '22340939',
             # '239501141',
             # '404272823',
             # '464101270',
             # '223164844',
             # '142118272',
             # '194520463',
             # '351922417',
             '438420345'
            ]
    for pid in tqdm(pids):
        files_list = os.listdir('../temp_files/source_gml_by_year/'+str(pid))
        years_list = sorted([int(file.split('.')[0]) for file in files_list])
        for year in years_list:
            print(year)
            gen_visible_depth_marked_skeleton_tree_gml_and_high_KE_node_detail(pid, year)

