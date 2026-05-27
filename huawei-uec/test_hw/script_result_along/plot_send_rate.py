#!/usr/bin/env python3
"""Plot send rate per flow from CSV."""

import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
import random
import argparse


def plot_send_rate(csv_path, output_path, max_flows=5):
    """Plot Data bandwidth for each flow."""
    # Read and clean data
    df = pd.read_csv(csv_path)
    df = df[pd.to_numeric(df.iloc[:, 0], errors='coerce').notna()]
    df.iloc[:, 0] = pd.to_numeric(df.iloc[:, 0])

    # Find Data columns (exclude Total columns)
    data_cols = [c for c in df.columns if '_Data(' in c and '_Total(' not in c]
    if not data_cols:
        print(f"Warning: No data columns in {csv_path}")
        return

    # Select flows
    if len(data_cols) > max_flows:
        data_cols = random.sample(data_cols, max_flows)

    # Plot
    fig, ax = plt.subplots(figsize=(10, 5))
    time_col = df.columns[0]

    for col in data_cols:
        flow_name = col.split('_Data(')[0]
        ax.plot(df[time_col], df[col], label=flow_name, linewidth=1.2)

    # Styling
    ax.set_xlabel('Time (us)', fontsize=11)
    ax.set_ylabel('Send Rate (Gbps)', fontsize=11)
    ax.set_title('Send Rate per Flow', fontsize=12)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)

    # X-axis ticks
    t_min, t_max = df[time_col].min(), df[time_col].max()
    t_range = t_max - t_min
    interval = max(1, round(t_range / 8 / 50) * 50) if t_range > 200 else 50
    ticks = list(range(int(t_min / interval) * interval,
                       int(t_max / interval) * interval + interval + 1,
                       interval))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks], fontsize=8, rotation=30)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', required=True)
    parser.add_argument('-o', '--output', required=True)
    parser.add_argument('-n', '--max-flows', type=int, default=5)
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    plot_send_rate(args.input, args.output, args.max_flows)


if __name__ == '__main__':
    main()
