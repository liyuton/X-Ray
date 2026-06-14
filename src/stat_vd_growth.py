#!/usr/bin/env python3
"""
Find PIDs whose visible depth has a large year-over-year increase.

The script reads generated VD JSON files from ../temp_files/year2visible_depth
and writes selected PID records to ../temp_files/vd_growth_ge2_pids.json.
"""

import json
import os


VD_DIR = "../temp_files/year2visible_depth"
OUTPUT_PATH = "../temp_files/vd_growth_ge2_pids.json"
MIN_DELTA_VD = 2


def read_year2vd(path):
    """Read a VD JSON file and normalize year keys and VD values to integers."""
    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    year2vd = {}
    for year, vd in raw_data.items():
        try:
            year2vd[int(year)] = int(vd)
        except (TypeError, ValueError):
            continue
    return year2vd


### xray: detect visible-depth jumps across generated yearly VD files ###
def find_large_vd_growth(vd_dir=VD_DIR, min_delta_vd=MIN_DELTA_VD):
    """Return PID records where VD increases by at least min_delta_vd."""
    records = []

    for file_name in sorted(os.listdir(vd_dir)):
        if not file_name.endswith(".json"):
            continue

        pid = file_name[:-5]
        file_path = os.path.join(vd_dir, file_name)
        year2vd = read_year2vd(file_path)
        years = sorted(year2vd)
        if len(years) < 2:
            continue

        spikes = []
        for index in range(1, len(years)):
            previous_year = years[index - 1]
            current_year = years[index]
            previous_vd = year2vd[previous_year]
            current_vd = year2vd[current_year]
            delta_vd = current_vd - previous_vd

            if delta_vd >= min_delta_vd:
                spikes.append({
                    "year": current_year,
                    "previous-year": previous_year,
                    "delta-vd": delta_vd,
                    "previous-vd": previous_vd,
                    "current-vd": current_vd,
                })

        if not spikes:
            continue

        max_spike = max(spikes, key=lambda item: (item["delta-vd"], item["year"]))
        records.append({
            "pid": pid,
            "max-delta-vd": max_spike["delta-vd"],
            "max-delta-vd-year": max_spike["year"],
            "previous-year": max_spike["previous-year"],
            "previous-vd": max_spike["previous-vd"],
            "current-vd": max_spike["current-vd"],
            "spikes": spikes,
        })

    return sorted(
        records,
        key=lambda item: (-item["max-delta-vd"], item["max-delta-vd-year"], item["pid"]),
    )


def main():
    records = find_large_vd_growth()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Scanned VD files: {len([f for f in os.listdir(VD_DIR) if f.endswith('.json')])}")
    print(f"Matched PIDs: {len(records)}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
