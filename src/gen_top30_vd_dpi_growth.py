#!/usr/bin/env python3
"""
Plot VD/DPI evolution for the top 30 max-delta-vd PIDs in two result files.

The script reads precomputed VD and DPI JSON files. It does not recompute
metrics, so it can compare results from different repository roots.
"""

import json
import os
import re
from textwrap import fill

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator


DATASETS = {
    "lyt": "/home/liyutong1117/jupyter/scientific_x_ray-lyt",
    "github": "/home/liyutong1117/jupyter/scientific_x_ray-github",
}
TOP_N = 30
OUTPUT_ROOT = "../output/top30_vd_dpi_growth"
SUMMARY_PATH = os.path.join(OUTPUT_ROOT, "top30_vd_dpi_growth_pids.json")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _year_labels(years):
    if len(years) > 15:
        return [str(y) if y % 5 == 0 else "" for y in years]
    return [str(y) for y in years]


def normalize_year_metric(raw_data):
    year_metric = {}
    for year, value in raw_data.items():
        try:
            year_metric[int(year)] = value
        except (TypeError, ValueError):
            continue
    return year_metric


def clean_title(title):
    title = re.sub(r"<[^>]+>", "", str(title or "")).strip()
    title = " ".join(title.split())
    return title


def load_pid_title_map(root):
    pid_list_path = os.path.join(root, "src", "pid_list.json")
    if not os.path.exists(pid_list_path):
        return {}

    data = read_json(pid_list_path)
    title_map = {}
    for item in data.get("details", []):
        pid_value = item.get("pid")
        title = clean_title(item.get("title"))
        if pid_value and title:
            title_map[str(pid_value)] = title
    return title_map


def read_title_from_gml(root, pid):
    source_dir = os.path.join(root, "temp_files", "source_gml_by_year", str(pid))
    if not os.path.isdir(source_dir):
        return None

    gml_files = sorted(
        [file_name for file_name in os.listdir(source_dir) if file_name.endswith(".gml")],
        reverse=True,
    )
    for file_name in gml_files:
        path = os.path.join(source_dir, file_name)
        node_id = None
        node_label = None

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped = line.strip()
                if stripped == "node":
                    node_id = None
                    node_label = None
                    continue

                if stripped.startswith("id "):
                    node_id = stripped.split(" ", 1)[1].strip().strip('"')
                elif stripped.startswith("label "):
                    node_label = stripped.split(" ", 1)[1].strip().strip('"')

                if node_id == str(pid) and node_label:
                    return clean_title(node_label)
    return None


def get_paper_title(root, title_map, pid):
    title = title_map.get(str(pid))
    if title:
        return title

    title = read_title_from_gml(root, pid)
    if title:
        return title

    return f"PID {pid}"


def get_top_growth_records(root, top_n=TOP_N):
    result_path = os.path.join(root, "temp_files", "vd_growth_ge2_pids.json")
    records = read_json(result_path)
    indexed_records = list(enumerate(records))
    ranked_records = sorted(
        indexed_records,
        key=lambda item: (-item[1].get("max-delta-vd", -999), item[0]),
    )
    return [record for _, record in ranked_records[:top_n]]


def read_metric(root, metric_dir, pid):
    metric_path = os.path.join(root, "temp_files", metric_dir, f"{pid}.json")
    return normalize_year_metric(read_json(metric_path))


### xray: plot top visible-depth growth PID VD/DPI evidence ###
def plot_vd_and_dpi(dataset, root, record, rank, out_dir):
    pid = str(record["pid"])
    year2vd = read_metric(root, "year2visible_depth", pid)
    year2dpi = read_metric(root, "year2delta_d", pid)

    years = sorted(set(year2vd.keys()) | set(year2dpi.keys()))
    if not years:
        print(f"[Skip] {dataset} rank={rank} pid={pid}: no year data.")
        return None

    x = list(range(len(years)))
    vd_values = [year2vd.get(year, np.nan) for year in years]
    dpi_raw_values = [year2dpi.get(year, -99) for year in years]

    dpi_values = []
    dpi_colors = []
    for value in dpi_raw_values:
        if value == -99:
            dpi_values.append(0)
            dpi_colors.append("lightgray")
        else:
            dpi_values.append(value)
            dpi_colors.append("#2E86AB" if value >= 0 else "#E15554")

    fig, (ax_vd, ax_dpi) = plt.subplots(
        2,
        1,
        figsize=(42, 40),
        dpi=100,
        sharex=True,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.08},
    )

    paper_title = get_paper_title(root, plot_vd_and_dpi.title_maps[dataset], pid)
    metric_title = (
        f"{dataset} | PID {pid} | "
        f"max-delta-vd={record['max-delta-vd']} in {record['max-delta-vd-year']}"
    )
    title = f"{metric_title}\n{fill(paper_title, width=80)}"
    ax_vd.plot(x, vd_values, lw=10, marker="o", ms=50, color="#ef3e59")
    ax_vd.set_title(title, fontsize=80, weight="bold", pad=20)
    ax_vd.set_ylabel("Visible Depth", fontsize=80, weight="bold")
    ax_vd.tick_params(length=16, width=12, labelsize=80)
    ax_vd.tick_params(axis="x", labelbottom=False)
    ax_vd.spines["bottom"].set_linewidth(10)
    ax_vd.spines["left"].set_linewidth(10)
    ax_vd.yaxis.set_major_locator(MaxNLocator(integer=True))

    bars = ax_dpi.bar(
        x,
        dpi_values,
        color=dpi_colors,
        edgecolor="black",
        linewidth=6,
        width=0.6,
    )
    for index, color in enumerate(dpi_colors):
        if color == "lightgray":
            bars[index].set_alpha(0)
            bars[index].set_edgecolor("gray")
            bars[index].set_linestyle(":")

    ax_dpi.set_ylabel("DPI Value", fontsize=80, weight="bold")
    ax_dpi.tick_params(length=16, width=12, labelsize=80)
    ax_dpi.spines["bottom"].set_linewidth(10)
    ax_dpi.spines["left"].set_linewidth(10)
    ax_dpi.axhline(0, color="black", linewidth=3)
    ax_dpi.axhline(1, color="black", linewidth=4, linestyle="--")
    ax_dpi.grid(True, axis="y", linestyle="--", alpha=0.3)
    ax_dpi.set_xticks(x)
    ax_dpi.set_xticklabels(_year_labels(years), rotation=45, ha="right")

    ensure_dir(out_dir)
    out_path = os.path.join(
        out_dir,
        f"{rank:02d}_{pid}_max_delta_vd_{record['max-delta-vd']}_VD_DPI.png",
    )
    fig.subplots_adjust(top=0.90, bottom=0.12, left=0.10, right=0.98, hspace=0.12)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[Done] {dataset} rank={rank} pid={pid}: {out_path}")
    return out_path


def build_summary_record(dataset, rank, record, figure_path):
    return {
        "dataset": dataset,
        "rank": rank,
        "pid": str(record["pid"]),
        "max-delta-vd": record["max-delta-vd"],
        "max-delta-vd-year": record["max-delta-vd-year"],
        "previous-year": record.get("previous-year"),
        "previous-vd": record.get("previous-vd"),
        "current-vd": record.get("current-vd"),
        "figure-path": figure_path,
    }


def main():
    summary_records = []
    plot_vd_and_dpi.title_maps = {
        dataset: load_pid_title_map(root)
        for dataset, root in DATASETS.items()
    }

    for dataset, root in DATASETS.items():
        top_records = get_top_growth_records(root)
        out_dir = os.path.join(OUTPUT_ROOT, dataset)

        for rank, record in enumerate(top_records, start=1):
            figure_path = plot_vd_and_dpi(dataset, root, record, rank, out_dir)
            if figure_path is None:
                continue
            summary_records.append(build_summary_record(dataset, rank, record, figure_path))

    write_json(SUMMARY_PATH, summary_records)
    print(f"[Done] wrote summary: {SUMMARY_PATH}")
    print(f"[Done] plotted figures: {len(summary_records)}")


if __name__ == "__main__":
    main()
