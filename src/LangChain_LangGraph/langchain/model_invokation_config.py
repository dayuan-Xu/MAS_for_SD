####

# Invocation config  调用配置
# When invoking a model, you can pass additional configuration
# through the config parameter using a RunnableConfig dictionary.
# This provides run-time control over execution behavior, callbacks, and metadata tracking.
# 调用模型时，可以通过 RunnableConfig 字典通过config参数传递额外的配置。这为执行行为、回调和元数据跟踪提供了运行时的控制。
# Common configuration options include:
# 常见的配置选项包括：
# Invocation with config  带配置的调用
# response = model.invoke(
#     "Tell me a joke",
#     config={
#         "run_name": "joke_generation",      # Custom name for this run
#         "tags": ["humor", "demo"],          # Tags for categorization
#         "metadata": {"user_id": "123"},     # Custom metadata
#         "callbacks": [my_callback_handler], # Callback handlers
#     }
# )
# These configuration values are particularly useful when:
# 这些配置值在以下情况下尤为有用：
# Debugging with LangSmith tracing
# 使用 LangSmith 追踪进行调试
# Implementing custom logging or monitoring
# 实现自定义日志或监控
# Controlling resource usage in production
# 生产中的资源使用控制
# Tracking invocations across complex pipelines
# 跨复杂管道跟踪调用
#
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from rich.pretty import pprint
from typing import Any

# 定义一个回调事件处理器类，用于监听或记录模型、链、工具、工具调用和工具结果
class MyCallbackHandler(BaseCallbackHandler):
    # ========== 模型相关 ==========
    def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[BaseMessage]], **kwargs):
        print("▶️ 聊天模型开始")

    def on_llm_new_token(self, token: str, **kwargs):
        # Only available when streaming is enabled
        print(f"🔤new_token = {token}", end="")  # 实时流式输出

    def on_llm_end(self, *args, **kwargs):
        print("\n✅ 模型结束")

    def on_llm_error(self, error, **kwargs):
        print(f"\n❌ 模型出错：{error}")

    # ========== 链相关 ==========
    def on_chain_start(self, *args, **kwargs):
        print("🔗 链开始")

    def on_chain_end(self, *args, **kwargs):
        print("🔗 链结束")

    # ========== 工具相关 ==========
    def on_tool_start(self, *args, **kwargs):
        print("🛠️ 工具开始")



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
    model = "gpt-3.5-turbo",
    temperature=0.5,
    max_tokens=1000,
    timeout=10,
    base_url=os.environ.get("OPENAI_BASE_URL"),
)

# response = LLM_1.invoke(
#     "Tell me a 中文 joke",
#     config={
#         "run_name": "joke_generation",      # Custom name for this run
#         "tags": ["humor", "demo"],          # Tags for categorization
#         "metadata": {"user_id": "123"},     # Custom metadata
#         "callbacks": [MyCallbackHandler()], # Callback handlers
#     }
# )
# pprint(response)

for response in LLM_1.stream(
    "给我讲一个关于猎魔人白狼杰洛特（利维亚的杰洛特、布拉维坎的屠夫）的故事",
    config={
        "run_name": "story_generation",      # Custom name for this run
        "tags": ["story_teller", "demo"],          # Tags for categorization
        "metadata": {"user_id": "123"},     # Custom metadata
        "callbacks": [MyCallbackHandler()], # Callback handlers
    },

):
    pprint(response)

"""
▶️ 聊天模型开始
🔤 AIMessageChunk(
│   content='',
│   additional_kwargs={},
│   response_metadata={'model_provider': 'openai'},
│   id='lc_run--019cfc08-bf3a-71d2-9f15-8310d302fe92',
│   tool_calls=[],
│   invalid_tool_calls=[],
│   tool_call_chunks=[]
)
🔤 在AIMessageChunk(
│   content='在',
│   additional_kwargs={},
│   response_metadata={'model_provider': 'openai'},
│   id='lc_run--019cfc08-bf3a-71d2-9f15-8310d302fe92',
│   tool_calls=[],
│   invalid_tool_calls=[],
│   tool_call_chunks=[]
)
"""