#!/bin/bash

set -euo pipefail

# ============================================================================
# HTSIM 实验运行脚本
# 用于运行仿真实验组
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
HTSIM 实验运行脚本

用法: $0 <实验组文件.json> [并发数]

参数:
  实验组文件.json    包含实验配置的JSON文件路径
  并发数             并行运行的实验数量（默认: ${MAX_CONCURRENT}）

环境变量:
  HTSIM_ROOT         htsim根目录路径（默认: /home/lrh/uet-htsim/htsim）
  PARSE_OUTPUT       parse_output工具路径（默认: \${HTSIM_ROOT}/sim/build/parse_output）
  MAX_CONCURRENT     默认并发数

示例:
  $0 experiment_group_test.json
  $0 experiment_group_test.json 8
  HTSIM_ROOT=/custom/path $0 experiment.json

EOF
}

# 参数验证
if [[ $# -eq 0 ]]; then
    show_help
    echo ""
    ls -1 experiment_group_*.json 2>/dev/null | xargs -n1 basename || true
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
mkdir -p "$EXPERIMENT_RESULT_DIR"

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
base_dir = os.path.dirname(os.path.abspath(exp_group))

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
    args_list = exp.get('args', [])

    new_args = []
    for arg in args_list:
        if arg.startswith('-'):
            new_args.append(arg)
        elif os.path.isabs(arg):
            new_args.append(arg)
        else:
            full_path = os.path.join(base_dir, arg)
            if os.path.exists(full_path):
                new_args.append(os.path.abspath(full_path))
            else:
                new_args.append(arg)

    cmd = exp['command'] + ' ' + ' '.join(new_args)
    if exp.get('log'): cmd += ' -o ' + exp['log']
    print(f\"{exp['name']}|{cmd}|{exp.get('output', '')}|{exp.get('log','')}\")
" > "$EXPS_FILE" || { err "解析实验组文件失败"; exit 1; }

# 运行单个实验
run_one() {
    local name=$1 cmd=$2 result=$3 logf=$4
    local dir="${EXPERIMENT_RESULT_DIR}/${name}"
    mkdir -p "$dir"

    inf "开始实验: $name"

    # 将结果和日志路径转换为绝对路径
    local abs_result abs_logf
    if [[ "$result" == /* ]]; then
        abs_result="$result"
    else
        abs_result="${BASE_DIR}/$result"
    fi

    if [[ -n "$logf" ]]; then
        if [[ "$logf" == /* ]]; then
            abs_logf="$logf"
        else
            abs_logf="${BASE_DIR}/$logf"
        fi
    fi

    # 运行实验
    if eval "$cmd > \"$abs_result\" 2>/dev/null" && [[ -f "$abs_result" ]]; then
        # 拷贝结果文件
        mv "$abs_result" "$dir/result.txt"

        # 拷贝并解析 log 文件
        if [[ -n "${abs_logf:-}" && -f "$abs_logf" ]]; then
            mv "$abs_logf" "$dir/result.log"
            if [[ -x "$PARSE_OUTPUT" ]]; then
                "$PARSE_OUTPUT" "$dir/result.log" -ascii > "$dir/result_parsed.log" 2>&1
            else
                warn "parse_output不可用: $PARSE_OUTPUT"
            fi
        fi

        echo "S:$name" >> "$STATUS_FILE"
        msg "实验完成: $name"
    else
        echo "F:$name" >> "$STATUS_FILE"
        err "实验失败: $name"
    fi
}

# 启动并发控制
run_with_concurrency() {
    while IFS='|' read -r name cmd result logf; do
        # 等待并发槽位
        while [[ $(wc -l < "$PIDS_FILE" 2>/dev/null || echo 0) -ge $MAX_CONCURRENT ]]; do
            sleep 1
            # 清理已完成的进程
            for pid in $(cat "$PIDS_FILE" 2>/dev/null | grep -v '^$' || true); do
                kill -0 "$pid" 2>/dev/null || sed -i "/^$pid$/d" "$PIDS_FILE" 2>/dev/null || true
            done
        done

        run_one "$name" "$cmd" "$result" "$logf" &
        echo $! >> "$PIDS_FILE"
        inf "实验 $name 已启动 (PID: $!)"
    done < "$EXPS_FILE"
}

# 等待所有实验完成
wait_all() {
    rm -f "$EXPS_FILE"
    inf "等待实验完成..."
    while [[ -s "$PIDS_FILE" ]]; do
        sleep 1
        for pid in $(cat "$PIDS_FILE" 2>/dev/null | grep -v '^$' || true); do
            kill -0 "$pid" 2>/dev/null || sed -i "/^$pid$/d" "$PIDS_FILE" 2>/dev/null || true
        done
    done
    rm -f "$PIDS_FILE"
    msg "所有实验已完成"
}

# 主流程
run_with_concurrency
wait_all

# 清理
rm -f "$STATUS_FILE"
exit 0
