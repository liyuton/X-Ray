# 根据title查id
import requests
from elasticsearch import Elasticsearch
from readgml import readgml
import os
import json
import re

# 配置Elasticsearch连接
es_hosts = [
    "http://10.10.10.0:9200",
    "http://elastic:ai8WoTKcmzUC9AW$@10.10.12.1:9200",
    "http://readonly:readonly@10.10.12.1:9201"
]
es_client = Elasticsearch(es_hosts[2])

def get_paper_id_from_es_by_title(title):
    """
    Get paper ID from Elasticsearch by title
    Returns a list of matching paper IDs
    """
    try:
        print(f"Searching ES for title: {title}")
        
        # 使用match查询进行模糊标题匹配
        query = {
            "query": {
                "match": {
                    "title": title
                }
            },
            "_source": ["title", "abstract", "_id", "publication_year","cited_by_count"],
            "size": 5  # 限制返回结果数量
        }
        
        response = es_client.search(index="acemap.works", body=query)
        hits = response['hits']['hits']
        
        results = []
        if hits:
            print(f"Found {len(hits)} results")
            for hit in hits:
                source = hit['_source']
                paper_id = hit['_id']
                title_found = source.get('title', 'Title not found')
                abstract = source.get('abstract', 'Abstract not found')
                year = source.get('publication_year', 'publication_year not found')
                citation = source.get('cited_by_count', 'cited_by_count not found')
                
                # 提取数字ID（如果ID是OpenAlex格式）
                numeric_id = None
                if paper_id.startswith('https://openalex.org/W'):
                    numeric_id = paper_id.replace('https://openalex.org/W', '')
                else:
                    numeric_id = paper_id
                
                results.append({
                    'id': paper_id,
                    'numeric_id': numeric_id,
                    'title': title_found,
                    'abstract': abstract,
                    'publication_year': year,
                    'cited_by_count': citation 
                })
            
            return results
        else:
            print(f"No results found for title: {title}")
            return []
            
    except Exception as e:
        print(f"Error querying ES for title '{title}': {e}")
        return []

def get_exact_paper_id_from_es_by_title(title):
    """
    Get exact paper ID from Elasticsearch by title using term query
    For exact title matching
    """
    try:
        print(f"Searching ES for exact title: {title}")
        
        # 使用term查询进行精确标题匹配
        query = {
            "query": {
                "term": {
                    "title.keyword": title
                }
            },
            "_source": ["title", "abstract", "_id", "publication_year","cited_by_count"],
            "size": 5
        }
        
        response = es_client.search(index="acemap.works", body=query)
        hits = response['hits']['hits']
        
        results = []
        if hits:
            print(f"Found {len(hits)} exact matches")
            for hit in hits:
                source = hit['_source']
                paper_id = hit['_id']
                # print(hit)
                title_found = source.get('title', 'Title not found')
                abstract = source.get('abstract', 'Abstract not found')
                publication_year = source.get('publication_year', 'publication_year not found')
                cited_by_count = source.get('cited_by_count', 'cited_by_count not found')
                
                # 提取数字ID
                numeric_id = None
                if paper_id.startswith('https://openalex.org/W'):
                    numeric_id = paper_id.replace('https://openalex.org/W', '')
                else:
                    numeric_id = paper_id
                
                results.append({
                    'id': paper_id,
                    'numeric_id': numeric_id,
                    'title': title_found,
                    'abstract': abstract,
                    'publication_year': publication_year,
                    'cited_by_count': cited_by_count
                })
            
            return results
        else:
            print(f"No exact matches found for title: {title}")
            return []
            
    except Exception as e:
        print(f"Error querying ES for exact title '{title}': {e}")
        return []

# 测试函数
if __name__ == "__main__":

    test_titles = ["Highly accurate protein structure prediction with AlphaFold"]
    
    
    for test_title in test_titles:
        print('-'*50,test_title,'-'*50)
        # 标题模糊匹配
        results = get_paper_id_from_es_by_title(test_title)
        print(f"\n模糊匹配结果 ({test_title}):")
        for i, result in enumerate(results):
            print(f"{i+1}. ID: {result['numeric_id']}, Title: {result['title']}, Publication Year:{result['publication_year']}, Citation:{result['cited_by_count']}")
        
        # 标题精确匹配
        if results:
            exact_title = results[0]['title']
            exact_results = get_exact_paper_id_from_es_by_title(exact_title)
            print(f"\n精确匹配结果 ({exact_title}):")
            for i, result in enumerate(exact_results):
                print(f"{i+1}. ID: {result['numeric_id']}, Title: {result['title']},\n Abstract: {result['abstract']}\n Publication Year:{result['publication_year']}\n Citation:{result['cited_by_count']}")
        
#####匹配结果#######
#【title】 A Language Modeling Approach to Information Retrieval 【ID】2093390569
#【title】The Effective Variance Weighting for Least Squares Calculations Applied to the Mass Balance Receptor Model 【ID】2044875653
    # pids = ['1963760477',
    #     '2164869345',
    #     '2143107875',
    #     '4229565668',
    #     '45806619',
    #     '2070360032'
    #     ]