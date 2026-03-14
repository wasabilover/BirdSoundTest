#!/bin/bash
# 观鸟助手 - 快速启动脚本
# 使用方式: ./run.sh [watch|demo|once]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON=$(which python3)
if [ -z "$PYTHON" ]; then
    echo "❌ 未找到 python3，请先安装 Python 3"
    exit 1
fi

MODE=${1:-once}

case "$MODE" in
    watch)
        echo "🔍 启动持续监控模式..."
        $PYTHON main.py --watch
        ;;
    demo)
        echo "🎮 启动演示模式..."
        $PYTHON main.py --demo
        ;;
    once|*)
        echo "📷 单次扫描内存卡..."
        $PYTHON main.py
        ;;
esac
