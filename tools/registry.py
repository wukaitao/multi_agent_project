from typing import Dict, Callable, Any, Optional
import inspect
import ast
from pathlib import Path
import importlib
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    """工具注册中心 - 单例模式"""

    _instance = None
    _tools: Dict[str, Dict] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._tools = {}
        self._auto_discover()

    def register(self, name: str, func: Callable, schema: Optional[Dict] = None):
        """注册工具"""
        # TODO
        # - 自动从函数名成成 JSON Schema
        # - 支持工具版管理
        # - 添加工具控制权限控制(哪些 Agent 可用)
        # - 实现工具热加载与卸装
        if schema is None:
            schema = self._generate_schema(func)

        self._tools[name] = {
            "func": func,
            "schema": schema
        }
        logger.info(f"Tool registered: {name}")

    def _generate_schema(self, func: Callable) -> Dict:
        """从函数签名自动生成 JSON Scheme"""
        # TODO
        # - 解析函数参数类型提示
        # - 生成符合 OpenAPI 规范的 schema
        # - 添加函数文档说明
        sig = inspect.signature(func)
        schema = {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {
                "types": "object",
                "properties": {},
                "required": []
            }
        }
        # ... 参数解析逻辑
        return schema
    
    def _auto_discover(self):
        """自动发现并注册 tools 目录下的工具"""
        # TODO
        # - AST 扫描decorator 标记
        # - 动态导入工具模块
        # - 避免重复注册
        tools_path = Path(__file__).parent / "builtin"
        for py_file in tools_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            module_name = f"tools.builtin.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)
                # 查找带有 @register 装饰器的函数
                # ...
            except Exception as e:
                logger.error(f"Failed to load tool {module_name}: {e}")
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """获取工具函数"""
        tool = self._tools.get(name)
        return tool["func"] if tool else None
    
    def list_tools(self) -> Dict[str, Dict]:
        """列出所有工具机器 schema"""
        return {
            name: info["schema"] for name, info in self._tools.items()
        }
    
    async def execute(self, name: str, **kwargs) -> Any:
        """执行工具"""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        
        # TODO
        # - 添加执行超时控制
        # - 添加参数校验
        # - 记录执行日志
        # - 添加结果缓存

        try: 
            result = tool(**kwargs)
            # 如果时协程, await
            if inspect.iscoroutinefunction(tool):
                result = await result
            return result
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {e}")
            raise