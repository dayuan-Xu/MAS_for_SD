# 统计智能体在某个thread_id下的所有运行的token总用量的中间件
# 实现方法：在after_agent这个节点钩子函数中读取agentstate中的messages并统一计算其中的AIMessage的token usage
# 或者直接不实现而是直接从langsmith查看
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime
from typing import Any


# {
#       "additional_kwargs": {
#         "refusal": null
#       },
#       "content": "<think>用户想查看 /tmp/persistent/team-skills 目录。让我用 ls 工具来列出这个目录的内容。</think>\n\n",
#       "id": "lc_run--019daaba-2317-7692-b89d-09e7d1a42388-0",
#       "invalid_tool_calls": [],
#       "name": "David_Engineer",
#       "response_metadata": {
#         "finish_reason": "tool_calls",
#         "id": "063545eb696873488ba9c11d397b049a",
#         "logprobs": null,
#         "model_name": "MiniMax-M2.7",
#         "model_provider": "openai",
#         "system_fingerprint": null,
#         "token_usage": {
#           "completion_tokens": 57,
#           "completion_tokens_details": null,
#           "prompt_tokens": 7877,
#           "prompt_tokens_details": {
#             "audio_tokens": null,
#             "cached_tokens": 0
#           },
#           "total_characters": 0,
#           "total_tokens": 7934
#         }
#       },
#       "tool_calls": [
#         {
#           "args": {
#             "path": "/tmp/persistent/team-skills"
#           },
#           "id": "call_function_atlbck5g2vb2_1",
#           "name": "ls",
#           "type": "tool_call"
#         }
#       ],
#       "type": "ai",
#       "usage_metadata": {
#         "input_token_details": {
#           "cache_read": 0
#         },
#         "input_tokens": 7877,
#         "output_token_details": {},
#         "output_tokens": 57,
#         "total_tokens": 7934
#       }
#     }


class StatisticsState(AgentState):
    input_tokens_sum: int
    output_tokens_sum: int
    total_tokens_sum: int


class StatisticsMiddleware(AgentMiddleware[StatisticsState]):
    state_schema = StatisticsState

    # 每次智能体运行之后，都重新从第一条AI消息开始统计，到目前为止在该thread上的token用量。
    def after_agent(self, state: StatisticsState, runtime: Runtime) -> dict[str, Any] | None:
        input_sum = 0
        output_sum = 0
        total_sum = 0
        for msg in state['messages']:
            if msg['type'] == 'ai' and msg['usage_metadata']:
                token_usage_info = msg['usage_metadata']
                input_sum += token_usage_info['input_token_s']
                output_sum += token_usage_info['output_tokens']
                total_sum += token_usage_info['total_tokens']

        return {
            'input_tokens_sum': input_sum,
            'output_tokens_sum': output_sum,
            'total_tokens_sum': total_sum
        }
