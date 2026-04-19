"""
具备以下特性：
1、deep_agent的内置工具
2、deep_agent的文件系统接口--LocalShellBackend，相较于FilesystemBackend，额外具备execute工具。
3、多轮对话、人在循环
4、流式图消息输出

"""
import uuid
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, StreamPart
from typing import cast

from src.config.llm import LLMs
from src.paths import LOCAL_AGENT_WORKSPACE

# 首先利用LangChain Deep Agents框架构建第一个和最重要的智能体：编码人员智能体Engineer
engineer_instructions = ("你是一名资深软件开发工程师。"
                         "你精熟主流操作系统、基础数据结构与算法、主流应用开发框架（Vue+FastAPI等等），严格遵守大型软件公司的开发规范。"
                         "你的日常职责，主要是按照'明确合理的任务要求'，在现有项目上进行二次开发，或者创建新项目从零开始开发。"
                         "二次开发时，请提前确保你对当前项目的结构、各部分功能有足够的认识。"
                         "从零开始时，你创建的项目文件夹应该结构规范，符合软件开发大厂的主流标准，并且提前使用execute安装好要用到的依赖包。"
                         "标准化项目结构参考举例："
                         """
                        项目文件夹/
                        ├── myapp/                # 核心源码包（所有代码都放这里）
                        │   ├── __init__.py       # 标记这是一个Python包（必须有）
                        │   ├── main.py           # ✅ 你的主程序文件（放这里！）
                        │   ├── core.py           # 业务逻辑
                        │   └── common.py          # 工具函数
                        ├── tests/                # 测试代码（和myapp同级）
                        ├── pyproject.toml        # 项目配置
                        └── requirements.txt      # 依赖包
                        
                        项目文件夹/
                        ├── myapp/                    # 主包
                        │   ├── __init__.py           # 包标记
                        │   ├── main.py               # 入口
                        │   ├── core/                 # 子包（有 __init__.py）
                        │   │   ├── __init__.py
                        │   │   └── logic.py
                        │   ├── utils/                # 工具子包
                        │   │   ├── __init__.py
                        │   │   └── common.py
                        │   └── config/               # 配置包
                        │       ├── __init__.py
                        │       └── settings.py
                        ├── tests/
                        └── pyproject.toml
                         """
                         "对于项目文件夹的创建和依赖的安装，你应该倾向于选择最主流而高效的包管理工具，如果用时发现没有，你应该安装。"
                         "项目文件夹准备就绪后，你接着会依照‘明确的任务要求’，编写正确、优雅、扩展性强、符合开发规范的代码，"
                         "你编写的代码总是既包含功能性代码，也包含测试代码。测试代码编写完成后，别忘了运行测试。")

# Checkpointer is REQUIRED for human-in-the-loop
checkpointer = MemorySaver()

agent = create_deep_agent(
    model=LLMs["gpt-5-mini"],
    tools=[],
    system_prompt=engineer_instructions,
    checkpointer=checkpointer,
    backend=LocalShellBackend(root_dir=LOCAL_AGENT_WORKSPACE, virtual_mode=True, inherit_env=True),
    # 注意，要继承父进程的全部环境变量，inherit_env=True，智能体输入shell中的命令才能正确执行。
    interrupt_on={
        "execute": True,  # 为终端命令执行工具设置中断，如果虚拟文件系统是沙盒的话，可以不用指定interrupt_on，应该让智能体自由在沙盒中执行 execute 工具。
    },
    # 在使用FilesystemBackend时，始终一起使用 virtual_mode=True 与 root_dir，
    # 这样在智能体调用内置文件操作工具时，才能真正启用基于路径的访问限制（阻止访问 ..、~ 和根以外的绝对路径）
    # 如果是带了execute工具的LocalShellFilesystem，virtual_mode=True也能通过内置的文件操作工具的实现限制智能体的的文件操作，
    # 但是还是没办法限制通过shell命令进行的文件操作，所以说尽量使用远程沙盒作为虚拟文件系统。
    name="Engineer_DeepAgent",
)

# Create config with thread_id for state persistence
config = {"configurable": {"thread_id": str(uuid.uuid4())}}

# input_text参考值：有一个加减乘除计算器脚本，在根目录下通过python -m运行pytest，给出测试报告，同时文件记录测试报告

last_output_msg = None
while True:
    # 第一次用户输入；或者上个ReAct循环完整结束后，等待用户新输入令。
    input_text = input("\n=========================================\n请用户输入：")
    if input_text == "exit":
        print("\n用户输入了exit，结束多轮对话。")
        break
    agent_input = {"messages": [{"role": "user", "content": input_text}]}

    print("\n=========================================\n下面开启全新的一轮ReAct循环\n")
    human_in_the_loop = False  # 每次开始前默认没发生人在循环
    current_loop_ends_totally = False  # 每次开始前默认本次ReAct没有完整结束

    while not current_loop_ends_totally:
        # 开启新一轮的 或 继续未完整结束的 ReAct循环
        for stream_part in agent.stream(input=agent_input, config=config, stream_mode=["values"], version="v2"):
            stream_part = cast(StreamPart, stream_part)
            # 先判断本次ReAct循环是否需要人类参与
            if stream_part['interrupts']:
                # 如果真需要人类参与
                print(
                    "\n=========================================\n工具中断触发，需要人类干预，之后才能继续进行本轮ReAct循环\n")
                interrupt_value = stream_part['interrupts'][0].value
                action_requests = interrupt_value["action_requests"]
                review_configs = interrupt_value["review_configs"]

                # Create a lookup map from tool name to review config
                config_map = {cfg["action_name"]: cfg for cfg in review_configs}

                # Display the pending actions to the user
                # 并发工具调用下，可能会有多个工具调用被中断，这些中断需要人类顺序逐个处理
                decisions = []
                for action in action_requests:
                    review_config = config_map[action["name"]]
                    print(f"Tool: {action['name']}")
                    print(f"Arguments: {action['args']}")
                    print(f"Allowed decisions: {review_config['allowed_decisions']}")
                    decision_type = input("\nEnter your decision(approve/reject/edit) for this tool_call: ")

                    if decision_type == "approve":
                        decisions.append({"type": "approve"})
                    elif decision_type == "reject":
                        decisions.append({"type": "reject"})
                    elif decision_type == "edit":
                        new_args = {}
                        for k in action["args"]:
                            new_arg_value = input(f"请为{k} = {action['args'][k]}提供一个新值:")
                            new_args[k] = new_arg_value
                        decisions.append({"type": "edit", "edited_action": {"name": action["name"], "args": new_args}})

                # Resume execution with decisions
                agent_input = Command(resume={"decisions": decisions})
                human_in_the_loop = True
                # 暂停当前ReAct执行，直接继续下一次ReAct
                break

            data = stream_part["data"]
            latest_message = data["messages"][-1]
            if last_output_msg is None:
                latest_message.pretty_print()
                last_output_msg = latest_message
            elif latest_message != last_output_msg:
                latest_message.pretty_print()
                last_output_msg = latest_message

        # 判断本次ReAct循环是否完整地结束了
        if human_in_the_loop:
            # 不是完整地结束
            print(
                "\n=========================================\n发生了人在循环，已经收集到人类干预，继续进行本轮ReAct循环\n")
            human_in_the_loop = False  # 继续进行本轮ReAct循环前，恢复默认值
            continue
        else:
            # 说明是完整地结束
            print("\n=========================================\n本轮ReAct循环圆满结束\n")
            current_loop_ends_totally = True

print("多轮对话成功结束。")

"""
下面是stream模式为values + messages时的输出, 浅浅看一下即可，非生产场景不需要考虑传输提供商模型的流式传输到前端。
{
│   'type': 'values',
│   'ns': (),
│   'data': {
│   │   'messages': [
│   │   │   HumanMessage(
│   │   │   │   content='创建一个python包，写一个二叉树层序遍历脚本，同时基于pytest完成它的测试脚本，运行测试给出测试报告。',
│   │   │   │   additional_kwargs={},
│   │   │   │   response_metadata={},
│   │   │   │   id='873703e7-5707-4fee-b72a-d1e8e3549023'
│   │   │   )
│   │   ]
│   },
│   'interrupts': ()
}
{
│   'type': 'messages',
│   'ns': (),
│   'data': (
│   │   AIMessageChunk(
│   │   │   content='',
│   │   │   additional_kwargs={},
│   │   │   response_metadata={'model_provider': 'openai'},
│   │   │   id='lc_run--019cfe8d-49dd-7f01-98d3-6735b47684f7',
│   │   │   tool_calls=[],
│   │   │   invalid_tool_calls=[
│   │   │   │   {
│   │   │   │   │   'name': None,
│   │   │   │   │   'args': '":"',
│   │   │   │   │   'id': None,
│   │   │   │   │   'error': None,
│   │   │   │   │   'type': 'invalid_tool_call'
│   │   │   │   }
│   │   │   ],
│   │   │   tool_call_chunks=[
│   │   │   │   {
│   │   │   │   │   'name': None,
│   │   │   │   │   'args': '":"',
│   │   │   │   │   'id': None,
│   │   │   │   │   'index': 0,
│   │   │   │   │   'type': 'tool_call_chunk'
│   │   │   │   }
│   │   │   ]
│   │   ),
│   │   {
│   │   │   'lc_agent_name': 'Engineer:DeepAgent',
│   │   │   'ls_integration': 'deepagents',
│   │   │   'thread_id': 'e1789095-3f6b-4e16-8d34-e6f917231f4b',
│   │   │   'langgraph_step': 2,
│   │   │   'langgraph_node': 'model',
│   │   │   'langgraph_triggers': ('branch:to:model',),
│   │   │   'langgraph_path': ('__pregel_pull', 'model'),
│   │   │   'langgraph_checkpoint_ns': 'model:1e62badf-0736-6c52-d304-c11d247a134f',
│   │   │   'checkpoint_ns': 'model:1e62badf-0736-6c52-d304-c11d247a134f',
│   │   │   'ls_provider': 'openai',
│   │   │   'ls_model_name': 'gpt-5-mini',
│   │   │   'ls_model_type': 'chat',
│   │   │   'ls_temperature': None,
│   │   │   'ls_max_tokens': 8192,
│   │   │   'ls_method': 'traceable'
│   │   }
│   )
}
"""

# invoke调用时，不可流式输出LLM token
#
# result = agent.invoke(
#         input=agent_input,
#         config=config,
#         version="v2"
# )
#
#
# # Check if execution was interrupted
# if result.interrupts:
#     # Extract interrupt information
#     interrupt_value = result.interrupts[0].value
#     action_requests = interrupt_value["action_requests"]
#     review_configs = interrupt_value["review_configs"]
#
#     # Create a lookup map from tool name to review config
#     config_map = {cfg["action_name"]: cfg for cfg in review_configs}
#
#     # Display the pending actions to the user
#     # 并发工具调用下，可能会有多个工具调用被中断，这些中断需要人类顺序逐个处理
#     decisions = []
#     for action in action_requests:
#         review_config = config_map[action["name"]]
#         print(f"Tool: {action['name']}")
#         print(f"Arguments: {action['args']}")
#         print(f"Allowed decisions: {review_config['allowed_decisions']}")
#         decision_type = input("Enter your decision(approve/reject/edit) for this tool_call: ")
#
#         if decision_type == "approve":
#             decisions.append({"type": "approve"})
#         elif decision_type == "reject":
#             decisions.append({"type": "reject"})
#         elif decision_type == "edit":
#             new_args = {}
#             for k in action["args"]:
#                 new_arg_value = input(f"请为{k} = {action['args'][k]}提供一个新值")
#                 new_args[k] = new_arg_value
#             decisions.append({
#                                 "type": "edit",
#                                 "edited_action": {
#                                     "name": action["name"],
#                                     "args": new_args
#                                 }
#                               }
#             )
#
#
#     # Get user decisions (one per action_request, in order)
#     decisions = [
#         {"type": "approve"}  # User approved the deletion
#     ]
#
#     # 如果是编辑决定，可以在工具执行前修改参数，比如下面的发邮件工具引起的中断。
#     # decisions = [{
#     #     "type": "edit",
#     #     "edited_action": {
#     #         "name": action_request["name"],  # Must include the tool name
#     #         "args": {"to": "team@company.com", "subject": "...", "body": "..."}
#     #     }
#     # }]
#
#     # Resume execution with decisions
#     result = agent.invoke(
#         input=Command(resume={"decisions": decisions}),
#         config=config,  # Must use the same config!
#         version="v2",
#     )
#
# # 打印最终结果
# print(result.value["messages"][-1].content)
