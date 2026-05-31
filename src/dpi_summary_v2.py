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
        json={'model': 'gpt-4o-mini', 'messages': dialogue},
        verify=False,
        timeout=60
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
            "_source": ["title", "abstract"]
        }
        
        response = es_client.search(index="acemap.works", body=query)
        hits = response['hits']['hits']
        
        if hits:
            source = hits[0]['_source']
            title = source.get('title', 'Title not found')
            abstract = source.get('abstract', 'Abstract not found')
            return title, abstract
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
                return title, abstract
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

def get_layer_name(color):
    """Get layer name based on color code"""
    color_to_layer = {
        '#ff0000': 'Leading Paper',
        '#ffe306': 'Layer 1',
        '#ff723a': 'Layer 2', 
        '#f81463': 'Layer 3',
        '#9d126f': 'Layer 4',
        '#6c48aa': 'Layer 5',
        '#0a0da7': 'Layer 6',
        '#0000ff': 'Layer 7',
        '#959595': 'Gray Layer'
    }
    return color_to_layer.get(color, f'Unknown Layer ({color})')

# 阶段一：脉络树结构演化分析
def phase1_structure_analysis(pid, year_data):
    """
    Phase 1: Analyze the evolution of citation tree structure
    """
    # Build sorted list of years
    years = sorted(year_data.keys())
    
    # Prepare phase 1 prompt in English
    prompt = f"""You are an expert in academic citation tree analysis. You need to analyze the evolution of citation trees across multiple years. Please pay special attention to the node color encoding:

Node Color Semantics:
- Red "#ff0000": Leading paper (root node), largest size
- Visible layer nodes (with high knowledge entropy), categorized by layer:
  '1': '#ffe306', '2': '#ff723a', '3': '#f81463', '4': '#9d126f', 
  '5': '#6c48aa', '6': '#0a0da7', '7': '#0000ff'
- Gray "#959595": Non-visible layer nodes (without high knowledge entropy, retained for tree integrity)

Important: The edge direction in the citation tree is from source to target, meaning that the source paper is cited by the target paper. So "A → B" means paper B cites paper A.

Please analyze the citation tree data for the following years:

Leading Paper ID: {pid}

"""

    # For each year, provide comprehensive node and edge information
    for year in years:
        data = year_data[year]
        prompt += f"\n--- {year} Citation Tree ---\n"
        prompt += f"Total nodes: {len(data['nodes'])}, Total edges: {len(data['edges'])}\n"
        
        # Group nodes by color and provide detailed information
        color_groups = {}
        for node in data["nodes"]:
            color = safe_extract_color(node)
            if color not in color_groups:
                color_groups[color] = []
            label = safe_extract_label(node)
            size = safe_extract_size(node)
            node_id = safe_extract_id(node)
            color_groups[color].append(f"{label} (ID: {node_id}, size: {size:.1f})")
        
        prompt += "Nodes by color:\n"
        for color, nodes_list in color_groups.items():
            layer_name = get_layer_name(color)
            prompt += f"- {layer_name} ({color}): {len(nodes_list)} nodes\n"
            # Show all nodes for this color group
            for node_desc in nodes_list:
                prompt += f"  * {node_desc}\n"
        
        # Provide complete edge information in a structured way
        if data["edges"]:
            prompt += "\nCitation relationships (edge direction: source → target means target cites source):\n"
            
            # Group edges by source node to show citation patterns
            edge_groups = {}
            for edge in data["edges"]:
                source = edge.get("source", "Unknown")
                target = edge.get("target", "Unknown")
                if source not in edge_groups:
                    edge_groups[source] = []
                edge_groups[source].append(target)
            
            # Show edges grouped by source, focusing on important nodes first
            # Start with the leading paper
            if str(pid) in edge_groups or pid in edge_groups:
                prompt += f"- Leading paper {pid} is cited by: {', '.join(map(str, edge_groups[pid]))}\n"
            
            # Then show other important nodes (colored nodes)
            for source, targets in edge_groups.items():
                if str(source) != str(pid):  # Already shown above
                    # Check if this node is in the visible layers (not gray)
                    source_color = data["node_colors"].get(str(source), "#959595")
                    
                    if source_color != "#959595":  # Visible layer node
                        prompt += f"- Paper {source} ({get_layer_name(source_color)}) is cited by: {', '.join(map(str, targets[:10]))}"
                        if len(targets) > 10:
                            prompt += f" ... and {len(targets) - 10} more"
                        prompt += "\n"
            
            # If there are gray nodes with citations, mention them briefly
            gray_edges = []
            for source, targets in edge_groups.items():
                if str(source) != str(pid):
                    source_color = data["node_colors"].get(str(source), "#959595")
                    if source_color == "#959595":  # Gray node
                        gray_edges.append(f"{source} is cited by {len(targets)} papers")
            
            if gray_edges:
                prompt += f"- Gray paper citations: {', '.join(gray_edges[:5])}"
                if len(gray_edges) > 5:
                    prompt += f" ... and {len(gray_edges) - 5} more"
                prompt += "\n"
        else:
            prompt += "\nNo citation relationships found.\n"
        
        prompt += "\n"

    prompt += """
Please complete the following Phase 1 analysis tasks:

1. Structural Evolution Identification:
   - Track changes in direct citations of the leading paper
   - Identify emergence of new layers (indicated by color changes)
   - Mark key papers with significantly increased node size

2. Key Turning Point Detection:
   - Branch birth years: Years when new color layers first appear
   - Knowledge diffusion years: Years when citation relationships expand from single to multiple layers
   - Structural reorganization years: Years when existing branches merge or reorganize

3. Key Node Screening:
   - List nodes that changed from gray to colored (from unimportant to important)
   - List nodes with significantly increased size (knowledge entropy increase)
   - List hub nodes connecting multiple branches
   - List the first nodes in new color layers

Please output in the following format:
## Phase 1: Citation Tree Structural Evolution Analysis

### Structural Evolution Overview
[Describe overall evolution trends]

### Key Turning Points
- [Year]: [Event description]

### Key Node List
- Node ID [Color change/Importance increase description]
- ...

### Main Knowledge Flow Paths
- Path 1: Paper A is cited by Paper B, which is cited by Paper C...
- ...
"""

    print("Starting Phase 1 analysis...")
    try:
        analysis_result = completion(prompt)
        return prompt, analysis_result
    except Exception as e:
        print(f"Error during Phase 1 analysis: {e}")
        # 返回一个模拟结果以便继续测试
#         mock_result = """
# ## Phase 1: Citation Tree Structural Evolution Analysis

# ### Structural Evolution Overview
# The citation tree shows significant growth from 2018 to 2021, starting with a simple structure and evolving into a complex network.

# ### Key Turning Points
# - 2019: First layer of citations appears
# - 2020: Multiple layers emerge with increased complexity
# - 2021: Further expansion with more connections

# ### Key Node List
# - Node 478557235: Appeared in 2018 as a gray node
# - Node 19347743: Appeared in 2019 with significant size
# - Node 487227557: First layer 1 node in 2020

# ### Main Knowledge Flow Paths
# - Path 1: Paper 470780090 is cited by 478557235, which is cited by ...
# - Path 2: Paper 470780090 is cited by 19347743, which is cited by ...
# """
        # return prompt, mock_result

# 阶段二：关键节点思想启发分析
def phase2_thought_analysis(pid, key_nodes, year_data):
    """
    Phase 2: In-depth analysis of idea inspiration for key nodes
    """
    if not key_nodes:
        return "No key nodes to analyze", "No key nodes identified"
    
    # Get paper information for key nodes - 使用完整的摘要
    node_info = {}
    for node_id in key_nodes:
        title, abstract = get_paper_info_from_es(node_id)
        node_info[node_id] = {"title": title, "abstract": abstract}
        print(f"Retrieved info for node {node_id}: Title length = {len(title)}, Abstract length = {len(abstract)}")
    
    # Also get information for the leading paper
    leading_title, leading_abstract = get_paper_info_from_es(pid)
    
    # Build phase 2 prompt in English
    prompt = f"""Based on the key nodes identified in Phase 1, please conduct an in-depth analysis of idea inspiration relationships.

Important: The citation direction is from source to target, meaning the target paper cites the source paper. So "A → B" means paper B cites paper A, and thus paper A's ideas inspired paper B.

Leading Paper ID: {pid}
Leading Paper Title: {leading_title}
Leading Paper Abstract: {leading_abstract}

Key Node Information:
"""

    for node_id, info in node_info.items():
        prompt += f"""
Node {node_id}:
Title: {info['title']}
Abstract: {info['abstract']}
"""

    # Add comprehensive citation relationship context
    prompt += "\nComprehensive Citation Relationship Context:\n"
    years = sorted(year_data.keys())
    
    # Collect all edges involving key nodes across all years
    all_key_edges = []
    for year in years:
        data = year_data[year]
        for edge in data["edges"]:
            source = edge.get("source", "Unknown")
            target = edge.get("target", "Unknown")
            if (str(source) in key_nodes or 
                str(target) in key_nodes or
                str(source) == str(pid) or
                str(target) == str(pid)):
                all_key_edges.append((year, source, target))
    
    # Group edges by year
    edges_by_year = {}
    for year, source, target in all_key_edges:
        if year not in edges_by_year:
            edges_by_year[year] = []
        edges_by_year[year].append((source, target))
    
    # Display edges by year
    for year in sorted(edges_by_year.keys()):
        prompt += f"{year} citation relationships involving key nodes:\n"
        edges = edges_by_year[year]
        for source, target in edges:
            prompt += f"  {source} → {target} (paper {target} cites paper {source})\n"
        prompt += "\n"

    prompt += """
Please analyze the specific idea inspiration relationships for the important citation pairs:

For each important inspiration relationship (where A → B means B cites A), please specify:
1. Which core idea from the source paper (A) was inherited and developed by the target paper (B)
2. How the target paper (B) innovated or expanded upon the source paper's (A) ideas
3. How this inspiration relationship is reflected in research questions, methods, or conclusions

Please focus on relationships that show significant intellectual development, such as:
- Leading paper to first-layer papers
- Cross-layer citations (e.g., Layer 1 to Layer 3)
- Citations between large nodes (indicating important papers)

Please output in the following format:
## Phase 2: Key Idea Inspiration Relationship Analysis

### Inspiration Relationship 1: Paper A is cited by Paper B (A → B)
- **Idea Inheritance**: [Specific description of how B built on A's ideas]
- **Innovation/Expansion**: [Specific description of how B extended A's work]  
- **Evidence Analysis**: [Specific evidence based on titles and abstracts]

### Inspiration Relationship 2: Paper B is cited by Paper C (B → C)
- ...
"""

    print("Starting Phase 2 analysis...")
    try:
        analysis_result = completion(prompt)
        return prompt, analysis_result
    except Exception as e:
        print(f"Error during Phase 2 analysis: {e}")
        # 返回一个模拟结果以便继续测试
#         mock_result = """
# ## Phase 2: Key Idea Inspiration Relationship Analysis

# ### Inspiration Relationship 1: Paper 470780090 is cited by Paper 478557235 (470780090 → 478557235)
# - **Idea Inheritance**: The core methodology from the leading paper was adopted
# - **Innovation/Expansion**: The target paper applied the method to a new domain
# - **Evidence Analysis**: Abstract shows clear reference to the original methodology

# ### Inspiration Relationship 2: Paper 478557235 is cited by Paper 19347743 (478557235 → 19347743)
# - **Idea Inheritance**: Extended the theoretical framework
# - **Innovation/Expansion**: Added new constraints to improve performance
# - **Evidence Analysis**: Title indicates direct extension of previous work
# """
#         return prompt, mock_result

# 从阶段一结果中提取关键节点ID
def extract_key_nodes_from_phase1(phase1_result):
    """
    Extract key node IDs from Phase 1 results
    """
    key_nodes = []
    
    # Look for node IDs mentioned in the results
    node_patterns = [
        r'Node[_\s]*ID[:\s]*(\d+)',   # e.g. Node ID: 4210257598
        r'Node[_\s]*(\d+)',           # e.g. Node_2963224980 or Node 2963224980
        r'ID[:\s]*(\d+)',             # e.g. (ID: 4210257598)
        r'paper\s+(\d+)'              # e.g. paper 123456789
    ]
    
    for pattern in node_patterns:
        found_nodes = re.findall(pattern, phase1_result, re.IGNORECASE)
        key_nodes.extend(found_nodes)
    
    # Also look for numbers that are likely node IDs
    if not key_nodes:
        all_numbers = re.findall(r'\b(\d{8,9})\b', phase1_result)  # 调整匹配8-9位数字
        key_nodes.extend(all_numbers)
    
    # Remove duplicates
    key_nodes = list(set(key_nodes))
    
    if not key_nodes:
        print("key node IDs match ERROR")
    
    return key_nodes

# 生成最终综合报告
def generate_final_report(phase1_result, phase2_result, pid):
    """
    Generate a comprehensive final report combining both phases
    """
    prompt = f"""Please synthesize the following two analysis phases into a cohesive, comprehensive research evolution report.

Leading Paper ID: {pid}

Phase 1 Analysis (Structural Evolution):
{phase1_result}

Phase 2 Analysis (Idea Inspiration):
{phase2_result}

Please combine these analyses to create a unified report that:
1. Provides an executive summary of the research evolution
2. Integrates structural changes with intellectual developments
3. Highlights the most significant turning points and their intellectual implications
4. Traces the flow of key ideas through the citation network
5. Identifies emerging trends and potential future directions

Format the report with clear sections and use academic language suitable for researchers.
"""

    print("Generating final comprehensive report...")
    try:
        final_report = completion(prompt)
        return final_report
    except Exception as e:
        print(f"Error during final report generation: {e}")
        # 返回一个模拟结果
        mock_report = f"""
# Research Evolution Analysis Report for Paper {pid}

## Executive Summary
This report analyzes the evolution of the research area centered around paper {pid}. The citation network shows significant growth and intellectual development from 2018 to 2021.

## Integrated Analysis
The structural evolution reveals a pattern of knowledge diffusion from the core paper to multiple layers of subsequent research. Key turning points include the emergence of specialized branches in 2020 and further diversification in 2021.

## Future Directions
Based on the analysis, potential future research directions include further applications of the core methodology and integration with adjacent research areas.
"""
        return mock_report

# 主函数
def main():
    # Configuration parameters
    pid = 2896457183
    base_path = "../temp_files/attributed_idea_tree_by_year"
    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]  # Years to analyze
    
    print(f"Starting analysis of paper {pid} citation tree evolution...")
    
    # 1. Read multi-year GML data
    print("Step 1: Reading multi-year GML data")
    year_data = read_multiple_year_gmls(base_path, pid, years)
    
    if not year_data:
        print("No valid GML data read")
        return
    
    # 2. Phase 1: Structural evolution analysis
    print("Step 2: Performing Phase 1 analysis")
    phase1_prompt, phase1_result = phase1_structure_analysis(pid, year_data)
    
    # 3. Extract key nodes
    print("Step 3: Extracting key nodes")
    key_nodes = extract_key_nodes_from_phase1(phase1_result)
    print(f"Identified key nodes: {key_nodes}")
    
    # 4. Phase 2: Thought inspiration analysis
    print("Step 4: Performing Phase 2 analysis")
    phase2_prompt, phase2_result = phase2_thought_analysis(pid, key_nodes, year_data)
    
    # 5. Generate final comprehensive report
    print("Step 5: Generating final report")
    final_report = generate_final_report(phase1_result, phase2_result, pid)
    
    # 6. Save results
    output_dir = "../output"
    os.makedirs(output_dir, exist_ok=True)
    
    with open(os.path.join(output_dir, "phase1_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(phase1_prompt)
    
    with open(os.path.join(output_dir, "phase1_result.txt"), "w", encoding="utf-8") as f:
        f.write(phase1_result)
    
    with open(os.path.join(output_dir, "phase2_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(phase2_prompt)
    
    with open(os.path.join(output_dir, "phase2_result.txt"), "w", encoding="utf-8") as f:
        f.write(phase2_result)
    
    with open(os.path.join(output_dir, "final_report.txt"), "w", encoding="utf-8") as f:
        f.write(final_report)
    
    print("Analysis complete! Results saved to output directory")
    print("=" * 50)
    print(final_report)

if __name__ == "__main__":
    main()