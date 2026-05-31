#!/usr/bin/env python
# coding: utf-8

# In[45]:


import os
import csv
import json
import datetime
# import MySQLdb
# import MySQLdb.cursors
# import pymysql
# from pymysql.cursors import SSCursor
from tqdm import tqdm

from get_delta_D_for_specific_topic import get_delta_D_for_specific_topic
from elasticsearch import Elasticsearch


hosts = [
    "http://10.10.10.0:9200",
    "http://elastic:ai8WoTKcmzUC9AW$@10.10.12.1:9200",  # dev
    "http://readonly:readonly@10.10.12.1:9201"          # web
]
client = Elasticsearch(hosts[2])


def find_paper_info(paper_id):
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
        "_source": ["title", "cited_by_count"]
    }

    paper_res = client.search(index="acemap.works", body=query)
    print("paper information done!")

    source = paper_res['hits']['hits'][0]['_source']
    paper_title = source.get('title', '')
    paper_citation = source.get('cited_by_count', '')
    return (paper_title, paper_citation)


# In[59]:

def main(tpids):
    # 使用scientific X-ray度量给定主题列表的发展潜力，并给出排名后的csv文件
    pid2topic_delta_D = {}
    for p_id in tqdm(tpids):
        topic_delta_D, detail= get_delta_D_for_specific_topic(p_id)
        try:
            topic_delta_D, detail= get_delta_D_for_specific_topic(p_id)
        except:
            continue
        pid2topic_delta_D[p_id] = topic_delta_D
    sorted_pid2topic_delta_D = sorted(pid2topic_delta_D.items(), key = lambda item:item[1], reverse=True)
    
    dt = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
    with open(f'topic_potential_ranking_{dt}.csv', 'w', encoding='utf-8') as fp:
        csv_writer = csv.writer(fp)
        csv_writer.writerow(('Leading paper','Delta D', 'Citation'))
        for pid, delta_D in tqdm(sorted_pid2topic_delta_D):
            pid_db = "https://openalex.org/W" + pid
            paper_title, paper_citation = find_paper_info(pid_db)
            print(pid_db, paper_title, paper_citation)
            csv_writer.writerow((paper_title, delta_D, str(paper_citation)))


# In[58]:


if __name__ == "__main__":
    # tpids = json.load(open('covid_high_citation_pids.json', 'r'))
    # tpids = ['470780090',
    #          '242975836',
    #          '200599618',
    #          '219704643',
    #          '76205213',
    #          '477291171',
    #          '496604792'
    #         ]
    # tpids = ['314384100']
    # tpids = ['107234871', '151483314', '369508772']
    # tpids = ['2896457183', '4294558607']
    tpids = ['2044875653']
    main(tpids)

