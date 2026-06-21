from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from langgraph.graph import StateGraph
from llm.factory import LLMFactory
from tools.registry import ToolRegistry
import logging

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Agent 抽象基类 - 模板方法模式"""

    def __init__(self, name: str, config: Optional[Dict]=None):
        self.name = name
        self.config = config or {}
        self.llm = LLMFactory.get_client("ollama")
        self.tool_registry = ToolRegistry()
        self.graph: Optional[StateGraph] = None

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """构建 LangGraph 工作流(子类必须实现)"""
        pass

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """模板方法: 统一处理流程"""
        try:
            # 1. 输入验证
            self._validate_input(input_data)

            # 2. 构建/重构图
            if self.graph is None:
                self.graph = self.build_graph()
                self._compile_graph()

            # 3. 执行处理
            result = await self._execute(input_data)

            # 4. 后处理与日志
            self._log_result(result)

            return result
        except Exception as e:
            logger.error(f"Agent {self.name} failed: {e}")
            return self._handle_error(e)
        
    def _validate_input(self, input_data: Dict) -> None:
        """输入验证"""
        # TODO
        # - 定义 JSON Schema 验证规则
        # - 校验必填字段
        # - 数据类型校验
        pass

    def _compile_graph(self) -> None:
        """编译 LangGraph 图"""
        # TODO
        # - 设置 checkpointer (SQLite持久化)
        # - 配置中断点(用于人工审批)
        # - 添加图编译缓存
        self.graph = self.graph.compile()

    async def _execute(self, input_data: Dict) -> Dict:
        """执行 Agent 逻辑"""
        # TODO
        # - 添加执行超时控制
        # - 添加重试机制
        # - 集成 OpenTelemetry 追踪
        pass

    def _log_result(self, result: Dict) -> None:
        """记录执行结果"""
        # TODO
        # - 结构化日志输出
        # - 性能指标记录(延迟|Token消耗)
        pass

    def _handle_error(self, error: Exception) -> Dict:
        """统一错误处理"""
        return {"status": "error", "message": str(error), "agent": self.name}