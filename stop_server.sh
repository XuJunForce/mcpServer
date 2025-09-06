#!/bin/bash

# MCP服务器停止脚本

echo "🛑 MCP服务器停止脚本"
echo "=========================================="

# 方法1: 使用PID文件停止
if [ -f "server.pid" ]; then
    SERVER_PID=$(cat server.pid)
    echo "📄 从PID文件读取进程ID: $SERVER_PID"
    
    if ps -p $SERVER_PID > /dev/null; then
        echo "🔄 正在停止服务器进程 $SERVER_PID..."
        kill $SERVER_PID
        
        # 等待进程结束
        sleep 2
        
        if ps -p $SERVER_PID > /dev/null; then
            echo "⚠️  进程仍在运行，使用强制终止..."
            kill -9 $SERVER_PID
        fi
        
        echo "✅ 服务器已停止"
        rm -f server.pid
    else
        echo "⚠️  PID文件中的进程不存在，清理PID文件"
        rm -f server.pid
    fi
else
    echo "📄 未找到PID文件"
fi

# 方法2: 按进程名停止
echo "🔍 查找所有server.py进程..."
PIDS=$(pgrep -f "python.*server.py")

if [ -n "$PIDS" ]; then
    echo "发现进程: $PIDS"
    echo "🔄 停止所有server.py进程..."
    pkill -f "python.*server.py"
    sleep 2
    
    # 检查是否还有残留进程
    REMAINING=$(pgrep -f "python.*server.py")
    if [ -n "$REMAINING" ]; then
        echo "⚠️  强制终止残留进程: $REMAINING"
        pkill -9 -f "python.*server.py"
    fi
    
    echo "✅ 所有server.py进程已停止"
else
    echo "ℹ️  未找到运行中的server.py进程"
fi

# 检查端口占用
echo "🔍 检查端口8001占用情况..."
PORT_PID=$(lsof -ti:8001 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "⚠️  端口8001仍被进程 $PORT_PID 占用"
    echo "🔄 释放端口..."
    kill -9 $PORT_PID 2>/dev/null
    echo "✅ 端口已释放"
else
    echo "✅ 端口8001未被占用"
fi

# 清理文件
echo "🧹 清理临时文件..."
rm -f server.pid nohup.out

echo ""
echo "🎯 服务器停止完成！"
echo ""
echo "📊 当前状态:"
echo "   进程检查: $(pgrep -f 'python.*server.py' | wc -l) 个相关进程"
echo "   端口状态: $(lsof -ti:8001 2>/dev/null | wc -l) 个端口占用"
