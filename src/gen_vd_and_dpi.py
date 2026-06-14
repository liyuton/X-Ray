#!/usr/bin/env python3
"""
vd_dpi_script.py

Compute Visible Depth (VD) and DPI (delta-D) for one or more PIDs,
using ORIGINAL plotting styles (font sizes, line widths, marker sizes)
from the provided legacy scripts.

All parameters (pids, thresholds) are configured INSIDE main().

Outputs:
    ../temp_files/year2visible_depth/{pid}.json
    ../temp_files/year2delta_d/{pid}.json
    {output_root}/{pid}/{threshold}_{pid}_VD_DPI.png
    or {output_root}/{pid}/threshold_{threshold}/{threshold}_{pid}_VD_DPI.png

X-axis rule:
    - total years > 15  -> label every 5 years
    - total years <=15 -> label every year
"""

import os
import json
from textwrap import fill
from typing import Any, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

try:
    from elasticsearch import Elasticsearch
except ImportError:
    Elasticsearch = None


ES_HOSTS = [
    'http://10.10.10.0:9200',
    'http://elastic:ai8WoTKcmzUC9AW$@10.10.12.1:9200',
    'http://readonly:readonly@10.10.12.1:9201',
]

# ============================================================
# Utilities
# ============================================================

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def init_es_client() -> Optional[Any]:
    if Elasticsearch is None:
        print('[Warn] elasticsearch package is not installed. Use fallback paper titles.')
        return None

    try:
        return Elasticsearch(ES_HOSTS[2])
    except Exception as exc:
        print(f'[Warn] Failed to init Elasticsearch client: {exc}')
        return None


es_client = init_es_client()


def get_year_list(pid: str):
    base = f'../temp_files/node_entropy_by_year/{pid}'
    years = sorted([int(f) for f in os.listdir(base) if not f.startswith('.')])
    return years


def get_paper_info_from_es(pid: str) -> Tuple[str, str, str]:
    """
    Get title and abstract from Elasticsearch by paper ID.
    Convert numeric ID to OpenAlex format: https://openalex.org/W{pid}
    Returns tuple (title, abstract, publication_year).
    """
    if es_client is None:
        return f'Paper_{pid}', 'Abstract not available', 'Unknown'

    try:
        openalex_id = f'https://openalex.org/W{pid}'
        query = {
            'query': {
                'term': {
                    '_id': openalex_id,
                }
            },
            '_source': ['title', 'abstract', 'publication_year'],
        }

        response = es_client.search(index='acemap.works', body=query)
        hits = response.get('hits', {}).get('hits', [])
        if hits:
            source = hits[0].get('_source', {})
            title = source.get('title', 'Title not found')
            abstract = source.get('abstract', 'Abstract not found')
            pub_year = source.get('publication_year', 'Year not found')
            return title, abstract, pub_year

        query_fallback = {
            'query': {
                'term': {
                    '_id': str(pid),
                }
            },
            '_source': ['title', 'abstract', 'publication_year'],
        }
        response_fallback = es_client.search(index='acemap.works', body=query_fallback)
        hits_fallback = response_fallback.get('hits', {}).get('hits', [])
        if hits_fallback:
            source = hits_fallback[0].get('_source', {})
            title = source.get('title', 'Title not found')
            abstract = source.get('abstract', 'Abstract not found')
            pub_year = source.get('publication_year', 'Year not found')
            return title, abstract, pub_year

        print(f'[Warn] No ES result for PID: {pid}')
        return f'Paper_{pid}', 'Abstract not available', 'Unknown'
    except Exception as exc:
        print(f'[Warn] Error querying ES for PID {pid}: {exc}')
        return f'Paper_{pid}', 'Abstract not available', 'Unknown'


def wrap_title(title: str, width: int = 52) -> str:
    clean_title = (title or '').strip()
    if not clean_title:
        return 'Untitled Paper'
    return fill(clean_title, width=width, break_long_words=False, break_on_hyphens=False)


# ============================================================
# VD computation
# ============================================================

def compute_visible_depth(pid: str, threshold: float):
    year2vd = {}
    for year in get_year_list(pid):
        pid2node_entropy = json.load(open(f'../temp_files/node_entropy_by_year/{pid}/{year}', 'r'))
        tree_node_deep = json.load(open(f'../temp_files/tree_deep_by_year/{pid}/{year}', 'r'))

        visible_depths = []
        for deep in tree_node_deep:
            for p_id in tree_node_deep[deep]:
                if float(pid2node_entropy.get(str(p_id), 0)) >= threshold:
                    visible_depths.append(int(deep))
                    break

        vd = 0 if len(visible_depths) == 0 else len(visible_depths) - 1
        year2vd[int(year)] = vd

    ensure_dir('../temp_files/year2visible_depth')
    json.dump({str(k): v for k, v in year2vd.items()},
              open(f'../temp_files/year2visible_depth/{pid}.json', 'w'))
    return year2vd


# ============================================================
# DPI computation (original logic)
# ============================================================

def get_delta_D_for_year(pid: str, year_now: int, threshold: float):
    pid2node_entropy_now = json.load(open(f'../temp_files/node_entropy_by_year/{pid}/{year_now}', 'r'))
    tree_node_deep_now = json.load(open(f'../temp_files/tree_deep_by_year/{pid}/{year_now}', 'r'))

    visible_depths = []
    for deep in tree_node_deep_now:
        for p_id in tree_node_deep_now[deep]:
            if float(pid2node_entropy_now.get(str(p_id), 0)) >= threshold:
                visible_depths.append(int(deep))
                break

    VD = 0 if len(visible_depths) == 0 else len(visible_depths) - 1
    if VD == 0:
        return -99

    if 0 in visible_depths:
        visible_depths.remove(0)

    sorted_visible_depths = sorted(visible_depths)
    tree_deep2visible_depth = {str(sorted_visible_depths[i]): i + 1 for i in range(len(sorted_visible_depths))}

    pid2tree_deep = {}
    for dp in tree_node_deep_now:
        for p_id in tree_node_deep_now[dp]:
            pid2tree_deep[str(p_id)] = dp

    candidates = [p_id for p_id in pid2node_entropy_now
                  if str(p_id) != str(pid) and float(pid2node_entropy_now[p_id]) >= threshold]

    year_list = get_year_list(pid)
    start_year = {}
    for y in year_list:
        ent = json.load(open(f'../temp_files/node_entropy_by_year/{pid}/{y}', 'r'))
        for p in candidates:
            if p in ent and float(ent[p]) >= threshold and p not in start_year:
                start_year[p] = y

    delta_vals = []
    for p in candidates:
        if p not in start_year:
            continue
        ke = float(pid2node_entropy_now[p])
        dt = max(1, year_now - start_year[p])
        delta_D = np.log10(ke / (dt ** 2))
        vd_term = VD - tree_deep2visible_depth[str(pid2tree_deep[p])]
        delta_vals.append(delta_D - vd_term)

    return max(delta_vals) if delta_vals else -99


def compute_delta_d_evolution(pid: str, threshold: float):
    year2dpi = {}
    for year in get_year_list(pid):
        year2dpi[int(year)] = get_delta_D_for_year(pid, year, threshold)

    ensure_dir('../temp_files/year2delta_d')
    json.dump({str(k): v for k, v in year2dpi.items()},
              open(f'../temp_files/year2delta_d/{pid}.json', 'w'))
    return year2dpi


# ============================================================
# Plotting (ORIGINAL STYLE)
# ============================================================

def _year_labels(years):
    if len(years) > 15:
        return [str(y) if y % 5 == 0 else '' for y in years]
    return [str(y) for y in years]


def _threshold_label(threshold: float) -> str:
    try:
        th_float = float(threshold)
        if th_float.is_integer():
            return str(int(th_float))
    except (TypeError, ValueError):
        pass
    return str(threshold)


def plot_vd(pid: str, threshold: float, out_dir: str):
    data = json.load(open(f'../temp_files/year2visible_depth/{pid}.json', 'r'))
    years = sorted([int(y) for y in data])
    values = [data[str(y)] for y in years]

    plt.figure(figsize=(42, 20), dpi=100)
    plt.plot(range(len(years)), values,
             lw=10, marker='o', ms=50, color='#ef3e59')

    plt.xticks(range(len(years)), _year_labels(years), rotation=45, ha='right')
    plt.title('Visible Depth Evolution', fontsize=100, weight='bold')
    plt.ylabel('Visible Depth', fontsize=80, weight='bold')
    plt.tick_params(length=16, width=12, labelsize=80)

    ax = plt.gca()
    ax.spines['bottom'].set_linewidth(10)
    ax.spines['left'].set_linewidth(10)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    ensure_dir(out_dir)
    plt.tight_layout()
    plt.savefig(f'{out_dir}/{int(threshold)}_{pid}_VD.png')
    plt.close()


def plot_dpi(pid: str, threshold: float, out_dir: str):
    data = json.load(open(f'../temp_files/year2delta_d/{pid}.json', 'r'))
    years = sorted([int(y) for y in data])

    values, colors = [], []
    for y in years:
        v = data[str(y)]
        if v == -99:
            values.append(0)
            colors.append('lightgray')
        else:
            values.append(v)
            colors.append('#2E86AB' if v >= 0 else '#E15554')

    plt.figure(figsize=(42, 20), dpi=100)
    bars = plt.bar(range(len(years)), values, color=colors,
                   edgecolor='black', linewidth=6, width=0.6)

    for i, c in enumerate(colors):
        if c == 'lightgray':
            bars[i].set_alpha(0)
            bars[i].set_edgecolor('gray')
            bars[i].set_linestyle(':')

    plt.xticks(range(len(years)), _year_labels(years), rotation=45, ha='right')
    plt.title('DPI Value Distribution', fontsize=100, weight='bold')
    plt.ylabel('DPI Value', fontsize=80, weight='bold')
    plt.tick_params(length=16, width=12, labelsize=80)

    ax = plt.gca()
    ax.spines['bottom'].set_linewidth(10)
    ax.spines['left'].set_linewidth(10)

    plt.axhline(0, color='black', linewidth=3)
    plt.grid(True, axis='y', linestyle='--', alpha=0.3)

    ensure_dir(out_dir)
    plt.tight_layout()
    plt.savefig(f'{out_dir}/{int(threshold)}_{pid}_DPI.png')
    plt.close()


def plot_vd_and_dpi(pid: str, threshold: float, out_dir: str, paper_title: str):
    year2vd_raw = json.load(open(f'../temp_files/year2visible_depth/{pid}.json', 'r'))
    year2dpi_raw = json.load(open(f'../temp_files/year2delta_d/{pid}.json', 'r'))
    year2vd = {int(year): value for year, value in year2vd_raw.items()}
    year2dpi = {int(year): value for year, value in year2dpi_raw.items()}

    years = sorted(set(year2vd.keys()) | set(year2dpi.keys()))
    if not years:
        print(f'[Skip] {pid}: no year data.')
        return

    x = list(range(len(years)))
    vd_values = [year2vd.get(y, np.nan) for y in years]
    dpi_raw_values = [year2dpi.get(y, -99) for y in years]

    dpi_values, dpi_colors = [], []
    for v in dpi_raw_values:
        if v == -99:
            dpi_values.append(0)
            dpi_colors.append('lightgray')
        else:
            dpi_values.append(v)
            dpi_colors.append('#2E86AB' if v >= 0 else '#E15554')

    fig, (ax_vd, ax_dpi) = plt.subplots(
        2,
        1,
        figsize=(42, 40),
        dpi=100,
        sharex=True,
        gridspec_kw={'height_ratios': [1, 1], 'hspace': 0.08},
    )

    ax_vd.plot(x, vd_values, lw=10, marker='o', ms=50, color='#ef3e59')
    ax_vd.set_title(wrap_title(paper_title), fontsize=80, weight='bold', pad=20)
    ax_vd.set_ylabel('Visible Depth', fontsize=80, weight='bold')
    ax_vd.tick_params(length=16, width=12, labelsize=80)
    ax_vd.tick_params(axis='x', labelbottom=False)
    ax_vd.spines['bottom'].set_linewidth(10)
    ax_vd.spines['left'].set_linewidth(10)
    ax_vd.yaxis.set_major_locator(MaxNLocator(integer=True))

    bars = ax_dpi.bar(
        x,
        dpi_values,
        color=dpi_colors,
        edgecolor='black',
        linewidth=6,
        width=0.6,
    )
    for i, c in enumerate(dpi_colors):
        if c == 'lightgray':
            bars[i].set_alpha(0)
            bars[i].set_edgecolor('gray')
            bars[i].set_linestyle(':')

    ax_dpi.set_ylabel('DPI Value', fontsize=80, weight='bold')
    ax_dpi.tick_params(length=16, width=12, labelsize=80)
    ax_dpi.spines['bottom'].set_linewidth(10)
    ax_dpi.spines['left'].set_linewidth(10)
    ax_dpi.axhline(0, color='black', linewidth=3)
    ax_dpi.axhline(1, color='black', linewidth=4, linestyle='--')
    ax_dpi.grid(True, axis='y', linestyle='--', alpha=0.3)
    ax_dpi.set_xticks(x)
    ax_dpi.set_xticklabels(_year_labels(years), rotation=45, ha='right')

    ensure_dir(out_dir)
    fig.subplots_adjust(top=0.90, bottom=0.12, left=0.10, right=0.98, hspace=0.12)
    out_path = f'{out_dir}/{_threshold_label(threshold)}_{pid}_VD_DPI.png'
    fig.savefig(out_path, bbox_inches='tight')
    plt.close(fig)
    print(f'[Done] {pid}: {out_path}')


# ============================================================
# Main
# ============================================================

def main():
    # ================= USER CONFIG =================
    # PIDs to process
    # pids = ['2100837269']
    # pids = ["2113233457","2137775453"]
    pids = ["3177828909"]
    # pids = [
    # '4313324526',
    # '1575585006',
    # '1486722793',
    # '2094366129',
    # '2063264144',
    # '1538902372',
    # '2137590150',
    # '2129319296',
    # '2033541702']
    # Thresholds for entropy (can specify multiple)
    thresholds = [10]
    # output_root = '../output/20260108zhangtao'
    output_root = '../output/20260607_alphafold' 
    # ===============================================

    use_default_threshold_dir = len(thresholds) == 1 and float(thresholds[0]) == 10.0

    for pid in pids:
        paper_title, _, _ = get_paper_info_from_es(pid)
        for th in thresholds:
            print(f'Processing PID={pid}, threshold={th}')
            compute_visible_depth(pid, th)
            compute_delta_d_evolution(pid, th)

            if use_default_threshold_dir:
                out_dir = f'{output_root}/{pid}'
            else:
                out_dir = f'{output_root}/{pid}/threshold_{_threshold_label(th)}'
            plot_vd_and_dpi(pid, th, out_dir, paper_title)


if __name__ == '__main__':
    main()
