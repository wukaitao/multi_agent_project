"""
Skills 动态加载器
扫描并加载所有 Skills
"""

from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import importlib
import inspect
import json
from tools.registry import ToolRegistry
import logging

logger = logging.getLogger(__name__)

class SkillRegistryLoader:
    """Skills 加载器"""

    def __init__(self):
        self.registry = ToolRegistry()
        self.skills_cache: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def load_all_skills(self) -> Dict[str, Dict[str, Any]]:
        """
        加载所有 Skills
        Returns:
            Skills 字典
        """
        if self._loaded:
            return self.skills_cache
        
        skills_dir = Path(__file__).parent

        # 扫描所有 _skills.py 文件
        for skill_file in skills_dir.glob("*_skills.py"):
            try:
                module_name = f"tools.skills.{skill_file.stem}"
                module = importlib.import_module(module_name)

                # 查找模块中的 Skill 函数
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # 检查是否被注册的工具
                    if hasattr(attr, "_is_tool") and attr._is_tool:
                        skill_name = getattr(attr, "_tool_name", attr_name)
                        skill_schema = getattr(attr, "_tool_schema", {})

                        self.skills_cache[skill_name] = {
                            "name": skill_name,
                            "func": attr,
                            "schema": skill_schema,
                            "module": module_name
                        }

                        logger.info(f"Loaded skill: {skill_name}")
            except Exception as e:
                logger.error(f"Failed to load skills from {skill_file}: {e}")

        self._loaded = True
        return self.skills_cache
    
    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取 Skill
        Args:
            name: Skill名称
        Returns:
            Skills列表
        """
        if not self._loaded:
            self.load_all_skills()

        skills_list = []
        for name, skill in self.skills_cache.items():
            skills_list.append({
                "name": name,
                "description": skill["schema"].get("description", ""),
                "parameters": skill["schema"].get("parameters", {}),
                "module": skill.get("module", "")
            })
        
        return skills_list
    
    async def execute_skill(
        self,
        name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        执行 Skill
        Args:
            name: Skill名称
            parameters: 参数
            context: 上下文
        Returns:
            执行结果
        """
        skill = self.get_skill(name)
        if not skill:
            raise ValueError(f"Skill not found: {name}")
        
        func = skill["func"]

        try:
            # 如果函数是异步的
            if inspect.iscoroutinefunction(func):
                result = await func(**parameters)
            else:
                result = func(**parameters)
            return result
        except Exception as e:
            logger.error(f"Skill {name} execution failed: {e}")
            raise

    def reload_skills(self):
        """重新加载 Skills"""
        self.skills_cache.clear()
        self._loaded = False
        self.load_all_skills()
        logger.info("Skills reloaded")

# 单例实例
_loader: Optional[SkillRegistryLoader] = None

def get_skill_loader() -> SkillRegistryLoader:
    """获取 Skills 加载器单例"""
    global _loader
    if _loader is None:
        _loader = SkillRegistryLoader()
    return _loader