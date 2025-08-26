import asyncio
import sys

# Third Party
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    try:
        # Connect to streamable HTTP server
        server_url = "http://localhost:8000/mcp"
        # 可以自定义添加header
        # headers = {
        #     "Authorization": "Bearer token123"
        # }
        
        #async with streamablehttp_client(server_url, headers=headers) as (read_stream, write_stream, _):
        async with streamablehttp_client(server_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the connection
                await session.initialize()
                print(f"✅ Connected to MCP streamable HTTP server: {server_url}")

                # List available tools
                tools = await session.list_tools()
                print(f"\n📋 Available tools ({len(tools.tools)}):")
                for tool in tools.tools:
                    print(f" • {tool.name}: {tool.description}")

                # Test tool calls
                print(f"\n🔧 Testing tools:")
                test_cases = [(5, 3), (10, 20), (-5, 15)]
                for a, b in test_cases:
                    result = await session.call_tool("add", {"a": a, "b": b})
                    result_text = result.content[0].text if result.content else "No result"
                    print(f" add({a}, {b}) = {result_text}")

                print(f"\n✅ All tests completed successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))