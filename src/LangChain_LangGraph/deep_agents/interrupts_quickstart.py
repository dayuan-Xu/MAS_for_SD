from deepagents.backends import FilesystemBackend
from langchain.tools import tool
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from rich.pretty import pprint

from src.paths import DEEP_AGENT_WORKSPACE
from src.config.llm import LLMs


@tool
def delete_file(path: str) -> str:
    """Delete a file from the filesystem."""
    return f"Deleted {path}"

@tool
def read_file(path: str) -> str:
    """Read a file from the filesystem."""
    return f"Contents of {path}"

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    return f"Sent email to {to}"

# Checkpointer is REQUIRED for human-in-the-loop
checkpointer = MemorySaver()

agent = create_deep_agent(
    model=LLMs["gpt-5-mini"],
    tools=[delete_file, read_file, send_email],
    interrupt_on={
        "delete_file": True,  # Default: approve, edit, reject
        "read_file": False,   # No interrupts needed
        "send_email": {"allowed_decisions": ["approve", "reject"]},  # No editing
    },
    checkpointer=checkpointer,  # Required!
    backend=FilesystemBackend(root_dir=DEEP_AGENT_WORKSPACE, virtual_mode=True),
)

import uuid
from langgraph.types import Command

# 先看看单个工具中断如何处理
#
# # Create config with thread_id for state persistence
# config = {"configurable": {"thread_id": str(uuid.uuid4())}}

# # Invoke the agent
# result = agent.invoke(
#     {"messages": [{"role": "user", "content": "Delete the file temp.txt"}]},
#     config=config,
#     version="v2",
# )
#
# # Check if execution was interrupted
# if result.interrupts:
#     # Extract interrupt information
#     interrupt_value = result.interrupts[0].value
#     # 查看一下框架底层调用中断函数时传入的value长啥样
#     pprint(interrupt_value)
#     """ 长这个样子
#     {
#     │   'action_requests': [
#     │   │   {
#     │   │   │   'name': 'delete_file',
#     │   │   │   'args': {'path': '/temp.txt'},
#     │   │   │   'description': "Tool execution requires approval\n\nTool: delete_file\nArgs: {'path': '/temp.txt'}"
#     │   │   }
#     │   ],
#     │   'review_configs': [
#     │   │   {
#     │   │   │   'action_name': 'delete_file',
#     │   │   │   'allowed_decisions': ['approve', 'edit', 'reject']
#     │   │   }
#     │   ]
#     }
#     """
#     action_requests = interrupt_value["action_requests"]
#     review_configs = interrupt_value["review_configs"]
#
#     # Create a lookup map from tool name to its review config
#     config_map = {cfg["action_name"]: cfg for cfg in review_configs}
#
#     # Display the pending actions to the user
#     for action in action_requests:
#         review_config = config_map[action["name"]]  # 获取当前工具的审阅配置
#         print(f"Tool: {action['name']}")
#         print(f"Arguments: {action['args']}")
#         print(f"Allowed decisions: {review_config['allowed_decisions']}")
#
#     # Get user decisions (one per action_request, in order)
#     decisions = [
#         {"type": "approve"}  # User approved the deletion
#     ]
#
#     # Resume execution with decisions
#     result = agent.invoke(
#         Command(resume={"decisions": decisions}),
#         config=config,  # Must use the same config!
#         version="v2",
#     )
#
# # Process final result
# print(result.value["messages"][-1].content)


### 接下来看看多个工具调用被中断
config = {"configurable": {"thread_id": str(uuid.uuid4())}}

result = agent.invoke(
    {"messages": [{
        "role": "user",
        "content": "Delete temp.txt and send an email to admin@example.com"
    }]},  # 同时请求agent调用两个会引起中断的工具
    config=config,
    version="v2",  # version2下，invoke方法返回的是一个GraphOutput对象，内部包含value、interrupts两个属性。
)

if result.interrupts:
    # 查看一下中断s
    pprint(result.interrupts)
    interrupt_value = result.interrupts[0].value

    """result.interrupts是一个由Interrupt对象构成的元组
    (
    │   Interrupt(
    │   │   value={
    │   │   │   'action_requests': [
    │   │   │   │   {
    │   │   │   │   │   'name': 'delete_file',
    │   │   │   │   │   'args': {'path': '/temp.txt'},
    │   │   │   │   │   'description': "Tool execution requires approval\n\nTool: delete_file\nArgs: {'path': '/temp.txt'}"
    │   │   │   │   },
    │   │   │   │   {
    │   │   │   │   │   'name': 'send_email',
    │   │   │   │   │   'args': {
    │   │   │   │   │   │   'to': 'admin@example.com',
    │   │   │   │   │   │   'subject': 'Notification: temp.txt deleted',
    │   │   │   │   │   │   'body': 'temp.txt was deleted from the server per your request.'
    │   │   │   │   │   },
    │   │   │   │   │   'description': "Tool execution requires approval\n\nTool: send_email\nArgs: {'to': 'admin@example.com', 'subject': 'Notification: temp.txt deleted', 'body': 'temp.txt was deleted from the server per your request.'}"
    │   │   │   │   }
    │   │   │   ],
    │   │   │   'review_configs': [
    │   │   │   │   {
    │   │   │   │   │   'action_name': 'delete_file',
    │   │   │   │   │   'allowed_decisions': ['approve', 'edit', 'reject']
    │   │   │   │   },
    │   │   │   │   {
    │   │   │   │   │   'action_name': 'send_email',
    │   │   │   │   │   'allowed_decisions': ['approve', 'reject']
    │   │   │   │   }
    │   │   │   ]
    │   │   },
    │   │   id='0ab9a79345f0e28402e55ac19c21cdda'
    │   ),
    )
    """

    # 查看一下多次中断函数调用时传入的多个value长啥样，框架说会被收集成一批后由用户顺序处理
    pprint(interrupt_value)

    action_requests = interrupt_value["action_requests"]

    # Two tools need approval
    assert len(action_requests) == 2

    # Provide decisions in the same order as action_requests  决策顺序要和action请求的顺序一一对应上
    decisions = [
        {"type": "approve"},  # First tool: delete_file
        {"type": "reject"}    # Second tool: send_email
    ]

    result = agent.invoke(
        Command(resume={"decisions": decisions}),
        config=config,
        version="v2",
    )