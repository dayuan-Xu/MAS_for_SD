from langchain_core.prompts import ChatPromptTemplate
from langchain.chat_models import init_chat_model
import os
from pprint import pprint

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

# 覆盖式加载环境变量
load_dotenv(override=True)

if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("请设置 OPENAI_API_KEY 环境变量（实际值为 OneAPI or ChatAnywhere 的访问令牌）")

if not os.environ.get("OPENAI_BASE_URL"):
    raise ValueError("请设置 OPENAI_BASE_URL 环境变量（实际值为 OneAPI or ChatAnywhere 的 API 地址）")
# ======================
# 两个模型，都加了 config_prefix
# 这样当你想为一条内部有多个configurable model的chain传入config时
# 不需要为每个模型单独写一个 config
# 而是一个 config 管所有模型
# config_prefix = 让多个模型在传入的同一个config里互不冲突
# ======================

# 模型1：做总结（前缀 first）
summarize_model = init_chat_model(
    temperature=0,
    configurable_fields=("model", "temperature"),
    config_prefix="first",  # 👈 前缀
)

# 模型2：做润色（前缀 second）
polish_model = init_chat_model(
    temperature=0.9,
    configurable_fields=("model", "temperature"),
    config_prefix="second",  # 👈 前缀
)

# ======================
# 真实自然的链：先总结 → 再润色
# ======================
summarize_prompt = ChatPromptTemplate.from_template("请总结这段文字：{text}")
polish_prompt = ChatPromptTemplate.from_template("请把这段话改得口语化：{summary}")

# 一条链里两个模型！
chain = (
    summarize_prompt | summarize_model  # 第一步：总结
    | {"summary": lambda x: x.content}  # 格式转换
    | polish_prompt | polish_model      # 第二步：润色
)

# ======================
# ✨ 关键：一个 config 配置两个模型
# ======================
config:RunnableConfig = {
    "run_name":"展示configurable model的config_prefix属性作用",
    "configurable": {
        "base_url": os.environ.get("OPENAI_BASE_URL"),

        # 给 总结模型 配置
        "first_model": "gpt-4.1-mini",
        "first_temperature": 0,

        # 给 润色模型 配置
        "second_model": "gpt-5-nano",
        "second_temperature": 0.9
    }
}

# 运行！只需要传这一个 config 就可以正确配置chain中的多个model
ai_message = chain.invoke(
    input={"text": ("我今天去公园玩，看到了很多花，还有小鸟在唱歌，天气特别好，心情很棒，"
                    "我还遇见了许多漂亮的郁金香，有红的白的粉的紫的黄的，"
                    "周围看的人都都把花圃给围满了，这个公园是本地的大公园，"
                    "那天刚刚好是大家都放假的日子，公园里人山人海呢")
    },
    config=config
)

pprint(ai_message)