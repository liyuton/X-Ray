import os
import re
from pathlib import Path
import matplotlib.pyplot as plt

def count_nodes_and_edges(gml_file):
    """
    统计GML文件中的节点数和边数
    
    Args:
        gml_file: GML文件路径
        
    Returns:
        (nodes_count, edges_count)
    """
    with open(gml_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 统计节点数：计算 'node' 后跟 '[' 的出现次数（支持中间有任意空白符）
    nodes_count = len(re.findall(r'node\s*\[', content))
    
    # 统计边数：计算 'edge' 后跟 '[' 的出现次数（支持中间有任意空白符）
    edges_count = len(re.findall(r'edge\s*\[', content))
    
    return nodes_count, edges_count

def process_gml_folder(folder_path):
    """
    处理文件夹下所有GML文件，返回统计结果字典
    
    Args:
        folder_path: GML文件所在的文件夹路径
        
    Returns:
        字典，格式为 {年份: {'nodes': 节点数, 'edges': 边数}, ...}
    """
    result = {}
    
    # 获取文件夹下所有.gml文件
    gml_files = sorted(Path(folder_path).glob('*.gml'))
    
    for gml_file in gml_files:
        year = gml_file.stem  # 获取文件名（不含扩展名），即年份
        nodes_count, edges_count = count_nodes_and_edges(str(gml_file))
        result[year] = {
            'nodes': nodes_count,
            'edges': edges_count
        }
    
    return result

if __name__ == '__main__':
    folder_path = '/home/liyutong1117/jupyter/scientific_x_ray-github/temp_files/source_gml_by_year/2100837269'
    
    # 处理GML文件
    statistics = process_gml_folder(folder_path)
    
    # 输出字典
    print("GML文件统计结果:")
    print("=" * 60)
    for year in sorted(statistics.keys(), key=lambda x: int(x)):
        nodes = statistics[year]['nodes']
        edges = statistics[year]['edges']
        print(f"{year}: nodes={nodes}, edges={edges}")
    
    print("\n" + "=" * 60)
    print("完整字典:")
    print(statistics)
    
    # 统计总数
    total_nodes = sum(data['nodes'] for data in statistics.values())
    total_edges = sum(data['edges'] for data in statistics.values())
    print("\n" + "=" * 60)
    print(f"总计: nodes={total_nodes}, edges={total_edges}")
    
    # 绘制折线图
    print("\n" + "=" * 60)
    print("生成折线图...")
    
    # 按年份排序提取数据
    years = sorted(statistics.keys(), key=lambda x: int(x))
    nodes_list = [statistics[year]['nodes'] for year in years]
    edges_list = [statistics[year]['edges'] for year in years]
    
    # 创建折线图
    plt.figure(figsize=(14, 6))
    plt.plot(years, nodes_list, marker='o', linestyle='-', linewidth=2, label='Nodes', color='blue')
    plt.plot(years, edges_list, marker='s', linestyle='-', linewidth=2, label='Edges', color='red')
    
    # 设置图表标签和标题
    plt.xlabel('Year', fontsize=12)
    plt.ylabel('Count', fontsize=12)
    plt.title('Nodes and Edges Evolution Over Years', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    
    # X轴旋转显示，避免重叠
    plt.xticks(rotation=45, ha='right', fontsize=2)
    plt.tight_layout()
    
    # 保存图表
    output_path = '/home/liyutong1117/jupyter/scientific_x_ray-github/output/nodes_edges_trend.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"折线图已保存至: {output_path}")
    
    # # 显示图表
    # plt.show()
