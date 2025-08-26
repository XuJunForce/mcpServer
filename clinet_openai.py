import asyncio
import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()

class MCPAgent:
    def __init__(self, openai_client, mcp_session):
        self.openai_client = openai_client
        self.mcp_session = mcp_session
        self.available_tools = []
    
    async def call_mcp_tool(self, tool_name, parameters):
        """调用 MCP 工具"""
        try:
            result = await self.mcp_session.call_tool(tool_name, parameters)
            if result.content:
                return result.content[0].text
            return "工具调用成功，但没有返回结果"
        except Exception as e:
            return f"工具调用失败: {str(e)}"
    
    def get_openai_tools_schema(self):
        """将 MCP 工具转换为 OpenAI 函数调用格式"""
        openai_tools = []
        for tool in self.available_tools:
            # 构建 OpenAI 工具的 schema
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"MCP tool: {tool.name}",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            # 根据工具名称添加参数定义
            if tool.name == "add":
                tool_schema["function"]["parameters"] = {
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer", "description": "第一个数字"},
                        "b": {"type": "integer", "description": "第二个数字"}
                    },
                    "required": ["a", "b"]
                }
            elif tool.name == "multiply":
                tool_schema["function"]["parameters"] = {
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer", "description": "第一个数字"},
                        "b": {"type": "integer", "description": "第二个数字"}
                    },
                    "required": ["a", "b"]
                }
            
            openai_tools.append(tool_schema)
        
        return openai_tools
    
    async def chat_with_tools(self, user_message):
        """使用工具进行对话"""
        messages = [
            {
                "role": "system", 
                "content": "You are a helpful math teacher that can perform calculations. When you need to calculate something, use the available tools. Always show your work and explain the steps."
            },
            {"role": "user", "content": user_message}
        ]
        
        tools = self.get_openai_tools_schema()
        
        try:
            # 第一次调用 OpenAI
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=500
            )
            
            response_message = response.choices[0].message
            
            # 检查是否需要调用工具
            if response_message.tool_calls:
                # print("工具选择回答:",response_message.content)
                # print("tool_calls:",response_message.tool_calls)
                # 添加助手的响应到消息历史
                messages.append({
                    "role": "assistant",
                    "content": response_message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": tool_call.type,
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        } for tool_call in response_message.tool_calls
                    ]
                })
                
                # 执行工具调用
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    print(f"🔧 调用工具: {function_name} 参数: {function_args}")
                    
                    # 调用 MCP 工具
                    tool_result = await self.call_mcp_tool(function_name, function_args)
                    
                    # 添加工具结果到消息历史
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(tool_result)
                    })
                
                # 第二次调用 OpenAI 获取最终答案
                final_response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=300
                )
                
                return final_response.choices[0].message.content
            else:
                return response_message.content
                
        except Exception as e:
            return f"对话过程中发生错误: {str(e)}"
    


async def main():
    # 初始化 OpenAI 客户端
    openai_client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL")
    )
    
    # 使用正确的异步上下文管理器模式
    mcp_server_url = "http://localhost:8000/mcp"
    
    try:
        # 连接到 MCP 服务器
        async with streamablehttp_client(mcp_server_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as mcp_session:
                # 初始化连接
                await mcp_session.initialize()
                
                # 获取可用工具
                tools_response = await mcp_session.list_tools()
                available_tools = tools_response.tools
                
                print(f"✅ 连接到 MCP 服务器: {mcp_server_url}")
                print(f"📋 可用工具 ({len(available_tools)}):")
                for tool in available_tools:
                    print(f" • {tool.name}: {tool.description}")
                
                # 创建 MCP Agent
                agent = MCPAgent(openai_client, mcp_session)
                agent.available_tools = available_tools
                
                # 测试对话
                print("\n💬 开始对话...")
                
                test_questions = [
                    "What is 25 plus 17? Use the calculator tool to work this out."
                ]
                
                for question in test_questions:
                    print(f"\n👤 用户: {question}")
                    response = await agent.chat_with_tools(question)
                    print(f"🤖 助手: {response}")
                    
    except Exception as e:
        print(f"❌ 运行时错误: {e}")
    
    print("🧹 连接已自动清理")

if __name__ == "__main__":
    print("🚀 启动 MCP Agent...")
    asyncio.run(main())