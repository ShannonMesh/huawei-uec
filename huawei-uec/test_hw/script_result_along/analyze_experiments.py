#!/usr/bin/env python3

import os
import numpy as np
import matplotlib.pyplot as plt
import re
import sys
from pathlib import Path

def parse_result_file(result_file):
    """解析单个实验结果文件"""
    data = {
        'experiment_name': '',
        'connections': 0,
        'fcts': [],
        'throughputs': [],
        'total_pkts': {},
        'flow_sizes': {},
        'flow_dst_bytes': {},  # 按目的地址统计流量: dst_id -> total_bytes
        'new_pkts': 0,
        'rtx_pkts': 0,
        'rts_pkts': 0,
        'bounced_pkts': 0,
        'acks': 0,
        'nacks': 0,
        'pulls': 0,
        'sleek_pkts': 0,
        'actual_connections': 0,
        'base_rtt_us': 0,  # 基础RTT (微秒)
        'base_bdp_bytes': 0,  # 基础BDP (字节)
        'network_rtt_us': 0,  # 网络RTT (微秒)
        'network_bdp_bytes': 0  # 网络BDP (字节)
    }
    
    with open(result_file, 'r') as f:
        for line in f:
            # 提取连接数
            if 'Connections:' in line:
                match = re.search(r'Connections:\s*(\d+)', line)
                if match:
                    data['connections'] = int(match.group(1))
            
            # 提取网络RTT和BDP (从静态NSCC参数)
            if 'Initializing static NSCC parameters:' in line:
                # 提取 _network_rtt (皮秒转微秒) - 使用负向回顾避免匹配到 _reference_network_rtt
                match = re.search(r'(?<!_reference)_network_rtt=(\d+)', line)
                if match:
                    data['network_rtt_us'] = int(match.group(1)) / 1e6  # 皮秒转微秒
                # 提取 _network_bdp - 使用负向回顾避免匹配到 _reference_network_bdp
                match = re.search(r'(?<!_reference)_network_bdp=(\d+)', line)
                if match:
                    data['network_bdp_bytes'] = int(match.group(1))
            
            # 提取每个流的base_rtt和base_bdp
            if 'Initialize per-instance NSCC parameters:' in line:
                # 提取 _base_rtt (皮秒转微秒)
                match = re.search(r'_base_rtt=(\d+)', line)
                if match:
                    rtt_ps = int(match.group(1))
                    # 只记录第一个流的值作为代表
                    if data['base_rtt_us'] == 0:
                        data['base_rtt_us'] = rtt_ps / 1e6  # 皮秒转微秒
                # 提取 _base_bdp
                match = re.search(r'_base_bdp=(\d+)', line)
                if match:
                    bdp = int(match.group(1))
                    if data['base_bdp_bytes'] == 0:
                        data['base_bdp_bytes'] = bdp
            
            # 提取流完成信息
            if 'finished at' in line:
                match = re.search(r'Flow\s+(\S+)\s+flowId\s+(\d+)\s+uecSrc\s+(\d+)\s+finished at\s+(\d+(?:\.\d+)?)\s+total messages\s+(\d+)\s+total packets\s+(\d+)\s+RTS\s+(\d+)\s+total bytes\s+(\d+)', line)
                if match:
                    flow_name = match.group(1)
                    flow_id = int(match.group(2))
                    src_id = int(match.group(3))
                    fct = float(match.group(4))
                    total_messages = int(match.group(5))
                    total_packets = int(match.group(6))
                    rts_count = int(match.group(7))
                    total_bytes = int(match.group(8))
                    
                    # 从流名称中提取源地址和目的地址 (格式: Uec_src_dst)
                    flow_parts = flow_name.split('_')
                    if len(flow_parts) >= 3:
                        src_id = int(flow_parts[1])
                        dst_id = int(flow_parts[2])
                    else:
                        src_id = 0
                        dst_id = 0
                    
                    data['fcts'].append(fct)
                    data['total_pkts'][flow_id] = total_packets
                    data['flow_sizes'][flow_id] = total_bytes
                    data['actual_connections'] += 1
                    
                    # 按目的地址累加流量
                    data['flow_dst_bytes'][dst_id] = data['flow_dst_bytes'].get(dst_id, 0) + total_bytes
                    
                    # 计算吞吐量 (Gbps)
                    thr = (total_bytes * 8) / (fct * 10**-6) / (10**9)
                    data['throughputs'].append(thr)
                    
                    # 保存流详细信息
                    if 'flow_details' not in data:
                        data['flow_details'] = []
                    data['flow_details'].append([flow_name, flow_id, src_id, dst_id, fct, total_messages, total_packets, rts_count, total_bytes, thr])
            
            # 提取数据包统计
            if 'New:' in line and 'Rtx:' in line:
                match = re.search(r'New:\s+(\d+)\s+Rtx:\s+(\d+)\s+RTS:\s+(\d+)\s+Bounced:\s+(\d+)\s+ACKs:\s+(\d+)\s+NACKs:\s+(\d+)\s+Pulls:\s+(\d+)\s+sleek_pkts:\s+(\d+)', line)
                if match:
                    data['new_pkts'] = int(match.group(1))
                    data['rtx_pkts'] = int(match.group(2))
                    data['rts_pkts'] = int(match.group(3))
                    data['bounced_pkts'] = int(match.group(4))
                    data['acks'] = int(match.group(5))
                    data['nacks'] = int(match.group(6))
                    data['pulls'] = int(match.group(7))
                    data['sleek_pkts'] = int(match.group(8))
    
    return data

def analyze_experiments(result_dir, output_dir='./figures/'):
    """分析所有实验结果"""
    
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 收集所有实验数据
    experiments_data = {}
    
    # 遍历result目录
    for item in os.listdir(result_dir):
        item_path = os.path.join(result_dir, item)
        
        # 跳过非目录文件
        if not os.path.isdir(item_path):
            continue
        
        # 查找result.txt文件
        result_file = os.path.join(item_path, 'result.txt')
        if os.path.exists(result_file):
            experiment_name = item
            data = parse_result_file(result_file)
            data['experiment_name'] = experiment_name
            experiments_data[experiment_name] = data
            
            # 保存每个流的FCT详细信息到实验目录
            if 'flow_details' in data and data['flow_details']:
                flow_csv = os.path.join(item_path, 'flow_fct_details.csv')
                with open(flow_csv, 'w') as f:
                    f.write('flow_name,flow_id,src_id,dst_id,fct_us,total_messages,total_packets,rts_count,total_bytes,throughput_gbps\n')
                    for row in data['flow_details']:
                        f.write(','.join(str(x) for x in row) + '\n')
                print(f"  保存流FCT详情: {flow_csv}")
            
            print(f"解析实验: {experiment_name}")
            print(f"  连接数: {data['connections']}, 实际完成: {data['actual_connections']}")
            print(f"  FCT范围: {min(data['fcts']) if data['fcts'] else 0:.2f} - {max(data['fcts']) if data['fcts'] else 0:.2f} us")
            print(f"  新数据包: {data['new_pkts']}, 重传: {data['rtx_pkts']}, ACK: {data['acks']}")
            print()
    
    # 生成FCT的CDF图
    plt.figure(figsize=(12, 8))
    for exp_name, data in experiments_data.items():
        if data['fcts']:
            fcts_sorted = sorted(data['fcts'])
            cdf = np.arange(1, len(fcts_sorted) + 1) / len(fcts_sorted)
            mean_fct = np.mean(data['fcts'])
            max_fct = max(data['fcts'])
            plt.plot(fcts_sorted, cdf, marker='.', markersize=2, linestyle='-', linewidth=1.0, 
                    label=f'{exp_name}, tail FCT ({max_fct:.2f} us)')
    
    plt.title('ECDF for FCTs')
    plt.xlabel('FCT (us)')
    plt.ylabel('CDF')
    plt.legend(loc='best', bbox_to_anchor=(1.02, 1), borderaxespad=0.1, fontsize=8)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fcts_cdf.png'), format='png', dpi=300)
    plt.close()
    print(f"生成图表: {os.path.join(output_dir, 'fcts_cdf.png')}")
    
    # 生成数据包统计柱状图
    metrics = [
        ('new_pkts', 'New Packets'),
        ('rtx_pkts', 'Retransmitted Packets'),
        ('rts_pkts', 'RTS Packets'),
        ('bounced_pkts', 'Bounced Packets'),
        ('acks', 'ACK Packets'),
        ('nacks', 'NACK Packets'),
        ('pulls', 'Pulls Packets'),
        ('sleek_pkts', 'Sleek Packets')
    ]
    
    for metric_key, metric_name in metrics:
        exp_names = list(experiments_data.keys())
        values = [experiments_data[exp][metric_key] for exp in exp_names]
        
        # 检查是否所有值都是0，如果是则跳过
        if all(v == 0 for v in values):
            print(f"跳过生成图表: {metric_name} (所有值均为0)")
            continue
        
        plt.figure(figsize=(10, 6))
        plt.bar(exp_names, values)
        plt.title(f'{metric_name} per Experiment')
        plt.xlabel('Experiment')
        plt.ylabel(f'# {metric_name}')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        safe_metric_name = metric_name.replace(' ', '_').lower()
        plt.savefig(os.path.join(output_dir, f'{safe_metric_name}.png'), format='png', dpi=300)
        plt.close()
        print(f"生成图表: {os.path.join(output_dir, f'{safe_metric_name}.png')}")
    
    # 生成统计摘要
    summary_file = os.path.join(output_dir, 'experiment_summary.txt')
    with open(summary_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("实验统计摘要\n")
        f.write("=" * 80 + "\n\n")
        
        for exp_name, data in experiments_data.items():
            f.write(f"实验: {exp_name}\n")
            f.write("-" * 80 + "\n")
            f.write(f"连接数: {data['connections']}\n")
            f.write(f"实际完成连接数: {data['actual_connections']}\n")
            f.write(f"基础RTT: {data['base_rtt_us']:.2f} us\n")
            f.write(f"基础BDP: {data['base_bdp_bytes']} bytes\n")
            f.write(f"网络RTT: {data['network_rtt_us']:.2f} us\n")
            f.write(f"网络BDP: {data['network_bdp_bytes']} bytes\n")
            
            if data['connections'] != data['actual_connections']:
                f.write(f"[FAIL] 连接数不匹配!\n")
            else:
                f.write(f"[PASS] 连接数匹配\n")
            
            if data['fcts']:
                f.write(f"FCT统计:\n")
                f.write(f"  平均FCT: {np.mean(data['fcts']):.2f} us\n")
                f.write(f"  最小FCT: {min(data['fcts']):.2f} us\n")
                f.write(f"  最大FCT (Tail): {max(data['fcts']):.2f} us\n")
                f.write(f"  中位数FCT: {np.median(data['fcts']):.2f} us\n")
                f.write(f"  标准差: {np.std(data['fcts']):.2f} us\n")
                
                if data['throughputs']:
                    f.write(f"吞吐量统计:\n")
                    f.write(f"  平均吞吐量: {np.mean(data['throughputs']):.2f} Gbps\n")
                    f.write(f"  最小吞吐量: {min(data['throughputs']):.2f} Gbps\n")
                    f.write(f"  最大吞吐量: {max(data['throughputs']):.2f} Gbps\n")
            
            f.write(f"数据包统计:\n")
            f.write(f"  新数据包: {data['new_pkts']}\n")
            f.write(f"  重传数据包: {data['rtx_pkts']}\n")
            f.write(f"  RTS数据包: {data['rts_pkts']}\n")
            f.write(f"  反弹数据包: {data['bounced_pkts']}\n")
            f.write(f"  ACK数据包: {data['acks']}\n")
            f.write(f"  NACK数据包: {data['nacks']}\n")
            f.write(f"  Pulls数据包: {data['pulls']}\n")
            f.write(f"  Sleek数据包: {data['sleek_pkts']}\n")
            
            # 计算重传率
            if data['new_pkts'] > 0:
                rtx_rate = (data['rtx_pkts'] / data['new_pkts']) * 100
                f.write(f"  重传率: {rtx_rate:.2f}%\n")
            
            f.write("\n")
    
    print(f"生成统计摘要: {summary_file}")
    
    # 生成CSV格式的详细数据
    csv_file = os.path.join(output_dir, 'experiment_details.csv')
    with open(csv_file, 'w') as f:
        # 动态生成表头：每个目的地址的流量 + 最大流量 + CCT + 总带宽
        max_dst_count = max(len(data['flow_dst_bytes']) for data in experiments_data.values()) if experiments_data else 0
        dst_headers = [f"Dst_{i}_Bytes" for i in range(max_dst_count)]
        
        f.write("Experiment,Connections,Actual_Connections,Base_RTT_us,Base_BDP_Bytes,Network_RTT_us,Network_BDP_Bytes,Mean_FCT_us,Min_FCT_us,Max_FCT_us,Median_FCT_us,")
        f.write("Mean_Throughput_Gbps,Min_Throughput_Gbps,Max_Throughput_Gbps,")
        f.write("New_Pkts,Rtx_Pkts,Rts_Pkts,Bounced_Pkts,Acks,Nacks,Pulls_Pkts,Sleek_Pkts,Rtx_Rate_%,")
        f.write(','.join(dst_headers) + ",")
        f.write("Max_Traffic_Bytes,CCT_us,Total_Bandwidth_Gbps\n")
        
        for exp_name, data in experiments_data.items():
            f.write(f"{exp_name},{data['connections']},{data['actual_connections']},{data['base_rtt_us']:.2f},{data['base_bdp_bytes']},{data['network_rtt_us']:.2f},{data['network_bdp_bytes']},")
            
            if data['fcts']:
                f.write(f"{np.mean(data['fcts']):.2f},{min(data['fcts']):.2f},{max(data['fcts']):.2f},{np.median(data['fcts']):.2f},")
            else:
                f.write("0,0,0,0,")
            
            if data['throughputs']:
                f.write(f"{np.mean(data['throughputs']):.2f},{min(data['throughputs']):.2f},{max(data['throughputs']):.2f},")
            else:
                f.write("0,0,0,")
            
            f.write(f"{data['new_pkts']},{data['rtx_pkts']},{data['rts_pkts']},{data['bounced_pkts']},{data['acks']},{data['nacks']},{data['pulls']},{data['sleek_pkts']},")
            
            if data['new_pkts'] > 0:
                rtx_rate = (data['rtx_pkts'] / data['new_pkts']) * 100
                f.write(f"{rtx_rate:.2f},")
            else:
                f.write("0,")
            
            # CCT = 最大FCT
            cct = max(data['fcts']) if data['fcts'] else 0
            
            # 收集每个目的地址的流量
            dst_bytes_list = []
            if data['flow_dst_bytes']:
                for dst_id in sorted(data['flow_dst_bytes'].keys()):
                    dst_bytes_list.append(data['flow_dst_bytes'][dst_id])
            
            # 填充到固定列数
            while len(dst_bytes_list) < max_dst_count:
                dst_bytes_list.append(0)
            
            # 最大流量
            max_traffic_bytes = max(dst_bytes_list) if dst_bytes_list else 0
            
            # 总带宽 = 最大流量 / CCT
            if cct > 0 and max_traffic_bytes > 0:
                total_bandwidth_gbps = (max_traffic_bytes * 8) / (cct * 1e-6) / 1e9
            else:
                total_bandwidth_gbps = 0
            
            # 写入每个目的地址的流量
            f.write(','.join(str(b) for b in dst_bytes_list) + ",")
            
            # 写入最大流量、CCT、总带宽
            f.write(f"{max_traffic_bytes},{cct:.2f},{total_bandwidth_gbps:.2f}")
            f.write("\n")
    
    print(f"生成详细数据CSV: {csv_file}")
    
    print("\n" + "=" * 80)
    print("分析完成！")
    print(f"结果保存在: {output_dir}")
    print("=" * 80)

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='HTSIM实验结果分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s /path/to/result /path/to/output
  %(prog)s ./result ./figures
        """
    )
    parser.add_argument('result_dir', nargs='?', default='./result',
                        help='结果目录路径 (默认: ./result)')
    parser.add_argument('output_dir', nargs='?', default='./figures',
                        help='输出目录路径 (默认: ./figures)')

    args = parser.parse_args()

    result_dir = args.result_dir
    output_dir = args.output_dir
    
    print("=" * 80)
    print("实验结果分析工具")
    print("=" * 80)
    print(f"结果目录: {result_dir}")
    print(f"输出目录: {output_dir}")
    print("=" * 80)
    print()
    
    # 分析实验
    analyze_experiments(result_dir, output_dir)

if __name__ == '__main__':
    main()
