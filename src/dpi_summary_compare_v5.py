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

VD_PATH = "../temp_files/year2visible_depth"
DPI_PATH = "../temp_files/year2delta_d"

# 调用API补全对话
def completion(user_prompt):
    dialogue = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_prompt},
    ]
    sjtu_temp = 'sk-o2ndZu1j0iWAg7LnJtsUzB957Zklec6mXnFDnDpA3gpOiSrt'

    response = requests.post(
        url='https://openai.acemap.cn/v1/chat/completions',
        headers={'Authorization': f'Bearer {sjtu_temp}'},
        json={'model': 'gpt-5.5', 'messages': dialogue},
        verify=False,
        timeout=600
    )
    try:
        response_data = response.json()
    except ValueError as e:
        print(f"API status: {response.status_code}")
        print(f"API non-JSON response: {response.text[:2000]}")
        raise RuntimeError("API returned a non-JSON response") from e

    if 'choices' not in response_data:
        print(f"API status: {response.status_code}")
        print("API response missing 'choices':")
        print(json.dumps(response_data, ensure_ascii=False, indent=2)[:4000])
        raise RuntimeError("API response missing choices")

    return response_data['choices'][0]['message']['content']

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

# 读取单个 pid 的年度 VD/DPI 文件
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
        else:
            try:
                vd_change = int(vd) - int(previous_vd)
            except (TypeError, ValueError):
                vd_change = "unknown"

        rows.append({
            "year": year,
            "VD": vd,
            "VD_change_from_previous_observed_year": vd_change,
            "DPI": dpi,
            "DPI_interpretation": classify_dpi(dpi),
        })
        previous_vd = vd

    display_name = paper_title or f"Paper {pid}"
    energy_info_str = f"\n\n## VD and DPI Annual Evidence for {display_name} (For transition reasoning; do not quote mechanically)\n\n"
    energy_info_str += (
        "VD is the main scale of the current academic energy level: when VD rises, "
        "a new effective layer has been lit by high-KE nodes. DPI is the predictive "
        "potential for the next transition: DPI >= 1 suggests that the tree has "
        "accumulated enough structural potential for a later transition, but the "
        "actual VD rise can lag because publications, citations, diffusion, and "
        "field absorption take time. DPI < 1 suggests that the observed structure "
        "does not yet provide enough forward potential, or that earlier high-KE "
        "nodes are losing effective driving power because of aging, layer distance, "
        "or a shift of the research frontier.\n\n"
    )
    energy_info_str += json.dumps(rows, ensure_ascii=False, indent=2)
    return energy_info_str

def extract_center_paper_title(node_info_str, pid):
    """Extract the center paper title from the formatted node information."""
    for line in node_info_str.splitlines():
        if line.startswith("Title: "):
            title = line[len("Title: "):].strip()
            if title:
                return title
    return f"Paper {pid}"

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
        root_paper_info = f"Center paper for analysis\nTitle: {title}\nYear: {pub_year}\nAbstract: {abstract}\n"
        node_info_list.append({"id": str(pid), "title": title, "abstract": abstract, "publication_year": pub_year})
        all_node_ids.add(str(pid))
    except Exception as e:
        print(f"Error fetching root paper {pid}: {e}")
        root_paper_info = "Center paper for analysis (Information fetching failed)\n"
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

### xray: refine comparative prompt with abstract-grounded idea evolution ###
# 构建最终综合 prompt（两个 pid -> 单个 prompt）
def build_combined_prompt(
    pid1,
    node_info_1,
    struct_info_1,
    energy_info_1,
    pid2,
    node_info_2,
    struct_info_2,
    energy_info_2,
    all_years1,
    all_years2,
):
    title1 = extract_center_paper_title(node_info_1, pid1)
    title2 = extract_center_paper_title(node_info_2, pid2)
    # v5 prompt: keep the v3 comparison structure, but make semantic concept flow
    # the primary analysis target and use tree/VD/DPI evidence as support.
    prompt_instructions = f"""
You are an expert research domain analyst specializing in semantic knowledge evolution, citation-based causal inference, and concept genealogy. Your task is to produce a single, coherent analysis report in English that compares the Idea Tree evolution of two target papers. The report must explain not only how the tree structure changes, but also how knowledge concepts, methods, problem framings, assumptions, and application contexts flow and transform across papers.

## Core Concepts (definitions you must use)
* **Idea Tree:** A directed graph representing knowledge evolution centered on a target paper. Nodes correspond to papers; edges correspond to citation relationships.
* **Edge Definition:** An edge (A → B) means paper A is cited by paper B, indicating directional knowledge flow from A to B.
* **Knowledge Flow:** A causal or inspirational relationship where concepts, methods, problem formulations, datasets, evaluation settings, theoretical assumptions, or application scenarios introduced in A contribute to or shape B.
* **Semantic Concept Flow:** The movement and transformation of research meaning across the Idea Tree. It includes concept inheritance, concept recombination, methodological adaptation, problem reframing, abstraction from a narrow task to a broader principle, and migration into new application contexts.
* **Semantic Shift:** A meaningful change in how an inherited idea is used, such as moving from theory to implementation, from method to benchmark, from single-domain use to cross-domain use, or from a local technique to a general research paradigm.
* **Knowledge Entropy:** A numeric metric measuring the diversity of upstream knowledge sources feeding into a node. Higher entropy indicates broader integration and higher potential for conceptual innovation.
* **Visible Depth (VD):** The number of effective layers lit by high-knowledge-entropy nodes; a VD rise indicates that the Idea Tree has completed an energy-level transition by forming a new effective inheritance layer.
* **Development Potential Index (DPI):** A forward-looking signal for whether the tree has accumulated structural potential for a later energy-level transition. It is not deterministic, and a later VD rise may lag behind a strong DPI signal.
* **Intellectual Predecessor / Successor:**  
  - A paper is an **intellectual predecessor** if its position in the Idea Tree and outgoing knowledge flows indicate that it established foundational concepts, methods, or problem framings later developed by another paper.  
  - A paper is an **intellectual successor** if it builds upon, extends, consolidates, or systematizes ideas introduced by earlier work.
* **Influence Strength:** A combined assessment based on downstream reach, structural centrality in the Idea Tree, persistence across time slices, and the propagation of ideas into multiple sub-branches.
* **Key Historical Intersection Points (under Idea Tree guidance):** Specific nodes, edges, or temporal slices where two or more research threads converge, interact, or cross-fertilize, often giving rise to new subfields or methodological shifts.

## Semantic Analysis Protocol (MANDATORY)
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

The report must be idea-centered, not structure-centered. Treat Idea Tree expansion, Knowledge Entropy, VD, and DPI as evidence for intellectual evolution, not as the main story. Whenever you describe a structural expansion, energy-level transition, transition window, or relative influence difference, immediately connect it to concrete ideas found in the relevant paper titles and abstracts.

Avoid monotonous statements such as "the tree became deeper," "VD increased," or "DPI was high" unless you also explain:
- Which paper or hub is involved.
- What specific idea, method, problem framing, experimental result, or application direction appears in its abstract.
- How that idea plausibly caused, enabled, or redirected downstream development in the Idea Tree.
- Which later papers, branches, or subfields absorbed that idea differently.

If an abstract is unavailable, say that the idea-level interpretation is limited and rely only on the title, citation direction, year, KE, and tree position. Do not invent missing content.

## Task Overview (STRICT)
You must produce ONE single English report that contains the following components, in the specified order.

### 1. Standalone Historical Analysis for Each Target Paper
Produce a **brief standalone analysis** for **each** target paper:
- "{title1}"
- "{title2}"
Each analysis should:

- Summarize the Idea Tree evolution for the target paper through an **idea-evolution narrative**. Temporal progression and major structural expansions should appear as the skeleton of the story, but the main explanation must be how specific ideas were born, inherited, recombined, or redirected by later papers.
- Explain which concepts or methods entered the lineage, which were preserved, and which were transformed over time.
- For each major energy-level transition or important structural expansion, explain the intellectual trigger: identify the paper(s) associated with the transition and use their abstracts to describe which concept, method, experiment, data resource, theoretical framing, or application demand made the new layer possible. Do not merely say that the VD rose or a new layer appeared.
- Use VD changes as supporting evidence for energy-level transitions, stalls, or widening-without-deepening patterns, without mechanically reporting raw VD values. Use DPI as evidence of structural potential or transition windows, but do not overstate it as a deterministic prediction. When a DPI window is discussed, connect it to the papers and ideas that accumulated before the later transition.
- Identify 2–4 key nodes or hubs in the Idea Tree, prioritizing nodes with high Knowledge Entropy or strong downstream branching.
- Explain concrete semantic knowledge flow paths using evidence from paper abstracts in the Node Information sections. For each key path, state:
  - the source concept or method,
  - the receiving paper's reinterpretation or extension,
  - the semantic shift created by that transfer.
- Include at least one short "concept trajectory" in prose for each target paper, connecting the target paper to later nodes through citation direction and abstract evidence.
- For every key node you mention, state its intellectual function in the lineage, such as "introduced the mechanism," "translated the idea into a new application field," "provided a measurement method," "generalized the model," or "connected two previously separate problem framings."
- Explicitly characterize the historical role of the target paper using one or more of the following lenses:
  - Foundational initiator
  - Methodological consolidator
  - Conceptual bridge
  - Domain-expanding successor
  - Semantic redirector
  - Application carrier
- Keep each standalone analysis concise (approximately 3–5 paragraphs), with more space devoted to semantic interpretation than to graph description.

### 2. Comparative Historical and Causal Analysis
After the two standalone analyses, produce a **comparative analysis** that goes beyond surface comparison and explicitly reasons about **precedence, succession, influence, inspiration, and semantic divergence** between the two papers.

This section MUST include:

#### 2.1 Intellectual Precedence and Succession
- Determine whether the two target papers stand in a **predecessor–successor relationship**, a **parallel but independent evolution**, or a **mutual reinforcement relationship**.
- Be conservative when assigning predecessor-successor status. Do **not** force a simple linear predecessor→successor relationship merely because one paper is earlier or one tree has stronger VD/DPI growth. If the evidence shows shared downstream descendants, overlapping but distinct lineages, or complementary technical roles, prefer a nuanced judgment such as **parallel but interlinked**, **mutual reinforcement**, or **chronological predecessor in a narrow substream but independent methodological foundation in the broader field**.
- Justify your judgment using:
  - Directionality of citation paths
  - Temporal ordering
  - Structural depth and expansion patterns in the Idea Trees
  - VD/DPI evidence as support for structural depth, transition timing, and long-term expansion capacity
  - Overlap and transformation in concepts, methods, problem framings, or application settings described in the abstracts
- Clearly state which paper (if any) should be regarded as the intellectual predecessor and which as the successor, and explain why.

#### 2.2 Relative Influence Assessment
- Compare the **historical influence** of the two papers by analyzing:
  - Which concrete research domains, application areas, methods, or theoretical questions each paper influenced.
  - What different downstream ideas each paper inspired, and how those directions diverged from one another.
  - Breadth and depth of downstream Idea Tree branches as evidence of those idea-level effects.
  - Persistence of influence across multiple years, especially whether later papers keep reusing the same conceptual mechanism, adapt it into new fields, or transform it into a methodological platform.
  - Presence in high-entropy or structurally central positions, interpreted as signs of cross-idea integration rather than merely large metric values.
  - Energy-level transitions and DPI-based predictive windows, interpreted through the specific papers and ideas that supplied the transition potential.
- For each influence claim, specify the semantic channel of influence, such as a method being reused, a problem framing being generalized, a benchmark or application setting being adopted, or concepts being recombined by high-entropy nodes.
- Conclude which paper demonstrates **higher long-term influence**, **broader cross-subfield impact**, or **stronger methodological legacy**, and specify the dimension(s) in which this holds.
- VD/DPI should strengthen this influence assessment, but it must not replace concrete citation-path, KE, title, and abstract evidence. Do not write this section as a chronological list of VD, DPI, or tree-shape changes. Start from the intellectual effects, then use tree structure and metrics as supporting evidence.
- When comparing influence, name the inspired directions separately. For example, distinguish influence on theory formation, empirical measurement, algorithmic method, system design, biomedical/physical/social application, or other domains only when those directions are supported by the provided titles and abstracts.

#### 2.3 Comparative Inspiration at Intersection Points
- Focus on **historical intersection points** where the two Idea Trees intersect, overlap, or share intellectual ancestry.
- Identify a rich set of concrete intersection papers when the data supports it; do not reduce the analysis to only a few examples if more shared or closely related nodes are present in the provided Idea Tree data.
- At each intersection:
  - Explain how ideas from each target paper interacted with the intersecting work at the semantic level.
  - Identify the concept, method, task, or application context through which the intersection occurred.
  - Judge which target paper exerted **stronger inspirational force** at that intersection, distinguishing concept origination from later extension, operationalization, synthesis, or domain transfer.
- If concrete intersection papers exist, you MUST return their full bibliographic information.

##### Identified Intersection Papers (MANDATORY if intersections exist)
For each intersecting paper, provide:
- Title
- Publication year
- Identifier (PID or OpenAlex ID)
If the same paper appears in multiple intersections, list it once and note the corresponding years or Idea Tree positions.
List the full "Identified Intersection Papers" only once in this section. Do not create a second intersection-paper list after the Reference List or in any appendix.

#### 2.4 Thematic and Methodological Divergence
- Highlight differences between the two papers in:
  - Thematic focus
  - Methodological strategy
  - Patterns of knowledge integration (as reflected by Knowledge Entropy)
- Add a semantic divergence analysis: explain where the two lineages preserve similar vocabulary but use it for different research purposes, or where they solve related problems through different conceptual mechanisms.
- Explain how these differences shaped their respective roles in the field's evolution.

### 3. Insights and Forward-Looking Hypotheses
Provide a short bullet list (3–6 items) of **actionable insights or research hypotheses**, such as:
- Which line of work is more likely to generate future breakthroughs
- Which conceptual gaps remain underexplored
- Which paper’s lineage is more adaptable to emerging subfields
- Which semantic combinations or concept transfers appear promising but underdeveloped

### 4. Report Format Requirements
- Use the following section headings exactly:
  - "Standalone Analysis — {title1}"
  - "Standalone Analysis — {title2}"
  - "Comparative Historical Intersection Analysis"
  - "Insights"
  - "Reference List"
- Do not expose raw IDs in the narrative; refer to papers by title or short descriptive names.
- Do not mechanically report raw VD or DPI values in the narrative; use them only to support causal interpretation of transitions and predictive windows.
- Do not let the standalone analyses or relative influence assessment become plain descriptions of tree shape, VD, or DPI. Every major structural statement must be paired with an abstract-grounded explanation of the paper idea that drove or absorbed that change.
- When explaining an energy-level transition, prefer the pattern: "paper idea from abstract -> citation/branch position -> new inheritance layer or transition evidence -> downstream research direction." Keep this as prose, not as a formula.
- Avoid saying DPI "predicted" a later transition unless the provided DPI evidence clearly appears before a later VD rise; otherwise describe it as structural potential, a transition window, or insufficient potential.
- The report should contain substantially more semantic interpretation than structural description. A useful target is at least two semantic claims for every graph-structure claim.
- Do not produce a purely chronological summary. Each chronological observation must be tied to a concept movement, method adaptation, problem reframing, or application shift.
- At the end, include a `## Reference List` listing all explicitly mentioned papers, formatted as:
  * [n] Title. (Year)
- The Reference List should be a normal bibliography only. Do not repeat the full intersection-paper list with identifiers there; identifiers belong only in the single "Identified Intersection Papers" list in section 2.3.

### 5. Data Usage Constraint (IMPORTANT)
The Node Information, Idea Tree Structure, and VD/DPI Annual Evidence data for each PID are provided below as separate sections. Use ONLY this information when making claims. Do NOT invent abstracts, citations, or historical facts.

Now proceed. First produce the two standalone analyses, then the comparative historical and causal analysis, followed by insights, and finally the Reference List.
"""

    # Combine everything. Node & structure parts are provided separately for clarity.
    final_prompt = prompt_instructions + "\n\n"
    final_prompt += f"--- PART A: {title1} DATA ---\n\n"
    final_prompt += node_info_1 + "\n\n"
    final_prompt += struct_info_1 + "\n\n"
    final_prompt += energy_info_1 + "\n\n"
    final_prompt += f"--- PART B: {title2} DATA ---\n\n"
    final_prompt += node_info_2 + "\n\n"
    final_prompt += struct_info_2 + "\n\n"
    final_prompt += energy_info_2 + "\n\n"
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
    year2vd_1, year2dpi_1 = read_vd_dpi_data(pid1, years1)
    year2vd_2, year2dpi_2 = read_vd_dpi_data(pid2, years2)

    if not year_data_1:
        print(f"No valid GML data for pid {pid1}")
        return
    if not year_data_2:
        print(f"No valid GML data for pid {pid2}")
        return

    # Build node_info and structure_info strings for each pid
    node_info_1, struct_info_1 = build_node_and_structure_strings(pid1, year_data_1, ke_data_1)
    node_info_2, struct_info_2 = build_node_and_structure_strings(pid2, year_data_2, ke_data_2)
    title1 = extract_center_paper_title(node_info_1, pid1)
    title2 = extract_center_paper_title(node_info_2, pid2)
    energy_info_1 = build_energy_evidence_str(pid1, years1, year2vd_1, year2dpi_1, title1)
    energy_info_2 = build_energy_evidence_str(pid2, years2, year2vd_2, year2dpi_2, title2)

    # Build combined prompt
    final_prompt = build_combined_prompt(
        pid1,
        node_info_1,
        struct_info_1,
        energy_info_1,
        pid2,
        node_info_2,
        struct_info_2,
        energy_info_2,
        years1,
        years2,
    )

    # Save prompt to output folder (single file)
    output_dir = f"../output/final_report/{pid1}_{pid2}"
    os.makedirs(output_dir, exist_ok=True)
    prompt_path = os.path.join(output_dir, "prompt_v5.txt")
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
    report_path = os.path.join(output_dir, "final_report_v5.txt")
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
