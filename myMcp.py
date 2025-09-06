import asyncio
import os
import json
import argparse
from openai import AsyncOpenAI
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import traceback #异常处理


load_dotenv()
mcp_server_url = os.getenv("MCP_SERVER_URL")

# 通过用户-q --questions 读取问题
question = []

DEFAULT_QUESTION = ["现在深圳的天气怎么样？"]

class MCPAgent():
    def __init__(self, openai_client, mcp_session=None):
        self.openai_client = openai_client
        self.mcp_session = mcp_session
        self.available_tools = []



    @property
    def mcp_available(self):
        return self.mcp_session is not None



    def get_openai_tools_schema(self):
        """
        将MCP工具转化为OpenAI函数调用格式
        """
        if not self.mcp_available or not self.available_tools:
            print("MCP不可用或无可用工具，返回空工具列表")
            return []
            
        try:
            # 加载schema参数定义
            try:
                with open("schemas.json", "r", encoding="utf-8") as f:
                    schema_params = json.load(f)
            except FileNotFoundError:
                print("schemas.json文件未找到，使用默认schema")
                schema_params = {}
            
            openai_tools = []
            print(f"开始构建OpenAI工具schema，可用工具数量: {len(self.available_tools)}")
            
            for tool in self.available_tools:
                print(f"处理工具: '{tool.name}'")
                
                # 获取该工具的schema参数
                tool_params = schema_params.get(tool.name, {})
                
                # 构建OpenAI工具的schema
                tool_schema = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or f"MCP tool: {tool.name}",
                        "parameters": tool_params if tool_params else self._get_default_schema(tool)
                    }
                }        
                openai_tools.append(tool_schema)
            
            print(f"总共构建了 {len(openai_tools)} 个工具schema")
            return openai_tools
            
        except Exception as e:
            print(f"构建工具schema错误: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_default_schema(self, tool):
        """为工具生成默认的schema"""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    async def call_map_tool(self, tool_name, parameters):
        if not self.mcp_available or not self.mcp_session:
            raise Exception("MCP服务器不可用，无法调用工具")
            
        try:    
            # 获取工具详细信息
            result = await self.mcp_session.call_tool(tool_name, parameters)

            if result.content and len(result.content) > 0:
                content_text = result.content[0].text
                # print(f"工具返回内容: {content_text}")
                return content_text
            else:
                return "工具调用成功，但无返回结果"
                
        except Exception as e:
            print(f"MCP工具调用异常: {type(e).__name__}: {str(e)}")
            raise e
    
    async def chat_with_tools(self, user_message):
        #初始化系统提示词
        system_content = "你是一个智能助手，可以回答各种问题。"
        if self.mcp_available and self.available_tools:
            system_content += "你有一些工具可以帮助获取实时信息，如天气查询等。"
        else:
            system_content += "虽然你没有实时数据访问能力，但你会基于你的知识尽力回答用户的问题。"
            
        messages = [
            {
                "role": "system", 
                "content": system_content
            },
            {
                "role":"user",
                "content":user_message
            }
        ]

        tools = self.get_openai_tools_schema()
        print(f"🎯 准备调用OpenAI，传递工具数量: {len(tools)}")
        if tools:
            print("传递的工具列表:")
            for i, tool in enumerate(tools, 1):
                print(f"  {i}. {tool['function']['name']}: {tool['function']['description']}")
        else:
            print("没有工具传递给OpenAI（MCP不可用或无可用工具）")

        try:
            #首次调用openAI
            print("开始调用OpenAI API...")
            
            # 根据是否有工具来决定调用参数
            if tools:
                respond = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages = messages,
                    tools = tools,
                    tool_choice="auto",
                    max_tokens=500
                )
            else:
                # 没有工具时不传递tools参数
                respond = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages = messages,
                    max_tokens=500
                )            
            respond_message = respond.choices[0].message 
            print(f"工具调用数量: {len(respond_message.tool_calls) if respond_message.tool_calls else 0}")
            print(f"OpenAI响应消息: {respond_message}")
            
            #检查是否需要调用工具
            if respond_message.tool_calls:
                messages.append({
                    "role":"assistant",
                    "content": respond_message.content,
                    "tool_calls":[{
                        "id": tool_call.id,
                        "type":tool_call.type, 
                        "function":{
                            "name":tool_call.function.name,
                            "arguments":tool_call.function.arguments
                        }
                    }for tool_call in respond_message.tool_calls]
                })


                for tool_call in respond_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    print(f"调用工具: {function_name}")
                    print(f"工具参数: {function_args}")

                    try:
                        tool_result = await self.call_map_tool(function_name, function_args)
                        
                        #记录工具调用结果
                        messages.append({
                            "role":"tool",
                            "tool_call_id":tool_call.id,
                            "content":str(tool_result)
                        })
                    except Exception as e:
                        error_msg = f"工具调用失败: {e}"
                        print(error_msg)
                        print(f"错误详情: {type(e).__name__}: {str(e)}")
                        
                        #记录工具调用失败结果
                        messages.append({
                            "role":"tool",
                            "tool_call_id":tool_call.id,
                            "content":error_msg
                        })
                print(f"二次调用OpenAI前的messages:")
                for message in messages:
                    print(message)
                #第二次调用 OpenAI,结合用户提问和MCP工具返回的内容
                final_response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages = messages,
                    max_tokens = 300
                )
                return final_response.choices[0].message.content
            else:
                return respond_message.content 
        except Exception as e:
            return f"对话过程中出现错误:{e}"

        





async def main():

    openai_client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL")
    )
    
    agent = None
    mcp_connection_success = False
    
    # 尝试连接MCP服务器
    if mcp_server_url:
        try:
            print(f"尝试连接到MCP服务器: {mcp_server_url}")
            async with streamablehttp_client(mcp_server_url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream,) as mcp_session:
                    
                    #初始化MCP连接
                    print("正在初始化MCP连接...")
                    await mcp_session.initialize()
                    print("MCP连接初始化成功")
                    mcp_connection_success = True
                    
                    #获取MCP服务器工具
                    print("正在获取MCP服务器工具...")
                    try:
                        tools_response = await mcp_session.list_tools()
                        available_tools = tools_response.tools
                    except Exception as e:
                        print(f"获取MCP工具失败: {type(e).__name__}: {str(e)}")
                        available_tools = []

                    print(f"连接MCP服务器: {mcp_server_url}")
                    print(f"可用工具数量: {len(available_tools)}")
                    
                    if available_tools:
                        print("可用工具列表:")
                        for i, tool in enumerate(available_tools, 1):
                            print(f"  {i}. 名称: '{tool.name}'")
                            print(f"     描述: '{tool.description}'")
                            print()
                    else:
                        print("警告: 没有找到可用的MCP工具")
                    
                    # 创建MCP Agent
                    agent = MCPAgent(openai_client, mcp_session)
                    # 设置可用工具
                    agent.available_tools = available_tools
                    
                    # 处理用户问题
                    await process_questions(agent)
                    
        except Exception as e:
            print(f"MCP连接错误: {type(e).__name__}: {str(e)}")
            print("将使用无MCP模式继续运行...")
            mcp_connection_success = False
    else:
        print("未设置MCP_SERVER_URL，跳过MCP连接")
    
    # 如果MCP连接失败，使用无MCP模式
    if not mcp_connection_success:
        print("\n" + "="*60)
        print("使用无MCP模式运行")
        print("="*60)
        agent = MCPAgent(openai_client, None)
        await process_questions(agent)





async def process_questions(agent):
    for query in question:
        print("\n" + "="*60)
        print(f"用户提问:{query}")
        print("="*60)

        try:
            response = await agent.chat_with_tools(query)
            print("\n" + "-"*60)
            print(f"LLM回答: {response}")
            print("-"*60)        
            
        except Exception as e:
            print(f"处理问题出错{e}")
            traceback.print_exc()

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="MCP Agent - 智能助手"
    )
    parser.add_argument(
        "-q", "--question",
        type=str,
        help="要询问的问题",
        metavar="问题内容"
    )
    return parser.parse_args()








if __name__ == "__main__":
    
    #解析用户提出的问题
    args = parse_arguments()

    if args.question:
        question = [args.question]
        print(f"--------------启动 MCP Agent (命令行问题模式)----------------")
        print(f"问题: {args.question}")   


    print("--------------启动 MCP Agent----------------")
    asyncio.run(main())

