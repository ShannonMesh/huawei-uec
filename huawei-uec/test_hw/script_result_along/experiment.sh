#!/bin/bash

set -euo pipefail

# ============================================================================
# HTSIM 实验结果分析脚本
# 用于分析已运行的仿真实验结果
# ============================================================================

# 自动检测脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# 可配置的路径（可通过环境变量覆盖）
PARSE_OUTPUT="${PARSE_OUTPUT:-${HTSIM_ROOT}/sim/build/parse_output}"
MAX_CONCURRENT="${MAX_CONCURRENT:-6}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'

msg() { echo -e "${GREEN}✓${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }
inf() { echo -e "${BLUE}ℹ${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

# 显示帮助信息
show_help() {
    cat << EOF
HTSIM 实验结果分析脚本

用法: $0 <实验组文件.json> [并发数]

参数:
  实验组文件.json    包含实验配置的JSON文件路径
  并发数             并行分析的实验数量（默认: ${MAX_CONCURRENT}）

环境变量:
  HTSIM_ROOT         htsim根目录路径（默认: /home/lrh/uet-htsim/htsim）
  PARSE_OUTPUT       parse_output工具路径（默认: \${HTSIM_ROOT}/sim/build/parse_output）
  MAX_CONCURRENT     默认并发数
  COUNT_THRESHOLD    count_threshold.py脚本路径（默认: 自动检测）

示例:
  $0 experiment_group_test.json
  $0 experiment_group_test.json 8
  HTSIM_ROOT=/custom/path $0 experiment.json

EOF
}

# 查找count_threshold.py脚本
find_count_threshold() {
    local search_paths=(
        "${SCRIPT_DIR}/count_threshold.py"
        "${SCRIPT_DIR}/../script/count_threshold.py"
        "${COUNT_THRESHOLD:-}"
    )

    for path in "${search_paths[@]}"; do
        if [[ -f "$path" ]]; then
            echo "$path"
            return 0
        fi
    done

    # 尝试which查找
    which count_threshold.py 2>/dev/null || true
}

COUNT_THRESHOLD_SCRIPT=$(find_count_threshold)

# 参数验证
if [[ $# -eq 0 ]]; then
    show_help
    exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

EXPERIMENT_GROUP="$1"
[[ -n "${2:-}" ]] && MAX_CONCURRENT="$2"

# 检查文件存在性
if [[ ! -f "$EXPERIMENT_GROUP" ]]; then
    err "实验组文件不存在: $EXPERIMENT_GROUP"
    exit 1
fi

# 解析目录结构
BASE_DIR=$(dirname "$(realpath "$EXPERIMENT_GROUP")")
RESULT_DIR="${BASE_DIR}/result"
EXPERIMENT_RESULT_DIR="${RESULT_DIR}_$(basename "$EXPERIMENT_GROUP" .json | sed 's/^experiment_group_//')"

if [[ ! -d "$EXPERIMENT_RESULT_DIR" ]]; then
    err "结果目录不存在: $EXPERIMENT_RESULT_DIR"
    exit 1
fi

inf "并发: ${MAX_CONCURRENT} | 实验组: $(basename "$EXPERIMENT_GROUP") | 结果: ${EXPERIMENT_RESULT_DIR}"
echo ""

# 临时文件
STATUS_FILE="/tmp/exp_status_$$.txt"
PIDS_FILE="/tmp/exp_pids_$$.txt"
EXPS_FILE="/tmp/exps_$$.txt"
> "$STATUS_FILE"
> "$PIDS_FILE"

# 解析实验组文件
python3 -c "
import json
import os
import sys

exp_group = '${EXPERIMENT_GROUP}'

try:
    with open(exp_group) as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    print(f'Error: Invalid JSON - {e}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)

for exp in data.get('experiments', []):
    print(f\"{exp['name']}|{exp.get('log','')}\")
" > "$EXPS_FILE" || { err "解析实验组文件失败"; exit 1; }

# 运行单个实验分析
analyze_one() {
    local name=$1 logf=$2
    local dir="${EXPERIMENT_RESULT_DIR}/${name}"

    if [[ ! -d "$dir" ]]; then
        err "实验目录不存在: $dir"
        echo "F:$name" >> "$STATUS_FILE"
        return
    fi

    if [[ ! -f "$dir/result.txt" ]]; then
        err "结果文件不存在: $dir/result.txt"
        echo "F:$name" >> "$STATUS_FILE"
        return
    fi

    inf "正在分析: $name"

    # 如果存在 result.log 但不存在 result_parsed.log，则解析
    if [[ -f "$dir/result.log" && ! -f "$dir/result_parsed.log" ]]; then
        if [[ -x "$PARSE_OUTPUT" ]]; then
            "$PARSE_OUTPUT" "$dir/result.log" -ascii > "$dir/result_parsed.log" 2>&1
        else
            warn "parse_output不可用: $PARSE_OUTPUT"
        fi
    fi

    # 提取流映射
    python3 "$SCRIPT_DIR/extract_flow_mapping.py" -i "$dir/result.txt" -o "$dir/cwnd_flow_map.txt" 2>/dev/null || true

    # 分析拥塞窗口
    python3 "$SCRIPT_DIR/analyze_cwnd.py" -i "$dir/result.txt" -m "$dir/cwnd_flow_map.txt" -o "$dir/cwnd_change.csv" -e "$dir/cwnd_events.txt" 2>/dev/null || true

    # 绘制拥塞窗口图
    python3 "$SCRIPT_DIR/plot_cwnd.py" -i "$dir/cwnd_change.csv" -o "$dir/cwnd_plot.png" -n 5 2>/dev/null || true

    # 分析发送速率
    python3 "$SCRIPT_DIR/analyze_send_rate.py" -i "$dir/result.txt" -o "$dir/send_rate_per_flow.csv" -n "$dir/send_rate_per_node.csv" 2>/dev/null || true

    # 绘制发送速率图
    if [[ -f "$dir/send_rate_per_flow.csv" ]]; then
        python3 "$SCRIPT_DIR/plot_send_rate.py" -i "$dir/send_rate_per_flow.csv" -o "$dir/send_rate_plot.png" -n 5 2>/dev/null || true
    fi

    # 分析接收速率
    if [[ -f "$dir/result_parsed.log" ]]; then
        python3 "$SCRIPT_DIR/analyze_receive_rate.py" -i "$dir/result_parsed.log" -o "$dir/receive_rate.csv" 2>/dev/null || true
    fi

    # 数据包在网时延统计
    if [[ -f "$dir/cwnd_flow_map.txt" ]]; then
        python3 "$SCRIPT_DIR/analyze_network_delay.py" "$dir/result.txt" "$dir/cwnd_flow_map.txt" "$dir/network_delay_stats.csv" 2>/dev/null || true
    fi

    echo "S:$name" >> "$STATUS_FILE"
    msg "分析完成: $name"
}

# 队列分析
run_queue_analysis() {
    inf "生成队列分析报告..."
    python3 "$SCRIPT_DIR/analyze_queues.py" -i "$EXPERIMENT_RESULT_DIR" 2>/dev/null || warn "队列分析失败"

    # 为每个实验生成队列深度阈值统计
    if [[ -n "$COUNT_THRESHOLD_SCRIPT" && -f "$COUNT_THRESHOLD_SCRIPT" ]]; then
        inf "生成队列深度阈值统计..."
        for exp_dir in "$EXPERIMENT_RESULT_DIR"/*/; do
            if [[ -f "$exp_dir/queue_depth.csv" ]]; then
                python3 "$COUNT_THRESHOLD_SCRIPT" \
                    -i "$exp_dir/queue_depth.csv" \
                    -o "$exp_dir/queue_depth_threshold.csv" \
                    -t 1245000 2>/dev/null || true
            fi
        done
    else
        warn "count_threshold.py未找到，跳过阈值统计"
    fi
}

# 启动并发控制
run_with_concurrency() {
    while IFS='|' read -r name logf; do
        # 等待并发槽位
        while [[ $(wc -l < "$PIDS_FILE" 2>/dev/null || echo 0) -ge $MAX_CONCURRENT ]]; do
            sleep 0.5
            for pid in $(cat "$PIDS_FILE" 2>/dev/null | grep -v '^$' || true); do
                kill -0 "$pid" 2>/dev/null || sed -i "/^$pid$/d" "$PIDS_FILE" 2>/dev/null || true
            done
        done

        analyze_one "$name" "$logf" &
        echo $! >> "$PIDS_FILE"
    done < "$EXPS_FILE"
}

# 等待所有分析完成
wait_all() {
    rm -f "$EXPS_FILE"
    inf "等待分析完成..."
    while [[ -s "$PIDS_FILE" ]]; do
        sleep 0.5
        for pid in $(cat "$PIDS_FILE" 2>/dev/null | grep -v '^$' || true); do
            kill -0 "$pid" 2>/dev/null || sed -i "/^$pid$/d" "$PIDS_FILE" 2>/dev/null || true
        done
    done
    rm -f "$PIDS_FILE"
    msg "所有分析已完成"
}

# 主流程
run_with_concurrency
wait_all

# 整体分析
if [[ -s "$STATUS_FILE" ]]; then
    python3 "$SCRIPT_DIR/analyze_experiments.py" "$EXPERIMENT_RESULT_DIR" "${EXPERIMENT_RESULT_DIR}/概要" 2>/dev/null && msg "整体分析完成" || warn "整体分析失败"
fi

# 队列分析
run_queue_analysis

# 清理
rm -f "$STATUS_FILE"
exit 0
