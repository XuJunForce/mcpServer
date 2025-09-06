import asyncio
import json
import os
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
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

app = FastAPI(title="MCP聊天助手", description="支持工具调用的流式聊天界面")

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    global openai_client
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

# 请求模型
class ChatRequest(BaseModel):
    message: str

# 全局变量
openai_client = None
mcp_agent = None

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

@app.get("/", response_class=HTMLResponse)
async def get_chat_page():
    """返回聊天页面"""
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP智能聊天助手</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .chat-container {
            width: 90%;
            max-width: 800px;
            height: 90vh;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .chat-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
            font-size: 1.5rem;
            font-weight: 600;
        }

        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
        }

        .message {
            margin-bottom: 15px;
            max-width: 80%;
        }

        .message.user {
            margin-left: auto;
            text-align: right;
        }

        .message.assistant {
            margin-right: auto;
        }

        .message-content {
            padding: 12px 16px;
            border-radius: 18px;
            display: inline-block;
            max-width: 100%;
            word-wrap: break-word;
        }

        .message.user .message-content {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .message.assistant .message-content {
            background: white;
            color: #333;
            border: 1px solid #e0e0e0;
        }

        .tool-call {
            background: #e3f2fd;
            border: 1px solid #2196f3;
            border-radius: 10px;
            padding: 10px;
            margin: 10px 0;
            font-family: monospace;
            font-size: 0.9rem;
        }

        .tool-call-header {
            font-weight: bold;
            color: #1976d2;
            margin-bottom: 5px;
        }

        .tool-result {
            background: #e8f5e8;
            border: 1px solid #4caf50;
            border-radius: 8px;
            padding: 8px;
            margin: 5px 0;
            font-size: 0.85rem;
        }

        .tool-error {
            background: #ffebee;
            border: 1px solid #f44336;
            border-radius: 8px;
            padding: 8px;
            margin: 5px 0;
            color: #c62828;
            font-size: 0.85rem;
        }

        .status-message {
            background: #fff3e0;
            border: 1px solid #ff9800;
            border-radius: 8px;
            padding: 8px;
            margin: 5px 0;
            color: #f57c00;
            font-size: 0.85rem;
            font-style: italic;
        }

        .chat-input-container {
            padding: 20px;
            background: white;
            border-top: 1px solid #e0e0e0;
            display: flex;
            gap: 10px;
        }

        .chat-input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 25px;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.3s;
        }

        .chat-input:focus {
            border-color: #667eea;
        }

        .send-button {
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 600;
            transition: transform 0.2s;
        }

        .send-button:hover {
            transform: translateY(-1px);
        }

        .send-button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .typing-indicator {
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 10px 16px;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 18px;
            margin-bottom: 15px;
        }

        .typing-dot {
            width: 8px;
            height: 8px;
            background: #999;
            border-radius: 50%;
            animation: typing 1.4s infinite ease-in-out;
        }

        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }

        @keyframes typing {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-10px); }
        }

        .chat-messages::-webkit-scrollbar {
            width: 6px;
        }

        .chat-messages::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 3px;
        }

        .chat-messages::-webkit-scrollbar-thumb {
            background: #c1c1c1;
            border-radius: 3px;
        }

        .chat-messages::-webkit-scrollbar-thumb:hover {
            background: #a1a1a1;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            🤖 MCP智能聊天助手
        </div>
        
        <div class="chat-messages" id="chatMessages">
            <div class="message assistant">
                <div class="message-content">
                    你好！我是MCP智能助手，可以帮你查询天气等实时信息。请问有什么可以帮助你的吗？
                </div>
            </div>
        </div>
        
        <div class="chat-input-container">
            <input type="text" class="chat-input" id="chatInput" placeholder="请输入您的问题..." />
            <button class="send-button" id="sendButton">发送</button>
        </div>
    </div>

    <script>
        const chatMessages = document.getElementById('chatMessages');
        const chatInput = document.getElementById('chatInput');
        const sendButton = document.getElementById('sendButton');
        
        let isGenerating = false;
        let currentAssistantMessage = null;

        function scrollToBottom() {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        function addUserMessage(message) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message user';
            messageDiv.innerHTML = `<div class="message-content">${escapeHtml(message)}</div>`;
            chatMessages.appendChild(messageDiv);
            scrollToBottom();
        }

        function addAssistantMessage() {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant';
            messageDiv.innerHTML = '<div class="message-content"></div>';
            chatMessages.appendChild(messageDiv);
            currentAssistantMessage = messageDiv.querySelector('.message-content');
            scrollToBottom();
            return currentAssistantMessage;
        }

        function addTypingIndicator() {
            const typingDiv = document.createElement('div');
            typingDiv.className = 'typing-indicator';
            typingDiv.innerHTML = `
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <span>AI正在思考...</span>
            `;
            chatMessages.appendChild(typingDiv);
            scrollToBottom();
            return typingDiv;
        }

        function addToolCall(tools) {
            const toolDiv = document.createElement('div');
            toolDiv.className = 'tool-call';
            
            let toolsHtml = '<div class="tool-call-header">🛠️ 调用工具:</div>';
            tools.forEach(tool => {
                toolsHtml += `
                    <div><strong>${tool.name}</strong></div>
                    <div>参数: ${JSON.stringify(tool.arguments, null, 2)}</div>
                `;
            });
            
            toolDiv.innerHTML = toolsHtml;
            chatMessages.appendChild(toolDiv);
            scrollToBottom();
        }

        function addToolResult(toolName, result) {
            const resultDiv = document.createElement('div');
            resultDiv.className = 'tool-result';
            resultDiv.innerHTML = `<strong>工具 ${toolName} 执行结果:</strong><br/>${escapeHtml(result)}`;
            chatMessages.appendChild(resultDiv);
            scrollToBottom();
        }

        function addToolError(toolName, error) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'tool-error';
            errorDiv.innerHTML = `<strong>工具 ${toolName} 执行失败:</strong><br/>${escapeHtml(error)}`;
            chatMessages.appendChild(errorDiv);
            scrollToBottom();
        }

        function addStatusMessage(message) {
            const statusDiv = document.createElement('div');
            statusDiv.className = 'status-message';
            statusDiv.textContent = message;
            chatMessages.appendChild(statusDiv);
            scrollToBottom();
            return statusDiv;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function sendMessage() {
            if (isGenerating) return;
            
            const message = chatInput.value.trim();
            if (!message) return;

            // 添加用户消息
            addUserMessage(message);
            chatInput.value = '';
            
            // 禁用输入
            isGenerating = true;
            sendButton.disabled = true;
            chatInput.disabled = true;

            // 添加打字指示器
            const typingIndicator = addTypingIndicator();

            try {
                const response = await fetch('/chat/stream', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                // 移除打字指示器
                typingIndicator.remove();

                // 创建助手消息容器
                const assistantContent = addAssistantMessage();

                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\\n');

                    for (const line of lines) {
                        if (line.trim()) {
                            try {
                                const data = JSON.parse(line);
                                
                                switch (data.type) {
                                    case 'start':
                                        addStatusMessage(data.message);
                                        break;
                                    case 'tool_calls':
                                        addToolCall(data.tools);
                                        break;
                                    case 'tool_executing':
                                        addStatusMessage(data.message);
                                        break;
                                    case 'tool_result':
                                        addToolResult(data.tool_name, data.result);
                                        break;
                                    case 'tool_error':
                                        addToolError(data.tool_name, data.error);
                                        break;
                                    case 'generating':
                                        addStatusMessage(data.message);
                                        break;
                                    case 'content':
                                        assistantContent.textContent += data.content;
                                        scrollToBottom();
                                        break;
                                    case 'end':
                                        // 移除所有状态消息
                                        document.querySelectorAll('.status-message').forEach(el => el.remove());
                                        break;
                                    case 'error':
                                        assistantContent.textContent = '❌ ' + data.error;
                                        break;
                                }
                            } catch (e) {
                                console.error('解析JSON失败:', e, '原始数据:', line);
                            }
                        }
                    }
                }

            } catch (error) {
                // 移除打字指示器
                if (typingIndicator && typingIndicator.parentNode) {
                    typingIndicator.remove();
                }
                
                const errorContent = addAssistantMessage();
                errorContent.textContent = `❌ 连接错误: ${error.message}`;
            } finally {
                // 重新启用输入
                isGenerating = false;
                sendButton.disabled = false;
                chatInput.disabled = false;
                chatInput.focus();
            }
        }

        // 事件监听
        sendButton.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // 页面加载完成后聚焦输入框
        window.addEventListener('load', () => {
            chatInput.focus();
        });
    </script>
</body>
</html>
    """

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
