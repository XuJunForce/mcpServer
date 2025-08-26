import pandas as pd 
import os 
def adcode(city:str):
    # excel_path = os.path.join(os.getcwd(), "AMap_adcode_citycode.xlsx")
    excel_path = "/root/python_learn/mcpServer/AMap_adcode_citycode.xlsx"
    try:
        data = pd.read_excel(excel_path,sheet_name="Sheet1")
        result = data[data["name"]==city]
        if not result.empty:
            return result.iloc[0]['adcode']
        else:
            print("未找到对应的城市，默认返回深圳市天气")
            return 440300
    except Exception as e:
        print(f"读取数据错误:{e}")  
        print("默认返回深圳市天气")
        return 440300

        
if __name__ == "__main__":
    print(adcode("北京市"))
    print(adcode("东城区"))