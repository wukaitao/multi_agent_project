"""
LLM 评分器
使用大语言模型评估 Agent 响应质量
"""

from typing import Dict, Any, Optional, List
import json
from llm.factory import LLMFactory
import logging

logger = logging.getLogger(__name__)

class LLMGrader:
    """基于 LLM 的评分器"""

    def __init__(self, model_name: Optional[str] = None):
        self.llm = LLMFactory.get_client("ollama")
        self.model_name = model_name or "qwen2.5:7b"

    async def grade(
        self,
        expected: str,
        actual: str,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        使用 LLM 评分
        Args:
            expected: 期望输出
            actual: 实际输出
            context: 上下文信息
        Returns:
            0-1之间的分数
        """
        if not actual:
            return 0.0
        
        # 构建评分提示词
        prompt = self._build_grader_prompt(expected, actual, context)

        try:
            response = await self.llm.generate([
                {"role": "system", "content": "你是一个严格但公正的评分器."},
                {"role": "user", "content": prompt}
            ])

            # 解析分数
            score = self._parse_score(response)
            return score
        
        except Exception as e:
            logger.error(f"LLM grading failed: {e}")
            return 0.5  # 默认分数
        
    def _build_grader_prompt(
        self,
        expected: str,
        actual: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """构建评分提示词"""
        prompt = """
请对以下回答进行评分(0-1分):

**期望的答案**:
{expected}

**实际的答案**:
{actual}

**评分维度**:
1. 准确性(0.3): 回答是否准确、正确
2. 完整性(0.25): 是否完整回答了问题
3. 相关性(0.2): 是否与问题相关
4. 清晰度(0.15): 表达是否清晰
5. 专业性(0.1): 是否专业、规范

请给出总分(0-1之间的浮点数), 并简要说明理由.

输出格式(JSON):
{{
    "score": 0.85,
    "reason": "回答准确完整, 表达清洗, 但缺少部分细节"
}}
"""
        if context:
            prompt += f"""\n**上下文信息**:\n{json.dumps(context, ensure_ascii=False, indent=2)}"""
            
        return prompt
        
    def _parse_score(self, response: str) -> float:
        """解析评分结果"""
        try:
            # 尝试提取 JSON
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                score = float(data.get("score", 0.5))
                return max(0.0, min(1.0, score))
            
            # 尝试提取数据
            import re
            numbers = re.findall(f"0\.\d+|1\.0[01]", response)
            if numbers:
                score = float(numbers[0])
                return max(0.0, min(1.0, score))
            
            return 0.5
        except Exception as e:
            logger.debug(f"Failed to parse score: {e}")
            return 0.5
        
    async def grade_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> List[float]:
        """批量评分"""
        import asyncio

        tasks = [
            self.grade(
                item.get("expected", ""),
                item.get("actual", ""),
                item.get("context", {})
            )
            for item in items
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        scores = []
        for result in results:
            if isinstance(result, Exception):
                scores.append(0.5)
            else:
                scores.append(result)
            
        return scores
    
class MultiDimensionGrader:
    """多维度 LLM 评分器"""

    DIMENSIONS = {
        "accuracy": "回答是否准确",
        "completeness": "是否完整覆盖问题",
        "relevance": "回答是否切题",
        "clarity": "表达是否清晰",
        "professionalism": "是否专业",
        "conciseness": "是否简介",
        "helpfulness": "是否有帮助"
    }

    def __init__(self):
        self.llm = LLMFactory.get_client("ollama")

    async def grade(
        self,
        expected: str,
        actual: str,
        context: Optional[Dict[str, Any]] = None,
        dimensions: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        多维度评分
        Args:
            expected: 期望输出
            actual: 实际输出
            context: 上下文
            dimensions: 评分维度列表
        Returns:
            各维度分数
        """
        if not actual:
            return {dim: 0.0 for dim in (dimensions or list(self.DIMENSIONS.keys()))}
        
        dimensions = dimensions or list(self.DIMENSIONS.keys())

        prompt = self._build_multi_dimension_prompt(expected, actual, context, dimensions)

        try:
            response = await self.llm.generate([
                {"role": "system", "content": "你是专业的评分专家"},
                {"role": "user", "content": prompt}
            ])

            scores = self._parse_dimension_scores(response, dimensions)
            return scores
        except Exception as e:
            logger.error(f"Multi-dimension grading failed: {e}")
            return {dim: 0.5 for dim in dimensions}
        
    def _build_multi_dimension_prompt(
        self,
        expected: str,
        actual: str,
        context: Optional[Dict[str, Any]],
        dimensions: List[str]
    ) -> str:
        """构建多为对评分提示词"""
        dim_descriptions = "\n".join([
            f"- {dim}: {self.DIMENSIONS.get(dim, '未定义')}" for dim in dimensions
        ])

        prompt = f"""
请对以下回答进行多维度评分:

**期望的回答**:
{expected}

**实际的回答**:
{actual}

**评分维度**:
{dim_descriptions}

请为每个维度给出0-1之间的分数.

输出格式(JSON):
{{
    {', '.join([f'"dim": 0.0' for dim in dimensions])},
    "overall": 0.0,
    "reason": "评分理由"
}}
"""
        if context:
            prompt += f"\n**上下文信息**:\n{json.dumps(context, ensure_ascii=False, indent=2)}"

        return prompt
    
    def _parse_dimension_scores(
        self,
        response: str,
        dimensions: List[str]
    ) -> Dict[str, float]:
        """解析多维度评分"""
        scores = {dim: 0.5 for dim in dimensions}

        try:
            json_start = response.find("{")
            json_end =  response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                for dim in dimensions:
                    if dim in data:
                        scores[dim] = max(0.0, min(1.0, float(data[dim])))
        except Exception as e:
            logger.debug(f"Failed to parse dimension score: {e}")
        
        return scores