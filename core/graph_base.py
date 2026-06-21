"""
LangGraph 工作流基类
提供统一的图构建、编译和执行接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncGenerator, Type
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from datetime import datetime
import logging
from pathlib import Path

from .state_base import BaseState
from config.settings import *

logger = logging.getLogger(__name__)

class BaseGraph(ABC):
    """ LangGraph 工作流基类"""

    def __init__(
        self,
        name: str,
        state_class: Type[BaseState],
        checkpointer: Optional[BaseCheckpointSaver]=None,
        **kwargs
    ):
        """
        初始化工作流

        Args:
            name: 工作流名称
            state_class: 状态类
            checkpointer: 检查点保存器
            **kwargs: 额外参数
        """
        self.name = name
        self.state_class = state_class
        self.checkpointer = checkpointer or self._init_checkpointer()
        self.workflow = None
        self.graph = None
        self._compiled = False
        self.kwargs = kwargs

        self._build_workflow()

    def _init_checkpointer(self) -> BaseCheckpointSaver:
        """初始化 SLQLite 检查点保存器"""
        # TODO
        # - 支持多种后端(SQLite, Redis, ProstgreSQL)
        # - 添加检查点压缩
        # - 实现检查点清理策略
        db_path = CHROMA_PATH
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        return SqliteSaver(conn)
    
    def _build_workflow(self) -> None:
        """构建工作流图(由子类实现具体节点和边)"""
        self.workflow = StateGraph(self.state_class)
        self._add_nodes()
        self._add_edges()
        self._configure_entry_and_exit()

    @abstractmethod
    def _add_nodes(self) -> None:
        """添加节点"""
        pass

    @abstractmethod
    def _add_edges(self) -> None:
        """添加所有边(包括条件边)"""
        pass
    
    @abstractmethod
    def _configure_entry_and_exit(self) -> None:
        """配置入口和结束点"""
        pass

    def compile(self, **kwargs) -> None:
        """
        编译工作流

        Args:
            **kwargs: 编译阐述(checkpointer, interrupt_before, interrupt_after等)
        """
        if self._compiled:
            logger.warning(f"Graph {self.name} already compiled, recompiling...")

        compile_kwargs = {
            "checkpointer": self.checkpointer,
            "interrupt_before": kwargs.get("interrupt_before", []),
            "interrupt_after": kwargs.get("interrupt_after", [])
        }

        try:
            self.graph = self.workflow.compile(**compile_kwargs)
            self._compiled = True
            logger.info(f"Graph {self.name} compiled successfully")
        except Exception as e:
            logger.error(f"Failed to compile graph {self.name}: {e}")
            raise

    async def invoke(self, state: Dict[str, Any], config: Optional[Dict]=None) -> Dict[str, Any]:
        """
        执行工作流(同步模式)

        Args:
            state: 初始状态
            config: 执行配置(thread_id, recursion_limit等)
        Returns:
            最终状态
        """
        if not self._compiled:
            self.compile()

        config = config or {}
        thread_id = config.get("thread_id", f"{self.name}_{datetime.now().timestamp()}")

        try:
            result = await self.graph.invoke(
                state,
                config={"configurable": {"thread_id": thread_id}}
            )
            logger.inf(f"Graph {self.name} invoked successfully, thread: {thread_id}")
            return result
        except Exception as e:
            logger.error(f"Graph {self.name} invocation failed: {e}")

    async def stream(
        self,
        state: Dict[str, Any],
        config: Optional[Dict]=None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式执行工作流
        Args:
            state: 初始状态
            config: 执行配置
        Yields:
            每个节点的输出
        """
        if not self._compiled:
            self.compile()

        config = config or {}
        thread_id = config.get("thread_id", f"{self.name}_{datetime.now().timestamp()}")

        async for event in self.graph.astream(
            state,
            config={"configurable": {"thread_id": thread_id}}
        ):
            yield event

    async def resume(
        self,
        config: Dict[str, Any],
        input: Optional[Dict[str, Any]]=None
    ) -> Dict[str, Any]:
        """
        恢复被中断的工作流
        Args:
            config: 配置(包含 thread_id)
            input: 恢复时输入
        Returns:
            最终状态
        """
        if not self._compiled:
            self.compile()

        try:
            result = await self.graph.invoke(
                input or {},
                config=config
            )
            return result
        except Exception as e:
            logger.error(f"Failed top resume graph {self.name}: {e}")

    def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取指定线程的状态"""
        if not self._compiled:
            self.compile()

        try:
            state = self.graph.invoke(
                config={"configurable": {"thread_id": thread_id}}
            )
            return state.values if state else None
        except Exception as e:
            logger.error(f"Failed to get state for thread {thread_id}: {e}")
            return None
        
    def get_history(self, thread_id: str, limit: int=10) -> list:
        """获取指定线程的历史记录"""
        if not self._compiled:
            self.compile()

        try:
            history = list(self.graph.get_state_history(
                config={"configurable": {"thread_id": thread_id}},
                limit=limit
            ))
            return history
        except Exception as e:
            logger.error(f"Failed to get history for thread {thread_id}: {e}")
            return []
        
    def add_node(self, name: str, func) -> None:
        """动态添加节点"""
        if self._compiled:
            logger.warning(f"Graph already compiled, node addition may not take effect")
        self.workflow.add_node(name, func)

    def add_edge(self, from_node: str, to_node: str) -> None:
        """动态添加边"""
        if self._compiled:
            logger.warning(f"Graph already compiled, edge eddtion may not take effect")
        self.workflow.add_edge(from_node, to_node)

    def add_conditional_edges(self, from_node: str, condition, mapping: Dict) -> None:
        """动态添加条件边"""
        if self._compiled:
            logger.warning("Graph already compiled, edge_addition may not take effect")
        self.workflow.add_conditional_edges(from_node, condition, mapping)

    # TODO
    # - 添加图可视化功能
    # - 添加性能监控(每个节点的执行时间)
    # - 添加执行追踪(OpenTelemetry)
    # - 实现版本管理
    # - 支持子图嵌套
    # - 添加节点重试装饰器