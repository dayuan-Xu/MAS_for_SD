import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 覆盖式加载环境变量
load_dotenv(override=True)

if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("请设置 OPENAI_API_KEY 环境变量（实际值为 OneAPI or ChatAnywhere 的访问令牌）")

if not os.environ.get("OPENAI_BASE_URL"):
    raise ValueError("请设置 OPENAI_BASE_URL 环境变量（实际值为 OneAPI or ChatAnywhere 的 API 地址）")

LLM_1 = ChatOpenAI(
    # model="qwen3.5-flash",
    model = "gpt-3.5-turbo",
    # stream_usage=True,
    temperature=0.5,
    max_tokens=1000,
    timeout=10,
    # reasoning_effort=None,
    # extra_body={
    #     "enable_thinking": False
    # },
    # max_retries=2,
    # api_key="...",  # If you prefer to pass api key in directly
    base_url=os.environ.get("OPENAI_BASE_URL"),
    # organization="...",
    # other params...
)

LLM_2 = ChatOpenAI(
    # model="qwen3.5-flash",
    model = "gpt-4o-mini",   # 支持按照 JSON Schema 生成输出
    # stream_usage=True,
    temperature=0.5,
    max_tokens=1000,
    timeout=10,
    # reasoning_effort=None,
    # extra_body={
    #     "enable_thinking": False
    # },
    # max_retries=2,
    # api_key="...",  # If you prefer to pass api key in directly
    base_url=os.environ.get("OPENAI_BASE_URL"),
    # organization="...",
    # other params...
)

LLMs ={
    "gpt-3.5-turbo": LLM_1
}