from core.agent_base import BaseAgent
from langgraph.graph import StateGraph
from typing import Dict, Any

class EntertainmentAgent(BaseAgent):
    """娱乐领域专家 Agent"""

    def __init__(self):
        super().__init__(name="entertainment_agent")

    def build_graph(self) -> StateGraph:
        """构建 EntertainmentAgent 工作流"""
        pass