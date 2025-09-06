#!/bin/bash

# MCP聊天服务器启动脚本

echo "=========================================="
echo "       MCP智能聊天助手启动脚本"
echo "=========================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python"
    exit 1
fi

# 检查当前目录
if [ ! -f "chat_server.py" ]; then
    echo "错误: 未找到chat_server.py文件，请确保在正确的目录中运行此脚本"
    exit 1
fi

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "警告: 未找到.env文件，请确保已配置以下环境变量："
    echo "  - OPENAI_API_KEY: OpenAI API密钥"
    echo "  - OPENAI_BASE_URL: OpenAI API基础URL"
    echo "  - MCP_SERVER_URL: MCP服务器URL (可选)"
    echo ""
fi


echo ""
echo "启动MCP聊天服务器..."
echo "服务器地址: http://localhost:8002"
echo "按 Ctrl+C 停止服务器"
echo ""

# 启动服务器
nohup python3 chat_server.py > chat.log 2>&1 &
echo "日志文件存放于chat.log"
