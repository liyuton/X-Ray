import matplotlib.pyplot as plt
import numpy as np
import json
import os

# Create output directory
output_dir = "/home/liyutong1117/jupyter/scientific_x_ray-github/output"
os.makedirs(output_dir, exist_ok=True)

# Your data
data_str = '{"1985": -99, "1986": -99, "1987": -99, "1988": -99, "1989": -99, "1990": -99, "1991": -99, "1992": -99, "1993": -99, "1994": -99, "1995": -99, "1996": -99, "1997": -99, "1998": -99, "1999": -99, "2000": -99, "2001": 1.0537912435254897, "2002": 1.019647157378623, "2003": 0.45256726274511705, "2004": 0.5606099835688029, "2005": 0.2803313588602832, "2006": 0.022825512730130615, "2007": -0.12010849950912156, "2008": -0.223533953829613, "2009": -0.29430684897107534, "2010": -0.3802683495419971, "2011": -0.47883711055677797, "2012": -0.3649919099364292, "2013": 1.0245243808468918, "2014": 1.042596426564514, "2015": 0.5183607951966974, "2016": 0.1622380943787971, "2017": 0.004933043502501672, "2018": -0.06226751111962009, "2019": -0.21606820461997733, "2020": 1.0184840805486806, "2021": 1.0336390958754287, "2022": 0.4189265063345737, "2023": 0.07327569942978283, "2024": -0.16115967879864834, "2025": -0.35613015444619345}'

# Parse JSON data
data = json.loads(data_str)

# Separate years and values
years = list(map(int, data.keys()))
values = list(data.values())

# Replace -99 with NaN
dpi_values = [np.nan if x == -99 else x for x in values]

# Create full timeline chart
plt.figure(figsize=(15, 8))

# Plot line chart
line = plt.plot(years, dpi_values, marker='o', linewidth=2, markersize=6, 
                color='#2E86AB', markerfacecolor='#2E86AB', markeredgecolor='white', 
                markeredgewidth=1, label='DPI Value')

# Set axes
plt.xlabel('Year', fontsize=12, fontweight='bold')
plt.ylabel('DPI Value', fontsize=12, fontweight='bold')
plt.title('Annual DPI Value Trend (1985-2025)', fontsize=14, fontweight='bold', pad=20)

# Set x-axis ticks
plt.xticks(years[::2], rotation=45)  # Show label every 2 years

# Add grid
plt.grid(True, alpha=0.3, linestyle='--')

# Add zero line
plt.axhline(y=0, color='red', linestyle='-', alpha=0.5, linewidth=1)

# Add legend for missing data
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#2E86AB', label='Valid DPI Data'),
    Patch(facecolor='lightgray', label='Missing Data (VD=0)')
]
plt.legend(handles=legend_elements, loc='upper right')

# Highlight different data phases
plt.axvspan(2001, 2012, alpha=0.1, color='blue', label='Phase 1')
plt.axvspan(2013, 2019, alpha=0.1, color='green', label='Phase 2')
plt.axvspan(2020, 2025, alpha=0.1, color='orange', label='Phase 3')

# Adjust layout
plt.tight_layout()

# Save full timeline chart
full_chart_path = os.path.join(output_dir, "dpi_trend_full.png")
plt.savefig(full_chart_path, dpi=300, bbox_inches='tight')
print(f"Full timeline chart saved to: {full_chart_path}")

# Close current chart
plt.close()

# Create valid data segment chart (after 2001)
plt.figure(figsize=(12, 6))

# Filter data from 2001 onwards
valid_years = [year for year in years if year >= 2001]
valid_dpi = [dpi_values[years.index(year)] for year in valid_years]

# Plot valid data segment
plt.plot(valid_years, valid_dpi, marker='o', linewidth=2.5, markersize=8,
         color='#E15554', markerfacecolor='#E15554', markeredgecolor='white',
         markeredgewidth=1.5)

plt.xlabel('Year', fontsize=12, fontweight='bold')
plt.ylabel('DPI Value', fontsize=12, fontweight='bold')
plt.title('DPI Value Trend (2001-2025)', fontsize=14, fontweight='bold', pad=20)
plt.grid(True, alpha=0.3, linestyle='--')
plt.axhline(y=0, color='red', linestyle='-', alpha=0.5, linewidth=1)

# Add value labels for each data point
for i, (year, value) in enumerate(zip(valid_years, valid_dpi)):
    if not np.isnan(value):
        plt.annotate(f'{value:.2f}', (year, value), 
                    textcoords="offset points", xytext=(0,10), 
                    ha='center', fontsize=8, alpha=0.7)

plt.xticks(valid_years[::2], rotation=45)
plt.tight_layout()

# Save valid data segment chart
valid_chart_path = os.path.join(output_dir, "dpi_trend_valid.png")
plt.savefig(valid_chart_path, dpi=300, bbox_inches='tight')
print(f"Valid data segment chart saved to: {valid_chart_path}")

# Close current chart
plt.close()

# Create bar chart version for comparison
plt.figure(figsize=(14, 7))

# Plot only valid data as bar chart
valid_data = {year: value for year, value in data.items() if value != -99}
valid_years_bar = list(map(int, valid_data.keys()))
valid_values_bar = list(valid_data.values())

# Set colors: blue for positive values, red for negative values
colors = ['#2E86AB' if x >= 0 else '#E15554' for x in valid_values_bar]

bars = plt.bar(valid_years_bar, valid_values_bar, color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)

plt.xlabel('Year', fontsize=12, fontweight='bold')
plt.ylabel('DPI Value', fontsize=12, fontweight='bold')
plt.title('Annual DPI Value Distribution (2001-2025)', fontsize=14, fontweight='bold', pad=20)
plt.grid(True, alpha=0.3, linestyle='--', axis='y')
plt.axhline(y=0, color='black', linestyle='-', alpha=0.8, linewidth=1)

# Add value labels on bars
for bar, value in zip(bars, valid_values_bar):
    height = bar.get_height()
    va = 'bottom' if height >= 0 else 'top'
    y_offset = 0.02 if height >= 0 else -0.02
    plt.text(bar.get_x() + bar.get_width()/2., height + y_offset,
             f'{value:.2f}', ha='center', va=va, fontsize=8, fontweight='bold')

plt.xticks(valid_years_bar[::2], rotation=45)
plt.tight_layout()

# Save bar chart
bar_chart_path = os.path.join(output_dir, "dpi_bar_chart.png")
plt.savefig(bar_chart_path, dpi=300, bbox_inches='tight')
print(f"Bar chart saved to: {bar_chart_path}")

# Close current chart
plt.close()

print(f"\nAll charts successfully saved to '{output_dir}' folder:")
print(f"1. {full_chart_path}")
print(f"2. {valid_chart_path}")
print(f"3. {bar_chart_path}")