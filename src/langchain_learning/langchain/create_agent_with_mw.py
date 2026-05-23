# By default, agents use AgentState to manage short term memory, specifically the conversation history via a messages key.
# 默认情况下，代理使用 AgentState 来管理短期记忆，特别是通过消息键记录对话历史。

# 1、可以自定义智能体的state短期记忆schema模式
# You can extend AgentState to add additional fields.
# Custom state schemas are passed to create_agent using the state_schema parameter.
# 你可以扩展 AgentState 来添加额外字段。
# 自定义状态模式通过 state_schema 参数传递给 create_agent。
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import wrap_tool_call, AgentMiddleware, ModelRequest
from langchain_core.messages import AIMessageChunk
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.prebuilt.tool_node import ToolCallRequest

from src.config.llm import LLMs


# 一个预先知道的静态工具
@tool
def get_user_info(runtime: ToolRuntime) -> str:
    """Get user info."""
    return f"用户的id是{runtime.state['user_id']}，用户的偏好是{runtime.state['preferences']}"


class CustomAgentState(AgentState):
    user_id: str
    preferences: dict


@wrap_tool_call
def check_wrap_tool_call(request, handler):
    """查看wrap_tool_call这个中间件的实参、返回值"""
    # print("check_wrap_tool_call中间件开始执行,"
    #       "如果发现toolCallRequest.tool_call是在调用calculate_tip这个工具函数，"
    #       "可以查看此时toolCallRequest中的tool属性是否等于calculate_tip这个工具，你会发现它的tool属性其实是None")
    # pprint(request)
    """
ToolCallRequest(
│   tool_call={
│   │   'name': 'calculate_tip',
│   │   'args': {'bill_amount': 85, 'tip_percentage': 25},
│   │   'id': 'call_24VKPrt1o9Kuh7T01FFJLqm4',
│   │   'type': 'tool_call'
│   },
│   tool=None,
│   state={
│   │   'messages': [
│   │   │   HumanMessage(
│   │   │   │   content='请调用工具计算85$账单上收25%的小费，小费要收多少钱？',
│   │   │   │   additional_kwargs={},
│   │   │   │   response_metadata={},
│   │   │   │   id='6f1c5512-69b6-45a2-b092-42cdc6b65860'
│   │   │   ),
│   │   │   AIMessage(
│   │   │   │   content='',
│   │   │   │   additional_kwargs={},
│   │   │   │   response_metadata={
│   │   │   │   │   'finish_reason': 'tool_calls',
│   │   │   │   │   'model_name': 'gpt-5-nano-2025-08-07',
│   │   │   │   │   'model_provider': 'openai'
│   │   │   │   },
│   │   │   │   name='带自定义middleware的账单计算员',
│   │   │   │   id='lc_run--019d2424-14fb-7913-af7e-e2733974634c',
│   │   │   │   tool_calls=[
│   │   │   │   │   {
│   │   │   │   │   │   'name': 'calculate_tip',
│   │   │   │   │   │   'args': {'bill_amount': 85, 'tip_percentage': 25},
│   │   │   │   │   │   'id': 'call_24VKPrt1o9Kuh7T01FFJLqm4',
│   │   │   │   │   │   'type': 'tool_call'
│   │   │   │   │   }
│   │   │   │   ],
│   │   │   │   invalid_tool_calls=[]
│   │   │   )
│   │   ],
│   │   'user_id': 'user_123',
│   │   'preferences': {'theme': 'dark'}
│   },
│   runtime=ToolRuntime(
│   │   state={
│   │   │   'messages': [
│   │   │   │   HumanMessage(
│   │   │   │   │   content='请调用工具计算85$账单上收25%的小费，小费要收多少钱？',
│   │   │   │   │   additional_kwargs={},
│   │   │   │   │   response_metadata={},
│   │   │   │   │   id='6f1c5512-69b6-45a2-b092-42cdc6b65860'
│   │   │   │   ),
│   │   │   │   AIMessage(
│   │   │   │   │   content='',
│   │   │   │   │   additional_kwargs={},
│   │   │   │   │   response_metadata={
│   │   │   │   │   │   'finish_reason': 'tool_calls',
│   │   │   │   │   │   'model_name': 'gpt-5-nano-2025-08-07',
│   │   │   │   │   │   'model_provider': 'openai'
│   │   │   │   │   },
│   │   │   │   │   name='带自定义middleware的账单计算员',
│   │   │   │   │   id='lc_run--019d2424-14fb-7913-af7e-e2733974634c',
│   │   │   │   │   tool_calls=[
│   │   │   │   │   │   {
│   │   │   │   │   │   │   'name': 'calculate_tip',
│   │   │   │   │   │   │   'args': {'bill_amount': 85, 'tip_percentage': 25},
│   │   │   │   │   │   │   'id': 'call_24VKPrt1o9Kuh7T01FFJLqm4',
│   │   │   │   │   │   │   'type': 'tool_call'
│   │   │   │   │   │   }
│   │   │   │   │   ],
│   │   │   │   │   invalid_tool_calls=[]
│   │   │   │   )
│   │   │   ],
│   │   │   'user_id': 'user_123',
│   │   │   'preferences': {'theme': 'dark'}
│   │   },
│   │   context=None,
│   │   config={
│   │   │   'tags': [],
│   │   │   'metadata': {
│   │   │   │   'ls_integration': 'langchain_create_agent',
│   │   │   │   'lc_agent_name': '带自定义middleware的账单计算员',
│   │   │   │   'langgraph_step': 2,
│   │   │   │   'langgraph_node': 'tools',
│   │   │   │   'langgraph_triggers': ('__pregel_push',),
│   │   │   │   'langgraph_path': ('__pregel_push', 0, False),
│   │   │   │   'langgraph_checkpoint_ns': 'tools:ef49734c-d1c9-4bdf-d7a3-d52f8d7279b2',
│   │   │   │   'checkpoint_ns': 'tools:ef49734c-d1c9-4bdf-d7a3-d52f8d7279b2'
│   │   │   },
│   │   │   'callbacks': <langchain_core.callbacks.manager.CallbackManager object at 0x0000025560DC84D0>,
│   │   │   'recursion_limit': 25,
│   │   │   'configurable': {
│   │   │   │   '__pregel_runtime': Runtime(
│   │   │   │   │   context=None,
│   │   │   │   │   store=None,
│   │   │   │   │   stream_writer=<function Pregel.stream.<locals>.stream_writer at 0x0000025560D60400>,
│   │   │   │   │   previous=None,
│   │   │   │   │   execution_info=ExecutionInfo(
│   │   │   │   │   │   node_attempt=1,
│   │   │   │   │   │   node_first_attempt_time=1774427842.5031273
│   │   │   │   │   )
│   │   │   │   ),
│   │   │   │   '__pregel_replay_state': None,
│   │   │   │   '__pregel_task_id': 'ef49734c-d1c9-4bdf-d7a3-d52f8d7279b2',
│   │   │   │   '__pregel_send': <built-in method extend of collections.deque object at 0x0000025560CD7E20>,
│   │   │   │   '__pregel_read': functools.partial(<function local_read at 0x000002555F7D9580>, PregelScratchpad(step=2, stop=10000, call_counter=<langgraph.pregel._algo.LazyAtomicCounter object at 0x000002555FC82830>, interrupt_counter=<langgraph.pregel._algo.LazyAtomicCounter object at 0x000002555FC82A10>, get_null_resume=<function _scratchpad.<locals>.get_null_resume at 0x000002555FCC8EA0>, resume=[], subgraph_counter=<langgraph.pregel._algo.LazyAtomicCounter object at 0x000002555FC82BC0>), {'messages': <langgraph.channels.binop.BinaryOperatorAggregate object at 0x0000025560DA8B40>, 'jump_to': <langgraph.channels.ephemeral_value.EphemeralValue object at 0x0000025560DA8B80>, 'structured_response': <langgraph.channels.last_value.LastValue object at 0x0000025560D6D7C0>, 'user_id': <langgraph.channels.last_value.LastValue object at 0x0000025560DA8C00>, 'preferences': <langgraph.channels.last_value.LastValue object at 0x0000025560DA8C80>, '__start__': <langgraph.channels.ephemeral_value.EphemeralValue object at 0x0000025560DA8CC0>, '__pregel_tasks': <langgraph.channels.topic.Topic object at 0x0000025560DA8D00>, 'branch:to:model': <langgraph.channels.ephemeral_value.EphemeralValue object at 0x0000025560DA8C40>, 'branch:to:tools': <langgraph.channels.ephemeral_value.EphemeralValue object at 0x0000025560DA8DC0>}, {}, PregelTaskWrites(path=('__pregel_push', 0, False), name='tools', writes=deque([]), triggers=('__pregel_push',))),
│   │   │   │   '__pregel_checkpointer': None,
│   │   │   │   'checkpoint_map': {
│   │   │   │   │   '': '1f12825d-7d31-6268-8001-964013c32b95'
│   │   │   │   },
│   │   │   │   'checkpoint_id': None,
│   │   │   │   'checkpoint_ns': 'tools:ef49734c-d1c9-4bdf-d7a3-d52f8d7279b2',
│   │   │   │   '__pregel_scratchpad': PregelScratchpad(
│   │   │   │   │   step=2,
│   │   │   │   │   stop=10000,
│   │   │   │   │   call_counter=<langgraph.pregel._algo.LazyAtomicCounter object at 0x000002555FC82830>,
│   │   │   │   │   interrupt_counter=<langgraph.pregel._algo.LazyAtomicCounter object at 0x000002555FC82A10>,
│   │   │   │   │   get_null_resume=<function _scratchpad.<locals>.get_null_resume at 0x000002555FCC8EA0>,
│   │   │   │   │   resume=[],
│   │   │   │   │   subgraph_counter=<langgraph.pregel._algo.LazyAtomicCounter object at 0x000002555FC82BC0>
│   │   │   │   ),
│   │   │   │   '__pregel_call': functools.partial(<function _call at 0x000002555F80B7E0>, <weakref at 0x0000025560D97C40; to 'PregelExecutableTask' at 0x0000025560D92710>, retry_policy=None, futures=<weakref at 0x0000025560D97B50; to 'FuturesDict' at 0x0000025560DDC650>, schedule_task=<bound method SyncPregelLoop.accept_push of <langgraph.pregel._loop.SyncPregelLoop object at 0x0000025560DA8690>>, submit=<weakref at 0x0000025560D8F5A0; to 'BackgroundExecutor' at 0x0000025560DA8810>)
│   │   │   }
│   │   },
│   │   stream_writer=<function Pregel.stream.<locals>.stream_writer at 0x0000025560D60400>,
│   │   tool_call_id='call_24VKPrt1o9Kuh7T01FFJLqm4',
│   │   store=None
│   )
)
"""
    # pprint(handler)

    # Execute the tool call(调用内层的处理器)
    result = handler(request)

    # # 打印tool_call的执行结果
    # pprint(result)

    # print("check_wrap_tool_call中间件执行结束")
    return result


# 可以通过中间件实现工具的动态注册和动态工具的执行处理
@tool
def calculate_tip(bill_amount: float, tip_percentage: float = 20.0) -> str:
    """Calculate the tip amount for a bill."""
    tip = bill_amount * (tip_percentage / 100)
    return f"Tip: ${tip:.2f}, Total: ${bill_amount + tip:.2f}"


@tool
def load_skill(skill_name: str) -> str:
    """Load the full content of a skill into the agent's context.

    Use this when you need detailed information about how to handle a specific
    type of request. This will provide you with comprehensive instructions,
    policies, and guidelines for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., "expense_reporting", "travel_booking")
    """
    pass


# 动态工具的添加需要在两个包裹式钩子函数内部进行相应处理。
class DynamicToolMiddleware(AgentMiddleware):
    """Middleware that registers and handles dynamic tools."""
    # Register the load_skill tool as a class variable
    # The load_skill tool is registered as a class variable, making it available to the agent.
    # 中间件tools类变量中的load_skill工具，会自动加入到ModelRequest对象中
    tools = [load_skill]

    def wrap_model_call(self, request: ModelRequest, handler):
        # Add dynamic tool to the request
        # 1、将运行时才获知的工具加入到模型调用请求中，以便让模型获知该工具的存在。
        # This could be loaded from an MCP server, database, etc.
        # pprint(request)

        """
ModelRequest(
│   model=ChatOpenAI(
│   │   profile={
│   │   │   'max_input_tokens': 272000,
│   │   │   'max_output_tokens': 128000,
│   │   │   'text_inputs': True,
│   │   │   'image_inputs': True,
│   │   │   'audio_inputs': False,
│   │   │   'video_inputs': False,
│   │   │   'text_outputs': True,
│   │   │   'image_outputs': False,
│   │   │   'audio_outputs': False,
│   │   │   'video_outputs': False,
│   │   │   'reasoning_output': True,
│   │   │   'tool_calling': True,
│   │   │   'structured_output': True,
│   │   │   'image_url_inputs': True,
│   │   │   'pdf_inputs': True,
│   │   │   'pdf_tool_message': True,
│   │   │   'image_tool_message': True,
│   │   │   'tool_choice': True
│   │   },
│   │   client=<openai.resources.chat.completions.completions.Completions object at 0x00000220447FF210>,
│   │   async_client=<openai.resources.chat.completions.completions.AsyncCompletions object at 0x00000220447FF950>,
│   │   root_client=<openai.OpenAI object at 0x00000220447FEC90>,
│   │   root_async_client=<openai.AsyncOpenAI object at 0x00000220447FF3D0>,
│   │   model_name='gpt-5-nano',
│   │   model_kwargs={},
│   │   openai_api_key=SecretStr('**********'),
│   │   openai_api_base='https://api.chatanywhere.tech/v1',
│   │   request_timeout=30.0,
│   │   max_retries=3,
│   │   max_tokens=8192
│   ),
│   messages=[
│   │   HumanMessage(
│   │   │   content='请调用工具计算85$账单上收25%的小费，小费要收多少钱？',
│   │   │   additional_kwargs={},
│   │   │   response_metadata={},
│   │   │   id='beb06783-159a-4229-b560-0176256dfb4d'
│   │   )
│   ],
│   system_message=None,
│   tool_choice=None,
│   tools=[
│   │   StructuredTool(
│   │   │   name='get_user_info',
│   │   │   description='Get user info.',
│   │   │   args_schema=<class 'langchain_core.utils.pydantic.get_user_info'>,
│   │   │   func=<function get_user_info at 0x000002203DD08EA0>
│   │   )
│   ],
│   response_format=None,
│   state={
│   │   'messages': [
│   │   │   HumanMessage(
│   │   │   │   content='请调用工具计算85$账单上收25%的小费，小费要收多少钱？',
│   │   │   │   additional_kwargs={},
│   │   │   │   response_metadata={},
│   │   │   │   id='beb06783-159a-4229-b560-0176256dfb4d'
│   │   │   )
│   │   ],
│   │   'user_id': 'user_123',
│   │   'preferences': {'theme': 'dark'}
│   },
│   runtime=Runtime(
│   │   context=None,
│   │   store=None,
│   │   stream_writer=<function Pregel.stream.<locals>.stream_writer at 0x0000022044840400>,
│   │   previous=None,
│   │   execution_info=ExecutionInfo(
│   │   │   node_attempt=1,
│   │   │   node_first_attempt_time=1774428176.5697381
│   │   )
│   ),
│   model_settings={}
)
"""
        # 扩展式重写ModelRequest对象中的tools属性
        updated = request.override(tools=[*request.tools, calculate_tip])
        # pprint(updated)
        """
ModelRequest(
│   model=ChatOpenAI(
│   │   profile={
│   │   │   'max_input_tokens': 272000,
│   │   │   'max_output_tokens': 128000,
│   │   │   'text_inputs': True,
│   │   │   'image_inputs': True,
│   │   │   'audio_inputs': False,
│   │   │   'video_inputs': False,
│   │   │   'text_outputs': True,
│   │   │   'image_outputs': False,
│   │   │   'audio_outputs': False,
│   │   │   'video_outputs': False,
│   │   │   'reasoning_output': True,
│   │   │   'tool_calling': True,
│   │   │   'structured_output': True,
│   │   │   'image_url_inputs': True,
│   │   │   'pdf_inputs': True,
│   │   │   'pdf_tool_message': True,
│   │   │   'image_tool_message': True,
│   │   │   'tool_choice': True
│   │   },
│   │   client=<openai.resources.chat.completions.completions.Completions object at 0x0000020D2C99F4D0>,
│   │   async_client=<openai.resources.chat.completions.completions.AsyncCompletions object at 0x0000020D2C99FC10>,
│   │   root_client=<openai.OpenAI object at 0x0000020D2C99EF50>,
│   │   root_async_client=<openai.AsyncOpenAI object at 0x0000020D2C99F690>,
│   │   model_name='gpt-5-nano',
│   │   model_kwargs={},
│   │   openai_api_key=SecretStr('**********'),
│   │   openai_api_base='https://api.chatanywhere.tech/v1',
│   │   request_timeout=30.0,
│   │   max_retries=3,
│   │   max_tokens=8192
│   ),
│   messages=[
│   │   HumanMessage(
│   │   │   content='请调用工具计算85$账单上收25%的小费，小费要收多少钱？',
│   │   │   additional_kwargs={},
│   │   │   response_metadata={},
│   │   │   id='8ec2d9ea-9386-4c5c-be40-c7ec70dc31ed'
│   │   )
│   ],
│   system_message=None,
│   tool_choice=None,
│   tools=[
│   │   StructuredTool(
│   │   │   name='get_user_info',
│   │   │   description='Get user info.',
│   │   │   args_schema=<class 'langchain_core.utils.pydantic.get_user_info'>,
│   │   │   func=<function get_user_info at 0x0000020D25E78EA0>
│   │   ),
│   │   StructuredTool(
│   │   │   name='calculate_tip',
│   │   │   description='Calculate the tip amount for a bill.',
│   │   │   args_schema=<class 'langchain_core.utils.pydantic.calculate_tip'>,
│   │   │   func=<function calculate_tip at 0x0000020D2C290E00>
│   │   )
│   ],
│   response_format=None,
│   state={
│   │   'messages': [
│   │   │   HumanMessage(
│   │   │   │   content='请调用工具计算85$账单上收25%的小费，小费要收多少钱？',
│   │   │   │   additional_kwargs={},
│   │   │   │   response_metadata={},
│   │   │   │   id='8ec2d9ea-9386-4c5c-be40-c7ec70dc31ed'
│   │   │   )
│   │   ],
│   │   'user_id': 'user_123',
│   │   'preferences': {'theme': 'dark'}
│   },
│   runtime=Runtime(
│   │   context=None,
│   │   store=None,
│   │   stream_writer=<function Pregel.stream.<locals>.stream_writer at 0x0000020D2C9E0400>,
│   │   previous=None,
│   │   execution_info=ExecutionInfo(
│   │   │   node_attempt=1,
│   │   │   node_first_attempt_time=1774428404.961764
│   │   )
│   ),
│   model_settings={}
)"""
        return handler(updated)

    def wrap_tool_call(self, request: ToolCallRequest, handler):
        # Handle execution of the dynamic tool
        # 2、同时也要在传入ToolCallRequest给内层处理器之前对它做出修改，
        # 让内层的处理器得到的toolCallRequest中真的能有calculate_tip这个工具函数而不是None
        # 因为我们其实事先是不知道有calculate_tip这个动态工具（比如该工具来自MCP server），所以只能通过中间件来动态注册
        # 确保工具执行节点处理时，真正能用上这个工具。
        if request.tool_call["name"] == "calculate_tip":
            # 重写ToolRequestRequest对象中的tool属性
            request = request.override(tool=calculate_tip)
            return handler(request)
        return handler(request)


agent = create_agent(
    LLMs["gpt-5-nano"],
    tools=[get_user_info],  # Only static tools registered here，运行时的动态工具无法提前获知并注册
    middleware=[check_wrap_tool_call, DynamicToolMiddleware()],
    # 对于包裹式中间件钩子(比如wrap model call和wrap tool call)，排序靠前的包在最外面
    state_schema=CustomAgentState,
    name="带自定义middleware的账单计算员"
)

# Custom state can be passed in invoke
for chunk, metadata in agent.stream(
        input={
            "messages": [{"role": "user", "content": "请调用工具计算85$账单上收25%的小费，小费要收多少钱？"}],
            "user_id": "user_123",
            "preferences": {"theme": "dark"}
        },
        stream_mode="messages"  # 仅流式输出LLM token
):
    if isinstance(chunk, AIMessageChunk):
        # print(metadata)
        if chunk.content:
            print(chunk.content)
        if chunk.tool_call_chunks:
            for tool_call_chunk in chunk.tool_call_chunks:
                print(tool_call_chunk)

"""
  如果直接输出生成器返回的元组，输出结果如下：
    (
│   AIMessageChunk(
│   │   content='',
│   │   additional_kwargs={},
│   │   response_metadata={'model_provider': 'openai'},
│   │   id='lc_run--019ceb7f-6f9f-7192-af3b-f6ff7a01ef0d',
│   │   tool_calls=[],
│   │   invalid_tool_calls=[],
│   │   tool_call_chunks=[]
│   ),
│   {
│   │   'thread_id': '1',
│   │   'langgraph_step': 1,
│   │   'langgraph_node': 'model',
│   │   'langgraph_triggers': ('branch:to:model',),
│   │   'langgraph_path': ('__pregel_pull', 'model'),
│   │   'langgraph_checkpoint_ns': 'model:a89d626a-1923-2a0d-2e68-f118f5f5fab8',
│   │   'checkpoint_ns': 'model:a89d626a-1923-2a0d-2e68-f118f5f5fab8',
│   │   'ls_provider': 'openai',
│   │   'ls_model_name': 'gpt-4o-mini',
│   │   'ls_model_type': 'chat',
│   │   'ls_temperature': 0.5,
│   │   'ls_max_tokens': 1000
│   }
)
"""

# # 2、给智能体的短期记忆加上自动总结功能
# # To summarize message history in an agent, use the built-in SummarizationMiddleware:
# # 要在代理中总结消息历史，可以使用内置的摘要中间件 ：
# from langchain.agents import create_agent
# from langchain.agents.middleware import SummarizationMiddleware
# from langgraph.checkpoint.memory import InMemorySaver
# from langchain_core.runnables import RunnableConfig
#
# checkpointer = InMemorySaver()
#
# agent = create_agent(
#     model=LLMs["gpt-4.1-mini"],
#     tools=[],
#     middleware=[
#         SummarizationMiddleware(
#             model=LLMs["gpt-4.1-mini"],
#             trigger=("tokens", 4000),
#             keep=("messages", 20)
#         )
#     ],
#     checkpointer=checkpointer,
# )
#
# config: RunnableConfig = {"configurable": {"thread_id": "1"}}
# agent.invoke({"messages": "你好，我叫鲍勃"}, config)
# agent.invoke({"messages": "write a short poem about cats"}, config)
# agent.invoke({"messages": "now do the same but for dogs"}, config)
# final_response = agent.invoke({"messages": "what's my name?"}, config)
#
# final_response["messages"][-1].pretty_print()
# """
# ================================== Ai Message ==================================
#
# Your name is Bob!
# """


# 3、查看许多内置中间件的实现源码
"""
问：
LangChain的预构建的中间件是如何实现往create_agent方法创建的langgraph的state中额外添加channel的，
比如TodoListMiddle就能在graph state中额外添加"todos"这个键。请分解源码并给出解释。
答：
中间件添加 channel 的三步机制：
声明阶段：中间件类定义自己的 state_schema 属性，其中包含额外的字段
收集阶段：create_agent 收集中所有中间件的 state_schema 并与基础 AgentState 合并
使用阶段：合并后的状态模式用于创建 StateGraph，使得所有节点（包括中间件节点）都能访问这些额外的 channel
这种设计非常优雅，因为：
✅ 模块化：每个中间件只关心自己需要的 state 字段
✅ 可扩展性：可以叠加多个中间件，每个都贡献自己的 state 扩展
✅ 类型安全：通过 TypedDict 保持类型检查
✅ 向后兼容：不影响现有的 AgentState 基础功能
"""
# check1 = TodoListMiddleware

# # 4、通过中间件自定义state schema
# from langchain.agents import create_agent
# from langchain.messages import HumanMessage
# from langchain.agents.middleware import AgentState, AgentMiddleware
# from typing_extensions import NotRequired
# from typing import Any
#
#
# class CustomState(AgentState):
#     model_call_count: NotRequired[int]
#     user_id: NotRequired[str]
#
#
# # 注意这里继承父类时还指定了泛型参数为CustomState
# class CallCounterMiddleware(AgentMiddleware[CustomState]):
#     """The schema for state passed to the middleware nodes."""
#     state_schema = CustomState
#
#     def before_model(self, state: CustomState, runtime) -> dict[str, Any] | None:
#         count = state.get("model_call_count", 0)
#         if count > 10:
#             return {"jump_to": "end"}
#         return None
#
#     def after_model(self, state: CustomState, runtime) -> dict[str, Any] | None:
#         return {"model_call_count": state.get("model_call_count", 0) + 1}
#
#
# @after_model
# def my_after_model(state, runtime) -> dict[str, Any] | None:
#     # 检查state中是否存在model_call_count字段
#     pprint(state)
#     return {}
#
#
# agent = create_agent(
#     model=LLMs["gpt-4o-mini"],
#     middleware=[my_after_model, CallCounterMiddleware()],  # after类型的钩子函数按照传入顺序，从后往前依次运行。
#     tools=[],
# )
#
# # Invoke with custom state
# result = agent.invoke({
#     "messages": [HumanMessage("Hello")],
#     "model_call_count": 0,
#     "user_id": "user-123",
# })

"""
Node-style hooks  Node 风格的钩子，可以读取state和runtime，runtime包含context、store、stream writer
Run sequentially at specific execution points. Use for logging, validation, and state updates.
按顺序在特定执行点运行。用于日志记录、验证和状态更新。


Wrap-style hooks  缠绕式钩子，无论是ModelRequest还是ToolCallRequest，内部都有state、runtime.context这两个属性可以读取。
Intercept execution and control when the handler is called. Use for retries, caching, and transformation.
拦截执行过程，并在调用处理器时进行控制。可用于重试、缓存和转换。
You decide if the handler is called zero times (short-circuit), once (normal flow), or multiple times (retry logic).
您可以决定处理程序是被调用零次（短路）、一次（正常流程）还是多次（重试逻辑）。

State updates  州政府最新动态
Both node-style and wrap-style hooks can update agent state. The mechanism differs:
节点式和包装式钩子都可以更新代理状态。它们的机制有所不同：
    Node-style hooks (before_agent, before_model, after_model, after_agent):
    Return a dict directly. The dict is applied to the agent state using the graph’s reducers.
    Node 风格的 hooks （ before_agent 、 before_model 、 after_model 、 after_agent ）：
    直接返回一个字典。该字典会使用图的 reducer 应用于 agent 状态。


    Wrap-style hooks (wrap_model_call, wrap_tool_call): 
    For model calls, return ExtendedModelResponse with a Command 
    to inject state updates alongside the model response.
     For tool calls, return a Command directly. Use these when you need to track or update state based on logic that runs during the model or tool call, such as summarization trigger points, usage metadata, or custom fields calculated from the request or response.
    包装式钩子 （ wrap_model_call 、 wrap_tool_call ）：
    对于模型调用的包裹式钩子，返回一个包含 Command 的 ExtendedModelResponse ，
    以便在模型响应中注入状态更新。
    对于工具调用，直接返回一个 ` Command 。
    当您需要根据模型或工具调用期间运行的逻辑（例如摘要触发点、使用情况元数据或从请求或响应计算出的自定义字段）来跟踪或更新状态时，请使用这些钩子。
    
    from typing import Callable
    from langchain.agents.middleware import (
        wrap_model_call,
        ModelRequest,
        ModelResponse,
        AgentState,
        ExtendedModelResponse
    )
    from langgraph.types import Command
    from typing_extensions import NotRequired
    
    class UsageTrackingState(AgentState):
        # Agent state with token usage tracking.
    
        last_model_call_tokens: NotRequired[int]
    
    
    @wrap_model_call(state_schema=UsageTrackingState)
    def track_usage(
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ExtendedModelResponse:
        response = handler(request)
        return ExtendedModelResponse(
            model_response=response,
            command=Command(update={"last_model_call_tokens": 150}),
        )
"""
