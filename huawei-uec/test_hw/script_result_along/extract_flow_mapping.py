#!/usr/bin/env python3
import sys
import argparse
import re

def extract_flow_mapping(input_file, output_file):
    try:
        flow_mappings = {}
        
        with open(input_file, 'r') as infile:
            for line in infile:
                if 'Flow Uec_' in line and 'flowId' in line:
                    match = re.search(r'Flow (Uec_\d+_\d+) flowId (\d+)', line)
                    if match:
                        flow_name = match.group(1)
                        flowid = match.group(2)
                        if flowid not in flow_mappings:
                            flow_mappings[flowid] = flow_name
        
        with open(output_file, 'w') as outfile:
            outfile.write("flowid,flow_name\n")
            for flowid in sorted(flow_mappings.keys()):
                outfile.write(f"{flowid},{flow_mappings[flowid]}\n")
        
        print(f"成功提取 {len(flow_mappings)} 个流映射关系")
        print(f"结果已保存到: {output_file}")
        
        if flow_mappings:
            print(f"\n=== 流映射示例 ===")
            for i, (flowid, flow_name) in enumerate(sorted(flow_mappings.items())[:5]):
                print(f"{i+1}. flowid {flowid} -> {flow_name}")
    
    except FileNotFoundError:
        print(f"错误: 找不到输入文件 {input_file}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='提取流映射信息')
    parser.add_argument('-i', '--input', required=True, help='输入文件路径')
    parser.add_argument('-o', '--output', required=True, help='输出文件路径')
    
    args = parser.parse_args()
    
    extract_flow_mapping(args.input, args.output)

if __name__ == "__main__":
    main()
