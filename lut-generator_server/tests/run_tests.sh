#!/bin/bash
#
# 运行第 4 周预览功能模块的单元测试
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$PROJECT_DIR/src"

echo "======================================"
echo " LUT Generator - 第 4 周单元测试"
echo "======================================"
echo ""

# 检查虚拟环境
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "错误：虚拟环境不存在"
    echo "请先运行：cd $PROJECT_DIR && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 激活虚拟环境
source "$PROJECT_DIR/.venv/bin/activate"

# 安装测试依赖
echo "检查测试依赖..."
pip install pytest pytest-cov --quiet

echo ""
echo "运行测试..."
echo ""

# 设置 Python 路径
export PYTHONPATH="$SRC_DIR:$PYTHONPATH"

# 运行测试
cd "$SCRIPT_DIR"
pytest \
    test_lut_applier.py \
    test_preview_generator.py \
    test_visualizer.py \
    test_html_report.py \
    -v \
    --tb=short \
    --cov="$SRC_DIR" \
    --cov-report=term-missing \
    --cov-report=html:"$PROJECT_DIR/tests/htmlcov" \
    "$@"

echo ""
echo "======================================"
echo " 测试完成!"
echo "======================================"
echo ""
echo "覆盖率报告：$PROJECT_DIR/tests/htmlcov/index.html"
echo ""
