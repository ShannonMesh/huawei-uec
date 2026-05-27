#!/usr/bin/env python3
import re
import argparse
from collections import defaultdict

def parse_log(filepath):
    send_records = defaultdict(list)
    flow_time_range = {}
    
    with open(filepath, 'r') as f:
        for line in f:
            match1 = re.match(r'([\d.]+)\s+(Uec_\d+_\d+)\s+sending\s+pkt\s+(\d+)\s+size\s+(\d+)', line)
            if match1:
                time_us = float(match1.group(1))
                flow_name = match1.group(2)
                size = int(match1.group(4))
                send_records[flow_name].append((time_us, size, False))
                if flow_name not in flow_time_range:
                    flow_time_range[flow_name] = [time_us, time_us]
                else:
                    flow_time_range[flow_name][1] = time_us
                continue
            
            match2 = re.match(r'([\d.]+)\s+(Uec_\d+_\d+)\s+\S+\s+\d+\s+sending\s+rtx\s+pkt\s+(\d+)\s+size\s+(\d+)', line)
            if match2:
                time_us = float(match2.group(1))
                flow_name = match2.group(2)
                size = int(match2.group(4))
                send_records[flow_name].append((time_us, size, True))
                if flow_name not in flow_time_range:
                    flow_time_range[flow_name] = [time_us, time_us]
                else:
                    flow_time_range[flow_name][1] = time_us
                continue
    
    return send_records, flow_time_range

def calculate_rates(send_records, flow_time_range, time_slice):
    all_times = []
    for records in send_records.values():
        all_times.extend([t for t, _, _ in records])
    
    if not all_times:
        return {}, {}
    
    max_time = max(all_times)
    min_time = min(all_times)
    num_slices = int((max_time - min_time) / time_slice) + 1
    
    flow_data = {}
    
    for flow_name, records in send_records.items():
        data_volume = [0] * num_slices
        total_volume = [0] * num_slices
        
        for time_us, size, is_rtx in records:
            bin_idx = int((time_us - min_time) / time_slice)
            if 0 <= bin_idx < num_slices:
                total_volume[bin_idx] += size
                if not is_rtx:
                    data_volume[bin_idx] += size
        
        data_rate = [v / time_slice for v in data_volume]
        total_rate = [v / time_slice for v in total_volume]
        
        time_centers = [min_time + (i + 1) * time_slice for i in range(num_slices)]
        
        total_data_bytes = sum(data_volume)
        total_total_bytes = sum(total_volume)
        
        if flow_name in flow_time_range:
            start_time = flow_time_range[flow_name][0]
            end_time = flow_time_range[flow_name][1]
            duration = end_time - start_time
            if duration > 0:
                avg_data_rate = total_data_bytes / duration
                avg_total_rate = total_total_bytes / duration
            else:
                avg_data_rate = 0
                avg_total_rate = 0
        else:
            avg_data_rate = 0
            avg_total_rate = 0
        
        flow_data[flow_name] = {
            'time': time_centers,
            'data_rate': data_rate,
            'total_rate': total_rate,
            'avg_data_rate': avg_data_rate,
            'avg_total_rate': avg_total_rate
        }
    
    return flow_data, min_time, num_slices, min_time, max_time

def extract_node_id(flow_name):
    parts = flow_name.split('_')
    return int(parts[1])

def output_per_flow(flow_data, time_slice, output_file):
    sorted_flows = sorted(flow_data.keys(), key=lambda x: (int(x.split('_')[1]), int(x.split('_')[2])))
    
    with open(output_file, 'w') as f:
        header = "Time(us),"
        for flow_name in sorted_flows:
            header += f"{flow_name}_Data(Gbps),{flow_name}_Total(Gbps),"
        header = header.rstrip(',') + "\n"
        f.write(header)
        
        num_slices = max(len(data['time']) for data in flow_data.values())
        
        for i in range(num_slices):
            time_val = flow_data[sorted_flows[0]]['time'][i] if i < len(flow_data[sorted_flows[0]]['time']) else 0
            line = f"{time_val:.2f},"
            
            for flow_name in sorted_flows:
                data = flow_data[flow_name]
                if i < len(data['data_rate']):
                    data_rate_gbps = data['data_rate'][i] * 8 / 1000
                    total_rate_gbps = data['total_rate'][i] * 8 / 1000
                else:
                    data_rate_gbps = 0
                    total_rate_gbps = 0
                line += f"{data_rate_gbps:.6f},{total_rate_gbps:.6f},"
            
            line = line.rstrip(',') + "\n"
            f.write(line)
        
        avg_line = "AvgRate(Gbps),"
        for flow_name in sorted_flows:
            data = flow_data[flow_name]
            avg_data_gbps = data['avg_data_rate'] * 8 / 1000
            avg_total_gbps = data['avg_total_rate'] * 8 / 1000
            avg_line += f"{avg_data_gbps:.6f},{avg_total_gbps:.6f},"
        avg_line = avg_line.rstrip(',') + "\n"
        f.write(avg_line)
    
    print(f"Per-flow data saved to: {output_file}")

def output_per_node(flow_data, time_slice, output_file):
    node_data = defaultdict(lambda: {'data_rate': [], 'total_rate': [], 'avg_data_rate': 0.0, 'avg_total_rate': 0.0})
    node_times = {}
    
    sorted_flows = sorted(flow_data.keys(), key=lambda x: (int(x.split('_')[1]), int(x.split('_')[2])))
    
    for flow_name in sorted_flows:
        node_id = extract_node_id(flow_name)
        data = flow_data[flow_name]
        
        if node_id not in node_times:
            node_times[node_id] = data['time']
        
        for i in range(len(data['data_rate'])):
            if i >= len(node_data[node_id]['data_rate']):
                node_data[node_id]['data_rate'].append(0)
                node_data[node_id]['total_rate'].append(0)
            node_data[node_id]['data_rate'][i] += data['data_rate'][i]
            node_data[node_id]['total_rate'][i] += data['total_rate'][i]
        
        node_data[node_id]['avg_data_rate'] += data['avg_data_rate']
        node_data[node_id]['avg_total_rate'] += data['avg_total_rate']
    
    sorted_nodes = sorted(node_data.keys())
    
    with open(output_file, 'w') as f:
        header = "Time(us),"
        for node_id in sorted_nodes:
            header += f"Node_{node_id}_Data(Gbps),Node_{node_id}_Total(Gbps),"
        header = header.rstrip(',') + "\n"
        f.write(header)
        
        num_slices = max(len(node_data[n]['data_rate']) for n in sorted_nodes)
        
        for i in range(num_slices):
            time_val = node_times[sorted_nodes[0]][i] if i < len(node_times[sorted_nodes[0]]) else 0
            line = f"{time_val:.2f},"
            
            for node_id in sorted_nodes:
                if i < len(node_data[node_id]['data_rate']):
                    data_rate_gbps = node_data[node_id]['data_rate'][i] * 8 / 1000
                    total_rate_gbps = node_data[node_id]['total_rate'][i] * 8 / 1000
                else:
                    data_rate_gbps = 0
                    total_rate_gbps = 0
                line += f"{data_rate_gbps:.6f},{total_rate_gbps:.6f},"
            
            line = line.rstrip(',') + "\n"
            f.write(line)
        
        avg_line = "AvgRate(Gbps),"
        for node_id in sorted_nodes:
            avg_data_gbps = node_data[node_id]['avg_data_rate'] * 8 / 1000
            avg_total_gbps = node_data[node_id]['avg_total_rate'] * 8 / 1000
            avg_line += f"{avg_data_gbps:.6f},{avg_total_gbps:.6f},"
        avg_line = avg_line.rstrip(',') + "\n"
        f.write(avg_line)
    
    print(f"Per-node data saved to: {output_file}")

def print_statistics(flow_data, time_slice):
    sorted_flows = sorted(flow_data.keys(), key=lambda x: (int(x.split('_')[1]), int(x.split('_')[2])))
    
    node_totals = defaultdict(lambda: {'data': 0, 'total': 0})
    
    print("\n" + "="*60)
    print(f"Per-flow Statistics (Time Slice: {time_slice} us)")
    print("="*60)
    
    for flow_name in sorted_flows:
        data = flow_data[flow_name]
        node_id = extract_node_id(flow_name)
        total_data = sum(d * time_slice / 1e9 for d in data['data_rate'])
        total_total = sum(t * time_slice / 1e9 for t in data['total_rate'])
        total_rtx = total_total - total_data
        node_totals[node_id]['data'] += total_data
        node_totals[node_id]['total'] += total_total
        print(f"{flow_name}: Data={total_data:.4f} GB, RTX={total_rtx:.4f} GB, Total={total_total:.4f} GB")
    
    print("-"*60)
    total_all = sum(v['data'] for v in node_totals.values())
    rtx_all = sum(v['total'] - v['data'] for v in node_totals.values())
    print(f"ALL FLOWS: Data={total_all:.4f} GB, RTX={rtx_all:.4f} GB, Total={total_all+rtx_all:.4f} GB")
    print("="*60)
    
    print("\n" + "="*60)
    print(f"Per-node Statistics")
    print("="*60)
    for node_id in sorted(node_totals.keys()):
        print(f"Node_{node_id}: Data={node_totals[node_id]['data']:.4f} GB, Total={node_totals[node_id]['total']:.4f} GB")
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze send rate from simulation log')
    parser.add_argument('-i', '--input', required=True, help='Input log file')
    parser.add_argument('-o', '--output-flow', help='Output per-flow CSV file')
    parser.add_argument('-n', '--output-node', help='Output per-node CSV file')
    parser.add_argument('-t', '--time-slice', type=float, default=20, help='Time slice in microseconds (default: 20)')
    
    args = parser.parse_args()
    
    time_slice = args.time_slice
    
    print(f"Parsing log file: {args.input}")
    send_records, flow_time_range = parse_log(args.input)
    print(f"Found {len(send_records)} flows")
    
    for flow_name, records in send_records.items():
        new_packets = sum(1 for _, _, is_rtx in records if not is_rtx)
        rtx_packets = sum(1 for _, _, is_rtx in records if is_rtx)
        print(f"  {flow_name}: {len(records)} packets (New: {new_packets}, RTX: {rtx_packets})")
    
    print("\nCalculating rates...")
    flow_data, start_time, num_slices, min_time, max_time = calculate_rates(send_records, flow_time_range, time_slice)
    print(f"Time slices: {num_slices}, Time range: {min_time:.2f} - {max_time:.2f} us")
    
    if args.output_flow:
        print("\nOutputting per-flow data...")
        output_per_flow(flow_data, time_slice, args.output_flow)
    
    if args.output_node:
        print("\nOutputting per-node data...")
        output_per_node(flow_data, time_slice, args.output_node)
    
    print_statistics(flow_data, time_slice)
    
    print("\nDone!")
