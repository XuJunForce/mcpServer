import asyncio
import json
import os
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import logging

# 导入现有的MCP Agent
from myMcp import MCPAgent

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# 全局变量
openai_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global openai_client
    
    # 启动时初始化
    try:
        openai_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        logger.info("✅ OpenAI客户端初始化成功")
        
        # 检查环境变量
        if not os.getenv("OPENAI_API_KEY"):
            logger.warning("⚠️  OPENAI_API_KEY 未设置")
        if not os.getenv("OPENAI_BASE_URL"):
            logger.warning("⚠️  OPENAI_BASE_URL 未设置")
            
        mcp_url = os.getenv("MCP_SERVER_URL")
        if mcp_url:
            logger.info(f"🔗 MCP服务器URL: {mcp_url}")
        else:
            logger.info("ℹ️  未配置MCP_SERVER_URL，将使用无MCP模式")
            
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        raise e
    
    yield  # 应用运行
    
    # 关闭时清理（如果需要）
    logger.info("🔄 应用关闭中...")

app = FastAPI(
    title="MCP聊天助手", 
    description="支持工具调用的流式聊天界面",
    lifespan=lifespan
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 请求模型
class ChatRequest(BaseModel):
    message: str

async def init_mcp_agent():
    """初始化MCP Agent"""
    global openai_client, mcp_agent
    
    # 初始化OpenAI客户端
    openai_client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL")
    )
    
    mcp_server_url = os.getenv("MCP_SERVER_URL")
    
    if mcp_server_url:
        try:
            logger.info(f"尝试连接到MCP服务器: {mcp_server_url}")
            # 这里我们需要保持连接，所以使用全局连接
            async with streamablehttp_client(mcp_server_url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as mcp_session:
                    await mcp_session.initialize()
                    
                    # 获取工具
                    tools_response = await mcp_session.list_tools()
                    available_tools = tools_response.tools
                    
                    logger.info(f"连接成功，可用工具数量: {len(available_tools)}")
                    
                    # 创建MCP Agent
                    mcp_agent = MCPAgent(openai_client, mcp_session)
                    mcp_agent.available_tools = available_tools
                    
                    return mcp_agent
        except Exception as e:
            logger.error(f"MCP连接失败: {e}")
            mcp_agent = MCPAgent(openai_client, None)
    else:
        logger.info("未设置MCP_SERVER_URL，使用无MCP模式")
        mcp_agent = MCPAgent(openai_client, None)
    
    return mcp_agent

class StreamingChatAgent:
    """流式聊天代理，基于现有的MCPAgent进行流式改造"""
    
    def __init__(self, openai_client, mcp_session=None):
        self.openai_client = openai_client
        self.mcp_session = mcp_session
        self.available_tools = []
    
    @property
    def mcp_available(self):
        return self.mcp_session is not None
    
    def get_openai_tools_schema(self):
        """复用MCPAgent的工具schema生成逻辑"""
        if not self.mcp_available or not self.available_tools:
            return []
            
        try:
            with open("/root/python_learn/mcpServer/schemas.json", "r", encoding="utf-8") as f:
                schema_params = json.load(f)
        except FileNotFoundError:
            schema_params = {}
        
        openai_tools = []
        
        for tool in self.available_tools:
            tool_params = schema_params.get(tool.name, {})
            
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"MCP tool: {tool.name}",
                    "parameters": tool_params if tool_params else {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }        
            openai_tools.append(tool_schema)
        
        return openai_tools
    
    async def call_mcp_tool(self, tool_name, parameters):
        """调用MCP工具"""
        if not self.mcp_available or not self.mcp_session:
            raise Exception("MCP服务器不可用")
            
        try:    
            result = await self.mcp_session.call_tool(tool_name, parameters)
            if result.content and len(result.content) > 0:
                return result.content[0].text
            else:
                return "工具调用成功，但无返回结果"
        except Exception as e:
            logger.error(f"MCP工具调用异常: {e}")
            raise e
    
    async def stream_chat_with_tools(self, user_message: str) -> AsyncGenerator[str, None]:
        """流式聊天，支持工具调用"""
        
        # 发送开始信号
        yield json.dumps({
            "type": "start",
            "message": "开始处理您的问题..."
        }, ensure_ascii=False) + "\n"
        
        # 构建消息
        system_content = "你是一个智能助手，可以回答各种问题。"
        if self.mcp_available and self.available_tools:
            system_content += "你有一些工具可以帮助获取实时信息，如天气查询等。"
        
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_message}
        ]
        
        tools = self.get_openai_tools_schema()
        
        try:
            # 首次调用OpenAI
            if tools:
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    max_tokens=500
                )
            else:
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=500
                )
            
            response_message = response.choices[0].message
            
            # 检查是否需要调用工具
            if response_message.tool_calls:
                # 发送工具调用信息
                yield json.dumps({
                    "type": "tool_calls",
                    "tools": [
                        {
                            "name": tool_call.function.name,
                            "arguments": json.loads(tool_call.function.arguments)
                        }
                        for tool_call in response_message.tool_calls
                    ]
                }, ensure_ascii=False) + "\n"
                
                # 添加助手消息
                messages.append({
                    "role": "assistant",
                    "content": response_message.content,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    } for tool_call in response_message.tool_calls]
                })
                
                # 执行工具调用
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    yield json.dumps({
                        "type": "tool_executing",
                        "tool_name": function_name,
                        "message": f"正在调用工具: {function_name}"
                    }, ensure_ascii=False) + "\n"
                    
                    try:
                        tool_result = await self.call_mcp_tool(function_name, function_args)
                        
                        yield json.dumps({
                            "type": "tool_result",
                            "tool_name": function_name,
                            "result": str(tool_result)
                        }, ensure_ascii=False) + "\n"
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(tool_result)
                        })
                    except Exception as e:
                        error_msg = f"工具调用失败: {e}"
                        yield json.dumps({
                            "type": "tool_error",
                            "tool_name": function_name,
                            "error": error_msg
                        }, ensure_ascii=False) + "\n"
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": error_msg
                        })
                
                # 第二次调用OpenAI，获取流式响应
                yield json.dumps({
                    "type": "generating",
                    "message": "正在生成回答..."
                }, ensure_ascii=False) + "\n"
                
                final_response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=300,
                    stream=True
                )
                
                # 流式输出最终回答
                async for chunk in final_response:
                    if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                        yield json.dumps({
                            "type": "content",
                            "content": chunk.choices[0].delta.content
                        }, ensure_ascii=False) + "\n"
            else:
                # 没有工具调用，直接流式输出
                yield json.dumps({
                    "type": "generating",
                    "message": "正在生成回答..."
                }, ensure_ascii=False) + "\n"
                
                # 重新调用获取流式响应
                if tools:
                    stream_response = await self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        tools=tools,
                        tool_choice="auto",
                        max_tokens=500,
                        stream=True
                    )
                else:
                    stream_response = await self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        max_tokens=500,
                        stream=True
                    )
                
                async for chunk in stream_response:
                    if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                        yield json.dumps({
                            "type": "content",
                            "content": chunk.choices[0].delta.content
                        }, ensure_ascii=False) + "\n"
            
            # 发送结束信号
            yield json.dumps({
                "type": "end",
                "message": "回答完成"
            }, ensure_ascii=False) + "\n"
            
        except Exception as e:
            logger.error(f"流式聊天处理错误: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            yield json.dumps({
                "type": "error",
                "error": f"处理过程中出现错误: {e}"
            }, ensure_ascii=False) + "\n"

# 全局流式聊天代理
streaming_agent = None

async def get_streaming_agent():
    """获取流式聊天代理"""
    global streaming_agent, openai_client
    
    if streaming_agent is None:
        if openai_client is None:
            openai_client = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL")
            )
        
        mcp_server_url = os.getenv("MCP_SERVER_URL")
        
        if mcp_server_url:
            try:
                # 这里为了简化，我们每次都创建新连接
                # 在生产环境中，应该维护长连接
                streaming_agent = StreamingChatAgent(openai_client, None)
                logger.info("创建无MCP连接的流式代理")
            except Exception as e:
                logger.error(f"创建流式代理失败: {e}")
                streaming_agent = StreamingChatAgent(openai_client, None)
        else:
            streaming_agent = StreamingChatAgent(openai_client, None)
    
    return streaming_agent

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天接口"""
    try:
        # 确保OpenAI客户端已初始化
        global openai_client
        if openai_client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL")
            
            if not api_key:
                raise HTTPException(
                    status_code=500, 
                    detail="OPENAI_API_KEY 环境变量未设置，请检查.env文件配置"
                )
            if not base_url:
                raise HTTPException(
                    status_code=500, 
                    detail="OPENAI_BASE_URL 环境变量未设置，请检查.env文件配置"
                )
                
            openai_client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            logger.info("OpenAI客户端已初始化")
        
        # 为了支持MCP连接，我们需要在每次请求时创建新的连接
        mcp_server_url = os.getenv("MCP_SERVER_URL")
        
        if mcp_server_url:
            try:
                async def generate_with_mcp():
                    async with streamablehttp_client(mcp_server_url) as (read_stream, write_stream, _):
                        async with ClientSession(read_stream, write_stream) as mcp_session:
                            await mcp_session.initialize()
                            
                            # 获取工具
                            tools_response = await mcp_session.list_tools()
                            available_tools = tools_response.tools
                            
                            # 创建流式代理
                            agent = StreamingChatAgent(openai_client, mcp_session)
                            agent.available_tools = available_tools
                            
                            # 流式生成响应
                            async for chunk in agent.stream_chat_with_tools(request.message):
                                yield chunk
                
                return StreamingResponse(
                    generate_with_mcp(),
                    media_type="text/plain",
                    headers={"Cache-Control": "no-cache"}
                )
            except Exception as e:
                logger.error(f"MCP连接失败，使用无MCP模式: {e}")
        
        # 无MCP模式
        agent = StreamingChatAgent(openai_client, None)
        
        return StreamingResponse(
            agent.stream_chat_with_tools(request.message),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache"}
        )
        
    except Exception as e:
        logger.error(f"聊天流处理错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def get_chat_page():
    """返回聊天页面"""
    return FileResponse("templates/chat.html")

@app.get("/health")
async def health_check():
    """健康检查接口"""
    global openai_client
    
    status = {
        "status": "ok",
        "message": "MCP聊天服务器运行正常",
        "openai_client": "已初始化" if openai_client else "未初始化",
        "mcp_server_url": os.getenv("MCP_SERVER_URL", "未配置"),
        "environment": {
            "openai_api_key": "已配置" if os.getenv("OPENAI_API_KEY") else "未配置",
            "openai_base_url": os.getenv("OPENAI_BASE_URL", "未配置")
        }
    }
    
    return status

@app.post("/test")
async def test_simple_chat():
    """简单的测试接口，不使用流式响应"""
    try:
        global openai_client
        if openai_client is None:
            openai_client = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL")
            )
        
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "请简单回复：你好"}],
            max_tokens=50
        )
        
        return {
            "status": "success",
            "response": response.choices[0].message.content,
            "message": "OpenAI连接正常"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "OpenAI连接失败"
        }

if __name__ == "__main__":
    import uvicorn
    
    # 初始化OpenAI客户端
    if openai_client is None:
        openai_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
    
    logger.info("启动MCP聊天服务器...")
    logger.info("访问 http://localhost:8002 开始聊天")
    
    uvicorn.run(
        "chat_server:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )
