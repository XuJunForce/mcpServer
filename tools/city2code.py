import pandas as pd 
import os 
def adcode(city:str):
    '''
    根据用户的城市，返回对应的高德地图支持的城市编码
    
    Args:
        city: 城市名
    
    Returns:
        result:对应的城市编码
    '''
    execel_path = os.path.join(os.getcwd(), "AMap_adcode_citycode.xlsx")
    try:
        data = pd.read_excel(execel_path,sheet_name="Sheet1")
        print(f"execel_path : {execel_path}")
        #精确匹配：
        result = data[data["name"]==city]
        if not result.empty:
            return result.iloc[0]['adcode']
        # suffixes = ["市", "省", "县", "区", "自治区", "特别行政区"]

        else:
            print("未找到对应的城市，默认返回深圳市天气")
            return 440300
        
    except Exception as e:
        print(f"读取数据错误:{e}")  
        print("默认返回深圳市天气")
        return 440300
