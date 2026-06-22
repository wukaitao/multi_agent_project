from core.agent_base import BaseAgent
from langgraph.graph import StateGraph
# from graphs.subgraphs.rag_subgraph import RAGSubgraph
from typing import Dict, Any

class ChatAgent(BaseAgent):
    """通用聊天 Agent"""

    def __init__(self):
        super().__init__(name="chat_agent")

    def build_graph(self) -> StateGraph:
        """构建 ChatAgent 工作流"""
        pass