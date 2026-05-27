#!/usr/bin/env python3
# 生成只使用前64个节点的all-to-all连接矩阵
# 每个节点向其他63个节点发送数据，使用start 0格式（并行发送）

import os

# 配置参数
NUM_NODES = 256
FLOW_SIZE = 1048576  # 1MB
OUTPUT_FILE = '/home/lrh/uet-htsim/test_hw/2spine_4leaf_256/connection_matrices/alltoall_256_1MB_parallel.cm'

# 生成连接矩阵
output_lines = []

# 添加头部信息
output_lines.append(f"Nodes {NUM_NODES}\n")

# 生成all-to-all连接
flow_id = 1
for src in range(NUM_NODES):
    for dst in range(NUM_NODES):
        if src != dst:  # 不包括自己到自己的连接
            line = f"{src}->{dst} id {flow_id} start 0 size {FLOW_SIZE}\n"
            output_lines.append(line)
            flow_id += 1

# 添加连接数统计
num_connections = len(output_lines) - 1  # 减去头部行
output_lines.insert(1, f"Connections {num_connections}\n")

# 确保输出目录存在
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

# 写入文件
with open(OUTPUT_FILE, 'w') as f:
    f.writelines(output_lines)

print(f"生成完成！")
print(f"节点数: {NUM_NODES}")
print(f"连接数: {num_connections}")
print(f"每个节点发送: {NUM_NODES - 1}个流")
print(f"每个节点接收: {NUM_NODES - 1}个流")
print(f"输出文件: {OUTPUT_FILE}")