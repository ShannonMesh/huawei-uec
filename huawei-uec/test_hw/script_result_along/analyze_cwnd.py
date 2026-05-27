#!/usr/bin/env python3
"""
统一窗口日志分析工具
支持NSCC和Z-INCAST算法的窗口变化日志分析
"""
import sys
import argparse
import re
import csv
from collections import defaultdict
from pathlib import Path


class CwndLogAnalyzer:
    """窗口日志分析器"""
    
    # 日志匹配模式
    LOG_PATTERN = re.compile(
        r'\[(NSCC|Z-INCAST)-CWND\]\s+'      # 算法类型
        r'([\d.]+)\s+'                       # 时间
        r'flowid\s+(\d+)\s+'                 # flowid
        r'(\w+)\s+'                          # 操作类型
        r'(\d+)\s*->\s*(\d+)'                # 原窗口->现窗口
    )
    
    def __init__(self):
        self.events = []
        self.flow_map = {}
    
    def parse_log(self, input_file):
        """解析日志文件"""
        with open(input_file, 'r') as f:
            for line in f:
                match = self.LOG_PATTERN.search(line)
                if match:
                    self.events.append({
                        'algo': match.group(1),
                        'time': float(match.group(2)),
                        'flowid': match.group(3),
                        'op_type': match.group(4),
                        'cwnd_before': int(match.group(5)),
                        'cwnd_after': int(match.group(6)),
                        'line': line.strip()
                    })
        
        return len(self.events)
    
    def load_flow_map(self, map_file):
        """加载flow映射"""
        with open(map_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.flow_map[row['flowid']] = row['flow_name']
    
    def get_flow_name(self, flowid):
        """获取flow名称"""
        return self.flow_map.get(flowid, f"Flow_{flowid}")
    
    def get_stats(self):
        """获取统计信息"""
        stats = {
            'total': len(self.events),
            'by_algo': defaultdict(int),
            'by_op': defaultdict(int),
            'by_flow': defaultdict(int)
        }
        
        for e in self.events:
            stats['by_algo'][e['algo']] += 1
            stats['by_op'][e['op_type']] += 1
            stats['by_flow'][e['flowid']] += 1
        
        return stats
    
    def export_csv(self, output_file):
        """导出CSV格式"""
        with open(output_file, 'w') as f:
            f.write("time,flow,flowid,algo,op_type,cwnd_before,cwnd_after\n")
            for e in self.events:
                flow_name = self.get_flow_name(e['flowid'])
                f.write(f"{e['time']},{flow_name},{e['flowid']},"
                       f"{e['algo']},{e['op_type']},"
                       f"{e['cwnd_before']},{e['cwnd_after']}\n")
    
    def export_events(self, output_file):
        """导出事件列表"""
        stats = self.get_stats()
        with open(output_file, 'w') as f:
            f.write(f"# 窗口变化事件\n")
            f.write(f"# 总计: {stats['total']} 个事件\n")
            f.write(f"# 算法: {dict(stats['by_algo'])}\n")
            f.write(f"# 操作: {dict(stats['by_op'])}\n\n")
            
            for e in self.events:
                f.write(f"[{e['algo']}] t={e['time']:.6f} "
                       f"flow={e['flowid']} {e['op_type']} "
                       f"{e['cwnd_before']}->{e['cwnd_after']}\n")
    
    def export_raw(self, output_file):
        """导出原始日志行"""
        with open(output_file, 'w') as f:
            for e in self.events:
                f.write(e['line'] + '\n')
    
    def print_summary(self):
        """打印摘要"""
        stats = self.get_stats()
        
        print(f"\n{'='*50}")
        print(f"窗口日志分析结果")
        print(f"{'='*50}")
        print(f"总事件数: {stats['total']}")
        
        print(f"\n按算法统计:")
        for algo, count in sorted(stats['by_algo'].items()):
            print(f"  {algo}: {count} 个事件")
        
        print(f"\n按操作类型统计:")
        for op, count in sorted(stats['by_op'].items()):
            print(f"  {op}: {count} 次")
        
        print(f"\n按Flow统计 (前10):")
        sorted_flows = sorted(stats['by_flow'].items(), key=lambda x: x[1], reverse=True)
        for flowid, count in sorted_flows[:10]:
            flow_name = self.get_flow_name(flowid)
            print(f"  {flow_name} (id={flowid}): {count} 次")
        
        if len(sorted_flows) > 10:
            print(f"  ... 还有 {len(sorted_flows)-10} 个flow")
        
        print(f"\n{'='*50}")


def main():
    parser = argparse.ArgumentParser(
        description='窗口日志分析工具 (支持NSCC和Z-INCAST)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s -i result.txt -s                    # 只显示摘要
  %(prog)s -i result.txt -o cwnd.csv           # 导出CSV
  %(prog)s -i result.txt -e events.txt         # 导出事件列表
  %(prog)s -i result.txt -r raw.txt            # 导出原始日志
  %(prog)s -i result.txt -m map.csv -o out.csv # 使用flow映射
        """
    )
    
    parser.add_argument('-i', '--input', required=True, help='输入日志文件')
    parser.add_argument('-m', '--map', help='Flow映射CSV文件 (可选)')
    parser.add_argument('-o', '--output', help='输出CSV文件')
    parser.add_argument('-e', '--events', help='输出事件列表文件')
    parser.add_argument('-r', '--raw', help='输出原始日志文件')
    parser.add_argument('-s', '--summary', action='store_true', help='只显示摘要')
    
    args = parser.parse_args()
    
    # 创建分析器
    analyzer = CwndLogAnalyzer()
    
    # 解析日志
    count = analyzer.parse_log(args.input)
    if count == 0:
        print("未找到窗口日志数据")
        print("提示: 确保使用 -log cwnd 参数运行仿真")
        sys.exit(1)
    
    print(f"成功解析 {count} 个窗口变化事件")
    
    # 加载flow映射
    if args.map:
        analyzer.load_flow_map(args.map)
        print(f"已加载flow映射: {args.map}")
    
    # 输出文件
    if args.output:
        analyzer.export_csv(args.output)
        print(f"CSV已导出: {args.output}")
    
    if args.events:
        analyzer.export_events(args.events)
        print(f"事件列表已导出: {args.events}")
    
    if args.raw:
        analyzer.export_raw(args.raw)
        print(f"原始日志已导出: {args.raw}")
    
    # 显示摘要
    if not args.summary or not (args.output or args.events or args.raw):
        analyzer.print_summary()


if __name__ == "__main__":
    main()
