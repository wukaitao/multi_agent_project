"""
代码评分器
用户评估代码生成和执行结果
"""

import ast
import subprocess
import tempfile
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import re

import logging

logger = logging.getLogger(__name__)

class CodeGrader:
    """代码质量评分器"""

    def __init__(self):
        self.supported_languages = ["python", "javascript", "java", "go"]

    async def grade(
        self,
        expected: str,
        actual: str,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        评分代码
        Args:
            expected: 期望的代码或要求
            actual: 实际生成的代码
            context: 上下文
        Returns:
            0-1之间的分数
        """
        if not actual:
            return 0.0
        
        language = context.get("language", "python") if context else "python"

        scores = []

        # 1. 语法检查(0-0.3)
        syntax_score = await self._check_syntax(actual, language)
        scores.append(syntax_score * 0.3)

        # 2. 代码风格(0-0.2)
        style_score = await self._check_style(actual, language)
        scores.append(style_score * 0.2)

        # 3. 功能完善性(0-0.3)
        completeness_score = await self._check_completeness(actual, expected, language)
        scores.append(completeness_score * 0.3)

        # 4. 可执行性(0-0.2)
        executable_score = await self._check_executable(actual, language)
        scores.append(executable_score)

        total_score = sum(scores)
        return min(1.0, total_score)
    
    async def _check_syntax(self, code: str, language: str) -> float:
        """检查语法正确性"""
        if language == "python":
            try:
                ast.parse(code)
                return 1.0
            except SyntaxError as e:
                logger.debug(f"Python syntax error: {e}")
                return 0.0
        elif language == "javascript":
            # TODO: 使用 esprima 或其他类似库检查 Javascript 语法
            return 0.5
        else:
            return 0.5

    async def _check_style(self, code: str, language: str) -> float:
        """检查代码风格"""
        score = 1.0
        issues = 0

        # 检查基本的 Python 风格问题
        if language == "python":
            # 检查是否有文档字符串
            if '"""' not in code and "'''" not in code:
                issues += 1
            
            # 检查是否使用了适当的命名规范
            # 类名应该使用驼峰命名
            class_pattern = r"class\s+([a-z]+)"
            if re.search(class_pattern, code, re.IGNORECASE):
                issues += 0.5

            # 检查是否使用了适当的缩进
            if re.search(r"\t", code):
                issues += 0.5

        # 计算得分
        if issues > 0:
            score = max(0, 1.0 -(issues * 0.2))
        
        return score

    async def _check_completeness(self, actual: str, expected: str, language: str) -> float:
        """检查功能完整性"""
        # 如果期望是空, 默认完善
        if not expected:
            return 0.8
        
        # 检查是否包含了期望中的关键词
        expected_keywords = self._extract_keywords(expected)
        actual_keywords = self._extract_keywords(actual)

        if not expected_keywords:
            return 0.8
        
        matched = sum(1 for kw in expected_keywords if kw in actual_keywords)
        ratio = matched / len(expected_keywords)

        return min(1.0, ratio + 0.2)  # 加0.2作为宽容系数

    async def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 移除代码注释
        text = re.sub(r"#.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"/\*.*?\*/", text, flags=re.DOTALL)

        # 提取函数名、类名、变量名
        keywords = re.findall(r"\b[a-zA-Z_][a-zA-Z0_9]{2,}\b", text)
        return list(set(keywords))

    async def _check_executable(self, code: str, language: str) -> float:
        """检查代码是否可执行"""
        if language != "python":
            return 0.5
        
        # 检查是否包含危险操作
        dangerous_patterns = [
            r"os\.system",
            r"subprocess\.",
            r"__import__",
            r"eval\(",
            r"exec\(",
            r"compile\(",
            r"socket\.",
            r"requrest\."
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                logger.warning(f"Detected dangerous pattern: {pattern}")
                return 0.3
            
        # 尝试在沙箱中执行(仅限简单代码)
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_file = f.name

            # 尝试语法检查
            result = subprocess.run(
                ["python", "-m", "py_compile", temp_file],
                capture_output=True,
                timeout=5
            )

            Path(temp_file).unlink()

            if result.returncode == 0:
                return 1.0
            else:
                return 0.5
        except Exception as e:
            logger.debug(f"Execution check failed: {e}")
            return 0.0

    def grade_batch(self, code_list: List[Dict[str, Any]]) -> List[float]:
        """批量评分"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        scores = []
        for item in code_list:
            score = loop.run_until_complete(
                self.grade(
                    item.get("expected", ""),
                    item.get("actual", ""),
                    item.get("context", {})
                )
            )
            scores.append(score)

        loop.close()
        return scores

# 代码质量指标
class CodeMetrics:
    """代码质量指标"""
    
    @staticmethod
    def count_lines(code: str) -> int:
        """统计代码行数"""
        return len([line for line in code.split("\n") if line.strip()])
    
    @staticmethod
    def count_functions(code: str, language: str = "python") -> int:
        """统计函数数量"""
        if language == "python":
            pattern = r"\bdef\s+\w+\s*\("
        elif language == "javascript":
            pattern = r"\bfunction\s+\w+\s*\("
        else:
            pattern = r"\bdef\s+\w+\s*\("
        
        return len(re.findall(pattern, code))
    
    @staticmethod
    def count_classes(code: str, language: str = "python") -> int:
        """统计类数量"""
        if language == "python":
            pattern = r"\bclass\s+\w+\s*[:\(]"
        else:
            pattern = r"\bclass\s+\w+\s*[:\(]"
        
        return len(re.findall(pattern, code))
    
    @staticmethod
    def calculate_complexity(code: str) -> float:
        """计算圈复杂度(简单估算)"""

        # 计算决策点数量
        decision_patterns = [
            r"\bif\b",
            r"\belif\b",
            r"\belse\b",
            r"\bfor\b",
            r"\bwhile\b",
            r"\bcase\b",
            r"\bamd\b",
            r"\bor\b",
            r"\bnot\b"
        ]

        complexity = 1
        for pattern in decision_patterns:
            complexity += len(re.findall(pattern, code))

        return complexity