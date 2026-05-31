from elasticsearch import Elasticsearch

# 配置Elasticsearch连接
es_hosts = [
    "http://10.10.10.0:9200",
    "http://elastic:ai8WoTKcmzUC9AW$@10.10.12.1:9200",
    "http://readonly:readonly@10.10.12.1:9201"
]
es_client = Elasticsearch(es_hosts[2])


# 从ES获取论文信息（标题和摘要）- 修改ID格式
def get_paper_info_from_es(pid):
    """
    Get title and abstract from Elasticsearch by paper ID
    Convert numeric ID to OpenAlex format: https://openalex.org/works/W{pid}
    """
    try:
        # 将数字ID转换为OpenAlex格式
        openalex_id = f"https://openalex.org/W{pid}"
        print(f"Searching ES for OpenAlex ID: {openalex_id}")
        
        query = {
            "query": {
                "term": {
                    "_id": openalex_id
                }
            },
            "_source": ["title", "abstract", "publication_year"]
        }
        
        response = es_client.search(index="acemap.works", body=query)
        hits = response['hits']['hits']
        
        if hits:
            source = hits[0]['_source']
            title = source.get('title', 'Title not found')
            abstract = source.get('abstract', 'Abstract not found')
            pub_year = source.get('publication_year', 'Year not found')
            return title, abstract, pub_year
        else:
            print(f"No results found for ID: {openalex_id}")
            # 尝试使用原始ID作为备选
            query_fallback = {
                "query": {
                    "term": {
                        "_id": str(pid)
                    }
                },
                "_source": ["title", "abstract"]
            }
            
            response_fallback = es_client.search(index="acemap.works", body=query_fallback)
            hits_fallback = response_fallback['hits']['hits']
            
            if hits_fallback:
                source = hits_fallback[0]['_source']
                title = source.get('title', 'Title not found')
                abstract = source.get('abstract', 'Abstract not found')
                pub_year = source.get('publication_year', 'Year not found')
                return title, abstract, pub_year
            else:
                return f"Paper_{pid}", "Abstract not available"
            
    except Exception as e:
        print(f"Error querying ES for PID {pid}: {e}")
        return f"Paper_{pid}", "Abstract not available"


pids = ['1978185779', '2047040143', '2051518078', '2089850899', '2138058376', '2943740841', '3088610511']
for pid in pids:
    res = get_paper_info_from_es(pid)
    print(res[2], " | " , res[0])