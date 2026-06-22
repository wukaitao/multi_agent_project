from core.agent_base import BaseAgent
from langgraph.graph import StateGraph
from typing import Dict, Any

class OfficeAgent(BaseAgent):
    """办公领域专家 Agent"""

    def __init__(self):
        super().__init__(name="office_agent")

    def build_graph(self) -> StateGraph:
        """构建 OfficeAgent 工作流"""
        pass