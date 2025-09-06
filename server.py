from mcp.server.fastmcp import FastMCP
import requests
from tools.city2code import adcode
from dotenv import load_dotenv
import os
import json
import logging

from reload import run_server_with_reload

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

mcp = FastMCP("McpServer", stateless_http=True, port=8001)
load_dotenv()

# 全局变量现在在reload.py中定义



#目前只编写了实时天气获取
@mcp.tool()
def weather(city:str, extensions:str="base", output:str="JSON")->str:
    '''
    获取天气信息

    Args:
        city: 城市编码 adcode格式(必填)
        extensions: 气象类型,可选值:base/all(可选,默认base)
        output: 返回格式,可选值:JSON/XML(可选,默认JSON)

    Returns:
        str: 天气信息或错误信息

'''
    result = []
    base_url = "https://restapi.amap.com/v3/weather/weatherInfo"
    code = adcode(city)
    params = {
        
        "key": os.getenv("KEY"),
        "city": code,
        "extensions": extensions,
        "output": output
    }

    
    #调试
    logger.info(f"正在获取天气数据--------")
    
    try:
        #尝试访问API
        response = requests.get(base_url, params=params, timeout=10) 
        if response.status_code ==200:
            api_response = response.json()
            #检查API响应情况
            if api_response.get("status") == "1":
                weather_data = api_response.get("lives")
                return json.dumps(weather_data,ensure_ascii=False)
    except Exception as e:
        logger.error(f"访问API出现错误:{e}")

    

if __name__ == "__main__":
    logger.info("="*50)
    logger.info("MCP 服务器启动中...")
    logger.info("支持热重载和后台运行")
    logger.info("="*50)
    
    run_server_with_reload()
