from core.agent_base import BaseAgent
from langgraph.graph import StateGraph
from typing import Dict, Any

class CodingAgent(BaseAgent):
    """编程领域专家 Agent"""

    def __init__(self):
        super().__init__(name="coding_agent")

    def build_graph(self) -> StateGraph:
        """构建 CodingAgent 工作流"""
        pass