from core.agent_base import BaseAgent
from langgraph.graph import StateGraph
from typing import Dict, Any

class FinanceAgent(BaseAgent):
    """金融领域专家 Agent"""

    def __init__(self):
        super().__init__(name="finance_agent")

    def build_graph(self) -> StateGraph:
        """构建 FinanceAgent 工作流"""
        pass