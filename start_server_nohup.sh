#!/bin/bash

# MCP服务器后台启动脚本
# 使用虚拟环境和nohup运行

echo "🚀 MCP服务器后台启动脚本"
echo "=========================================="

# 检查当前目录
if [ ! -f "server.py" ]; then
    echo "❌ 错误: 未找到server.py文件"
    echo "请确保在正确的目录中运行此脚本"
    exit 1
fi

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "❌ 错误: 未找到.venv虚拟环境"
    echo "请先创建虚拟环境: python3 -m venv .venv"
    exit 1
fi

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source .venv/bin/activate

if [ $? -ne 0 ]; then
    echo "❌ 错误: 无法激活虚拟环境"
    exit 1
fi

echo "✅ 虚拟环境已激活: $VIRTUAL_ENV"

# 检查Python和依赖
echo "🔍 检查Python环境..."
python --version

# 检查是否有requirements.txt并安装依赖
if [ -f "requirements.txt" ]; then
    echo "📦 检查并安装依赖..."
    pip install -r requirements.txt --quiet
else
    echo "⚠️  未找到requirements.txt，跳过依赖安装"
fi

# 停止已运行的服务器
echo "🛑 检查并停止已运行的服务器..."
pkill -f "python.*server.py" 2>/dev/null && echo "已停止旧的服务器进程" || echo "没有发现运行中的服务器"

# 等待端口释放
sleep 2

# 使用nohup启动服务器
echo "🌟 使用nohup启动MCP服务器..."
nohup python server.py > server.log 2>&1 &

# 获取进程ID
SERVER_PID=$!
echo $SERVER_PID > server.pid

echo "✅ MCP服务器已在后台启动"
echo "   进程ID: $SERVER_PID"
echo "   日志文件: server.log"
echo "   PID文件: server.pid"

# 等待几秒检查服务器是否成功启动
echo "⏳ 检查服务器启动状态..."
sleep 3

if ps -p $SERVER_PID > /dev/null; then
    echo "🎉 服务器启动成功！"
    echo ""
    echo "📋 管理命令:"
    echo "   查看日志: tail -f server.log"
    echo "   停止服务: kill $SERVER_PID"
    echo "   或使用: pkill -f 'python.*server.py'"
    echo ""
    
    # 检查日志中是否有错误
    if [ -f "server.log" ]; then
        echo "📄 最近日志:"
        tail -5 server.log
    fi
else
    echo "❌ 服务器启动失败"
    echo "📄 错误日志:"
    if [ -f "server.log" ]; then
        cat server.log
    else
        echo "未找到日志文件"
    fi
    exit 1
fi

echo ""
echo "🔧 有用的命令:"
echo "   ps aux | grep server.py    # 查看进程"
echo "   netstat -tlnp | grep :8001 # 检查端口"
echo "   ./stop_server.sh           # 停止服务器"
