import os,json,requests
from tools.city2code import adcode 
from dotenv import load_dotenv

load_dotenv()

def weather(city:str, extensions:str="base", output:str="JSON")->str:
    result = []
    """
    获取天气信息
    
    Args:
        city: 城市编码 adcode格式(必填)
        extensions: 气象类型,可选值:base/all(可选,默认base)
        output: 返回格式,可选值:JSON/XML(可选,默认JSON)
    
    Returns:
        str: 天气信息或错误信息
    """
    base_url = "https://restapi.amap.com/v3/weather/weatherInfo"
    code = adcode(city)
    params = {
        "key": os.getenv("KEY"),
        "city": code,
        "extensions": extensions,
        "output": output
    }

    #调试
    print(f"正在获取天气数据--------")
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
        print(f"访问API出现错误:{e}")

if __name__ == "__main__":
    print(weather("北京市"))
