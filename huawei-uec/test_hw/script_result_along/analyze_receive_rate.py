#!/usr/bin/env python3
import re
import argparse
from collections import defaultdict

def parse_parsed_log(filepath):
    nic_data = defaultdict(list)
    with open(filepath, 'r') as f:
        for line in f:
            match = re.match(r'([\d.]+)\s+Type NIC_EVENT ID (\d+) Data (\d+) Total (\d+)', line)
            if match:
                nic_data[int(match.group(2))].append((
                    float(match.group(1)) * 1e6,
                    int(match.group(3)),
                    int(match.group(4))
                ))
    return nic_data

def output_csv(nic_data, output_file):
    if not nic_data:
        print("No data found")
        return

    sorted_nodes = sorted(nic_data.keys())
    with open(output_file, 'w') as f:
        f.write("Time(us)," + ",".join(f"Node_{n}_Data(Gbps),Node_{n}_Total(Gbps)" for n in sorted_nodes) + "\n")
        max_len = max(len(nic_data[n]) for n in sorted_nodes)
        
        time_values = []
        data_values = [[] for _ in sorted_nodes]
        total_values = [[] for _ in sorted_nodes]
        
        for i in range(max_len):
            time_val = nic_data[sorted_nodes[0]][i][0]
            time_values.append(time_val)
            row = [f"{time_val:.2f}"]
            for idx, n in enumerate(sorted_nodes):
                if i < len(nic_data[n]):
                    data_val = nic_data[n][i][1] * 8 / 1e9
                    total_val = nic_data[n][i][2] * 8 / 1e9
                    data_values[idx].append(data_val)
                    total_values[idx].append(total_val)
                    row.append(f"{data_val:.6f}")
                    row.append(f"{total_val:.6f}")
                else:
                    # data_values[idx].append(0.0)
                    # total_values[idx].append(0.0)
                    row.append("0.000000")
                    row.append("0.000000")
            f.write(",".join(row) + "\n")
        
        if len(time_values) > 1:
            total_time = time_values[-1]
            weighted_avg_row = ["TimeWeightedAvg"]
            for idx in range(len(sorted_nodes)):
                weighted_sum_data = 0.0
                weighted_sum_total = 0.0
                for i in range(len(time_values)):
                    if i == 0:
                        duration = time_values[i]
                    else:
                        duration = time_values[i] - time_values[i-1]
                    weighted_sum_data += data_values[idx][i] * duration
                    weighted_sum_total += total_values[idx][i] * duration
                avg_data = weighted_sum_data / total_time if total_time > 0 else 0.0
                avg_total = weighted_sum_total / total_time if total_time > 0 else 0.0
                weighted_avg_row.append(f"{avg_data:.6f}")
                weighted_avg_row.append(f"{avg_total:.6f}")
            f.write(",".join(weighted_avg_row) + "\n")

    print(f"Saved to: {output_file}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', required=True)
    parser.add_argument('-o', required=True)
    args = parser.parse_args()

    nic_data = parse_parsed_log(args.i)
    print(f"Found {len(nic_data)} NICs")
    output_csv(nic_data, args.o)
