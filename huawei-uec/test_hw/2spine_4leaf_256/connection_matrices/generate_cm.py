#!/usr/bin/env python3

# 组定义
GROUP_A_START = 32
GROUP_A_END = 63
GROUP_B_START = 64
GROUP_B_END = 95

# 参数
PACKET_SIZE = 1048576  # 1MB
START_TIME = 0

def get_offset(node, group_start):
    """计算节点在其组内的偏移量"""
    return node - group_start

def generate_intragroup_connections(src_node, group_start, group_end):
    """生成组内pairwise连接"""
    connections = []
    offset = get_offset(src_node, group_start)
    
    # 首先生成到比自己大的节点的连接
    for dst in range(src_node + 1, group_end + 1):
        connections.append((src_node, dst))
    
    # 然后按照偏移量补充到比自己小的节点的连接
    # 从组第一个节点开始，补充offset个节点（只补充比src_node小的）
    count = 0
    for dst in range(group_start, src_node):
        if count < offset:
            connections.append((src_node, dst))
            count += 1
        else:
            break
    
    return connections

def generate_intergroup_connections(src_node, src_group_start, other_group_start, other_group_end):
    """生成组间pairwise连接"""
    connections = []
    offset = get_offset(src_node, src_group_start)
    
    # 按照偏移量跳过对方组的前几个节点，从第offset个节点开始
    start_idx = other_group_start + offset
    
    # 首先遍历从跳过位置到对方组最后一个节点
    for dst in range(start_idx, other_group_end + 1):
        connections.append((src_node, dst))
    
    # 然后补充被跳过的那些节点（按升序）
    for dst in range(other_group_start, start_idx):
        connections.append((src_node, dst))
    
    return connections

def main():
    all_connections = []
    
    # 处理组A中的每个源节点
    for src in range(GROUP_A_START, GROUP_A_END + 1):
        # 组内连接（到组A其他节点）
        intra_conns = generate_intragroup_connections(src, GROUP_A_START, GROUP_A_END)
        all_connections.extend(intra_conns)
        
        # 组间连接（到组B所有节点）
        inter_conns = generate_intergroup_connections(src, GROUP_A_START, GROUP_B_START, GROUP_B_END)
        all_connections.extend(inter_conns)
    
    # 处理组B中的每个源节点
    for src in range(GROUP_B_START, GROUP_B_END + 1):
        # 组内连接（到组B其他节点）
        intra_conns = generate_intragroup_connections(src, GROUP_B_START, GROUP_B_END)
        all_connections.extend(intra_conns)
        
        # 组间连接（到组A所有节点）
        inter_conns = generate_intergroup_connections(src, GROUP_B_START, GROUP_A_START, GROUP_A_END)
        all_connections.extend(inter_conns)
    
    # 写入文件
    output_file = "/home/lrh/uet-htsim/test_hw/2spine_4leaf_256/connection_matrices/32to1_a2a1MB.cm"
    
    with open(output_file, 'w') as f:
        f.write(f"Nodes 256\n")
        f.write(f"Connections {len(all_connections)}\n")
        for src, dst in all_connections:
            f.write(f"{src}->{dst} start {START_TIME} size {PACKET_SIZE}\n")
    
    print(f"Generated {len(all_connections)} connections")
    print(f"Output file: {output_file}")

if __name__ == "__main__":
    main()