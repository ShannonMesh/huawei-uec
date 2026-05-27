#!/bin/bash
# 配置文件 - 定义可配置的路径变量
# 使用方法: source config.sh

# 自动检测脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 自动检测项目根目录（脚本位于 script_result_along/ 下，项目根目录是父目录的父目录）
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# 可配置的路径变量（可通过环境变量覆盖）
# 注意：根据实际路径结构，parse_output 位于 ${PROJECT_ROOT}/htsim/sim/build/parse_output
export HTSIM_ROOT="${HTSIM_ROOT:-${PROJECT_ROOT}}"
export PARSE_OUTPUT="${PARSE_OUTPUT:-${HTSIM_ROOT}/htsim/sim/build/parse_output}"

# 日志级别控制
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

# 帮助函数
log_info() {
    if [[ "$LOG_LEVEL" == "DEBUG" || "$LOG_LEVEL" == "INFO" ]]; then
        echo -e "[\033[0;34mINFO\033[0m] $1"
    fi
}

log_warn() {
    echo -e "[\033[0;33mWARN\033[0m] $1"
}

log_error() {
    echo -e "[\033[0;31mERROR\033[0m] $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "未找到命令: $1"
        return 1
    fi
    return 0
}
