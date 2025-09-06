// MCP智能聊天助手 - 前端JavaScript代码

class ChatClient {
    constructor() {
        this.chatMessages = document.getElementById('chatMessages');
        this.chatInput = document.getElementById('chatInput');
        this.sendButton = document.getElementById('sendButton');
        
        this.isGenerating = false;
        this.currentAssistantMessage = null;
        
        this.init();
    }

    init() {
        // 事件监听
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // 页面加载完成后聚焦输入框
        window.addEventListener('load', () => {
            this.chatInput.focus();
        });
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    addUserMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `<div class="message-content">${this.escapeHtml(message)}</div>`;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    addAssistantMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = '<div class="message-content"></div>';
        this.chatMessages.appendChild(messageDiv);
        this.currentAssistantMessage = messageDiv.querySelector('.message-content');
        this.scrollToBottom();
        return this.currentAssistantMessage;
    }

    addTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <span>AI正在思考...</span>
        `;
        this.chatMessages.appendChild(typingDiv);
        this.scrollToBottom();
        return typingDiv;
    }

    addToolCall(tools) {
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
        this.chatMessages.appendChild(toolDiv);
        this.scrollToBottom();
    }

    addToolResult(toolName, result) {
        const resultDiv = document.createElement('div');
        resultDiv.className = 'tool-result';
        resultDiv.innerHTML = `<strong>工具 ${toolName} 执行结果:</strong><br/>${this.escapeHtml(result)}`;
        this.chatMessages.appendChild(resultDiv);
        this.scrollToBottom();
    }

    addToolError(toolName, error) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'tool-error';
        errorDiv.innerHTML = `<strong>工具 ${toolName} 执行失败:</strong><br/>${this.escapeHtml(error)}`;
        this.chatMessages.appendChild(errorDiv);
        this.scrollToBottom();
    }

    addStatusMessage(message) {
        const statusDiv = document.createElement('div');
        statusDiv.className = 'status-message';
        statusDiv.textContent = message;
        this.chatMessages.appendChild(statusDiv);
        this.scrollToBottom();
        return statusDiv;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async sendMessage() {
        if (this.isGenerating) return;
        
        const message = this.chatInput.value.trim();
        if (!message) return;

        // 添加用户消息
        this.addUserMessage(message);
        this.chatInput.value = '';
        
        // 禁用输入
        this.isGenerating = true;
        this.sendButton.disabled = true;
        this.chatInput.disabled = true;

        // 添加打字指示器
        const typingIndicator = this.addTypingIndicator();

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
            const assistantContent = this.addAssistantMessage();

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            let buffer = '';
            
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;
                
                // 处理完整的行
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // 保留最后不完整的行

                for (const line of lines) {
                    if (line.trim()) {
                        try {
                            const data = JSON.parse(line);
                            this.handleStreamData(data, assistantContent);
                        } catch (e) {
                            console.error('解析JSON失败:', e);
                            console.error('原始数据:', line);
                            console.error('数据长度:', line.length);
                        }
                    }
                }
            }
            
            // 处理缓冲区中剩余的数据
            if (buffer.trim()) {
                try {
                    const data = JSON.parse(buffer);
                    this.handleStreamData(data, assistantContent);
                } catch (e) {
                    console.error('处理最后数据失败:', e, '数据:', buffer);
                }
            }

        } catch (error) {
            // 移除打字指示器
            if (typingIndicator && typingIndicator.parentNode) {
                typingIndicator.remove();
            }
            
            const errorContent = this.addAssistantMessage();
            errorContent.textContent = `❌ 连接错误: ${error.message}`;
        } finally {
            // 重新启用输入
            this.isGenerating = false;
            this.sendButton.disabled = false;
            this.chatInput.disabled = false;
            this.chatInput.focus();
        }
    }

    handleStreamData(data, assistantContent) {
        switch (data.type) {
            case 'start':
                this.addStatusMessage(data.message);
                break;
            case 'tool_calls':
                this.addToolCall(data.tools);
                break;
            case 'tool_executing':
                this.addStatusMessage(data.message);
                break;
            case 'tool_result':
                this.addToolResult(data.tool_name, data.result);
                break;
            case 'tool_error':
                this.addToolError(data.tool_name, data.error);
                break;
            case 'generating':
                this.addStatusMessage(data.message);
                break;
            case 'content':
                assistantContent.textContent += data.content;
                this.scrollToBottom();
                break;
            case 'end':
                // 移除所有状态消息
                document.querySelectorAll('.status-message').forEach(el => el.remove());
                break;
            case 'error':
                assistantContent.textContent = '❌ ' + data.error;
                break;
        }
    }
}

// 初始化聊天客户端
document.addEventListener('DOMContentLoaded', () => {
    new ChatClient();
});
