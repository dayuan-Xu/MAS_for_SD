# 创建一个自定义的LangGraph
from langchain.agents import create_agent
from src.Tools import internet_search
from src.config.llm import LLMs

agent = create_agent(
    model=LLMs["gpt-5-mini"],
    tools=[internet_search],
    system_prompt=("你是一个团队领导，你直面用户的复杂需求。你知人善任，擅长复杂任务。"
                  "的高层规划调度，你并不会事事亲历亲为，而是委派团队成员完成任务。"
                  "你用中文回答用户问题。"),
)

# 不使用agent这个对象，单纯基于正则表达式匹配，实现一个函数，能够检测输入的字符串中是否有个人可识别信息（比如身份证、电话、银行卡号等），并可以将其用符号*掩蔽
def mask_sensitive_info(input_text: str) -> str:
    """Mask sensitive information in input text."""
    pass