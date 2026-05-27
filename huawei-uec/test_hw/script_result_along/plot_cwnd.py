#!/usr/bin/env python3
"""
绘制窗口变化折线图
从cwnd_change.csv读取数据，支持随机选择指定数量的流进行绘制
"""
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import random
from pathlib import Path


def plot_cwnd(csv_file, output_file, num_flows=5, seed=None):
    """
    绘制窗口变化折线图
    
    Args:
        csv_file: 输入CSV文件路径
        output_file: 输出图片路径
        num_flows: 要显示的流数量（默认5条）
        seed: 随机种子（可选）
    """
    # 读取数据
    df = pd.read_csv(csv_file)
    
    if df.empty:
        print(f"错误: {csv_file} 为空文件")
        sys.exit(1)
    
    # 获取所有唯一的流
    all_flows = df['flow'].unique()
    total_flows = len(all_flows)
    
    print(f"总流数: {total_flows}")
    
    # 如果流数少于指定数量，则显示所有流
    if total_flows <= num_flows:
        selected_flows = all_flows
        print(f"流数不足{num_flows}，显示所有{total_flows}条流")
    else:
        # 设置随机种子（如果提供）
        if seed is not None:
            random.seed(seed)
        # 随机选择指定数量的流
        selected_flows = random.sample(list(all_flows), num_flows)
        print(f"随机选择{num_flows}条流显示 (seed={seed})")
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 颜色映射
    colors = plt.cm.tab10.colors
    
    # 为每个选中的流绘制折线
    for idx, flow_name in enumerate(selected_flows):
        flow_data = df[df['flow'] == flow_name].copy()
        
        # 按时间排序
        flow_data = flow_data.sort_values('time')
        
        # 绘制细线折线（不描点）
        color = colors[idx % len(colors)]
        ax.plot(flow_data['time'], flow_data['cwnd_after'],
                label=flow_name, color=color, linewidth=0.8, alpha=0.7, zorder=5)
    
    # 设置图形属性
    ax.set_xlabel('Time (us)', fontsize=12)
    ax.set_ylabel('Congestion Window (bytes)', fontsize=12)
    ax.set_title(f'Congestion Window Changes ({len(selected_flows)} flows)', fontsize=14)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)  # 纵坐标起点固定为0
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图片
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"图片已保存: {output_file}")
    
    # 显示统计信息
    print(f"\n选中流的统计信息:")
    for flow_name in selected_flows:
        flow_data = df[df['flow'] == flow_name]
        algo = flow_data['algo'].iloc[0] if not flow_data.empty else 'N/A'
        event_count = len(flow_data)
        min_cwnd = flow_data['cwnd_after'].min() if not flow_data.empty else 0
        max_cwnd = flow_data['cwnd_after'].max() if not flow_data.empty else 0
        print(f"  {flow_name}: {event_count} events, algo={algo}, cwnd=[{min_cwnd}, {max_cwnd}]")
    
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description='绘制窗口变化折线图',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s -i cwnd_change.csv -o cwnd_plot.png           # 默认显示5条流
  %(prog)s -i cwnd_change.csv -o cwnd_plot.png -n 10     # 显示10条流
  %(prog)s -i cwnd_change.csv -o cwnd_plot.png -n 5 -s 42 # 指定随机种子
        """
    )
    
    parser.add_argument('-i', '--input', required=True, help='输入CSV文件路径')
    parser.add_argument('-o', '--output', required=True, help='输出图片路径')
    parser.add_argument('-n', '--num-flows', type=int, default=5, 
                       help='要显示的流数量（默认5）')
    parser.add_argument('-s', '--seed', type=int, default=None,
                       help='随机种子（用于复现相同的流选择）')
    
    args = parser.parse_args()
    
    plot_cwnd(args.input, args.output, args.num_flows, args.seed)


if __name__ == "__main__":
    main()
