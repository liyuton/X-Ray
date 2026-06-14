###使用每年的脉络树切片和ES库生成总结###

"""
prompt设计
1. 任务说明
    a.介绍脉络树和知识熵的含义，说明更关注高知识熵的节点以及知识流动路径和文献间的启发关系
    b.让模型先从脉络树结构的演化上得到一些关键节点，在此基础上再去文章摘要中分析启发关系和路径
    c.限制生成报告的格式:如在文本最后按照reference list的格式列出生成文本的所有参考文献信息
2. 节点信息
各年度涉及到的所有节点的信息，包括:id title abstract publication_year等（忽略size和color信息，不用）
3. 脉络树结构信息
每年度脉络树上的引用关系列表和本年度所有节点的知识熵大小
"""
import requests
from elasticsearch import Elasticsearch
from readgml import readgml
import os
import json
import math

# 配置Elasticsearch连接
es_hosts = [
    "http://10.10.10.0:9200",
    "http://elastic:ai8WoTKcmzUC9AW$@10.10.12.1:9200",
    "http://readonly:readonly@10.10.12.1:9201"
]
es_client = Elasticsearch(es_hosts[2])

VD_PATH = "../temp_files/year2visible_depth"
DPI_PATH = "../temp_files/year2delta_d"

# 调用API补全对话
def completion(user_prompt):
    dialogue = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_prompt},
    ]
    sjtu_temp = 'sk-hBzYhO9CB1r1bZJf7407DcF261Af46A8Ad5eF71fB4C102F2'

    response = requests.post(
        url='https://openai.acemap.cn/v1/chat/completions',
        headers={'Authorization': f'Bearer {sjtu_temp}'},
        json={'model': 'gpt-5.4-mini', 'messages': dialogue},
        verify=False,
        timeout=600
    )
    return response.json()['choices'][0]['message']['content']

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

# 处理GML数据结构
def process_gml_data(nodes, edges):
    """
    处理GML数据，修复数据结构问题
    """
    processed_nodes = []
    processed_edges = []
    
    # 处理节点列表
    for item in nodes:
        if isinstance(item, dict):
            # 检查是否是节点字典
            if 'id' in item:
                # 这是节点字典
                processed_nodes.append(item)
            elif 'node' in item and item['node'] == '[':
                # 这是节点开始标记，跳过
                continue
        elif isinstance(item, list):
            # 如果是列表，递归处理
            sub_nodes, sub_edges = process_gml_data(item, [])
            processed_nodes.extend(sub_nodes)
    
    # 处理边列表
    for item in edges:
        if isinstance(item, dict):
            # 检查是否是边字典
            if 'source' in item and 'target' in item:
                # 这是边字典
                processed_edges.append(item)
            elif 'edge' in item and item['edge'] == '[':
                # 这是边开始标记，跳过
                continue
        elif isinstance(item, list):
            # 如果是列表，递归处理
            sub_nodes, sub_edges = process_gml_data([], item)
            processed_edges.extend(sub_edges)
    
    return processed_nodes, processed_edges

# 安全的属性提取函数
def safe_extract_color(node):
    """安全地从节点中提取颜色，修复缺少#前缀的问题"""
    if not isinstance(node, dict):
        return "#959595"
    
    # 尝试直接获取颜色
    color = node.get("fill", node.get("color", "959595"))
    
    # 确保颜色有#前缀
    if color and not color.startswith("#"):
        color = "#" + color
    
    # 检查颜色是否有效，否则使用默认值
    if len(color) != 7 or not all(c in "0123456789abcdef" for c in color[1:].lower()):
        color = "#959595"
    
    return color

def safe_extract_size(node):
    """安全地从节点中提取大小"""
    if not isinstance(node, dict):
        return 10.0
    
    # 尝试直接获取大小
    size = node.get("w", node.get("width", 10.0))
    
    try:
        return float(size)
    except (ValueError, TypeError):
        return 10.0

def safe_extract_label(node):
    """安全地从节点中提取标签"""
    if not isinstance(node, dict):
        return "Unknown_Node"
    
    label = node.get("label", "")
    if not label:
        node_id = node.get("id", "Unknown")
        return f"Node_{node_id}"
    return label

def safe_extract_id(node):
    """安全地从节点中提取ID"""
    if not isinstance(node, dict):
        return "Unknown"
    
    return str(node.get("id", "Unknown"))

# 读取多个年份的GML文件
def read_multiple_year_gmls(base_path, pid, years):
    """
    Read GML files for multiple years with improved parsing
    """
    year_data = {}
    for year in years:
        gml_path = os.path.join(base_path, str(pid), f"{year}.gml")
        if os.path.exists(gml_path):
            try:
                print(f"Reading GML file: {gml_path}")
                nodes, edges = readgml.read_gml(gml_path)
                
                # 调试信息：打印数据结构
                print(f"Year {year}: node type: {type(nodes)}, edge type: {type(edges)}")
                if nodes and len(nodes) > 0:
                    print(f"First node: {nodes[0]}")
                if edges and len(edges) > 0:
                    print(f"First edge: {edges[0]}")
                
                # 处理GML数据，修复数据结构问题
                processed_nodes, processed_edges = process_gml_data(nodes, edges)
                
                print(f"Processed nodes: {len(processed_nodes)}, processed edges: {len(processed_edges)}")
                
                # 创建节点颜色和大小映射
                node_colors = {}
                node_sizes = {}
                for node in processed_nodes:
                    node_id = safe_extract_id(node)
                    node_colors[node_id] = safe_extract_color(node)
                    node_sizes[node_id] = safe_extract_size(node)
                
                year_data[year] = {
                    "nodes": processed_nodes,
                    "edges": processed_edges,
                    "node_colors": node_colors,
                    "node_sizes": node_sizes
                }
                print(f"Successfully processed {year} data")
                
            except Exception as e:
                print(f"Failed to read {year} GML file: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"File does not exist: {gml_path}")
    
    return year_data


def read_multiple_year_ke(ke_path, pid, years):
    ke_data = {}
    for year in years:
        ke_file_path = os.path.join(ke_path, str(pid), f"{year}")
        if os.path.exists(ke_file_path):
            try:
                with open(ke_file_path, 'r', encoding='utf-8') as f:
                    year_ke_data = json.load(f)
                    ke_data[year] = year_ke_data
                    print(f"Successfully read KE data for year {year}")
            except Exception as e:
                print(f"Failed to read KE file for year {year}: {e}")
        else:
            print(f"KE file does not exist for year {year}: {ke_file_path}")
    
    return ke_data


### xray: add VD/DPI evidence for semantic transition reasoning ###
def resolve_year_metric_path(metric_dir, pid):
    json_path = os.path.join(metric_dir, f"{pid}.json")
    raw_path = os.path.join(metric_dir, str(pid))
    if os.path.exists(json_path):
        return json_path
    if os.path.exists(raw_path):
        return raw_path
    raise FileNotFoundError(f"Metric file does not exist: {json_path} or {raw_path}")


def read_year_metric(metric_dir, pid, years, metric_name):
    try:
        metric_path = resolve_year_metric_path(metric_dir, pid)
    except FileNotFoundError as e:
        print(f"Warning: {metric_name} file missing for pid {pid}: {e}")
        return {}

    with open(metric_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    year_set = set(years)
    year_metric = {}
    for year, value in raw_data.items():
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            continue
        if year_int in year_set:
            year_metric[year_int] = value
    return year_metric


def read_vd_dpi_data(pid, years):
    year2vd = read_year_metric(VD_PATH, pid, years, "VD")
    year2dpi = read_year_metric(DPI_PATH, pid, years, "DPI")
    return year2vd, year2dpi


def classify_dpi(value):
    try:
        dpi = float(value)
    except (TypeError, ValueError):
        return "unavailable"
    if dpi == -99:
        return "unavailable"
    if dpi >= 1:
        return "has predictive potential for a later energy-level transition"
    if dpi >= 0:
        return "has weak or insufficient predictive potential"
    return "has negative predictive potential"


def build_energy_evidence_str(pid, years, year2vd, year2dpi, paper_title=None):
    rows = []
    previous_vd = None
    for year in years:
        vd = year2vd.get(year, "missing")
        dpi = year2dpi.get(year, "missing")
        if previous_vd is None or vd == "missing" or previous_vd == "missing":
            vd_change = "baseline"
            major_vd_jump = False
        else:
            try:
                vd_change = int(vd) - int(previous_vd)
                major_vd_jump = vd_change >= 2
            except (TypeError, ValueError):
                vd_change = "unknown"
                major_vd_jump = False

        rows.append({
            "year": year,
            "VD": vd,
            "VD_change_from_previous_observed_year": vd_change,
            "major_VD_jump_two_or_more_layers": major_vd_jump,
            "DPI": dpi,
            "DPI_interpretation": classify_dpi(dpi),
        })
        previous_vd = vd

    display_name = paper_title or f"Paper {pid}"
    energy_info_str = f"\n\n## 6. VD and DPI Annual Evidence for {display_name} (For transition reasoning; do not quote mechanically)\n\n"
    energy_info_str += (
        "VD is the main scale of the current academic energy level: when VD rises, "
        "a new effective layer has been lit by high-KE nodes. A VD jump of two or "
        "more layers in one observed year marks a major transition year that must "
        "receive focused explanation in the phase-based summary. DPI is the "
        "predictive potential for the next transition: DPI >= 1 suggests that the "
        "tree has accumulated enough structural potential for a later transition, "
        "but the actual VD rise can lag because publications, citations, diffusion, "
        "and field absorption take time. DPI < 1 suggests that the observed "
        "structure does not yet provide enough forward potential, or that earlier "
        "high-KE nodes are losing effective driving power because of aging, layer "
        "distance, or a shift of the research frontier.\n\n"
    )
    energy_info_str += json.dumps(rows, ensure_ascii=False, indent=2)
    return energy_info_str



# # 生成最终综合报告
# def generate_final_report(pid, year_data, ke_data):
#     prompt = f"""generate a report based on the following information and instructions."""

#     # todo:
#     ## 1. 构架 prompt 说明和任务要求
#         # a.介绍脉络树和知识熵的含义，说明更关注高知识熵的节点以及知识流动路径和文献间的启发关系
#         # b.让模型先从脉络树结构的演化上得到一些关键节点，在此基础上再去文章摘要中分析启发关系和路径
#         # c.限制生成报告的格式:如在文本最后按照reference list的格式列出生成文本的所有参考文献信息
#     ## 2. 整理节点信息和脉络树结构信息
#     ### 2.1 节点信息
#         # yead_data 中的各年的所有 nodes 信息，可以先拿出所有不重复的节点ID，然后通过 get_paper_info_from_es 函数获取标题和摘要
#         # 整理所有年度的所有节点的信息，包括:id title abstract publication_year等（忽略size和color信息，不用）
#     ### 2.2 脉络树结构信息
#         # 每年度脉络树上的引用关系列表和本年度引文关系中节点的知识熵大小
#     ## 3. 调用 completion 函数获取结果


### xray: update single-paper prompt with semantic protocol and VD leap constraints ###
# 生成最终综合报告
def generate_final_report(pid, year_data, ke_data):
    """
    根据多年的脉络树数据 (year_data) 和知识熵数据 (ke_data) 生成综合分析报告。
    (Generates a comprehensive analysis report based on multi-year idea tree data (year_data) 
    and knowledge entropy data (ke_data).)

    Args:
        pid (int): 目标论文ID (The target paper ID)
        year_data (dict): 包含多年GML节点和边信息的字典, 格式: {year: {"nodes": [...], "edges": [...]}}
                          (Dictionary containing multi-year GML node and edge info)
        ke_data (dict): 包含多年节点知识熵的字典, 格式: {year: {node_id: ke_value, ...}}
                        (Dictionary containing multi-year node knowledge entropy)

    Returns:
        str: 生成的综合报告 (The generated comprehensive report)
    """
    
    # --- 1. 构架 prompt 说明和任务要求 (Build prompt instructions and task requirements) ---

    # 获取年份范围 (Get year range)
    all_years = sorted(list(year_data.keys()))
    if not all_years:
        return "Error: No data available for analysis (year_data is empty)."
    min_year = min(all_years)
    max_year = max(all_years)
    year2vd, year2dpi = read_vd_dpi_data(pid, all_years)

    # a. 介绍脉络树和知识熵的含义 (Introduce concepts)
    # b. 引导模型分析路径 (Guide the model's analysis framework)
    # c. 限制生成报告的格式 (Constrain the report format)
    #
    # [Prompt updated based on user feedback]
    #
    prompt_instructions = f"""
You are an expert research domain analyst specializing in semantic knowledge evolution, citation-based causal inference, and concept genealogy. Your task is to generate a detailed single-paper analysis report based on the following "Idea Tree" evolution data for paper ID {pid}. The report must explain not only how the tree structure changes, but also how knowledge concepts, methods, problem framings, assumptions, and application contexts flow and transform across papers.

## 1. Core Concepts
* **Idea Tree:** This is a directed graph showing the knowledge evolution centered on paper {pid}. Nodes represent papers.
* **Edge Definition:** **[Important]** An edge (A -> B) means **paper A is cited by paper B**.
* **Knowledge Flow:** This signifies that knowledge flowed **from A to B (A inspired B)** through concepts, methods, problem formulations, datasets, evaluation settings, theoretical assumptions, or application scenarios.
* **Semantic Concept Flow:** The movement and transformation of research meaning across the Idea Tree. It includes concept inheritance, concept recombination, methodological adaptation, problem reframing, abstraction from a narrow task to a broader principle, and migration into new application contexts.
* **Semantic Shift:** A meaningful change in how an inherited idea is used, such as moving from theory to implementation, from method to benchmark, from single-domain use to cross-domain use, or from a local technique to a general research paradigm.
* **Knowledge Entropy:** This metric measures the diversity or uncertainty of knowledge sources for a node (paper) within its local citation network. A node with high knowledge entropy often integrates knowledge from diverse research directions, making it a potential key hub, synthesis point, or innovative starting point.
* **Visible Depth (VD):** VD is the number of effective layers lit by high-knowledge-entropy nodes. A VD rise indicates that the Idea Tree has completed an energy-level transition by forming a new effective inheritance layer.
* **Development Potential Index (DPI):** DPI is a forward-looking signal for whether the tree has accumulated structural potential for a later energy-level transition. It is not deterministic, and a later VD rise may lag behind a strong DPI signal.

## 2. Semantic Analysis Protocol (MANDATORY)
Before writing each section, internally extract semantic evidence from the provided Node Information:
- Core concepts and technical terms from titles and abstracts.
- Methods, models, algorithms, datasets, evaluation goals, theoretical claims, and application domains.
- The target paper's initial conceptual contribution.
- Later papers that inherit, specialize, generalize, combine, operationalize, or redirect those concepts.

In the final report:
- Give priority to semantic explanation. Tree structure, KE, VD, and DPI should support the semantic argument, not replace it.
- For every important structural expansion, explain what conceptual content is flowing through that expansion.
- When discussing a citation path, describe the actual idea transfer along the path: what was preserved, what changed, and what new research possibility emerged.
- Avoid generic structure-only phrases such as "the tree expands", "the branch deepens", or "the node is central" unless immediately followed by a semantic explanation grounded in titles or abstracts.
- If abstracts are missing or too vague for a node, explicitly mark the semantic evidence as limited instead of inventing details.
- Distinguish these semantic roles when evidence supports them: concept originator, method importer, method stabilizer, bridge paper, benchmark/application carrier, synthesis node, and frontier redirector.

The report must be idea-centered, not structure-centered. Treat Idea Tree expansion, Knowledge Entropy, VD, and DPI as evidence for intellectual evolution, not as the main story. Whenever you describe a structural expansion, energy-level transition, transition window, or influence difference, immediately connect it to concrete ideas found in the relevant paper titles and abstracts.

Avoid monotonous statements such as "the tree became deeper," "VD increased," or "DPI was high" unless you also explain:
- Which paper or hub is involved.
- What specific idea, method, problem framing, experimental result, or application direction appears in its abstract.
- How that idea plausibly caused, enabled, or redirected downstream development in the Idea Tree.
- Which later papers, branches, or subfields absorbed that idea differently.

If an abstract is unavailable, say that the idea-level interpretation is limited and rely only on the title, citation direction, year, KE, VD/DPI evidence, and tree position. Do not invent missing content.

## 3. Your Task and Analysis Framework
Your core task is to analyze the evolution of this Idea Tree from {min_year} to {max_year}, summarize the knowledge flow paths, and deeply investigate the inspirational relationships between documents.

Please follow this analysis framework **strictly**:
1.  **Annual or Phase-Based Evolution Analysis:** Start with a chronological analysis of the Idea Tree's evolution. You may analyze year by year, but when the timeline spans many years, group years into larger phases (for example, 3-5 years) based on major semantic and structural changes. Clearly indicate the time span of each phase. Each phase must explain the structural changes and the semantic content moving through those changes.
    * If VD changes by **two or more layers** in any observed year, treat that year as a major transition year. You must explicitly focus on that year in the phase-based summary and explain why the jump occurred by connecting: key papers or hubs from that year, new citation links or branch formation, high-KE nodes, titles and abstracts, and historical events visible in the provided timeline, such as important publications, emergence of a new method/application branch, or field absorption of an earlier idea.
    * Do not simply write that VD jumped. Explain which ideas or papers made the new effective inheritance layers possible, and how the transition changed downstream research direction.
2.  **Key Node Analysis:** After the chronological review, identify and analyze the key nodes across the entire period. Focus on nodes with persistently high Knowledge Entropy, nodes that drive VD transitions, and nodes that act as crucial hubs in knowledge flow. For every key node you mention, state its intellectual function in the lineage, such as "introduced the mechanism," "translated the idea into a new application field," "provided a measurement method," "generalized the model," or "connected two previously separate problem framings."
3.  **Key Path and Inspiration Analysis:** **[This is the most critical step]** Identify the most significant knowledge flow paths (for example, A -> B). You must consult the paper abstracts provided in the "Node Information" section below to analyze their specific inspirational relationship.
    * Do not just say "B cited A." Instead, explain: "Paper A proposed the XX method. Paper B states in its abstract that it builds upon this method to solve the YY problem."
    * For each key path, describe the source concept or method, the receiving paper's reinterpretation or extension, and the semantic shift created by that transfer.
    * Include at least one short concept trajectory in prose, connecting the target paper to later nodes through citation direction and abstract evidence.
4.  **DPI Predictive Role Analysis:** Use DPI evidence to explain whether a future transition was already structurally foreseeable before the visible layer actually rose. If DPI shows potential before a later VD rise, explain the possible lag through publication timing, citation formation, knowledge diffusion, and field absorption. If DPI weakens or stays insufficient, explain whether the available high-KE nodes may have aged, sat too far from the active frontier, or failed to convert local fuel into a new tree-level layer. Avoid saying DPI "predicted" a later transition unless the provided DPI evidence clearly appears before a later VD rise.
5.  **Overall Summary:** Conclude with a final summary of the field's evolution based on this Idea Tree. Characterize the historical role of the target paper using one or more lenses such as foundational initiator, methodological consolidator, conceptual bridge, domain-expanding successor, semantic redirector, or application carrier.

## 4. Report Format Requirements
1.  The report must be clearly structured and logically follow the framework above.
2.  The Annual or Phase-Based Evolution Analysis should be written in detailed and comprehensive paragraphs, not just as bullet points.
3.  Do not expose raw IDs in the narrative; refer to papers by title or short descriptive names, along with the appropriate citation marker.
4.  Do not mechanically report raw VD or DPI values in the narrative; use them only to support causal interpretation of transitions and predictive windows.
5.  Do not let the report become a plain description of tree shape, VD, or DPI. Every major structural statement must be paired with an abstract-grounded explanation of the paper idea that drove or absorbed that change.
6.  When explaining an energy-level transition, prefer the pattern: "paper idea from abstract -> citation/branch position -> new inheritance layer or transition evidence -> downstream research direction." Keep this as prose, not as a formula.
7.  The report should contain substantially more semantic interpretation than structural description. A useful target is at least two semantic claims for every graph-structure claim.
8.  Do not produce a purely chronological summary. Each chronological observation must be tied to a concept movement, method adaptation, problem reframing, or application shift.
9.  **[Mandatory]** At the end of the report, include a section titled `## Reference List`.
10. In this section, list the detailed information for all papers you specifically mentioned in the body of the report, using the following format:
    * [1] Title of the paper. (Publication Year)

## 5. Data Usage Constraint (IMPORTANT)
The Node Information, Idea Tree Structure, and VD/DPI Annual Evidence data are provided below. Use ONLY this information when making claims. Do NOT invent abstracts, citations, or external historical facts. When the task asks you to explain transition years using "historical events", interpret those events as events visible in the supplied Idea Tree timeline unless the provided abstracts or titles themselves contain broader historical context.

---
Now, please begin your analysis based on the following data:
"""

    # --- 2. 整理节点信息和脉络树结构信息 (Organize node info and tree structure info) ---

    # ### 2.1 节点信息 (Node Information) ###
    print("Step 2.1: Collecting all unique node IDs...")
    all_node_ids = set()
    for year, data in year_data.items():
        nodes = data.get("nodes", [])
        for node in nodes:
            node_id = safe_extract_id(node)
            if node_id != "Unknown":
                all_node_ids.add(node_id)
        
        edges = data.get("edges", [])
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source:
                all_node_ids.add(str(source))
            if target:
                all_node_ids.add(str(target))
    
    print(f"Found {len(all_node_ids)} unique nodes. Fetching info from ES...")
    
    node_info_list = []
    # 获取根节点（目标论文）的信息 (Get info for the root (target) paper)
    center_paper_title = f"Paper {pid}"
    try:
        title, abstract, pub_year = get_paper_info_from_es(pid)
        center_paper_title = title
        # [Translated to English]
        root_paper_info = f"Center paper for analysis ID: {pid}\nTitle: {title}\nYear: {pub_year}\nAbstract: {abstract}\n"
        node_info_list.append({"id": str(pid), "title": title, "abstract": abstract, "publication_year": pub_year})
        # 确保根节点ID在集合中 (Ensure root ID is in the set)
        all_node_ids.add(str(pid)) 
    except Exception as e:
        print(f"Error fetching root paper {pid} info: {e}")
        root_paper_info = f"Center paper for analysis ID: {pid} (Information fetching failed)\n"


    # 获取所有其他节点的信息 (Get info for all other nodes)
    for node_id in all_node_ids:
        if node_id == str(pid): # 已经获取过 (Already fetched)
             continue
        try:
            # 确保 node_id 是可以传给 ES 的格式 (Ensure node_id is in a format for ES)
            title, abstract, pub_year = get_paper_info_from_es(node_id)
            node_info_list.append({
                "id": node_id,
                "title": title,
                "abstract": abstract,
                "publication_year": pub_year
            })
        except Exception as e:
            print(f"Error fetching info for node {node_id}: {e}")
            # 即使失败也添加占位符 (Add placeholder even if fetch fails)
            node_info_list.append({
                "id": node_id,
                "title": f"Paper_{node_id}",
                "abstract": "Abstract not available or fetching error.",
                "publication_year": "Unknown"
            })
    
    # 格式化节点信息 (Format node information)
    # [Translated to English]
    node_info_str = "## 4. Node Information (For your abstract analysis)\n\n"
    node_info_str += root_paper_info + "\n"
    # 使用json格式化列表，便于LLM解析 (Use JSON for easy LLM parsing)
    node_info_str += json.dumps(node_info_list, ensure_ascii=False, indent=2)
    
    # ### 2.2 脉络树结构信息 (Idea Tree Structure Information) ###
    print("Step 2.2: Formatting structural and KE data...")
    # [Translated to English]
    structure_info_str = "\n\n## 5. Idea Tree Annual Evolution Data (Structure and Entropy)\n\n"
    
    for year in sorted(year_data.keys()):
        # [Translated to English]
        structure_info_str += f"### Year {year}\n"
        
        # 收集当年涉及的所有节点 (Collect all nodes involved this year)
        involved_node_ids = set()
        
        # From the node list
        current_year_nodes = year_data[year].get("nodes", [])
        for node in current_year_nodes:
            node_id = safe_extract_id(node)
            if node_id != "Unknown":
                involved_node_ids.add(node_id)

        # 引用关系 (Citation Relationships)
        edges = year_data[year].get("edges", [])
        edge_list = []
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
                # Per instructions: (A -> B) means A is cited by B.
                # GML source -> target. We format it as (source -> target)
                edge_list.append(f"({source} -> {target})") 
                # Also add edge nodes to the set
                involved_node_ids.add(str(source))
                involved_node_ids.add(str(target))
        
        # [Translated to English]
        if edge_list:
            structure_info_str += "**Citation Relationships (Edges):** " + ", ".join(edge_list) + "\n"
        else:
            structure_info_str += "**Citation Relationships (Edges):** None\n"
            
        # 知识熵 (Knowledge Entropy)
        # [MODIFIED as per user request]
        # 仅包含当年脉络树中涉及的节点的KE (Only include KE for nodes involved in this year's tree)
        
        year_ke_data = ke_data.get(year, {})
        filtered_ke_data = {}
        for node_id in involved_node_ids:
            # Ensure node_id is a string for lookup, as ke_data keys might be strings
            str_node_id = str(node_id)
            if str_node_id in year_ke_data:
                filtered_ke_data[str_node_id] = year_ke_data[str_node_id]

        # 保护性处理并计算上限
        for node_id, v in filtered_ke_data.items():
            try:
                val = float(v)
            except Exception:
                val = 0.0
            # 仿照原逻辑对极大值做平滑
            if val > 1000:
                val = 1000 + math.log(max(1.0, val - 1000)) * 10.0
            filtered_ke_data[node_id] = val

        # [Translated to English]
        structure_info_str += "**Node Knowledge Entropy (for nodes in this year's tree):**\n"
        if not filtered_ke_data:
            structure_info_str += "  - N/A\n"
        else:
            # 按知识熵从高到低排序 (Sort by KE, high to low)
            sorted_ke = sorted(filtered_ke_data.items(), key=lambda item: item[1], reverse=True)
            for node_id, ke_value in sorted_ke:
                structure_info_str += f"  - ID {node_id}: {ke_value:.4f}\n"
        
        structure_info_str += "\n"

    # --- 3. 组合 Prompt 并调用 completion 函数 (Combine prompt and call completion) ---
    
    energy_info_str = build_energy_evidence_str(pid, all_years, year2vd, year2dpi, center_paper_title)
    final_prompt = prompt_instructions + node_info_str + structure_info_str + energy_info_str
    
    # 调试：打印最终的prompt（或保存到文件）
    # (Debug: print final prompt or save to file)
    folder_path = f"../output/final_report/{pid}"
    os.makedirs(folder_path, exist_ok=True)
    sss = f"../output/final_report/{pid}/prompt_v7.txt"
    print(sss)
    with open(sss, "w", encoding="utf-8") as f:
        f.write(final_prompt)
    
    print(f"Step 3: Calling completion API... (Prompt size: ~{len(final_prompt)} chars)")

    try:
        report = completion(final_prompt)
        return report
    except Exception as e:
        print(f"Error calling completion API: {e}")
        # [Translated to English]
        return f"Error: Report generation failed. {e}"


# 主函数
def main(pid):
    # Configuration parameters
    base_path = "../temp_files/attributed_idea_tree_by_year"
    ke_path = "../temp_files/node_entropy_by_year"
    files_list = os.listdir('../temp_files/source_gml_by_year/'+str(pid)) #存储每年的.gml 文件
    years = sorted([int(file.split('.')[0]) for file in files_list])
    # years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]  # Years to analyze
    output_dir = "../output/final_report"
    os.makedirs(f"{output_dir}/{pid}", exist_ok=True)
    print(f"Starting analysis of paper {pid} idea tree evolution...")
    
    # 1. Read multi-year GML data
    print("Step 1: Reading multi-year GML data")
    year_data = read_multiple_year_gmls(base_path, pid, years)

    # 2. read multi-year KE data
    ke_data = read_multiple_year_ke(ke_path, pid, years)

    if not year_data:
        print("No valid GML data read")
        return
    if not ke_data:
        print("No valid KE data read")
        return

    # 3. generate final report
    final_report = generate_final_report(pid=pid, year_data=year_data, ke_data=ke_data)
    
    # 4. Save results
    # output_dir = "../output/final_report"
    # os.makedirs(f"{output_dir}/{pid}", exist_ok=True)
    
    with open(os.path.join(f"{output_dir}/{pid}", "final_report_v7.txt"), "w", encoding="utf-8") as f:
        f.write(final_report)
    
    print("Analysis complete! Results saved to output directory")
    print("=" * 50)
    print(final_report)

if __name__ == "__main__":
    pid = 3177828909

    main(pid)
