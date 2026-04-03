# LangChain chat models can expose a dictionary of supported features and capabilities through a .profile attribute:
# LangChain 聊天模型可以通过 .profile 属性展示支持的功能和能力词典：
#
# model.profile
# {
#   "max_input_tokens": 400000,
#   "image_inputs": True,
#   "reasoning_output": True,
#   "tool_calling": True,
#   ...
# }

# Model profile data allow applications to work around model capabilities dynamically. For example:
# 模型配置文件数据允许应用程序动态绕过模型能力。例如：
# Model profile data allow applications to work around model capabilities dynamically. For example:
# 模型配置文件数据允许应用程序动态绕过模型能力。例如：
# Summarization middleware can trigger summarization based on a model’s context window size.
# 摘要中间件可以根据模型的上下文窗口大小触发摘要。
# Structured output strategies in create_agent can be inferred automatically (e.g., by checking support for native structured output features).
# create_agent 中的结构化输出策略可以被自动推断（例如，通过检查对原生结构化输出特征的支持）。
# Model inputs can be gated based on supported modalities and maximum input tokens.
# 模型输入可以根据支持的模态和最大输入标记进行门禁。

import os
from pprint import pprint

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
    base_url=os.environ.get("OPENAI_BASE_URL"),
)

# 通过模型配置文件动态检测模型的能力
pprint(LLM_1.profile)

"""
{'audio_inputs': False,
 'audio_outputs': False,
 'image_inputs': False,
 'image_outputs': False,
 'image_tool_message': False,
 'image_url_inputs': False,
 'max_input_tokens': 16385,
 'max_output_tokens': 4096,
 'pdf_inputs': False,
 'pdf_tool_message': False,
 'reasoning_output': False,
 'structured_output': False,
 'text_inputs': True,
 'text_outputs': True,
 'tool_calling': False,
 'tool_choice': True,
 'video_inputs': False,
 'video_outputs': False}
 """



LLM_2 = ChatOpenAI(
    model = "gpt-4o-mini",   # 支持按照 JSON Schema 生成输出
    temperature=0.5,
    max_tokens=1000,
    timeout=10,
    base_url=os.environ.get("OPENAI_BASE_URL"),
)
pprint(LLM_2.profile)
"""
{'audio_inputs': False,
 'audio_outputs': False,
 'image_inputs': True,
 'image_outputs': False,
 'image_tool_message': True,
 'image_url_inputs': True,
 'max_input_tokens': 128000,
 'max_output_tokens': 16384,
 'pdf_inputs': True,
 'pdf_tool_message': True,
 'reasoning_output': False,
 'structured_output': True,
 'text_inputs': True,
 'text_outputs': True,
 'tool_calling': True,
 'tool_choice': True,
 'video_inputs': False,
 'video_outputs': False}
"""
