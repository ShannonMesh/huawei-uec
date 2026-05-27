# HTSIM 结果分析脚本目录 (script_result_along)

本目录包含用于分析 HTSIM 网络仿真实验结果的脚本。

## 目录结构

```
script_result_along/
├── README.md                    # 本文件
├── config.sh                    # 共享配置模块
├── experiment.sh                # 主结果分析脚本
│
├── analyze_experiments.py       # 整体实验结果分析
├── analyze_cwnd.py             # 拥塞窗口变化分析
├── analyze_cwnd_changes.py     # 拥塞窗口变化详细分析
├── analyze_send_rate.py        # 发送速率分析
├── analyze_receive_rate.py     # 接收速率分析
├── analyze_network_delay.py    # 网络时延分析
├── analyze_queues.py           # 队列深度分析
│
├── extract_flow_mapping.py     # 流映射提取
├── parse_cwnd_events.py      # 拥塞窗口事件解析
├── count_threshold.py        # 阈值统计
├── fct_cdf_split.py          # FCT CDF分组分析
│
├── plot_cwnd.py              # 拥塞窗口绘图
├── plot_cwnd_change.py       # 拥塞窗口变化绘图
├── plot_send_rate.py         # 发送速率绘图
│
├── send_receive_bandwidth.py      # 发送/接收带宽计算
├── send_receive_bandwidth_jq.py   # 发送/接收带宽计算(jq版本)
└── subtract_csv.py           # CSV文件相减
```

## 环境要求

- Bash 4.0+
- Python 3.6+
- 依赖包：`pandas`, `numpy`, `matplotlib`

安装依赖：
```bash
pip3 install pandas numpy matplotlib
```

## 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `HTSIM_ROOT` | `/home/lrh/uet-htsim/htsim` | HTSIM 安装根目录 |
| `PARSE_OUTPUT` | `${HTSIM_ROOT}/sim/build/parse_output` | parse_output 工具路径 |
| `MAX_CONCURRENT` | `6` | 默认并发数 |
| `COUNT_THRESHOLD` | 自动检测 | count_threshold.py 路径 |

## 主脚本使用说明

### experiment.sh

主结果分析脚本，用于分析已完成的仿真实验结果。

**用法：**
```bash
./experiment.sh <实验组文件.json> [并发数]
```

**参数：**
- `实验组文件.json` - 包含实验配置的 JSON 文件（与实验运行时使用相同文件）
- `并发数` - 并行分析的实验数量（默认：6）

**使用示例：**
```bash
# 基本用法
./experiment.sh experiment_group_test.json

# 指定并发数
./experiment.sh experiment_group_test.json 8

# 自定义 HTSIM 路径
export HTSIM_ROOT=/custom/path/to/htsim
./experiment.sh experiment_group_test.json
```

**分析流程：**
1. 解析实验组文件
2. 对每个实验目录执行分析：
   - 解析 log 文件（如果存在）
   - 提取流映射 (`extract_flow_mapping.py`)
   - 分析拥塞窗口 (`analyze_cwnd.py`)
   - 绘制拥塞窗口图 (`plot_cwnd.py`)
   - 分析发送速率 (`analyze_send_rate.py`)
   - 绘制发送速率图 (`plot_send_rate.py`)
   - 分析接收速率 (`analyze_receive_rate.py`)
   - 分析网络时延 (`analyze_network_delay.py`)
3. 整体分析 (`analyze_experiments.py`)
4. 队列分析 (`analyze_queues.py`)
5. 队列深度阈值统计 (`count_threshold.py`)

## 独立分析脚本说明

### analyze_experiments.py

整体实验结果分析，生成统计摘要和图表。

**用法：**
```bash
python3 analyze_experiments.py [结果目录] [输出目录]
```

**示例：**
```bash
python3 analyze_experiments.py ./result ./figures
```

**输出：**
- `fcts_cdf.png` - FCT 累积分布图
- `experiment_summary.txt` - 实验统计摘要
- `experiment_details.csv` - 详细实验数据

### analyze_cwnd.py

拥塞窗口变化分析。

**用法：**
```bash
python3 analyze_cwnd.py -i <输入文件> -m <流映射文件> -o <输出文件> -e <事件文件>
```

**参数：**
- `-i, --input` - 输入结果文件
- `-m, --map` - 流映射文件
- `-o, --output` - 输出CSV文件
- `-e, --events` - 事件输出文件

### extract_flow_mapping.py

从结果文件中提取流映射。

**用法：**
```bash
python3 extract_flow_mapping.py -i <输入文件> -o <输出文件>
```

### fct_cdf_split.py

将流分成两组生成FCT CDF图（奇数组和其他组）。

**用法：**
```bash
python3 fct_cdf_split.py <实验组文件.json>
```

### count_threshold.py

统计CSV文件中每列超过阈值的值的数量。

**用法：**
```bash
python3 count_threshold.py -i <输入文件> -t <阈值> -o <输出文件> -p <图表文件>
```

## 注意事项

1. **路径设置**：首次使用前请确保 `HTSIM_ROOT` 环境变量指向正确的 HTSIM 安装路径

2. **依赖安装**：确保已安装所有 Python 依赖：
   ```bash
   pip3 install pandas numpy matplotlib
   ```

3. **并发设置**：根据机器性能调整 `MAX_CONCURRENT`，默认为 6

4. **磁盘空间**：实验结果可能占用大量磁盘空间，建议定期清理旧结果

5. **日志查看**：分析过程中会输出进度信息，可通过重定向保存日志：
   ```bash
   ./experiment.sh experiment.json 2>&1 | tee analysis.log
   ```

## 故障排除

### 1. "parse_output: command not found"

解决方案：
```bash
export PARSE_OUTPUT=/path/to/parse_output
# 或
export HTSIM_ROOT=/path/to/htsim  # 将自动推导 parse_output 路径
```

### 2. "ModuleNotFoundError: No module named 'pandas'"

解决方案：
```bash
pip3 install pandas numpy matplotlib
```

### 3. 权限不足

解决方案：
```bash
chmod +x experiment.sh config.sh
```

### 4. 找不到实验结果

确保实验已成功运行并生成结果目录，然后使用相同的实验组 JSON 文件运行分析脚本。

## 相关链接

- HTSIM 项目文档
- 实验配置指南
- 结果分析最佳实践
