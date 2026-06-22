"""
工具注册中心 - 单例模式
支持自动发现和注册工具
"""

from typing import Dict, Callable, Any, Optional
import inspect
import ast
import sys
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
        """
        注册工具
        Args:
            name: 工具名称
            func: 工具函数
            schema: 工具 Schema (可选, 自动生成)
        """
        # TODO
        # - 自动从函数名成成 JSON Schema
        # - 支持工具版管理
        # - 添加工具控制权限控制(哪些 Agent 可用)
        # - 实现工具热加载与卸装
        if schema is None:
            schema = self._generate_schema(func)

        self._tools[name] = {
            "name": name,
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
            "description": func.__doc__ or f"Tool: {func.__name__}",
            "parameters": {
                "types": "object",
                "properties": {},
                "required": []
            }
        }
        # 解析参数
        for param_name, param in sig.parameters.items():
            # 跳过 self 和 cls
            if param_name in ["self", "cls"]:
                continue
            
            # 获取参数类型
            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation
                if annotation == str:
                    param_type = "string"
                elif annotation == int:
                    param_type = "integer"
                elif annotation == float:
                    param_type = "number"
                elif annotation == bool:
                    param_type = "bollean"
                elif annotation == list:
                    param_type = "array"
                elif annotation == dict:
                    param_type = "object"
                else:
                    # 尝试从字符串注解获取
                    annotation_str = str(annotation).lower()
                    if "str" in annotation_str:
                        param_type = "string"
                    elif "int" in annotation_str:
                        param_type = "integer"
                    elif "float" in annotation_str:
                        param_type = "number"
                    elif "bool" in annotation_str:
                        param_type = "boolean"
                    elif "list" in annotation_str:
                        param_type = "array"
                    elif "dict" in annotation_str:
                        param_type = "object"

            schema["parameters"]["properties"][param_name] = {
                "type": param_type,
                "description:" : f"参数: {param_name}"
            }

            # 检查是否有默认值
            if param.default == inspect.Parameter.empty:
                schema["parameters"]["required"].append(param_name)

        return schema
    
    def _auto_discover(self):
        """自动发现并注册 tools 目录下的工具 - 改进版"""
        # - AST 扫描decorator 标记
        # - 动态导入工具模块
        # - 避免重复注册
        tools_path = Path(__file__).parent / "builtin"

        if not tools_path.exists():
            logger.warning(f"Tools directory not found: {tools_path}")
            return

        # 遍历所有 Python 文件
        for py_file in tools_path.glob("*.py"):
            if py_file.name.startswith("__"):
                continue

            module_name = f"tools.builtin.{py_file.stem}"
            try:
                # 导入模块
                module = importlib.import_module(module_name)
                # 方法1: 查找被 @register 装饰器标记的函数
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # 检查是否是被装饰器标记的工具
                    if self._is_tool_function(attr):
                        # 获取工具名称
                        tool_name = self._get_tool_name(attr, attr_name)

                        # 检查是否已在注册表中
                        if tool_name not in self._tools:
                            # 获取 schema (如果存在)
                            schema = self._get_tool_schema(attr)

                            # 注册工具
                            self.register(tool_name, attr, schema)
                            logger.info(f"Auto-discovered tool: {tool_name}")

                    # 方法2: 查找函数名以 "tool_" 开头的函数(备选)
                    elif callable(attr) and attr_name.startswith("tool_"):
                        tool_name = attr_name
                        if tool_name not in self._tools:
                            self.register(tool_name, attr)
                            logger.info(f"Auto-discovered tool: {tool_name} (by naming convention)")
                
                # 方法3: 检查模块中是否由 TOOLS 列表(显示导出)
                if hasattr(module, "TOOLS"):
                    tools_list = getattr(module, "TOOLS")
                    if isinstance(tools_list, list):
                        for tool_info in tools_list:
                            if isinstance(tool_info, dict):
                                tool_name = tool_info.get("name")
                                tool_func = tool_info.get("func")
                                tool_schema = tool_info.get("schema")
                                if tool_name and tool_func and tool_name not in self._tools:
                                    self.register(tool_name, tool_func, tool_schema)
                                    logger.info(f"Auto-discovered tool: {tool_name} (from TOOLS list)")
            except Exception as e:
                logger.error(f"Failed to load tool {module_name}: {e}")
                # 添加详细的调试信息
                import traceback
                logger.debug(traceback.format_exc())

    def _is_tool_function(self, obj: Any) -> bool:
        """检查对象是否是被标记的工具函数"""
        # 检查是否为函数
        if not callable(obj):
            return False
        
        # 检查是否有 @register 装饰器标记
        if hasattr(obj, "_is_tool"):
            return True
        
        # 检查函数名是否以特定前缀开头(可选)
        if hasattr(obj, "__name__") and obj.__name__.startswith("tool_"):
            return True
        
        return False
    
    def _get_tool_name(self, func: Callable, default_name: str) -> str:
        """获取工具名称"""
        # 如果有自定义名称属性
        if hasattr(func, "_tool_name"):
            return func._tool_name
        
        # 使用函数名
        if hasattr(func, "__name__"):
            return func.__name__
        
        return default_name
    
    def _get_tool_schema(self, func: Callable) -> Optional[Dict]:
        """获取工具的 Schema """
        if hasattr(func, "_tool_schema"):
            return func._tool_schema
        return None
    
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
        # - 添加参数校验
        # - 记录执行日志
        # - 添加结果缓存

        # - 添加执行超时控制
        import asyncio
        try: 
            # 如果是异步函数
            if inspect.iscoroutinefunction(tool):
                result = await asyncio.wait_for(tool(**kwargs), timeout=30)
            else:
                # 同步函数在线程池中执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(tool, **kwargs)
                    result = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(executor, tool, **kwargs),
                        timeout=30
                    )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tool {name} execution timed out")
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {e}")
            raise

    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有工具的统计信息"""
        stats = {}
        for name, tool_info in self._tools.items():
            func = tool_info["func"]
            if hasattr(func, "get_stats"):
                stats[name] = func.get_stats()
            else:
                # 基本统计
                stats[name] = {
                    "name": name,
                    "registered": True,
                    "schema": tool_info["schema"]
                }
        return stats
    
# ==================== 装饰器实现 ====================
def register(name: Optional[str] = None, schema: Optional[Dict] = None):
    """
    工具注册器
    Usage:
        @register(name="my_tool")
        async def my_tool_function(param1: str, param2: int) -> str:
            '''工具描述'''
            return "result"
    Args:
        name: 工具名称(可选, 默认使用函数名)
        schema: 工具 Schema(可选, 自动生成)
    """
    def decorator(func):
        # 标记为工具
        func._is_tool = True
        func._tool_name = name or func.__name__
        func._tool_schema = schema

        # 立即注册(当装饰器被加载时)
        # 但更好的做法时在模块导入时由 Registry 统一处理
        return func
    return decorator

# 便捷注册函数(用户手动注册)
def register_tool(name: str, func: Callable, schema: Optional[Dict] = None):
    """手动注册工具到全局 Registry"""
    registry = ToolRegistry()
    registry.register(name, func, schema)