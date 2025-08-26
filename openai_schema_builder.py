import inspect
import json
from typing import get_type_hints, get_origin, get_args, Union
from dataclasses import dataclass
from enum import Enum


class SchemaBuilder:
    """自动构建OpenAI函数调用schema的工具类"""
    
    @staticmethod
    def python_type_to_json_schema(py_type):
        """将Python类型转换为JSON Schema类型"""
        type_mapping = {
            int: {"type": "integer"},
            float: {"type": "number"},
            str: {"type": "string"},
            bool: {"type": "boolean"},
            list: {"type": "array"},
            dict: {"type": "object"},
        }
        
        # 处理基本类型
        if py_type in type_mapping:
            return type_mapping[py_type]
        
        # 处理Union类型 (例如 Optional[str] = Union[str, None])
        if get_origin(py_type) is Union:
            args = get_args(py_type)
            # 过滤掉None类型
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                return SchemaBuilder.python_type_to_json_schema(non_none_args[0])
        
        # 处理List类型
        if get_origin(py_type) is list:
            args = get_args(py_type)
            if args:
                return {
                    "type": "array",
                    "items": SchemaBuilder.python_type_to_json_schema(args[0])
                }
            return {"type": "array"}
        
        # 默认返回string类型
        return {"type": "string"}
    
    @staticmethod
    def function_to_schema(func, tool_name=None, description=None):
        """
        从Python函数自动生成OpenAI函数调用schema
        
        Args:
            func: Python函数对象
            tool_name: 工具名称，默认使用函数名
            description: 工具描述，默认使用函数的docstring
        
        Returns:
            dict: OpenAI函数调用schema
        """
        # 获取函数签名
        sig = inspect.signature(func)
        
        # 获取类型提示
        try:
            type_hints = get_type_hints(func)
        except:
            type_hints = {}
        
        # 构建参数schema
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            # 跳过self参数
            if param_name == 'self':
                continue
                
            # 获取参数类型
            param_type = type_hints.get(param_name, str)
            
            # 转换为JSON Schema
            param_schema = SchemaBuilder.python_type_to_json_schema(param_type)
            
            # 添加描述（从参数注释或默认描述）
            param_schema["description"] = f"参数 {param_name}"
            
            properties[param_name] = param_schema
            
            # 判断是否为必需参数
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
        
        # 构建完整的schema
        schema = {
            "type": "function",
            "function": {
                "name": tool_name or func.__name__,
                "description": description or func.__doc__ or f"函数 {func.__name__}",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        
        return schema


class MCPSchemaGenerator:
    """MCP工具schema自动生成器"""
    
    def __init__(self):
        self.tool_registry = {}
    
    def register_tool_function(self, tool_name: str, func, description: str = None):
        """注册工具函数"""
        self.tool_registry[tool_name] = {
            'function': func,
            'description': description
        }
    
    def get_schema_for_tool(self, tool_name: str):
        """获取指定工具的schema"""
        if tool_name not in self.tool_registry:
            return None
        
        tool_info = self.tool_registry[tool_name]
        return SchemaBuilder.function_to_schema(
            tool_info['function'],
            tool_name,
            tool_info['description']
        )
    
    def get_all_schemas(self):
        """获取所有已注册工具的schema"""
        schemas = []
        for tool_name in self.tool_registry:
            schema = self.get_schema_for_tool(tool_name)
            if schema:
                schemas.append(schema)
        return schemas


# 示例：定义一些工具函数
def add(a: int, b: int) -> int:
    """两个整数相加"""
    return a + b

def multiply(a: int, b: int) -> int:
    """两个整数相乘"""
    return a * b

def search_web(query: str, max_results: int = 10) -> list:
    """在网络上搜索信息"""
    # 实际实现会调用搜索API
    return []

def calculate_area(length: float, width: float) -> float:
    """计算矩形面积"""
    return length * width


# 使用示例
if __name__ == "__main__":
    # 创建schema生成器
    generator = MCPSchemaGenerator()
    
    # 注册工具函数
    generator.register_tool_function("add", add, "执行两个数字的加法运算")
    generator.register_tool_function("multiply", multiply, "执行两个数字的乘法运算")
    generator.register_tool_function("search_web", search_web, "在互联网上搜索相关信息")
    generator.register_tool_function("calculate_area", calculate_area, "计算矩形的面积")
    
    # 获取所有schema
    schemas = generator.get_all_schemas()
    
    # 打印结果
    print("自动生成的OpenAI函数调用schemas:")
    print(json.dumps(schemas, indent=2, ensure_ascii=False))
