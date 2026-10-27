#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "正在启动 AirMouse 服务..."

if [ -f "./venv/bin/python3" ]; then
    ./venv/bin/python3 server.py
elif command -v python3 >/dev/null 2>&1; then
    python3 server.py
else
    echo "未检测到 Python 3，请先安装 Python！"
    exit 1
fi
