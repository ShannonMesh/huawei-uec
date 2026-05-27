#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据包在网时延统计脚本
功能：解析 result.txt 中的 [NetworkDelay] 日志，生成每条流的在网时延统计 CSV
"""

import re
import sys
import os
import csv
from collections import defaultdict
import statistics


def parse_network_delay(result_file, flow_map_file=None):
    """
    解析 result.txt 文件中的 NetworkDelay 日志
    
    格式：[NetworkDelay] pkt_id=0 flow_id=1000000001 delay_us=2.449 stor_time=1.183 dtor_time=3.632
    
    返回：dict[flow_id] -> list of delay records
    """
    # 正则表达式匹配 NetworkDelay 行
    pattern = r'\[NetworkDelay\] pkt_id=(\d+) flow_id=(\d+) delay_us=([\d.]+) stor_time=([\d.]+) dtor_time=([\d.]+)'
    
    # 存储每个流的时延数据
    flow_delays = defaultdict(list)
    
    with open(result_file, 'r') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                pkt_id = int(match.group(1))
                flow_id = int(match.group(2))
                delay_us = float(match.group(3))
                stor_time = float(match.group(4))
                dtor_time = float(match.group(5))
                
                flow_delays[flow_id].append({
                    'pkt_id': pkt_id,
                    'delay_us': delay_us,
                    'stor_time': stor_time,
                    'dtor_time': dtor_time
                })
    
    return flow_delays


def load_flow_mapping(flow_map_file):
    """
    加载 flowid 到 flowname 的映射
    
    格式：flowid,flow_name
          1000000001,Uec_0_255
    """
    flow_map = {}
    if not os.path.exists(flow_map_file):
        return flow_map
    
    with open(flow_map_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            flow_id = int(row['flowid'])
            flow_name = row['flow_name']
            flow_map[flow_id] = flow_name
    
    return flow_map


def calculate_statistics(delay_list):
    """
    计算时延统计信息
    """
    delays = [d['delay_us'] for d in delay_list]
    
    if not delays:
        return {
            'count': 0,
            'mean': 0,
            'min': 0,
            'max': 0,
            'median': 0,
            'p99': 0,
            'p95': 0
        }
    
    delays_sorted = sorted(delays)
    n = len(delays_sorted)
    
    # 计算百分位数
    p95_idx = int(n * 0.95)
    p99_idx = int(n * 0.99)
    
    return {
        'count': n,
        'mean': statistics.mean(delays),
        'min': min(delays),
        'max': max(delays),
        'median': statistics.median(delays),
        'p95': delays_sorted[min(p95_idx, n-1)],
        'p99': delays_sorted[min(p99_idx, n-1)]
    }


def generate_csv(flow_delays, flow_map, output_file):
    """
    生成 CSV 统计文件
    """
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # 写入表头
        writer.writerow([
            'flow_id', 'flow_name', 'pkt_count',
            'delay_mean_us', 'delay_min_us', 'delay_max_us',
            'delay_median_us', 'delay_p95_us', 'delay_p99_us'
        ])
        
        # 按 flow_id 排序
        for flow_id in sorted(flow_delays.keys()):
            delays = flow_delays[flow_id]
            stats = calculate_statistics(delays)
            flow_name = flow_map.get(flow_id, f'Unknown_{flow_id}')
            
            writer.writerow([
                flow_id,
                flow_name,
                stats['count'],
                f"{stats['mean']:.3f}",
                f"{stats['min']:.3f}",
                f"{stats['max']:.3f}",
                f"{stats['median']:.3f}",
                f"{stats['p95']:.3f}",
                f"{stats['p99']:.3f}"
            ])
    
    print(f"Network delay statistics saved to: {output_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_network_delay.py <result.txt> [cwnd_flow_map.txt] [output.csv]")
        sys.exit(1)
    
    result_file = sys.argv[1]
    flow_map_file = sys.argv[2] if len(sys.argv) > 2 else None
    output_file = sys.argv[3] if len(sys.argv) > 3 else 'network_delay_stats.csv'
    
    if not os.path.exists(result_file):
        print(f"Error: Result file not found: {result_file}")
        sys.exit(1)
    
    # 解析在网时延数据
    flow_delays = parse_network_delay(result_file)
    
    if not flow_delays:
        print("Warning: No NetworkDelay data found in result file")
        sys.exit(0)
    
    # 加载流映射
    flow_map = {}
    if flow_map_file and os.path.exists(flow_map_file):
        flow_map = load_flow_mapping(flow_map_file)
    
    # 生成 CSV
    generate_csv(flow_delays, flow_map, output_file)
    
    # 打印汇总信息
    print(f"\nSummary:")
    print(f"  Total flows: {len(flow_delays)}")
    total_pkts = sum(len(delays) for delays in flow_delays.values())
    print(f"  Total packets: {total_pkts}")
    
    # 计算总体统计
    all_delays = []
    for delays in flow_delays.values():
        all_delays.extend([d['delay_us'] for d in delays])
    
    if all_delays:
        print(f"  Overall mean delay: {statistics.mean(all_delays):.3f} us")
        print(f"  Overall median delay: {statistics.median(all_delays):.3f} us")
        print(f"  Overall min delay: {min(all_delays):.3f} us")
        print(f"  Overall max delay: {max(all_delays):.3f} us")


if __name__ == '__main__':
    main()