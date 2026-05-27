#!/usr/bin/env python3
"""
解析cwnd事件文件，生成每个流的拥塞窗口变化CSV和PNG图表
"""

import re
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import argparse
from collections import defaultdict


def parse_cwnd_events(filename):
    """解析cwnd事件文件"""
    events = defaultdict(list)

    with open(filename, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # 解析事件行
            # 格式: <timestamp> <event_type> <node_id> <flow_id> <cwnd>
            parts = line.split()
            if len(parts) < 5:
                print(f"警告: 第{line_num}行格式不正确，跳过")
                continue

            try:
                timestamp = float(parts[0])
                event_type = parts[1]
                node_id = int(parts[2])
                flow_id = parts[3]
                cwnd = int(parts[4])

                events[flow_id].append({
                    'timestamp': timestamp,
                    'event_type': event_type,
                    'node_id': node_id,
                    'cwnd': cwnd
                })
            except ValueError as e:
                print(f"警告: 第{line_num}行解析错误: {e}")
                continue

    return events


def create_cwnd_csv(flow_id, events_list, output_dir):
    """为单个流生成cwnd变化CSV"""
    if not events_list:
        return None

    # 按时间排序
    sorted_events = sorted(events_list, key=lambda x: x['timestamp'])

    # 准备数据
    data = []
    for event in sorted_events:
        data.append({
            'timestamp': event['timestamp'],
            'event_type': event['event_type'],
            'node_id': event['node_id'],
            'cwnd': event['cwnd']
        })

    # 创建DataFrame并保存
    df = pd.DataFrame(data)
    csv_path = os.path.join(output_dir, f'cwnd_flow_{flow_id}.csv')
    df.to_csv(csv_path, index=False)
    return csv_path


def plot_cwnd_curve(flow_id, events_list, output_dir):
    """绘制单个流的cwnd变化曲线"""
    if not events_list or len(events_list) < 2:
        return None

    # 按时间排序
    sorted_events = sorted(events_list, key=lambda x: x['timestamp'])

    # 提取数据
    timestamps = [e['timestamp'] for e in sorted_events]
    cwnds = [e['cwnd'] for e in sorted_events]

    # 创建图表
    plt.figure(figsize=(12, 6))
    plt.plot(timestamps, cwnds, marker='o', linewidth=2, markersize=4)
    plt.xlabel('Time')
    plt.ylabel('CWND')
    plt.title(f'CWND vs Time - Flow {flow_id}')
    plt.grid(True, alpha=0.3)

    # 保存图表
    png_path = os.path.join(output_dir, f'cwnd_flow_{flow_id}.png')
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.close()
    return png_path


def main():
    parser = argparse.ArgumentParser(
        description='解析cwnd事件文件，生成每个流的拥塞窗口变化CSV和PNG图表',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s /path/to/cwnd_events.txt -o /path/to/output
  %(prog)s ./cwnd_events.txt
        '''
    )
    parser.add_argument('input_file', nargs='?',
                        help='cwnd事件文件路径')
    parser.add_argument('-i', '--input', dest='input_file_opt',
                        help='cwnd事件文件路径（与位置参数二选一）')
    parser.add_argument('-o', '--output', default='./cwnd_output',
                        help='输出目录路径 (默认: ./cwnd_output)')
    parser.add_argument('--no-png', action='store_true',
                        help='不生成PNG图表')

    args = parser.parse_args()

    # 确定输入文件
    input_file = args.input_file_opt or args.input_file
    if not input_file:
        parser.error("必须提供输入文件，使用 -i 或位置参数")

    # 检查文件是否存在
    if not os.path.exists(input_file):
        print(f"错误: 文件不存在: {input_file}")
        sys.exit(1)

    # 创建输出目录
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    print(f"解析文件: {input_file}")
    print(f"输出目录: {output_dir}")
    print()

    # 解析事件
    events = parse_cwnd_events(input_file)

    print(f"共解析到 {len(events)} 个流的事件")
    print()

    # 为每个流生成CSV和PNG
    csv_count = 0
    png_count = 0
    for flow_id, events_list in events.items():
        # 生成CSV
        csv_path = create_cwnd_csv(flow_id, events_list, output_dir)
        if csv_path:
            csv_count += 1
            print(f"生成CSV: {csv_path}")

        # 生成PNG
        if not args.no_png:
            png_path = plot_cwnd_curve(flow_id, events_list, output_dir)
            if png_path:
                png_count += 1
                print(f"生成PNG: {png_path}")

    print()
    print(f"完成!")
    print(f"生成了 {csv_count} 个CSV文件, {png_count} 个PNG图表")
    print(f"输出目录: {output_dir}")


if __name__ == '__main__':
    main()
