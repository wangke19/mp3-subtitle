#!/bin/bash
# 豆包流水线 - 环境安装脚本

set -e

echo "📦 豆包图片去水印 + 调色流水线 安装程序"
echo "=========================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

echo "✅ Python 版本:"
python3 --version

# 检查 ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "📥 正在安装 ffmpeg..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y ffmpeg
    elif command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "❌ 无法自动安装 ffmpeg，请手动安装"
        exit 1
    fi
fi
echo "✅ FFmpeg 版本:"
ffmpeg -version | head -1

# 创建目录
echo "📁 创建工作目录..."
mkdir -p ~/doubao_pipeline/{bin,input,output,logs}

# 安装 GeminiWatermarkTool
TOOL_DIR="$HOME/doubao_pipeline/bin/GeminiWatermarkTool"
if [ ! -d "$TOOL_DIR" ]; then
    echo "📥 下载 GeminiWatermarkTool..."
    cd /tmp
    curl -sSL -o gwt.tar.gz https://github.com/allenk/GeminiWatermarkTool/archive/refs/heads/main.tar.gz
    mkdir -p "$TOOL_DIR"
    tar -xzf gwt.tar.gz -C "$TOOL_DIR" --strip-components=1
    rm gwt.tar.gz
    echo "✅ GeminiWatermarkTool 安装完成"
else
    echo "✅ GeminiWatermarkTool 已安装"
fi

# 验证安装
echo "🔍 验证工具..."
if [ -f "$TOOL_DIR/cli.py" ]; then
    echo "✅ 工具目录: $TOOL_DIR"
    python3 "$TOOL_DIR/cli.py" --help || true
else
    echo "⚠️  未找到 cli.py，尝试 pip 安装..."
    pip3 install gemini-watermark-tool 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "✅ 安装完成！"
echo ""
echo "使用方式:"
echo "  1. 把豆包生成的图片放入: ~/doubao_pipeline/input/"
echo "  2. 运行: python3 ~/doubao_pipeline/doubao_pipeline.py ~/doubao_pipeline/input"
echo "  3. 处理完成的图片在: ~/doubao_pipeline/output/"
echo ""
echo "目录结构:"
echo "  ~/doubao_pipeline/"
echo "  ├── bin/           # 工具目录"
echo "  ├── input/         # 放要处理的图片"
echo "  ├── output/        # 处理后的图片"
echo "  ├── logs/          # 日志"
echo "  └── doubao_pipeline.py  # 主脚本"