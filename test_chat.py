#!/usr/bin/env python3
"""
简单的测试脚本，验证聊天服务器的基本功能
"""

import asyncio
import os
from dotenv import load_dotenv

async def test_basic_functionality():
    """测试基本功能"""
    print("🧪 开始测试MCP聊天服务器基本功能...")
    
    # 加载环境变量
    load_dotenv()
    
    # 检查环境变量
    required_vars = ["OPENAI_API_KEY", "OPENAI_BASE_URL"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ 缺少必要的环境变量: {', '.join(missing_vars)}")
        print("请在.env文件中配置这些变量")
        return False
    
    print("✅ 环境变量检查通过")
    
    # 检查MCP服务器URL
    mcp_url = os.getenv("MCP_SERVER_URL")
    if mcp_url:
        print(f"🔗 MCP服务器URL: {mcp_url}")
    else:
        print("⚠️  未配置MCP_SERVER_URL，将使用无MCP模式")
    
    try:
        # 尝试导入必要的模块
        from openai import AsyncOpenAI
        print("✅ OpenAI模块导入成功")
        
        # 测试OpenAI客户端创建
        client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        print("✅ OpenAI客户端创建成功")
        
        # 如果配置了MCP，尝试导入MCP模块
        if mcp_url:
            try:
                from mcp.client.session import ClientSession
                from mcp.client.streamable_http import streamablehttp_client
                print("✅ MCP模块导入成功")
            except ImportError as e:
                print(f"❌ MCP模块导入失败: {e}")
                return False
        
        print("✅ 所有基本功能测试通过！")
        return True
        
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        print("请运行: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        return False

def print_usage_instructions():
    """打印使用说明"""
    print("\n" + "="*60)
    print("🚀 MCP智能聊天助手使用说明")
    print("="*60)
    print("1. 确保已安装所有依赖:")
    print("   pip install -r requirements.txt")
    print("")
    print("2. 配置环境变量 (.env文件):")
    print("   OPENAI_API_KEY=your_openai_api_key")
    print("   OPENAI_BASE_URL=your_openai_base_url")
    print("   MCP_SERVER_URL=http://localhost:8001 (可选)")
    print("")
    print("3. 启动聊天服务器:")
    print("   python chat_server.py")
    print("   或者运行: ./start_chat_server.sh")
    print("")
    print("4. 打开浏览器访问:")
    print("   http://localhost:8002")
    print("")
    print("5. 如果需要MCP工具支持，请先启动MCP服务器:")
    print("   python server.py")
    print("="*60)

async def main():
    """主函数"""
    print("🤖 MCP智能聊天助手测试工具")
    print("-" * 40)
    
    success = await test_basic_functionality()
    
    if success:
        print("\n🎉 测试完成！系统准备就绪。")
        print_usage_instructions()
    else:
        print("\n❌ 测试失败，请检查配置后重试。")
        print("\n📋 常见问题解决方案:")
        print("1. 安装依赖: pip install -r requirements.txt")
        print("2. 检查.env文件中的API密钥配置")
        print("3. 确保MCP服务器正在运行 (如果使用MCP功能)")

if __name__ == "__main__":
    asyncio.run(main())
