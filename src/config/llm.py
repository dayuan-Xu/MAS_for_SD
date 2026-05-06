from langchain_openai import ChatOpenAI
from rich.pretty import pprint

from src.config.settings import settings

# 下面是一些提供了LangSmith追踪集成的模型实例

gpt5 = ChatOpenAI(
    model="gpt-5",
    stream_usage=True,
    temperature=0.5,
    max_tokens=8192,
    max_retries=3,
    timeout=120,
    api_key=settings.CHATANYWHERE_OPENAI_API_KEY,
    base_url=settings.CHATANYWHERE_OPENAI_BASE_URL,
)

gpt5_mini = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.5,
    max_tokens=8192,
    timeout=120,
    max_retries=3,
    api_key=settings.CHATANYWHERE_OPENAI_API_KEY,
    base_url=settings.CHATANYWHERE_OPENAI_BASE_URL,
)

gpt5_nano = ChatOpenAI(
    model="gpt-5-nano",
    temperature=0.5,
    max_tokens=8192,
    timeout=120,
    max_retries=3,
    api_key=settings.CHATANYWHERE_OPENAI_API_KEY,
    base_url=settings.CHATANYWHERE_OPENAI_BASE_URL,

)

gpt41 = ChatOpenAI(
    model="gpt-4.1",
    temperature=0.5,
    max_tokens=8192,
    timeout=120,
    max_retries=3,
    api_key=settings.CHATANYWHERE_OPENAI_API_KEY,
    base_url=settings.CHATANYWHERE_OPENAI_BASE_URL,
)

gpt41_mini = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0.5,
    max_tokens=8192,
    timeout=120,
    max_retries=3,
    api_key=settings.CHATANYWHERE_OPENAI_API_KEY,
    base_url=settings.CHATANYWHERE_OPENAI_BASE_URL,
)

gpt4o = ChatOpenAI(
    model="gpt-4o",
    temperature=0.5,
    max_tokens=8192,
    timeout=120,
    max_retries=3,
    api_key=settings.CHATANYWHERE_OPENAI_API_KEY,
    base_url=settings.CHATANYWHERE_OPENAI_BASE_URL,
)

gpt4o_mini = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.5,
    max_tokens=8192,
    timeout=120,
    max_retries=3,
    api_key=settings.CHATANYWHERE_OPENAI_API_KEY,
    base_url=settings.CHATANYWHERE_OPENAI_BASE_URL,
)

gpt41_nano = ChatOpenAI(
    model="gpt-4o-nano",
    temperature=0.5,
    max_tokens=8192,
    timeout=120,
    max_retries=3,
    api_key=settings.CHATANYWHERE_OPENAI_API_KEY,
    base_url=settings.CHATANYWHERE_OPENAI_BASE_URL,
)

gpt35_turbo = ChatOpenAI(
    model="gpt-3.5-turbo",  # 默认指向 gpt-3.5-turbo-0125，该版本的gpt-3.5-turbo全面支持工具调用
    temperature=0.5,
    max_tokens=4096,
    timeout=120,
    max_retries=3,
    api_key=settings.CHATANYWHERE_OPENAI_API_KEY,
    base_url=settings.CHATANYWHERE_OPENAI_BASE_URL,
)

minimax_m27 = ChatOpenAI(
    model="MiniMax-M2.7",
    temperature=1.0,
    # max_tokens=4096,  # 直接省略，"让模型自己决定用多少"
    timeout=180,  # 增加到 180 秒，给 MiniMax 更多响应时间
    max_retries=5,  # 增加到 5 次，配合 RetryMiddleware 使用
    api_key=settings.MINIMAX_API_KEY,
    base_url=settings.MINIMAX_BASE_URL,
    # extra_body={"reasoning_split": True}  # 设置 reasoning_split=True 将思考内容分离到 reasoning_details 字段
)

custom_profile = {
    "max_input_tokens": 200_000,
    # ...
}

minimax_m27.profile = custom_profile


def test_minimax_m27():
    res = minimax_m27.invoke("你好啊，你是什么模型")
    # res.pretty_print()
    pprint(res)


LLMs = {
    "minimax-m2.7": minimax_m27,
    "gpt-5": gpt5,  # chatanywhere 免费支持一天5次
    "gpt-5-mini": gpt5_mini,  # chatanywhere 免费支持一天200次
    "gpt-5-nano": gpt5_nano,  # chatanywhere 免费支持一天200次
    "gpt-4.1": gpt41,  # chatanywhere 免费支持一天5次
    "gpt-4.1-mini": gpt41_mini,  # chatanywhere 免费支持一天200次
    "gpt-4.1-nano": gpt41_nano,  # chatanywhere 免费支持一天200次
    "gpt-4o": gpt4o,  # chatanywhere 免费支持一天5次
    "gpt-4o-mini": gpt4o_mini,  # 性能、价格全面碾压gpt-3.5-turbo  # chatanywhere 免费支持一天200次
    "gpt-3.5-turbo": gpt35_turbo,  # chatanywhere 免费支持一天200次
}


def show_LLMs_profile():
    for k, v in LLMs.items():
        print("================================================")
        print(k)
        pprint(v.profile)


"""
================================================
gpt-5
{
│   'max_input_tokens': 272000,
│   'max_output_tokens': 128000,
│   'text_inputs': True,
│   'image_inputs': True,
│   'audio_inputs': False,
│   'video_inputs': False,
│   'text_outputs': True,
│   'image_outputs': False,
│   'audio_outputs': False,
│   'video_outputs': False,
│   'reasoning_output': True,
│   'tool_calling': True,
│   'structured_output': True,
│   'image_url_inputs': True,
│   'pdf_inputs': True,
│   'pdf_tool_message': True,
│   'image_tool_message': True,
│   'tool_choice': True
}

gpt-5-mini
{
│   'max_input_tokens': 272000,
│   'max_output_tokens': 128000,
│   'text_inputs': True,
│   'image_inputs': True,
│   'audio_inputs': False,
│   'video_inputs': False,
│   'text_outputs': True,
│   'image_outputs': False,
│   'audio_outputs': False,
│   'video_outputs': False,
│   'reasoning_output': True,
│   'tool_calling': True,
│   'structured_output': True,
│   'image_url_inputs': True,
│   'pdf_inputs': True,
│   'pdf_tool_message': True,
│   'image_tool_message': True,
│   'tool_choice': True
}
================================================
gpt-5-nano
{
│   'max_input_tokens': 272000,
│   'max_output_tokens': 128000,
│   'text_inputs': True,
│   'image_inputs': True,
│   'audio_inputs': False,
│   'video_inputs': False,
│   'text_outputs': True,
│   'image_outputs': False,
│   'audio_outputs': False,
│   'video_outputs': False,
│   'reasoning_output': True,
│   'tool_calling': True,
│   'structured_output': True,
│   'image_url_inputs': True,
│   'pdf_inputs': True,
│   'pdf_tool_message': True,
│   'image_tool_message': True,
│   'tool_choice': True
}
================================================
gpt-4.1-mini
{
│   'max_input_tokens': 1047576,
│   'max_output_tokens': 32768,
│   'text_inputs': True,
│   'image_inputs': True,
│   'audio_inputs': False,
│   'video_inputs': False,
│   'text_outputs': True,
│   'image_outputs': False,
│   'audio_outputs': False,
│   'video_outputs': False,
│   'reasoning_output': False,
│   'tool_calling': True,
│   'structured_output': True,
│   'image_url_inputs': True,
│   'pdf_inputs': True,
│   'pdf_tool_message': True,
│   'image_tool_message': True,
│   'tool_choice': True
}
================================================
gpt-4.1-nano
{
│   'max_input_tokens': 128000,
│   'max_output_tokens': 16384,
│   'text_inputs': True,
│   'image_inputs': True,
│   'audio_inputs': False,
│   'video_inputs': False,
│   'text_outputs': True,
│   'image_outputs': False,
│   'audio_outputs': False,
│   'video_outputs': False,
│   'reasoning_output': False,
│   'tool_calling': True,
│   'structured_output': True,
│   'image_url_inputs': True,
│   'pdf_inputs': True,
│   'pdf_tool_message': True,
│   'image_tool_message': True,
│   'tool_choice': True
}
================================================
gpt-4o-mini
{
│   'max_input_tokens': 128000,
│   'max_output_tokens': 16384,
│   'text_inputs': True,
│   'image_inputs': True,
│   'audio_inputs': False,
│   'video_inputs': False,
│   'text_outputs': True,
│   'image_outputs': False,
│   'audio_outputs': False,
│   'video_outputs': False,
│   'reasoning_output': False,
│   'tool_calling': True,
│   'structured_output': True,
│   'image_url_inputs': True,
│   'pdf_inputs': True,
│   'pdf_tool_message': True,
│   'image_tool_message': True,
│   'tool_choice': True
}
================================================
gpt-4
{
│   'max_input_tokens': 8192,
│   'max_output_tokens': 8192,
│   'text_inputs': True,
│   'image_inputs': False,
│   'audio_inputs': False,
│   'video_inputs': False,
│   'text_outputs': True,
│   'image_outputs': False,
│   'audio_outputs': False,
│   'video_outputs': False,
│   'reasoning_output': False,
│   'tool_calling': True,
│   'structured_output': False,
│   'image_url_inputs': True,
│   'pdf_inputs': True,
│   'pdf_tool_message': True,
│   'image_tool_message': True,
│   'tool_choice': True
}
================================================
gpt-3.5-turbo
{
│   'max_input_tokens': 16385,
│   'max_output_tokens': 4096,
│   'text_inputs': True,
│   'image_inputs': False,
│   'audio_inputs': False,
│   'video_inputs': False,
│   'text_outputs': True,
│   'image_outputs': False,
│   'audio_outputs': False,
│   'video_outputs': False,
│   'reasoning_output': False,
│   'tool_calling': False,
│   'structured_output': False,
│   'image_url_inputs': False,
│   'pdf_inputs': False,
│   'pdf_tool_message': False,
│   'image_tool_message': False,
│   'tool_choice': True
}

"""
