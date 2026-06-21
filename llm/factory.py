from typing import Dict, Type
from .base import BaseLLM
from .providers.ollama_client import OllamaClient

class LLMFactory:
    """LLM 客户端工厂"""

    _clients: Dict[str, BaseLLM] = {}

    @classmethod
    def get_client(cls, provider: str="ollama", **kwargs) -> BaseLLM:
        """获取 LLM 客户端示例(单例模式)"""
        if provider not in cls._clients:
            if provider == "ollama":
                cls._clients[provider] = OllamaClient()
            else:
                raise ValueError(f"Unsupported provider: {provider}")
        return cls._clients[provider]
    
    # TODO
    # - 支持多实例管理(为不同 Agent 分配不同模型)
    # - 添加连接池管理
    # - 实现自动健康检查与故障切换
    # - 支持 OpenAI/Deepseek 等其他提供商接入