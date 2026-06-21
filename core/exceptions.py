"""
自定义异常体系
"""
from typing import Optional, Dict, Any

class AgentExpection(Exception):
    """Agent 基础异常类"""
    
    def __init__(
        self,
        message: str,
        agent_name: Optional[str]=None,
        details: Optional[Dict[str, Any]]=None
    ):
        self.agent_name = agent_name
        self.details = details or {}
        super().__init__(message)

class GraphExpection(AgentExpection):
    """工作流图异常"""
    pass

class StateExpection(AgentExpection):
    """状态管理异常"""
    pass

class ToolExpection(AgentExpection):
    """工具调用异常"""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str]=None,
        params: Optional[Dict[str, Any]]=None,
        **kwargs
    ):
        self.tool_name = tool_name
        self.params = params or {}
        super().__init__(message, **kwargs)

class LLMExpection(AgentExpection):
    """LLM 调用异常"""

    def __init__(
        self,
        message: str,
        provider: Optional[str]=None,
        model: Optional[str]=None,
        **kwargs
    ):
        self.provider = provider
        self.model = model
        super().__init__(message, **kwargs)

class ValidationExpection(AgentExpection):
    """数据验证异常"""
    pass

class TimeoutExpection(AgentExpection):
    """超时异常"""

    def __init__(
        self,
        message: str="Operation timed out",
        timeout_seconds: Optional[int]=None,
        **kwargs
    ):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, **kwargs)

class RetryExpection(AgentExpection):
    """重试异常"""

    def __init__(
        self,
        message: str,
        attempts: int=0,
        max_attempts: int=0,
        **kwargs
    ):
        self.attempts = attempts
        self.max_attempts = max_attempts
        super().__init__(message, **kwargs)

class ConfigurationExpection(AgentExpection):
    """配置异常"""
    pass

class SecurityExpection(AgentExpection):
    """安全异常"""
    pass

class ApprovalExpection(AgentExpection):
    """审批流程异常"""
    pass

class RoutingExpection(AgentExpection):
    """路由异常"""
    pass

class MemoryExpection(AgentExpection):
    """记忆系统异常"""
    pass