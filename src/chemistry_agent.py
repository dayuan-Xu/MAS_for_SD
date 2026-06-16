"""
化工智能体工具调用Demo
"""
import uuid

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver

from src.config.llm import LLMs
from src.tools.mock_chemistry_tools import resolve_molecule, calculate_vapor_pressure, \
    calculate_unifac_activity_coefficients, \
    calculate_bubble_point
from src.utils.graph_running import multi_turn_conversation

# 首先利用LangChain Deep Agents框架构建第一个和最重要的智能体：编码人员智能体Engineer
engineer_instructions = """You are a chemical engineering agent."""

# Checkpointer is REQUIRED for multi react-loop
checkpointer = MemorySaver()

agent = create_deep_agent(
    model=LLMs["minimax-m2.7"],
    tools=[resolve_molecule, calculate_vapor_pressure, calculate_unifac_activity_coefficients, calculate_bubble_point],
    system_prompt=engineer_instructions,
    checkpointer=checkpointer,
    name="Chemistry_DeepAgent",
)

# Create config with thread_id for state persistence
config = {"configurable": {"thread_id": str(uuid.uuid4())}}

multi_turn_conversation(agent, config)
