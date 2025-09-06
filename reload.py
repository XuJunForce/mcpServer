import time 
import logging 
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import signal
import sys
import time
import threading
import os 

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mcpserver.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("server.py")

# 全局变量用于控制服务器
server_running = True
reload_requested = False

# 热重载文件监控器
class ReloadHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_reload = time.time()
        
    def on_modified(self, event):
        global reload_requested
        if event.is_directory:
            return

        # 只监控Python文件
        if not event.src_path.endswith('.py'):
            return
        
        # 避免频繁重载
        current_time = time.time()
        if current_time - self.last_reload < 2:  # 2秒内不重复重载
            return

        self.last_reload = current_time
        logger.info(f"检测到文件变化: {event.src_path}")
        reload_requested = True

def setup_file_watcher():
    """设置文件监控器"""
    event_handler = ReloadHandler()
    observer = Observer()
    
    # 监控当前目录及子目录
    watch_path = Path(__file__).parent
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()
    logger.info(f"文件监控器已启动，监控路径: {watch_path}")
    return observer

def signal_handler(signum, frame):
    """处理信号"""
    global server_running
    logger.info(f"接收到信号 {signum}，准备关闭服务器...")
    server_running = False
    sys.exit(0)

def run_server_with_reload():
    """带有热重载功能的服务器运行器"""
    global server_running, reload_requested
    
    # 设置信号处理器
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # 启动文件监控器
    observer = setup_file_watcher()
    
    try:
        while server_running:
            try:
                logger.info("启动MCP服务器...")
                logger.info(f"服务器运行在端口 8001")
                logger.info("按 Ctrl+C 停止服务器")
                
                # 在新线程中运行服务器，以便可以检查重载请求
                # 这里需要从server.py导入mcp实例
                from server import mcp
                server_thread = threading.Thread(
                    target=lambda: mcp.run(transport="streamable-http"),
                    daemon=True
                )
                server_thread.start()
                
                # 检查重载请求
                while server_running and not reload_requested:
                    time.sleep(1)
                
                if reload_requested:
                    logger.info("检测到文件变化，正在重启服务器...")
                    reload_requested = False
                    # 这里我们使用进程重启的方式来实现热重载
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                    
            except KeyboardInterrupt:
                logger.info("接收到键盘中断，停止服务器...")
                break
            except Exception as e:
                logger.error(f"服务器运行错误: {e}")
                time.sleep(5)  # 等待5秒后重试
                
    finally:
        observer.stop()
        observer.join()
        logger.info("服务器已停止")
