import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

# 覆盖式加载环境变量
load_dotenv(override=True)

if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("请设置 OPENAI_API_KEY 环境变量（实际值为 OneAPI 的访问令牌）")

if not os.environ.get("OPENAI_BASE_URL"):
    raise ValueError("请设置 OPENAI_BASE_URL 环境变量（实际值为 OneAPI 的 API 地址）")

llm = ChatOpenAI(
    model="qwen3.5-flash",
    temperature=0.5,
    base_url=os.environ.get("OPENAI_BASE_URL"),
)


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


agent = create_agent(
    model=llm,
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
    name = "weather_assistant"
)