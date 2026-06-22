from core.agent_base import BaseAgent
from langgraph.graph import StateGraph
# from graphs.subgraphs.rag_subgraph import RAGSubgraph
from typing import Dict, Any

class MultimodalAgent(BaseAgent):
    """多模态 Agent"""

    def __init__(self):
        super().__init__(name="multimodal_agent")

    def build_graph(self) -> StateGraph:
        """构建 MultimodalAgent 工作流"""
        pass