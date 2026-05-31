#!/usr/bin/env python3
"""
Generate combined VD and DPI plots for all available PIDs.

Inputs:
    ../temp_files/year2visible_depth/{pid}.json
    ../temp_files/year2delta_d/{pid}.json

Output:
    ../output/vd_and_dpi/{pid}_VD_DPI.png

Rules:
    - For x-axis labels, if total years > 15, only show labels at years divisible by 5.
    - DPI value -99 is treated as unavailable and is not drawn as a line point.
"""

import json
import os
from textwrap import fill
from typing import Any, Dict, Optional, Set, Tuple

import matplotlib.pyplot as plt
import numpy as np
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


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def get_pid_set(folder: str) -> Set[str]:
    if not os.path.isdir(folder):
        return set()
    pids = set()
    for name in os.listdir(folder):
        if name.startswith('.') or not name.endswith('.json'):
            continue
        pids.add(name[:-5])
    return pids


def load_year_value_map(path: str) -> Dict[int, float]:
    data = json.load(open(path, 'r'))
    return {int(year): value for year, value in data.items()}


def year_labels(years):
    if len(years) > 15:
        return [str(y) if y % 5 == 0 else '' for y in years]
    return [str(y) for y in years]


def has_non_zero_vd(year2vd: Dict[int, float]) -> bool:
    for value in year2vd.values():
        try:
            if float(value) != 0.0:
                return True
        except (TypeError, ValueError):
            continue
    return False


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


def plot_pid(
    pid: str,
    year2vd: Dict[int, float],
    year2dpi: Dict[int, float],
    out_dir: str,
    paper_title: str,
) -> None:
    years = sorted(set(year2vd.keys()) | set(year2dpi.keys()))
    if not years:
        print(f'[Skip] {pid}: no year data.')
        return

    x = list(range(len(years)))
    vd_values = [year2vd.get(y, np.nan) for y in years]
    dpi_raw_values = [year2dpi.get(y, -99) for y in years]
    dpi_values = []
    dpi_colors = []
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

    # Top subplot: keep VD line style consistent with original script.
    ax_vd.plot(x, vd_values, lw=10, marker='o', ms=50, color='#ef3e59')
    ax_vd.set_title(wrap_title(paper_title), fontsize=80, weight='bold', pad=20)
    ax_vd.set_ylabel('Visible Depth', fontsize=80, weight='bold')
    ax_vd.tick_params(length=16, width=12, labelsize=80)
    ax_vd.spines['bottom'].set_linewidth(10)
    ax_vd.spines['left'].set_linewidth(10)
    ax_vd.yaxis.set_major_locator(MaxNLocator(integer=True))

    # Bottom subplot: keep DPI bar style from original script.
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

    # Shared x-axis with aligned year labels.
    ax_dpi.set_xticks(x)
    ax_dpi.set_xticklabels(year_labels(years), rotation=45, ha='right')
    ax_vd.tick_params(axis='x', labelbottom=False)

    ensure_dir(out_dir)
    fig.tight_layout()
    out_path = f'{out_dir}/{pid}_VD_DPI.png'
    fig.savefig(out_path)
    plt.close(fig)
    print(f'[Done] {pid}: {out_path}')


def main() -> None:
    vd_dir = '../temp_files/year2visible_depth'
    dpi_dir = '../temp_files/year2delta_d'
    out_dir = '../output/vd_and_dpi2'

    vd_pids = get_pid_set(vd_dir)
    dpi_pids = get_pid_set(dpi_dir)
    all_pids = sorted(vd_pids | dpi_pids)

    if not all_pids:
        print('No PID json files found in the input folders.')
        return

    print(f'Total PIDs detected: {len(all_pids)}')
    for pid in all_pids:
        vd_file = f'{vd_dir}/{pid}.json'
        dpi_file = f'{dpi_dir}/{pid}.json'

        if not os.path.exists(vd_file):
            print(f'[Skip] {pid}: missing {vd_file}')
            continue
        if not os.path.exists(dpi_file):
            print(f'[Skip] {pid}: missing {dpi_file}')
            continue

        try:
            year2vd = load_year_value_map(vd_file)
            year2dpi = load_year_value_map(dpi_file)
            if not has_non_zero_vd(year2vd):
                print(f'[Skip] {pid}: VD data is all zero.')
                continue

            paper_title, _, _ = get_paper_info_from_es(pid)
            plot_pid(pid, year2vd, year2dpi, out_dir, paper_title)
        except Exception as exc:
            print(f'[Error] {pid}: {exc}')


if __name__ == '__main__':
    main()
