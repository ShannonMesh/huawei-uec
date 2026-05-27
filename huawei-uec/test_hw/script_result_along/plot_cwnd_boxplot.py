#!/usr/bin/env python3
"""
绘制窗口大小箱线图
从cwnd_change.csv读取数据，为每个实验生成窗口大小的箱线图
"""
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import re
from pathlib import Path


def plot_cwnd_boxplot(input_dir, output_dir):
    """
    为每个实验生成窗口大小箱线图
    读取数据中的总时间，将时间分成五段，取中间三段的数据进行统计
    
    Args:
        input_dir: 输入目录，包含多个实验子目录
        output_dir: 输出目录
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取所有实验目录
    experiment_dirs = []
    for entry in os.listdir(input_dir):
        entry_path = os.path.join(input_dir, entry)
        if os.path.isdir(entry_path):
            experiment_dirs.append(entry_path)
    
    if not experiment_dirs:
        print(f"错误: 在 {input_dir} 中未找到实验目录")
        sys.exit(1)
    
    print(f"找到 {len(experiment_dirs)} 个实验目录")
    
    # 收集所有实验的窗口数据
    all_cwnd_data = {}
    
    for exp_dir in experiment_dirs:
        exp_name = os.path.basename(exp_dir)
        csv_file = os.path.join(exp_dir, 'cwnd_change.csv')
        
        if not os.path.exists(csv_file):
            print(f"跳过 {exp_name}: 未找到 cwnd_change.csv")
            continue
        
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            print(f"跳过 {exp_name}: 读取文件失败 - {e}")
            continue
        
        if df.empty or 'cwnd_after' not in df.columns or 'time' not in df.columns:
            print(f"跳过 {exp_name}: 数据为空或格式不正确")
            continue
        
        # 获取时间范围
        min_time = df['time'].min()
        max_time = df['time'].max()
        total_time = max_time - min_time
        
        # 将时间分成5段，取中间3段 (第2、3、4段)
        segment_size = total_time / 5
        start_time = min_time + segment_size  # 第2段开始
        end_time = min_time + 4 * segment_size  # 第4段结束
        
        # 过滤中间3段的数据
        filtered_df = df[(df['time'] >= start_time) & (df['time'] <= end_time)]
        
        # 获取窗口值
        cwnd_values = filtered_df['cwnd_after'].tolist()
        all_cwnd_data[exp_name] = cwnd_values
        print(f"{exp_name}: 总时间 {total_time:.2f}s, 取中间3段时间 [{start_time:.2f}, {end_time:.2f}], 共 {len(cwnd_values)} 个窗口数据点")
    
    if not all_cwnd_data:
        print("错误: 未找到有效的窗口数据")
        sys.exit(1)
    
    # 按均值排序（从小到大）
    sorted_exp_names = sorted(all_cwnd_data.keys(), key=lambda name: np.mean(all_cwnd_data[name]))
    cwnd_data = [all_cwnd_data[name] for name in sorted_exp_names]
    
    # 根据箱线数量动态计算图表宽度和箱体宽度
    n_exps = len(sorted_exp_names)
    # 每个箱线至少占用 2 英寸宽度，最小宽度 10 英寸
    fig_width = max(10, n_exps * 2)
    fig_height = 7
    
    # 箱体宽度：实验越多，箱体越窄
    # 2个实验时宽度0.6，10个实验时宽度0.4，更多实验时更窄
    box_width = max(0.2, min(0.6, 0.7 - n_exps * 0.03))
    
    # 创建箱线图
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    
    # 绘制箱线图
    bp = ax.boxplot(cwnd_data, tick_labels=sorted_exp_names, patch_artist=True,
                    positions=range(1, n_exps + 1), widths=box_width)
    
    # 设置箱体颜色
    colors = plt.cm.Set3(np.linspace(0, 1, len(sorted_exp_names)))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
    
    # 计算并标注均值（在箱体右侧）
    for i, (data, name) in enumerate(zip(cwnd_data, sorted_exp_names), 1):
        mean_val = np.mean(data)
        ax.text(i + 0.35, mean_val, f'{mean_val:.0f}',
                ha='left', va='center', fontsize=9, color='red', fontweight='bold')
    
    # 设置图形属性
    ax.set_xlabel('Experiment', fontsize=12)
    ax.set_ylabel('Congestion Window (bytes)', fontsize=12)
    ax.set_title('Congestion Window Distribution by Experiment', fontsize=14)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(bottom=0)  # 纵坐标起点固定为0
    
    # 设置x轴刻度
    ax.set_xticks(range(1, len(sorted_exp_names) + 1))
    ax.set_xticklabels(sorted_exp_names, rotation=45, ha='right')
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图片
    output_file = os.path.join(output_dir, 'cwnd_boxplot.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n图片已保存: {output_file}")
    
    # 输出统计信息
    print("\n各实验窗口统计 (按均值排序):")
    for name in sorted_exp_names:
        data = all_cwnd_data[name]
        print(f"  {name}: min={min(data)}, max={max(data)}, mean={int(np.mean(data))}, count={len(data)}")
    
    plt.close()


def main():
    parser = argparse.ArgumentParser(description='绘制窗口大小箱线图')
    parser.add_argument('input_dir', help='输入目录，包含多个实验子目录')
    parser.add_argument('-o', '--output', default='.', help='输出目录 (默认: 当前目录)')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.input_dir):
        print(f"错误: 输入目录不存在: {args.input_dir}")
        sys.exit(1)
    
    plot_cwnd_boxplot(args.input_dir, args.output)


if __name__ == '__main__':
    main()
