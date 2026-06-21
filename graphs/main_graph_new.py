from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from .state_schema import AgentState
from agents.supervisor.router import DomainRouter
from agents.specialized import (
    RAGAgent, ChatAgent, 
    ApprovalAgent, MultimodalAgent
)
from agents.domain import MedicalAgent, FinanceAgent, EntertainmentAgent, CodingAgent, OfficeAgent
import sqlite3
from config.settings import *

class MainGraph:
    """主监督者工作流"""

    def __init__(self):
        self.router = DomainRouter()
        self.checkpointer = self._init_checkpointer()
        self.graph = self._build_graph()

    def _init_checkpointer(self):
        """初始化 SQLite 状态持久化"""
        # TODO
        # - 使用 SQLite 存储 LangGraph 检查点
        # - 实现状态压缩(只保留最后N个检查点)
        # - 添加检查点清理策略(7天过期)
        conn = sqlite3.connect(MEMORY_DB)
        return SqliteSaver(conn)

    def _build_graph(self) -> StateGraph:
        """构建工作流图"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("route_domain", self.route_domain)
        # 垂直领域专家 Agent
        workflow.add_node("medical", MedicalAgent().process)
        workflow.add_node("finance", FinanceAgent().process)
        workflow.add_node("entertainment", EntertainmentAgent().process)
        workflow.add_node("coding", CodingAgent().process)
        workflow.add_node("office", OfficeAgent().process)
        # 专业能力子 Agent
        workflow.add_node("rag", RAGAgent().process)
        workflow.add_node("multimodal", MultimodalAgent().process)
        workflow.add_node("approval", ApprovalAgent().process)
        workflow.add_node("chat", ChatAgent().process)
        # 异常处理 Agent
        workflow.add_node("error_handler", self.handle_error)

        # 设置入口点
        workflow.set_entry_point("route_domain")

        # 添加条件边
        workflow.add_conditional_edges(
            "route_domain",
            self.decide_next_agent,
            {
                "medical": "medical",
                "finance": "finance",
                "entertainment": "entertainment",
                "coding": "coding",
                "office": "office",
                "rag": "rag",
                "multimodal": "multimodal",
                "approval": "approval",
                "chat": "chat",
                "error": "error_handler"
            }
        )

        # 所有领域 Agent 执行完毕后回到路由或结束
        agents = ["medical", "finance", "entertainment", "coding", "office"]
        for agent in agents:
            workflow.add_edge(agent, "route_domain")
        
        workflow.add_edge("rag", "chat")
        workflow.add_edge("multimodal", END)
        workflow.add_edge("approval", END)
        workflow.add_edge("chat", END)
        workflow.add_edge("error_handler", END)

        return workflow.compile(checkpointer=self.checkpointer)

    async def route_domain(self, state: AgentState) -> AgentState:
        """路由节点: 分析用户意图并分派到领域 Agent"""
        # TODO
        # - 调用 DomainRouter 进行 LLM 意图分类
        # - 提取实体和关键信息
        # - 检测是否需要多轮对话
        # - 路由置信度低于阈值时走人工确认
        state["iteration"] = state.get("iteration", 0) + 1
        return state
    
    async def decide_next_agent(self, state: AgentState) -> str:
        """决定下一个要用的 Agent"""
        # TODO
        # - 基于意图分类结果路由
        # - 检测是否需要 RAG 增强
        # - 检测是否需要审批节点
        # - 检测执行次数防止死循环
        if state.get("requires_approval"):
            return "approval"
        if state.get("domain") == "medical":
            return "medical"
        # ... 其他路由逻辑
        return "chat"
    
    async def handle_error(self, state: AgentState) -> AgentState:
        """统一错误处理节点"""
        state["state"] = "failed"
        # TODO: 记录错误栈、发送告警
        return state
    
    async def stream(self, input_state: AgentState):
        """流式执行工作流"""
        # TODO
        # - 实现流式输出
        # - 支持中途中断和恢复
        async for event in self.graph.astream(input_state):
            yield event