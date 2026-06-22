"""
自定义异常体系
"""
from typing import Optional, Dict, Any

class AgentException(Exception):
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

class GraphException(AgentException):
    """工作流图异常"""
    pass

class StateException(AgentException):
    """状态管理异常"""
    pass

class ToolException(AgentException):
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

class LLMException(AgentException):
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

class ValidationException(AgentException):
    """数据验证异常"""
    pass

class TimeoutException(AgentException):
    """超时异常"""

    def __init__(
        self,
        message: str="Operation timed out",
        timeout_seconds: Optional[int]=None,
        **kwargs
    ):
        self.timeout_seconds = timeout_seconds
        super().__init__(message, **kwargs)

class RetryException(AgentException):
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

class ConfigurationException(AgentException):
    """配置异常"""
    pass

class SecurityException(AgentException):
    """安全异常"""
    pass

class ApprovalException(AgentException):
    """审批流程异常"""
    pass

class RoutingException(AgentException):
    """路由异常"""
    pass

class MemoryException(AgentException):
    """记忆系统异常"""
    pass