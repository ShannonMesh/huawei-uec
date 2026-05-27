#!/bin/bash

# 实验配置
# 自动检测项目根目录（脚本位于 script_emu_along/ 下，项目根目录是父目录的父目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# 注意：根据实际路径结构，parse_output 位于 ${PROJECT_ROOT}/htsim/sim/build/parse_output
export HTSIM_ROOT="${HTSIM_ROOT:-${PROJECT_ROOT}}"
export PARSE_OUTPUT="${PARSE_OUTPUT:-${HTSIM_ROOT}/htsim/sim/build/parse_output}"
