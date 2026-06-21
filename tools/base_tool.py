"""
工具基类
定义所有工具的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
import inspect
import json
from datetime import datetime

@dataclass
class ToolSchema:
    """工具 Schema 定义"""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema 格式
    required: List[str] = field(default_factory=list)
    returns: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required
            },
            "returns": self.returns
        }
    
@dataclass
class ToolExecutionResult:
    """工具执行结果"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseTool(ABC):
    """工具抽象基类"""

    def __init__(
        self,
        name: str,
        description: str,
        schema: Optional[ToolSchema] = None,
        timeout: int = 0,
        retry_count: int = 3
    ):
        """
        初始化工具
        Args:
            name: 工具名称
            description: 工具描述
            schema: 工具参数 schema
            timeout: 执行超时时间(秒)
            retry_count: 重试次数
        """
        self.name = name
        self.description = description
        self.schema = schema or self._generate_schema()
        self.timeout = timeout
        self.retry_count = retry_count

        # 统计信息
        self.call_count = 0
        self.success_count = 0
        self.total_time = 0.0

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        执行工具
        Args:
            **kwargs: 工具参数
        Returns:
            执行结果
        """
        pass

    def _generate_schema(self) -> ToolSchema:
        """从 execute 方法签名自动生成 Schema"""
        sig = inspect.signature(self.execute)
        parameters = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # 获取参数类型
            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation
                if annotation == str:
                    param_type = "string"
                elif annotation == int:
                    param_type = "integer"
                elif annotation == float:
                    param_type = "number"
                elif annotation == bool:
                    param_type = "boolean"
                elif annotation == list:
                    param_type = "array"
                elif annotation == dict:
                    param_type = "object"

            parameters[param_name] = {
                "type": param_type,
                "description": f"参数 {param_name}"
            }

            # 检查是否由默认值
            if param.default == inspect.Parameter.empty:
                required.append[param_name]

        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=parameters,
            required=required
        )
    
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证参数
        Args:
            params: 参数字典
        Returns:
            (是否有效, 错误信息)
        """
        if not self.schema:
            return True, None
        
        # 检查必填参数
        for required_param in self.schema.required:
            if required_param not in params:
                return False, f"缺少必填参数: {required_param}"
            
        # 检查参数类型
        for param_name, param_value in params.items():
            if param_name in self.schema.parameters:
                param_schema = self.schema.parameters[param_name]
                param_type = param_schema.get("type")

                # 类型检查
                if param_type == "string" and not isinstance(param_value, str):
                    return False, f"参数 {param_name} 应为字符串类型"
                elif param_type == "integer" and not isinstance(param_value, int):
                    return False, f"参数 {param_name} 应为整数类型"
                elif param_type == "number" and not isinstance(param_value, (int, float)):
                    return False, f"参数 {param_name} 应为数字类型"
                elif param_type == "boolean" and not isinstance(param_value, bool):
                    return False, f"参数 {param_name} 应为布尔类型"
                
        return True, None
    
    async def call(self, **kwargs) -> ToolExecutionResult:
        """
        调用工具(带重试和统计)
        Args:
            **kwargs: 工具参数
        Returns:
            执行结果
        """
        start_time = datetime.now()
        self.call_count += 1

        # 验证参数
        is_valid, error_msg = self.validate_params(kwargs)
        if not is_valid:
            return ToolExecutionResult(
                success=False,
                error=f"参数验证失败: {error_msg}",
                metadata={"call_count": self.call_count}
            )
        
        # 带重试的执行
        last_error = None
        for attempt in range(self.retry_count):
            try:
                result = await self.execute(**kwargs)

                # 执行成功
                execution_time = (datetime.now() - start_time).total_seconds()
                self.success_count += 1
                self.total_time += execution_time

                return ToolExecutionResult(
                    success=True,
                    result=result,
                    execution_time=execution_time,
                    metadata={
                        "call_count": self.call_count,
                        "attempt": attempt + 1
                    }
                )
            except Exception as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    import asyncio
                    await asyncio.sleep(1 * (attempt + 1))  # 指数退避

        # 所有重试都失败
        execution_time = (datetime.now() - start_time).total_seconds()
        return ToolExecutionResult(
            success=False,
            error=str(last_error),
            execution_time=execution_time,
            metadata={
                "call_count": self.call_count,
                "retry_count": self.retry_count
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        return {
            "name": self.name,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "success_rate": self.success_count / self.call_count if self.call_count > 0 else 0,
            "total_time": self.total_time,
            "avg_time": self.total_time / self.call_count if self.call_count > 0 else 0
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.call_count = 0
        self.success_count = 0
        self.total_time = 0.0

    # TODO
    # - 添加工具执行日志
    # - 实现工具权限控制
    # - 添加工具执行监控