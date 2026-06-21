from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass

@dataclass
class Message:
    role: str  # system, user, assistant
    content: str

class BaseLLM(ABC):
    """LLM 客户端抽象基类"""

    @abstractmethod
    async def generate(self, messages: List[Message], **kwargs) -> str:
        """同步生成响应"""
        pass

    @abstractmethod
    async def stream(self, messages: List[Message], **kwargs) -> AsyncGenerator[str, None]:
        """流式生成响应"""
        pass

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        pass

class LLMConfig:
    """待实现: 模型配置管理"""

    # TODO
    # - 模型参数动态调整(根据任务复杂度自动调整 temperature/top_p)
    # - 多模型负载均衡与故障转移
    # - 模型性能监控与统计
    # - Token 使用量计算与限额控制

    pass