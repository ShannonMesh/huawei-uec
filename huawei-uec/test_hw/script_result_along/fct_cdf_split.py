#!/usr/bin/env python3

import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def parse_flow_id(flow_id_str):
    """从flow_id字符串中提取数字部分"""
    try:
        return int(flow_id_str) % 1000000000
    except:
        return 0

def is_odd_group(flow_id_num):
    """判断流是否属于奇数组 (2n+1, n=0-31)"""
    last_digits = flow_id_num % 100000000
    for n in range(32):
        if last_digits == (2 * n + 1):
            return True
    return False

def load_fct_data(result_dir, experiment_name):
    """从实验目录加载FCT数据"""
    exp_dir = os.path.join(result_dir, experiment_name)
    csv_file = os.path.join(exp_dir, 'flow_fct_details.csv')
    
    odd_group_fcts = []
    even_group_fcts = []
    odd_group_dst_bytes = {}   # 奇数组按目的地址累加流量
    even_group_dst_bytes = {}  # 其他组按目的地址累加流量
    
    if not os.path.exists(csv_file):
        print(f"警告: 找不到文件 {csv_file}")
        return odd_group_fcts, even_group_fcts, 0, 0
    
    with open(csv_file, 'r') as f:
        lines = f.readlines()
        if len(lines) <= 1:
            return odd_group_fcts, even_group_fcts, 0, 0
        
        for line in lines[1:]:
            parts = line.strip().split(',')
            if len(parts) >= 9:
                try:
                    flow_id_str = parts[1]
                    dst_id = int(parts[3])
                    fct = float(parts[4])
                    total_bytes = int(parts[8])
                    
                    flow_id_num = parse_flow_id(flow_id_str)
                    
                    if is_odd_group(flow_id_num):
                        odd_group_fcts.append(fct)
                        odd_group_dst_bytes[dst_id] = odd_group_dst_bytes.get(dst_id, 0) + total_bytes
                    else:
                        even_group_fcts.append(fct)
                        even_group_dst_bytes[dst_id] = even_group_dst_bytes.get(dst_id, 0) + total_bytes
                except:
                    continue
    
    # 总流量 = 该组中流量最大的目的地址的流量
    odd_max_bytes = max(odd_group_dst_bytes.values()) if odd_group_dst_bytes else 0
    even_max_bytes = max(even_group_dst_bytes.values()) if even_group_dst_bytes else 0
    
    return odd_group_fcts, even_group_fcts, odd_max_bytes, even_max_bytes

def generate_cdf_plot(data_dict, output_file, title):
    """生成CDF图"""
    plt.figure(figsize=(12, 8))
    
    for exp_name, fcts in data_dict.items():
        if fcts:
            fcts_sorted = sorted(fcts)
            cdf = np.arange(1, len(fcts_sorted) + 1) / len(fcts_sorted)
            max_fct = max(fcts)
            plt.plot(fcts_sorted, cdf, marker='.', markersize=2, linestyle='-', linewidth=1.0,
                    label=f'{exp_name}, tail={max_fct:.2f}us')
    
    plt.title(title)
    plt.xlabel('FCT (us)')
    plt.ylabel('CDF')
    plt.legend(loc='best', bbox_to_anchor=(1.02, 1), borderaxespad=0.1, fontsize=8)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_file, format='png', dpi=300)
    plt.close()
    print(f"生成图表: {output_file}")

def update_experiment_details(summary_dir, result_dir, experiments):
    """更新experiment_details.csv，添加两组的CCT、总流量和带宽列"""
    csv_file = os.path.join(summary_dir, 'experiment_details.csv')
    if not os.path.exists(csv_file):
        print(f"警告: 找不到 {csv_file}")
        return
    
    with open(csv_file, 'r') as f:
        lines = f.readlines()
    
    if len(lines) < 2:
        return
    
    header = lines[0].strip().split(',')
    
    # 移除已存在的分组列
    new_cols = ['Odd_Group_CCT_us', 'Odd_Group_Max_Bytes', 'Odd_Group_Bandwidth_Gbps',
                'Even_Group_CCT_us', 'Even_Group_Max_Bytes', 'Even_Group_Bandwidth_Gbps']
    for col in new_cols:
        if col in header:
            idx = header.index(col)
            header = header[:idx]
    
    new_header = header + new_cols
    new_lines = [','.join(new_header) + '\n']
    
    for line in lines[1:]:
        parts = line.strip().split(',')
        exp_name = parts[0]
        
        # 直接从flow_fct_details.csv获取分组数据和总流量
        odd_fcts, even_fcts, odd_max_bytes, even_max_bytes = load_fct_data(result_dir, exp_name)
        
        # 计算CCT（最大FCT）
        odd_cct = max(odd_fcts) if odd_fcts else 0
        even_cct = max(even_fcts) if even_fcts else 0
        
        # 计算带宽 = 总流量 * 8 / CCT / 1e9
        odd_bw = (odd_max_bytes * 8) / (odd_cct * 1e-6) / 1e9 if odd_cct > 0 and odd_max_bytes > 0 else 0
        even_bw = (even_max_bytes * 8) / (even_cct * 1e-6) / 1e9 if even_cct > 0 and even_max_bytes > 0 else 0
        
        base_parts = parts[:len(header)]
        new_line = base_parts + [
            f'{odd_cct:.2f}', f'{odd_max_bytes}', f'{odd_bw:.2f}',
            f'{even_cct:.2f}', f'{even_max_bytes}', f'{even_bw:.2f}'
        ]
        new_lines.append(','.join(str(x) for x in new_line) + '\n')
    
    with open(csv_file, 'w') as f:
        f.writelines(new_lines)
    print(f"更新CSV文件: {csv_file}")

def main():
    if len(sys.argv) < 2:
        print("用法: python3 fct_cdf_split.py <实验组文件>")
        sys.exit(1)
    
    exp_group_file = sys.argv[1]
    if not os.path.exists(exp_group_file):
        print(f"错误: 实验组文件不存在: {exp_group_file}")
        sys.exit(1)
    
    base_name = os.path.basename(exp_group_file)
    result_suffix = base_name.replace('experiment_group_', '').replace('.json', '')
    
    base_dir = os.path.dirname(exp_group_file)
    result_dir = os.path.join(base_dir, f'result_{result_suffix}')
    summary_dir = os.path.join(result_dir, '概要')
    
    if not os.path.exists(result_dir):
        print(f"错误: 结果目录不存在: {result_dir}")
        sys.exit(1)
    
    if not os.path.exists(summary_dir):
        os.makedirs(summary_dir)
    
    with open(exp_group_file, 'r') as f:
        exp_group = json.load(f)
    
    experiments = exp_group.get('experiments', [])
    
    odd_group_data = {}
    even_group_data = {}
    
    for exp in experiments:
        exp_name = exp['name']
        print(f"处理实验: {exp_name}")
        
        odd_fcts, even_fcts, odd_max_bytes, even_max_bytes = load_fct_data(result_dir, exp_name)
        
        if odd_fcts:
            odd_group_data[exp_name] = odd_fcts
            print(f"  奇数组(2n+1): {len(odd_fcts)} 条流, 总流量: {odd_max_bytes} bytes")
        if even_fcts:
            even_group_data[exp_name] = even_fcts
            print(f"  其他组: {len(even_fcts)} 条流, 总流量: {even_max_bytes} bytes")
    
    if odd_group_data:
        output_file = os.path.join(summary_dir, 'fcts_cdf_odd_group.png')
        generate_cdf_plot(odd_group_data, output_file, 'ECDF for FCTs (Odd Group: 2n+1, n=0-31)')
    
    if even_group_data:
        output_file = os.path.join(summary_dir, 'fcts_cdf_even_group.png')
        generate_cdf_plot(even_group_data, output_file, 'ECDF for FCTs (Even Group: Others)')
    
    update_experiment_details(summary_dir, result_dir, experiments)
    
    print("\n完成!")

if __name__ == '__main__':
    main()
