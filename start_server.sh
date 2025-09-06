#!/bin/bash

# MCP服务器启动脚本
# 支持前台运行、后台运行和热重载
source .venv/bin/activate
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_SCRIPT="$SCRIPT_DIR/server.py"
PID_FILE="$SCRIPT_DIR/mcpserver.pid"
LOG_FILE="$SCRIPT_DIR/mcpserver.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 函数：显示使用方法
show_usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  start           前台启动服务器"
    echo "  start-bg        后台启动服务器 (使用nohup)"
    echo "  stop            停止后台服务器"
    echo "  restart         重启后台服务器"
    echo "  status          查看服务器状态"
    echo "  logs            查看服务器日志"
    echo "  tail-logs       实时查看服务器日志"
    echo "  help            显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start         # 前台启动"
    echo "  $0 start-bg      # 后台启动"
    echo "  $0 status        # 查看状态"
    echo "  $0 logs          # 查看日志"
}

# 函数：检查是否已安装依赖
check_dependencies() {
    echo -e "${YELLOW}检查依赖...${NC}"
    
    # 检查Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: 未找到 python3${NC}"
        exit 1
    fi
    
    # 检查必要的Python包
    python3 -c "import watchdog" 2>/dev/null || {
        echo -e "${YELLOW}警告: 未安装 watchdog 包，正在安装...${NC}"
        pip3 install watchdog
    }
    
    echo -e "${GREEN}依赖检查完成${NC}"
}

# 函数：获取服务器进程ID
get_server_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "$pid"
        else
            rm -f "$PID_FILE"
            echo ""
        fi
    else
        echo ""
    fi
}

# 函数：检查服务器状态
check_status() {
    local pid=$(get_server_pid)
    if [ -n "$pid" ]; then
        echo -e "${GREEN}服务器正在运行 (PID: $pid)${NC}"
        
        # 检查端口是否开放
        if netstat -tlnp 2>/dev/null | grep ":8001 " > /dev/null; then
            echo -e "${GREEN}端口 8001 正在监听${NC}"
        else
            echo -e "${YELLOW}警告: 端口 8001 未在监听${NC}"
        fi
        return 0
    else
        echo -e "${RED}服务器未运行${NC}"
        return 1
    fi
}

# 函数：前台启动服务器
start_foreground() {
    echo -e "${GREEN}前台启动MCP服务器...${NC}"
    cd "$SCRIPT_DIR"
    python3 "$SERVER_SCRIPT"
}

# 函数：后台启动服务器
start_background() {
    local pid=$(get_server_pid)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}服务器已在运行 (PID: $pid)${NC}"
        return 1
    fi
    
    echo -e "${GREEN}后台启动MCP服务器...${NC}"
    cd "$SCRIPT_DIR"
    
    # 使用nohup后台启动
    nohup python3 "$SERVER_SCRIPT" > "$LOG_FILE" 2>&1 &
    local new_pid=$!
    
    # 保存PID
    echo "$new_pid" > "$PID_FILE"
    
    # 等待一下确保启动成功
    sleep 2
    
    if ps -p "$new_pid" > /dev/null 2>&1; then
        echo -e "${GREEN}服务器启动成功 (PID: $new_pid)${NC}"
        echo -e "${GREEN}日志文件: $LOG_FILE${NC}"
        echo -e "${GREEN}使用 '$0 logs' 查看日志${NC}"
        echo -e "${GREEN}使用 '$0 status' 查看状态${NC}"
    else
        echo -e "${RED}服务器启动失败${NC}"
        rm -f "$PID_FILE"
        return 1
    fi
}

# 函数：停止服务器
stop_server() {
    local pid=$(get_server_pid)
    if [ -z "$pid" ]; then
        echo -e "${YELLOW}服务器未运行${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}停止服务器 (PID: $pid)...${NC}"
    
    # 尝试优雅停止
    kill "$pid"
    
    # 等待进程停止
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    # 如果还没停止，强制杀死
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}强制停止服务器...${NC}"
        kill -9 "$pid"
        sleep 1
    fi
    
    # 清理PID文件
    rm -f "$PID_FILE"
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}服务器已停止${NC}"
    else
        echo -e "${RED}无法停止服务器${NC}"
        return 1
    fi
}

# 函数：重启服务器
restart_server() {
    echo -e "${YELLOW}重启服务器...${NC}"
    stop_server
    sleep 2
    start_background
}

# 函数：查看日志
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${GREEN}显示服务器日志:${NC}"
        echo "=================================="
        cat "$LOG_FILE"
    else
        echo -e "${YELLOW}日志文件不存在: $LOG_FILE${NC}"
    fi
}

# 函数：实时查看日志
tail_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${GREEN}实时查看服务器日志 (按 Ctrl+C 退出):${NC}"
        echo "=================================="
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}日志文件不存在: $LOG_FILE${NC}"
        echo -e "${YELLOW}请先启动服务器${NC}"
    fi
}

# 主程序
main() {
    case "${1:-help}" in
        "start")
            check_dependencies
            start_foreground
            ;;
        "start-bg")
            check_dependencies
            start_background
            ;;
        "stop")
            stop_server
            ;;
        "restart")
            check_dependencies
            restart_server
            ;;
        "status")
            check_status
            ;;
        "logs")
            show_logs
            ;;
        "tail-logs")
            tail_logs
            ;;
        "help"|"--help"|"-h")
            show_usage
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# 执行主程序
main "$@"
