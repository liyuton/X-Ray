import requests
from elasticsearch import Elasticsearch
from readgml import readgml
import os
import json
import math
import traceback

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
        json={'model': 'gpt-5-mini', 'messages': dialogue},
        verify=False,
        timeout=600
    )
    return response.json()['choices'][0]['message']['content']

# 从ES获取论文信息（标题和摘要）- 修改ID格式
def get_paper_info_from_es(pid):
    """
    Get title and abstract from Elasticsearch by paper ID
    Convert numeric ID to OpenAlex format: https://openalex.org/works/W{pid}
    Returns tuple (title, abstract, publication_year)
    """
    try:
        openalex_id = f"https://openalex.org/W{pid}"
        query = {
            "query": {
                "term": {
                    "_id": openalex_id
                }
            },
            "_source": ["title", "abstract", "publication_year"]
        }
        response = es_client.search(index="acemap.works", body=query)
        hits = response.get('hits', {}).get('hits', [])
        if hits:
            source = hits[0].get('_source', {})
            title = source.get('title', 'Title not found')
            abstract = source.get('abstract', 'Abstract not found')
            pub_year = source.get('publication_year', 'Year not found')
            return title, abstract, pub_year
        else:
            # fallback to raw pid
            query_fallback = {
                "query": {
                    "term": {
                        "_id": str(pid)
                    }
                },
                "_source": ["title", "abstract", "publication_year"]
            }
            response_fallback = es_client.search(index="acemap.works", body=query_fallback)
            hits_fb = response_fallback.get('hits', {}).get('hits', [])
            if hits_fb:
                source = hits_fb[0].get('_source', {})
                title = source.get('title', 'Title not found')
                abstract = source.get('abstract', 'Abstract not found')
                pub_year = source.get('publication_year', 'Year not found')
                return title, abstract, pub_year
            else:
                return f"Paper_{pid}", "Abstract not available", "Unknown"
    except Exception as e:
        print(f"Error querying ES for PID {pid}: {e}")
        traceback.print_exc()
        return f"Paper_{pid}", "Abstract not available", "Unknown"

# 处理GML数据结构（与原函数保持一致）
def process_gml_data(nodes, edges):
    processed_nodes = []
    processed_edges = []
    for item in nodes:
        if isinstance(item, dict):
            if 'id' in item:
                processed_nodes.append(item)
            elif 'node' in item and item['node'] == '[':
                continue
        elif isinstance(item, list):
            sub_nodes, sub_edges = process_gml_data(item, [])
            processed_nodes.extend(sub_nodes)
    for item in edges:
        if isinstance(item, dict):
            if 'source' in item and 'target' in item:
                processed_edges.append(item)
            elif 'edge' in item and item['edge'] == '[':
                continue
        elif isinstance(item, list):
            sub_nodes, sub_edges = process_gml_data([], item)
            processed_edges.extend(sub_edges)
    return processed_nodes, processed_edges

# 安全属性提取
def safe_extract_color(node):
    if not isinstance(node, dict):
        return "#959595"
    color = node.get("fill", node.get("color", "959595"))
    if color and not str(color).startswith("#"):
        color = "#" + str(color)
    try:
        if len(color) != 7 or not all(c in "0123456789abcdef" for c in color[1:].lower()):
            color = "#959595"
    except Exception:
        color = "#959595"
    return color

def safe_extract_size(node):
    if not isinstance(node, dict):
        return 10.0
    size = node.get("w", node.get("width", 10.0))
    try:
        return float(size)
    except (ValueError, TypeError):
        return 10.0

def safe_extract_label(node):
    if not isinstance(node, dict):
        return "Unknown_Node"
    label = node.get("label", "")
    if not label:
        node_id = node.get("id", "Unknown")
        return f"Node_{node_id}"
    return label

def safe_extract_id(node):
    if not isinstance(node, dict):
        return "Unknown"
    return str(node.get("id", "Unknown"))

# 读取单个 pid 的多年度GML
def read_multiple_year_gmls(base_path, pid, years):
    year_data = {}
    for year in years:
        gml_path = os.path.join(base_path, str(pid), f"{year}.gml")
        if os.path.exists(gml_path):
            try:
                nodes, edges = readgml.read_gml(gml_path)
                processed_nodes, processed_edges = process_gml_data(nodes, edges)
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
            except Exception as e:
                print(f"Failed to read {gml_path}: {e}")
                traceback.print_exc()
        else:
            print(f"File does not exist: {gml_path}")
    return year_data

# 读取单个 pid 的多年度 KE 文件
def read_multiple_year_ke(ke_path, pid, years):
    ke_data = {}
    for year in years:
        ke_file_path = os.path.join(ke_path, str(pid), f"{year}")
        if os.path.exists(ke_file_path):
            try:
                with open(ke_file_path, 'r', encoding='utf-8') as f:
                    year_ke_data = json.load(f)
                    ke_data[year] = year_ke_data
            except Exception as e:
                print(f"Failed to read KE file {ke_file_path}: {e}")
                traceback.print_exc()
        else:
            print(f"KE file does not exist for year {year}: {ke_file_path}")
    return ke_data

# 为单个 pid 构建 node_info_str 与 structure_info_str （与原逻辑类似）
def build_node_and_structure_strings(pid, year_data, ke_data):
    # collect unique node ids
    all_node_ids = set()
    for year, data in year_data.items():
        for node in data.get("nodes", []):
            nid = safe_extract_id(node)
            if nid != "Unknown":
                all_node_ids.add(nid)
        for edge in data.get("edges", []):
            source = edge.get("source")
            target = edge.get("target")
            if source is not None:
                all_node_ids.add(str(source))
            if target is not None:
                all_node_ids.add(str(target))
    # fetch paper infos
    node_info_list = []
    try:
        title, abstract, pub_year = get_paper_info_from_es(pid)
        root_paper_info = f"Center paper for analysis ID: {pid}\nTitle: {title}\nYear: {pub_year}\nAbstract: {abstract}\n"
        node_info_list.append({"id": str(pid), "title": title, "abstract": abstract, "publication_year": pub_year})
        all_node_ids.add(str(pid))
    except Exception as e:
        print(f"Error fetching root paper {pid}: {e}")
        root_paper_info = f"Center paper for analysis ID: {pid} (Information fetching failed)\n"
    for node_id in sorted(all_node_ids):
        if node_id == str(pid):
            continue
        try:
            title, abstract, pub_year = get_paper_info_from_es(node_id)
            node_info_list.append({
                "id": node_id,
                "title": title,
                "abstract": abstract,
                "publication_year": pub_year
            })
        except Exception as e:
            print(f"Error fetching info for node {node_id}: {e}")
            node_info_list.append({
                "id": node_id,
                "title": f"Paper_{node_id}",
                "abstract": "Abstract not available or fetching error.",
                "publication_year": "Unknown"
            })
    node_info_str = "## Node Information (For your abstract analysis)\n\n"
    node_info_str += root_paper_info + "\n"
    node_info_str += json.dumps(node_info_list, ensure_ascii=False, indent=2)
    # structure info
    structure_info_str = "\n\n## Idea Tree Annual Evolution Data (Structure and Entropy)\n\n"
    for year in sorted(year_data.keys()):
        structure_info_str += f"### Year {year}\n"
        involved_node_ids = set()
        for node in year_data[year].get("nodes", []):
            node_id = safe_extract_id(node)
            if node_id != "Unknown":
                involved_node_ids.add(node_id)
        edges = year_data[year].get("edges", [])
        edge_list = []
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source is not None and target is not None:
                edge_list.append(f"({source} -> {target})")
                involved_node_ids.add(str(source))
                involved_node_ids.add(str(target))
        if edge_list:
            structure_info_str += "**Citation Relationships (Edges):** " + ", ".join(edge_list) + "\n"
        else:
            structure_info_str += "**Citation Relationships (Edges):** None\n"
        year_ke_data = ke_data.get(year, {})
        filtered_ke_data = {}
        for node_id in involved_node_ids:
            s = str(node_id)
            if s in year_ke_data:
                try:
                    val = float(year_ke_data[s])
                except Exception:
                    val = 0.0
                if val > 1000:
                    val = 1000 + math.log(max(1.0, val - 1000)) * 10.0
                filtered_ke_data[s] = val
        structure_info_str += "**Node Knowledge Entropy (for nodes in this year's tree):**\n"
        if not filtered_ke_data:
            structure_info_str += "  - N/A\n"
        else:
            sorted_ke = sorted(filtered_ke_data.items(), key=lambda item: item[1], reverse=True)
            for node_id, ke_value in sorted_ke:
                structure_info_str += f"  - ID {node_id}: {ke_value:.4f}\n"
        structure_info_str += "\n"
    return node_info_str, structure_info_str

# 构建最终综合 prompt（两个 pid -> 单个 prompt）
def build_combined_prompt(pid1, node_info_1, struct_info_1, pid2, node_info_2, struct_info_2, all_years1, all_years2):
    # core concepts & instructions in English, and specific task: first brief individual analysis (concise),
    # then comparative analysis focusing on theme-tree-guided historical intersection points.
    prompt_instructions = f"""
You are an expert research domain analyst specializing in historical knowledge evolution and citation-based causal inference. Your task is to produce a single, coherent analysis report in English that compares the Idea Tree evolution of two target papers and explicitly reasons about their historical roles, relative influence, and intellectual precedence within the same research domain.

## Core Concepts (definitions you must use)
* **Idea Tree:** A directed graph representing knowledge evolution centered on a target paper. Nodes correspond to papers; edges correspond to citation relationships.
* **Edge Definition:** An edge (A → B) means paper A is cited by paper B, indicating directional knowledge flow from A to B.
* **Knowledge Flow:** A causal or inspirational relationship where concepts, methods, or problem formulations introduced in A contribute to or shape B.
* **Knowledge Entropy:** A numeric metric measuring the diversity of upstream knowledge sources feeding into a node. Higher entropy indicates broader integration and higher potential for conceptual innovation.
* **Intellectual Predecessor / Successor:**  
  - A paper is an **intellectual predecessor** if its position in the Idea Tree and outgoing knowledge flows indicate that it established foundational concepts, methods, or problem framings later developed by another paper.  
  - A paper is an **intellectual successor** if it builds upon, extends, consolidates, or systematizes ideas introduced by earlier work.
* **Influence Strength:** A combined assessment based on downstream reach, structural centrality in the Idea Tree, persistence across time slices, and the propagation of ideas into multiple sub-branches.
* **Key Historical Intersection Points (under Idea Tree guidance):** Specific nodes, edges, or temporal slices where two or more research threads converge, interact, or cross-fertilize, often giving rise to new subfields or methodological shifts.

## Task Overview (STRICT)
You must produce ONE single English report that contains the following components, in the specified order.

### 1. Standalone Historical Analysis for Each Target Paper
Produce a **brief standalone analysis** for **each** target paper (PID 2105934661 and PID 3090704166). Each analysis should:

- Summarize the Idea Tree evolution for the target paper, emphasizing temporal progression and major structural expansions.
- Identify 2–4 key nodes or hubs in the Idea Tree, prioritizing nodes with high Knowledge Entropy or strong downstream branching.
- Explain concrete knowledge flow paths using evidence from paper abstracts in the Node Information sections (e.g., how a method, concept, or problem framing introduced in one paper influenced later work).
- Explicitly characterize the historical role of the target paper using one or more of the following lenses:
  - Foundational initiator
  - Methodological consolidator
  - Conceptual bridge
  - Domain-expanding successor
- Keep each standalone analysis concise (approximately 2–4 paragraphs).

### 2. Comparative Historical and Causal Analysis
After the two standalone analyses, produce a **comparative analysis** that goes beyond surface comparison and explicitly reasons about **precedence, succession, influence, and inspiration** between the two papers.

This section MUST include:

#### 2.1 Intellectual Precedence and Succession
- Determine whether the two target papers stand in a **predecessor–successor relationship**, a **parallel but independent evolution**, or a **mutual reinforcement relationship**.
- Justify your judgment using:
  - Directionality of citation paths
  - Temporal ordering
  - Structural depth and expansion patterns in the Idea Trees
  - Overlap in concepts or methods described in the abstracts
- Clearly state which paper (if any) should be regarded as the intellectual predecessor and which as the successor, and explain why.

#### 2.2 Relative Influence Assessment
- Compare the **historical influence** of the two papers by analyzing:
  - Breadth and depth of downstream Idea Tree branches
  - Persistence of influence across multiple years
  - Presence in high-entropy or structurally central positions
- Conclude which paper demonstrates **higher long-term influence**, **broader cross-subfield impact**, or **stronger methodological legacy**, and specify the dimension(s) in which this holds.

#### 2.3 Comparative Inspiration at Intersection Points
- Focus on **historical intersection points** where the two Idea Trees intersect, overlap, or share intellectual ancestry.
- At each intersection:
  - Explain how ideas from each target paper interacted with the intersecting work.
  - Judge which target paper exerted **stronger inspirational force** at that intersection (e.g., introducing the key idea vs. extending or operationalizing it).
- If concrete intersection papers exist, you MUST return their full bibliographic information.

##### Identified Intersection Papers (MANDATORY if intersections exist)
For each intersecting paper, provide:
- Title
- Publication year
- Identifier (PID or OpenAlex ID)
If the same paper appears in multiple intersections, list it once and note the corresponding years or Idea Tree positions.

#### 2.4 Thematic and Methodological Divergence
- Highlight differences between the two papers in:
  - Thematic focus
  - Methodological strategy
  - Patterns of knowledge integration (as reflected by Knowledge Entropy)
- Explain how these differences shaped their respective roles in the field’s evolution.

### 3. Insights and Forward-Looking Hypotheses
Provide a short bullet list (3–6 items) of **actionable insights or research hypotheses**, such as:
- Which line of work is more likely to generate future breakthroughs
- Which conceptual gaps remain underexplored
- Which paper’s lineage is more adaptable to emerging subfields

### 4. Report Format Requirements
- Use the following section headings exactly:
  - "Standalone Analysis — PID 2105934661"
  - "Standalone Analysis — PID 3090704166"
  - "Comparative Historical Intersection Analysis"
  - "Insights"
  - "Reference List"
- Do not expose raw IDs in the narrative; refer to papers by title or short descriptive names.
- At the end, include a `## Reference List` listing all explicitly mentioned papers, formatted as:
  * [n] Title. (Year)

### 5. Data Usage Constraint (IMPORTANT)
The Node Information and Idea Tree Structure data for each PID are provided below as separate sections. Use ONLY this information when making claims. Do NOT invent abstracts, citations, or historical facts.

Now proceed. First produce the two standalone analyses, then the comparative historical and causal analysis, followed by insights, and finally the Reference List.
"""

    # Combine everything. Node & structure parts are provided separately for clarity.
    final_prompt = prompt_instructions + "\n\n"
    final_prompt += f"--- PART A: PID {pid1} DATA ---\n\n"
    final_prompt += node_info_1 + "\n\n"
    final_prompt += struct_info_1 + "\n\n"
    final_prompt += f"--- PART B: PID {pid2} DATA ---\n\n"
    final_prompt += node_info_2 + "\n\n"
    final_prompt += struct_info_2 + "\n\n"
    return final_prompt

# 主函数：接受两个 pid
def main(pid1, pid2):
    base_path = "../temp_files/attributed_idea_tree_by_year"
    ke_path = "../temp_files/node_entropy_by_year"
    # determine years for each pid by listing files in source_gml_by_year/<pid>
    def get_years_for_pid(pid):
        folder = os.path.join('../temp_files/source_gml_by_year', str(pid))
        if not os.path.exists(folder):
            print(f"Warning: source GML folder does not exist for pid {pid}: {folder}")
            return []
        files_list = os.listdir(folder)
        years = []
        for file in files_list:
            # expect files like "2018.gml"
            if file.endswith('.gml'):
                try:
                    years.append(int(file.split('.')[0]))
                except Exception:
                    continue
        return sorted(years)

    years1 = get_years_for_pid(pid1)
    years2 = get_years_for_pid(pid2)
    if not years1:
        print(f"No GML years found for pid {pid1} — aborting.")
        return
    if not years2:
        print(f"No GML years found for pid {pid2} — aborting.")
        return

    # Read year data and KE data for both pids
    year_data_1 = read_multiple_year_gmls(base_path, pid1, years1)
    year_data_2 = read_multiple_year_gmls(base_path, pid2, years2)
    ke_data_1 = read_multiple_year_ke(ke_path, pid1, years1)
    ke_data_2 = read_multiple_year_ke(ke_path, pid2, years2)

    if not year_data_1:
        print(f"No valid GML data for pid {pid1}")
        return
    if not year_data_2:
        print(f"No valid GML data for pid {pid2}")
        return

    # Build node_info and structure_info strings for each pid
    node_info_1, struct_info_1 = build_node_and_structure_strings(pid1, year_data_1, ke_data_1)
    node_info_2, struct_info_2 = build_node_and_structure_strings(pid2, year_data_2, ke_data_2)

    # Build combined prompt
    final_prompt = build_combined_prompt(pid1, node_info_1, struct_info_1, pid2, node_info_2, struct_info_2, years1, years2)

    # Save prompt to output folder (single file)
    output_dir = f"../output/final_report/{pid1}_{pid2}"
    os.makedirs(output_dir, exist_ok=True)
    prompt_path = os.path.join(output_dir, "prompt_v2.txt")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(final_prompt)

    print(f"Calling completion API with combined prompt for PID {pid1} and PID {pid2} (prompt saved to {prompt_path})")
    try:
        report = completion(final_prompt)
    except Exception as e:
        print(f"Error calling completion API: {e}")
        traceback.print_exc()
        report = f"Error: Report generation failed. {e}"

    # Save final report
    report_path = os.path.join(output_dir, "final_report_v2.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Analysis complete! Results saved to {report_path}")
    print("=" * 50)
    print(report)


if __name__ == "__main__":
    # Example usage: replace pid1 and pid2 with your two target IDs
    pid1 = 2105934661
    pid2 = 3090704166
    main(pid1, pid2)
