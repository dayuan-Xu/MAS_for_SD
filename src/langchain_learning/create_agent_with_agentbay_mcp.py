import asyncio
import uuid

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient

from src.config.llm import LLMs
from src.config.settings import settings
from src.utils.graph_running import multi_turn_conversation


async def main():
    client = MultiServerMCPClient(
        {
            # "math": {
            #     "transport": "stdio",  # Local subprocess communication
            #     "command": "python",
            #     # Absolute path to your math_server.py file
            #     "args": ["/path/to/math_server.py"],
            # },
            "wuying_mcp_server": {
                "transport": "http",  # HTTP-based remote server
                # Ensure you start your weather server on port 8000
                "url": f"https://agentbay.wuying.aliyuncs.com/v2/mcp?APIKEY={settings.WUYING_AGENTBAY_API_KEY}&IMAGEID=linux_latest",
            }
        }
    )

    tools = await client.get_tools()
    agent = create_agent(
        LLMs["minimax-m2.7"],
        tools
    )
    # # math_response = await agent.ainvoke(
    # #     {"messages": [{"role": "user", "content": "what's (3 + 5) x 12?"}]}
    # # )
    # weather_response = await agent.ainvoke(
    #     {"messages": [{"role": "user", "content": "wuying mcp给予了你哪些工具？"}]}
    # )
    # # print(math_response)
    # print(weather_response['messages'][-1].content)
    # 配置运行参数
    run_config: RunnableConfig = {
        "tags": ["agent_with_mcp_tools"],
        "run_name": "带MCP工具的智能体测试",
        "configurable": {"thread_id": str(uuid.uuid4())}
    }

    # 启动多轮对话
    multi_turn_conversation(agent, run_config)


if __name__ == "__main__":
    asyncio.run(main())
