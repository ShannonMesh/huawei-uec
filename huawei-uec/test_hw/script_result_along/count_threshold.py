#!/usr/bin/env python3
import argparse
import csv
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def count_high_values(csv_path, threshold=1245000):
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        counts = [0] * len(header)
        
        for row in reader:
            for i, val in enumerate(row):
                if i == 0:
                    continue
                try:
                    if float(val) > threshold:
                        counts[i] += 1
                except ValueError:
                    pass
    
    return header, counts


def plot_threshold_counts(header, counts, output_file, threshold):
    columns = header[1:]
    values = counts[1:]
    
    nonzero_indices = [i for i, v in enumerate(values) if v > 0]
    nonzero_columns = [columns[i] for i in nonzero_indices]
    nonzero_values = [values[i] for i in nonzero_indices]
    
    if not nonzero_values:
        print(f"警告: 没有超过阈值 {threshold} 的值")
        nonzero_columns = columns[:1]
        nonzero_values = [0]
    
    fig, ax = plt.subplots(figsize=(max(14, len(nonzero_columns) * 1.5), 7))
    
    bars = ax.bar(range(len(nonzero_columns)), nonzero_values, color='steelblue', edgecolor='black', alpha=0.8)
    
    ax.set_xlabel('Queue', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title(f'Queue Depth Threshold Analysis\n(Threshold: {threshold})', fontsize=14)
    
    ax.set_xticks(range(len(nonzero_columns)))
    ax.set_xticklabels(nonzero_columns, rotation=45, ha='right', fontsize=9)
    
    ax.grid(True, alpha=0.3, axis='y')
    
    max_val = max(nonzero_values) if nonzero_values else 0
    for i, (bar, val) in enumerate(zip(bars, nonzero_values)):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max_val * 0.02,
                    str(val), ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_ylim(0, max_val * 1.2 if max_val > 0 else 1)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"图表已保存到: {output_file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='统计CSV文件中每列超过阈值的值的数量')
    parser.add_argument('-i', '--input', required=True, help='输入CSV文件')
    parser.add_argument('-t', '--threshold', type=float, default=1245000, help='阈值 (默认: 1245000)')
    parser.add_argument('-o', '--output', help='输出CSV文件 (可选)')
    parser.add_argument('-p', '--plot', help='输出图片文件 (可选)')
    args = parser.parse_args()

    header, counts = count_high_values(args.input, args.threshold)
    
    plot_file = args.plot or (args.output.replace('.csv', '.png') if args.output else None)
    if plot_file:
        plot_threshold_counts(header, counts, plot_file, args.threshold)

    if args.output:
        with open(args.output, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Column', 'Count'])
            for h, c in zip(header[1:], counts[1:]):
                writer.writerow([h, c])
        print(f"结果已保存到: {args.output}")
    elif not args.plot:
        print(f"列名, 超过{args.threshold}的值数量")
        for h, c in zip(header[1:], counts[1:]):
            print(f"{h}, {c}")