# MCP智能聊天助手

一个基于FastAPI和MCP协议的智能聊天助手，支持流式输出和工具调用可视化。

## ✨ 主要功能

- 🔄 **流式对话**: 实时显示AI回答，提供流畅的聊天体验
- 🛠️ **工具调用可视化**: 清晰展示AI调用的工具和执行结果
- 🌤️ **天气查询**: 支持实时天气信息查询
- 🎨 **现代化界面**: 美观的聊天界面，支持响应式设计
- ⚡ **高性能**: 基于FastAPI的异步处理

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件并配置以下变量：

```env
# OpenAI配置 (必需)
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=your_openai_base_url

# MCP服务器配置 (可选，用于工具调用)
MCP_SERVER_URL=http://localhost:8001

# 天气API配置 (如果使用天气查询工具)
KEY=your_amap_api_key
```

### 3. 启动服务

#### 方式一：使用启动脚本 (推荐)

```bash
./start_chat_server.sh
```

#### 方式二：直接运行

```bash
python chat_server.py
```

### 4. 访问聊天界面

打开浏览器访问：http://localhost:8002

## 🔧 完整部署流程

### 1. 启动MCP服务器 (如果需要工具支持)

```bash
# 在一个终端中启动MCP服务器
python server.py
```

### 2. 启动聊天服务器

```bash
# 在另一个终端中启动聊天服务器
python chat_server.py
```

### 3. 测试功能

```bash
# 运行测试脚本检查配置
python test_chat.py
```

## 💬 使用示例

### 基本对话
```
用户: 你好，请介绍一下自己
AI: 你好！我是MCP智能助手...
```

### 天气查询 (需要MCP服务器支持)
```
用户: 深圳现在天气怎么样？
AI: 🛠️ 调用工具: weather
    参数: {"city": "深圳市"}
    
    工具执行结果: [天气数据]
    
    根据查询结果，深圳当前天气...
```

## 📁 项目结构

```
mcpServer/
├── chat_server.py          # 聊天服务器主文件
├── server.py              # MCP服务器 (工具提供者)
├── myMcp.py               # MCP客户端代理
├── test_chat.py           # 测试脚本
├── start_chat_server.sh   # 启动脚本
├── requirements.txt       # 依赖列表
├── schemas.json          # 工具参数定义
└── .env                  # 环境变量配置
```

## 🔄 流式响应格式

聊天服务器使用以下JSON格式进行流式通信：

```json
{"type": "start", "message": "开始处理您的问题..."}
{"type": "tool_calls", "tools": [{"name": "weather", "arguments": {...}}]}
{"type": "tool_executing", "tool_name": "weather", "message": "正在调用工具: weather"}
{"type": "tool_result", "tool_name": "weather", "result": "..."}
{"type": "generating", "message": "正在生成回答..."}
{"type": "content", "content": "部分回答内容"}
{"type": "end", "message": "回答完成"}
```

## 🛠️ 支持的工具

当前支持以下工具 (需要MCP服务器运行):

- **weather**: 天气查询工具
  - 参数: `city` (城市名称)
  - 返回: 实时天气信息

## ⚙️ 配置说明

### OpenAI配置
- `OPENAI_API_KEY`: OpenAI API密钥
- `OPENAI_BASE_URL`: API基础URL (支持代理服务器)

### MCP配置
- `MCP_SERVER_URL`: MCP服务器地址，不配置则使用无工具模式

### 天气API配置
- `KEY`: 高德地图API密钥 (用于天气查询)

## 🐛 故障排除

### 1. 依赖安装问题
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. 端口冲突
如果8002端口被占用，可以修改 `chat_server.py` 中的端口号。

### 3. MCP连接失败
- 确保MCP服务器正在运行 (`python server.py`)
- 检查 `MCP_SERVER_URL` 配置是否正确
- 查看服务器日志获取详细错误信息

### 4. API调用失败
- 检查OpenAI API密钥是否正确
- 确认网络连接正常
- 验证API基础URL配置

## 📊 性能优化

- 使用异步处理提高并发性能
- 流式响应减少用户等待时间
- 支持工具调用的并行处理
- 智能错误处理和重试机制

## 🔒 安全考虑

- API密钥通过环境变量配置，不在代码中硬编码
- 支持HTTPS部署
- 输入验证和错误处理
- 日志记录便于问题追踪

## 📝 开发说明

### 添加新工具

1. 在 `server.py` 中定义新的MCP工具
2. 在 `schemas.json` 中添加工具参数定义
3. 重启MCP服务器和聊天服务器

### 自定义界面

修改 `chat_server.py` 中的HTML模板部分，可以自定义聊天界面的样式和功能。

## 📄 许可证

本项目采用MIT许可证。

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📞 支持

如有问题，请查看故障排除部分或提交Issue。
