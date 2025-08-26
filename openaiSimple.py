import asyncio 

from agents import Agent, Runner 
from agents.mcp import MCPServerStreamableHttp
from dotenv import load_dotenv

load_dotenv()

async def main():
    mcp_server  = MCPServerStreamableHttp(
        params={"url":"http://localhost:8000/mcp/"}
    )

    await mcp_server.connect()

    try:
        agent = Agent(
            name="Math teacher",
            instructions="You are a helpful assitant that can perform calculator",
            mcp_servers=[mcp_server]
        )
        result = await Runner.run(
            agent,
            input="What is 25 plus 17? Use tool to work this out"
        )
        print("Agent Respond:", result.final_output)


    finally:
        await mcp_server.cleanup()

if __name__ == "__main__":
    asyncio.run(main())