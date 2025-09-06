#!/usr/bin/env python3
"""
调试脚本：快速测试聊天服务器功能
"""

import asyncio
import aiohttp
import json
import time

async def test_health():
    """测试健康检查接口"""
    print("🔍 测试健康检查接口...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8002/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ 健康检查通过")
                    print(f"   状态: {data.get('status')}")
                    print(f"   OpenAI客户端: {data.get('openai_client')}")
                    print(f"   MCP服务器: {data.get('mcp_server_url')}")
                    return True
                else:
                    print(f"❌ 健康检查失败: HTTP {response.status}")
                    return False
    except Exception as e:
        print(f"❌ 健康检查错误: {e}")
        return False

async def test_simple_chat():
    """测试简单聊天接口"""
    print("\n💬 测试简单聊天接口...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("http://localhost:8002/test") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success":
                        print("✅ 简单聊天测试通过")
                        print(f"   AI回复: {data.get('response')}")
                        return True
                    else:
                        print(f"❌ 简单聊天测试失败: {data.get('error')}")
                        return False
                else:
                    print(f"❌ 简单聊天测试失败: HTTP {response.status}")
                    return False
    except Exception as e:
        print(f"❌ 简单聊天测试错误: {e}")
        return False

async def test_stream_chat():
    """测试流式聊天接口"""
    print("\n🌊 测试流式聊天接口...")
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"message": "你好，请简单介绍一下自己"}
            async with session.post(
                "http://localhost:8002/chat/stream",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    print("✅ 开始接收流式响应...")
                    content_parts = []
                    
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str:
                            try:
                                data = json.loads(line_str)
                                msg_type = data.get("type")
                                
                                if msg_type == "start":
                                    print(f"   🚀 {data.get('message')}")
                                elif msg_type == "generating":
                                    print(f"   ⚡ {data.get('message')}")
                                elif msg_type == "content":
                                    content = data.get("content", "")
                                    content_parts.append(content)
                                    print(content, end="", flush=True)
                                elif msg_type == "end":
                                    print(f"\n   ✅ {data.get('message')}")
                                elif msg_type == "error":
                                    print(f"\n   ❌ {data.get('error')}")
                                    return False
                            except json.JSONDecodeError:
                                print(f"   ⚠️ 无法解析JSON: {line_str}")
                    
                    full_response = "".join(content_parts)
                    if full_response.strip():
                        print(f"\n   📝 完整回复: {full_response}")
                        return True
                    else:
                        print("\n   ❌ 没有收到有效内容")
                        return False
                else:
                    print(f"❌ 流式聊天测试失败: HTTP {response.status}")
                    error_text = await response.text()
                    print(f"   错误详情: {error_text}")
                    return False
    except Exception as e:
        print(f"❌ 流式聊天测试错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("🧪 MCP聊天服务器调试测试")
    print("=" * 50)
    
    # 等待服务器启动
    print("⏳ 等待服务器启动...")
    await asyncio.sleep(2)
    
    # 运行测试
    tests = [
        ("健康检查", test_health),
        ("简单聊天", test_simple_chat),
        ("流式聊天", test_stream_chat)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        start_time = time.time()
        success = await test_func()
        elapsed = time.time() - start_time
        results.append((test_name, success, elapsed))
        print(f"耗时: {elapsed:.2f}秒")
    
    # 总结结果
    print("\n" + "=" * 50)
    print("📊 测试结果总结:")
    
    passed = 0
    for test_name, success, elapsed in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"   {test_name}: {status} ({elapsed:.2f}s)")
        if success:
            passed += 1
    
    print(f"\n🎯 总计: {passed}/{len(results)} 个测试通过")
    
    if passed == len(results):
        print("🎉 所有测试通过！聊天服务器运行正常。")
    else:
        print("⚠️  存在问题，请检查服务器日志。")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 测试已取消")
    except Exception as e:
        print(f"\n❌ 测试运行错误: {e}")
        import traceback
        traceback.print_exc()
