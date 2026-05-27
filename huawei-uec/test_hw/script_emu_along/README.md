# HTSIM 仿真运行脚本目录 (script_emu_along)

本目录包含用于运行 HTSIM 网络仿真实验的脚本。

## 目录结构

```
script_emu_along/
├── README.md              # 本文件
├── config.sh              # 共享配置模块
├── experiment.sh          # 主实验运行脚本
└── alltoall.py            # 生成 all-to-all 连接矩阵
```

## 环境要求

- Bash 4.0+
- Python 3.6+
- HTSIM 仿真环境已正确安装

## config.sh 配置文件详解

`config.sh` 是共享配置模块，用于统一管理环境变量和通用函数。

### 工作原理

`config.sh` 被主脚本 `experiment.sh` 通过 `source` 命令加载，实现配置的统一管理和复用：

```bash
source "${SCRIPT_DIR}/config.sh"
```

### 环境变量说明

脚本支持通过环境变量自定义配置：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `HTSIM_ROOT` | `/home/lrh/uet-htsim/htsim` | HTSIM 安装根目录 |
| `PARSE_OUTPUT` | `${HTSIM_ROOT}/sim/build/parse_output` | parse_output 工具路径 |
| `MAX_CONCURRENT` | `6` | 默认并发数 |
| `LOG_LEVEL` | `INFO` | 日志级别 (DEBUG/INFO/WARN/ERROR) |

### 提供的函数

`config.sh` 提供了以下通用函数，可在主脚本中直接调用：

#### log_info "message"
输出信息日志（蓝色，仅在 LOG_LEVEL 为 DEBUG 或 INFO 时显示）

```bash
log_info "开始执行实验"
# 输出: [INFO] 开始执行实验
```

#### log_warn "message"
输出警告日志（黄色，始终显示）

```bash
log_warn "文件不存在，跳过"
# 输出: [WARN] 文件不存在，跳过
```

#### log_error "message"
输出错误日志（红色，始终显示）

```bash
log_error "实验执行失败"
# 输出: [ERROR] 实验执行失败
```

#### check_command "cmd"
检查命令是否存在，返回 0 表示存在，1 表示不存在

```bash
if check_command "python3"; then
    log_info "Python3 已安装"
else
    log_error "请先安装 Python3"
    exit 1
fi
```

### 使用示例

#### 方式一：使用默认配置
```bash
./experiment.sh experiment_group_test.json
```

#### 方式二：指定并发数
```bash
./experiment.sh experiment_group_test.json 8
```

#### 方式三：自定义 HTSIM 路径
```bash
export HTSIM_ROOT=/custom/path/to/htsim
./experiment.sh experiment_group_test.json
```

#### 方式四：调试模式（显示更多日志）
```bash
export LOG_LEVEL=DEBUG
./experiment.sh experiment_group_test.json
```

#### 方式五：自定义 parse_output 路径
```bash
export PARSE_OUTPUT=/custom/path/to/parse_output
./experiment.sh experiment_group_test.json
```

## 脚本说明

### experiment.sh

主实验运行脚本，负责并发执行仿真实验。

**用法：**
```bash
./experiment.sh <实验组文件.json> [并发数]
```

**参数：**
- `实验组文件.json` - 包含实验配置的 JSON 文件
- `并发数` - 并行运行的实验数量（默认：6，可通过环境变量 `MAX_CONCURRENT` 修改）

**实验组文件格式示例：**
```json
{
  "experiments": [
    {
      "name": "exp1",
      "command": "/path/to/simulator",
      "args": ["-c", "config1.txt"],
      "output": "result1.txt",
      "log": "log1.txt"
    }
  ]
}
```

**工作流程：**
1. 加载 `config.sh` 配置文件
2. 解析实验组 JSON 文件
3. 并发执行实验（受 `MAX_CONCURRENT` 限制）
4. 收集结果并输出状态

### alltoall.py

生成 all-to-all 连接矩阵，用于配置仿真实验的连接模式。

**用法：**
```bash
python3 alltoall.py
```

**配置参数（在脚本内修改）：**
- `NUM_NODES` - 节点数量
- `FLOW_SIZE` - 流大小（字节）
- `OUTPUT_FILE` - 输出文件路径

## 故障排除

### 1. 权限不足

```bash
chmod +x experiment.sh config.sh
```

### 2. 找不到 parse_output

确保 `HTSIM_ROOT` 环境变量正确设置，或手动指定 `PARSE_OUTPUT`：

```bash
export PARSE_OUTPUT=/path/to/parse_output
```

### 3. Python 依赖缺失

确保 Python 3.6+ 已安装：

```bash
python3 --version
```

### 4. 日志输出太多/太少

调整 `LOG_LEVEL` 环境变量：

```bash
# 显示所有日志
export LOG_LEVEL=DEBUG

# 只显示警告和错误
export LOG_LEVEL=WARN

# 默认级别（信息和以上）
export LOG_LEVEL=INFO
```

## 注意事项

1. **实验运行过程中会创建临时文件**，正常结束后会自动清理。如果脚本异常退出，可能需要手动清理 `/tmp/exp_status_*.txt` 等临时文件。

2. **定期检查磁盘空间**，实验结果可能占用较大空间。

3. **config.sh 的修改会立即生效**，无需重启终端，但需要在修改后重新运行主脚本。

4. **环境变量的优先级**：命令行参数 > 环境变量 > config.sh 中的默认值。
