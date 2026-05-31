"""
Generate final idea-tree reports with VD/DPI evidence.

This script keeps the overall prompt structure from dpi_summary_v6.py while
adding per-PID visible depth (VD) and development potential index (DPI) data.
VD/DPI values are provided to the model as reasoning evidence, but the prompt
asks the report to explain the causes of transitions instead of quoting the
metric values mechanically.
"""
import json
import math
import os
import sys
from datetime import datetime

import requests
from dpi_summary_v6 import (
    get_paper_info_from_es,
    read_multiple_year_gmls,
    read_multiple_year_ke,
    safe_extract_id,
)


BASE_PATH = "../temp_files/attributed_idea_tree_by_year"
KE_PATH = "../temp_files/node_entropy_by_year"
SOURCE_GML_BY_YEAR_PATH = "../temp_files/source_gml_by_year"
VD_PATH = "../temp_files/year2visible_depth"
DPI_PATH = "../temp_files/year2delta_d"
OUTPUT_DIR = "../output/final_report_vd_dpi"


def completion(user_prompt, model_name):
    """Call the chat completion API with the model selected in main()."""
    dialogue = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_prompt},
    ]
    sjtu_temp = 'sk-hBzYhO9CB1r1bZJf7407DcF261Af46A8Ad5eF71fB4C102F2'

    response = requests.post(
        url='https://openai.acemap.cn/v1/chat/completions',
        headers={'Authorization': f'Bearer {sjtu_temp}'},
        json={'model': model_name, 'messages': dialogue},
        verify=False,
        timeout=600
    )
    return response.json()['choices'][0]['message']['content']


def build_file_suffix(pid, model_name, timestamp):
    """Build a stable filename suffix with PID, model name, and timestamp."""
    safe_model_name = "".join(
        c if c.isalnum() or c in ("-", "_") else "_"
        for c in model_name
    )
    return f"{pid}_{safe_model_name}_{timestamp}"


def get_paper_info(pid):
    """Return normalized paper metadata from ES."""
    paper_info = get_paper_info_from_es(pid)
    if len(paper_info) == 3:
        return paper_info
    if len(paper_info) == 2:
        title, abstract = paper_info
        return title, abstract, "Unknown"
    return f"Paper_{pid}", "Abstract not available", "Unknown"


def resolve_year_metric_path(metric_dir, pid):
    """Resolve local metric files stored as either {pid}.json or {pid}."""
    json_path = os.path.join(metric_dir, f"{pid}.json")
    raw_path = os.path.join(metric_dir, str(pid))
    if os.path.exists(json_path):
        return json_path
    if os.path.exists(raw_path):
        return raw_path
    raise FileNotFoundError(f"Metric file does not exist: {json_path} or {raw_path}")


def read_year_metric(metric_dir, pid, years):
    """Read a year-value JSON file and normalize year keys to integers."""
    metric_path = resolve_year_metric_path(metric_dir, pid)
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
    """Read VD and DPI values for the corresponding target PID."""
    year2vd = read_year_metric(VD_PATH, pid, years)
    year2dpi = read_year_metric(DPI_PATH, pid, years)
    return year2vd, year2dpi


def get_years(pid):
    """Read available yearly GML slices for a PID."""
    source_dir = os.path.join(SOURCE_GML_BY_YEAR_PATH, str(pid))
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Source GML directory does not exist: {source_dir}")

    years = []
    for file_name in os.listdir(source_dir):
        if not file_name.endswith(".gml"):
            continue
        try:
            years.append(int(file_name.split(".")[0]))
        except ValueError:
            continue
    return sorted(years)


def smooth_ke_value(value):
    """Smooth extreme KE values without changing their rank ordering."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    if value > 1000:
        value = 1000 + math.log(max(1.0, value - 1000)) * 10.0
    return value


def classify_dpi(value):
    """Convert a DPI value into prompt-facing qualitative evidence."""
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


def build_energy_evidence_str(years, year2vd, year2dpi):
    """
    Format VD/DPI data as internal evidence.

    The report prompt asks the model to use these values to locate transitions
    and predictive windows, but to explain the structural causes in prose.
    """
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

    energy_info_str = "\n\n## 6. VD and DPI Annual Evidence (For transition reasoning; do not quote mechanically)\n\n"
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


def generate_final_report(
    pid,
    year_data,
    ke_data,
    year2vd,
    year2dpi,
    model_name,
    timestamp,
    call_model=True,
):
    """
    Generate a comprehensive report from yearly tree, KE, VD and DPI evidence.
    """
    all_years = sorted(list(year_data.keys()))
    if not all_years:
        return "Error: No data available for analysis (year_data is empty)."
    min_year = min(all_years)
    max_year = max(all_years)

    prompt_instructions = f"""
You are an expert research domain analyst. Your task is to generate a detailed analysis report based on the following "Idea Tree" evolution data for paper ID {pid}.

## 1. Core Concepts
* **Idea Tree:** This is a directed graph showing the knowledge evolution centered on paper {pid}. Nodes represent papers.
* **Edge Definition:** **[Important]** An edge (A -> B) means **paper A is cited by paper B**. 
* **Knowledge Flow:** This signifies that knowledge flowed **from A to B (A inspired B)**.
* **Knowledge Entropy:** This metric measures the diversity or uncertainty of knowledge sources for a node (paper) within its local citation network. **A node with high knowledge entropy** often indicates it integrates knowledge from diverse research directions, making it a potential key hub or innovative starting point.
* **Visible Depth (VD):** VD is the number of effective layers that have been lit by high-knowledge-entropy nodes. It is the main scale of the current academic energy level. When VD rises, the idea tree has completed an energy-level transition because a new effective inheritance layer has appeared.
* **Development Potential Index (DPI):** DPI is the forward-looking potential for the next energy-level transition. It is not a deterministic prediction. A strong DPI signal indicates that enough structural potential may already exist, but the later VD rise can lag because publication, citation formation, knowledge diffusion, and field absorption take time.

## 2. Your Task and Analysis Framework
Your core task is to analyze the structural evolution of this Idea Tree from {min_year} to {max_year}, summarize the knowledge flow paths, and deeply investigate the **inspirational relationships** between documents.

Please follow this analysis framework **strictly**:
1.  **Annual Evolution Analysis:** First, provide a **year-by-year summary** of the Idea Tree's evolution. For each year (from {min_year} to {max_year}), describe the overall changes in its structure (e.g., new nodes added, new citation links formed, key changes from the previous year). You do not need to analyze the evolution strictly year by year; when the overall timeline spans many years, you may group years into larger phases (e.g., 3–5 years) based on major structural changes, but please clearly indicate the time span of each phase. In this part, incorporate VD changes as evidence of energy-level transitions, but do **not** directly write sentences such as "VD is X in year Y"; instead, explain why a new effective layer was lit, why a transition stalled, or why growth widened branches without deepening the tree.
2.  **Key Node Analysis:** After the year-by-year review, identify and analyze the **key nodes** across the entire period. Focus on nodes with persistently high knowledge entropy or those that act as crucial hubs in the knowledge flow. For years or phases where the academic energy level rises, judge which node mainly drove that transition and explain the mechanism using KE, tree position, edge direction, title, and abstract evidence.
3.  **Key Path & Inspiration Analysis:** **[This is the most critical step]** Identify the most significant knowledge flow paths (e.g., A -> B). You must consult the **paper abstracts** provided in the "Node Information" section below to analyze their specific **inspirational relationship**.
    * For example: Don't just say "B cited A." Instead, explain: "Paper A (ID: ...) proposed the XX method. Paper B (ID: ...) states in its abstract that it builds upon this method to solve the XX problem."
    * When a transition-driving node appears, trace how it later branches out through direct or indirect descendants and identify which later papers were generated or enabled by that branch. Explain what each descendant paper adds, rather than only listing the citation chain.
4.  **DPI Predictive Role Analysis:** Use DPI evidence to explain whether a future transition was already structurally foreseeable before the visible layer actually rose. If DPI shows potential before the later structural transition, explain the possible lag through publication timing, citation formation, knowledge diffusion, and field absorption. If DPI weakens or stays insufficient, explain whether the available high-KE nodes may have aged, sat too far from the active frontier, or failed to convert local fuel into a new tree-level layer.
5.  **Overall Summary:** Conclude with a final summary of the field's evolution based on this Idea Tree.

## 3. Report Format Requirements
1.  The report must be clearly structured and logically follow the framework above. 
2.  Your Annual Evolution Analysis for each year should be written in **detailed and comprehensive paragraphs**, not just as a list of bullet points.
3.  Please avoid citing the original paper ID directly in your summary; instead, use the paper's title or a short form thereof, along with the appropriate citation marker.
4.  Do not directly report raw VD or DPI values in the body. Use them only to support causal interpretation of transitions and predictive windows.
5.  **[Mandatory]** At the end of the report, you must include a section titled `## Reference List`.
6.  In this section, list the detailed information for all papers you **specifically mentioned** in the body of the report, using the following format:
    * [1. ] Title of the paper. (Publication Year)

---
Now, please begin your analysis based on the following data:
"""

    print("Step 2.1: Collecting all unique node IDs...")
    all_node_ids = set()
    for data in year_data.values():
        for node in data.get("nodes", []):
            node_id = safe_extract_id(node)
            if node_id != "Unknown":
                all_node_ids.add(node_id)

        for edge in data.get("edges", []):
            source = edge.get("source")
            target = edge.get("target")
            if source is not None:
                all_node_ids.add(str(source))
            if target is not None:
                all_node_ids.add(str(target))

    print(f"Found {len(all_node_ids)} unique nodes. Fetching info from ES...")

    node_info_list = []
    title, abstract, pub_year = get_paper_info(pid)
    root_paper_info = f"Center paper for analysis ID: {pid}\nTitle: {title}\nYear: {pub_year}\nAbstract: {abstract}\n"
    node_info_list.append({
        "id": str(pid),
        "title": title,
        "abstract": abstract,
        "publication_year": pub_year,
    })
    all_node_ids.add(str(pid))

    for node_id in sorted(all_node_ids):
        if node_id == str(pid):
            continue
        try:
            title, abstract, pub_year = get_paper_info(node_id)
            node_info_list.append({
                "id": node_id,
                "title": title,
                "abstract": abstract,
                "publication_year": pub_year,
            })
        except Exception as e:
            print(f"Error fetching info for node {node_id}: {e}")
            node_info_list.append({
                "id": node_id,
                "title": f"Paper_{node_id}",
                "abstract": "Abstract not available or fetching error.",
                "publication_year": "Unknown",
            })

    node_info_str = "## 4. Node Information (For your abstract analysis)\n\n"
    node_info_str += root_paper_info + "\n"
    node_info_str += json.dumps(node_info_list, ensure_ascii=False, indent=2)

    print("Step 2.2: Formatting structural, KE, VD and DPI data...")
    structure_info_str = "\n\n## 5. Idea Tree Annual Evolution Data (Structure and Entropy)\n\n"

    for year in sorted(year_data.keys()):
        structure_info_str += f"### Year {year}\n"
        involved_node_ids = set()

        current_year_nodes = year_data[year].get("nodes", [])
        for node in current_year_nodes:
            node_id = safe_extract_id(node)
            if node_id != "Unknown":
                involved_node_ids.add(node_id)

        edges = year_data[year].get("edges", [])
        edge_list = []
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source and target:
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
            str_node_id = str(node_id)
            if str_node_id in year_ke_data:
                filtered_ke_data[str_node_id] = smooth_ke_value(year_ke_data[str_node_id])

        structure_info_str += "**Node Knowledge Entropy (for nodes in this year's tree):**\n"
        if not filtered_ke_data:
            structure_info_str += "  - N/A\n"
        else:
            sorted_ke = sorted(filtered_ke_data.items(), key=lambda item: item[1], reverse=True)
            for node_id, ke_value in sorted_ke:
                structure_info_str += f"  - ID {node_id}: {ke_value:.4f}\n"

        structure_info_str += "\n"

    energy_info_str = build_energy_evidence_str(all_years, year2vd, year2dpi)
    final_prompt = prompt_instructions + node_info_str + structure_info_str + energy_info_str

    folder_path = os.path.join(OUTPUT_DIR, str(pid))
    os.makedirs(folder_path, exist_ok=True)
    file_suffix = build_file_suffix(pid, model_name, timestamp)
    prompt_path = os.path.join(folder_path, f"prompt_vd_dpi_{file_suffix}.txt")
    print(prompt_path)
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(final_prompt)

    if not call_model:
        return None

    print(f"Step 3: Calling completion API... (Prompt size: ~{len(final_prompt)} chars)")
    try:
        return completion(final_prompt, model_name)
    except Exception as e:
        print(f"Error calling completion API: {e}")
        return f"Error: Report generation failed. {e}"


def main(pid, call_model=True):
    model_name = "gpt-5.4-mini"
    # model_name = "deepseek-v4-pro"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    years = get_years(pid)
    output_dir = OUTPUT_DIR
    os.makedirs(f"{output_dir}/{pid}", exist_ok=True)
    print(f"Starting analysis of paper {pid} idea tree evolution with model {model_name}...")

    print("Step 1: Reading multi-year GML data")
    year_data = read_multiple_year_gmls(BASE_PATH, pid, years)

    ke_data = read_multiple_year_ke(KE_PATH, pid, years)
    year2vd, year2dpi = read_vd_dpi_data(pid, years)

    if not year_data:
        print("No valid GML data read")
        return
    if not ke_data:
        print("No valid KE data read")
        return

    final_report = generate_final_report(
        pid=pid,
        year_data=year_data,
        ke_data=ke_data,
        year2vd=year2vd,
        year2dpi=year2dpi,
        model_name=model_name,
        timestamp=timestamp,
        call_model=call_model,
    )
    if final_report is None:
        print("Prompt-only mode enabled. Completion API was not called.")
        return

    file_suffix = build_file_suffix(pid, model_name, timestamp)
    report_path = os.path.join(f"{output_dir}/{pid}", f"final_report_vd_dpi_{file_suffix}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_report)

    print("Analysis complete! Results saved to output directory")
    print("=" * 50)
    print(final_report)


if __name__ == "__main__":
    args = sys.argv[1:]
    prompt_only = "--prompt-only" in args
    pid_args = [arg for arg in args if arg != "--prompt-only"]
    pid = int(pid_args[0]) if pid_args else 2321807788
    main(pid, call_model=not prompt_only)
