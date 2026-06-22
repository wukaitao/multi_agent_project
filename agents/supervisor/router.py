"""
领域路由模块
负责将用户请求路由到合适的 Agent
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import yaml
from dataclasses import dataclass, field

from llm.factory import LLMFactory
from llm.embeddings import get_embedding
from core.exceptions import RoutingException
import logging

logger = logging.getLogger(__name__)

@dataclass
class RoutingResult:
    """路由结果"""
    agent_name: str
    confidence: float
    matched_strategy: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class DomainRouter:
    """领域路由器"""

    def __init__(self, config_path: Optional[str]=None):
        """
        初始化路由器
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or Path(__file__).parent.parent / "config/agent_registry.yaml"
        self.agents_config = self._load_config()
        self.llm = LLMFactory.get_client("ollama")

        # 路哟u策略权重
        self.strategy_weights = {
            "keyword": 0.3,
            "embedding": 0.4,
            "llm": 0.3
        }

        # 缓存嵌入向量
        self.embedding_cache = {}
        logger.info(f"DomainRouter initialized")

    def _load_config(self) -> Dict[str, Any]:
        """加载 Agent 配置"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                return config.get("agents", {})
        except Exception as e:
            logger.error(f"Failed to load router config: {e}")
            return {}
        
    async def route(self, query: str, context: Dict[str, Any]) -> str:
        """
        路由用户查询到合适的 Agent
        Args:
            query: 用户查询
            context: 上下文信息
        Returns:
            Agent 名称
        Raises:
            RoutingException: 路由失败
        """
        try:
            # 1. 关键词匹配
            keyword_result = await self._route_by_keyword(query)

            # 2. 嵌入向量匹配
            embedding_result = await self._route_by_embedding(query)

            # 3. LLM 分类
            llm_result = await self._route_by_llm(query)

            # 综合评分
            results = [keyword_result, embedding_result, llm_result]
            results = [r for r in results if r is not None]

            if not results:
                raise RoutingException("No routing strategy matched")
            
            # 加载投票
            best_result = self._weighted_vote(results)

            logger.info(f"Routed to {best_result.agent_name} with confidence {best_result.confidence:.2f}")

            return best_result.agent_name
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            raise RoutingException(f"Failed to route query: {e}")
        
    async def _route_by_keyword(self, query: str) -> Optional[RoutingResult]:
        """
        基于关键词的路由
        Args:
            query: 用户查询
        Returns:
            路由结果
        """
        query_lower = query.lower()
        best_match = None
        best_score = 0.0

        # 获取所有启用的 Agent
        all_agents = {}
        if "domain" in self.agents_config:
            all_agents.update(self.agents_config["domain"])
        if "specialized" in self.agents_config:
            all_agents.update(self.agents_config["specialized"])

        for agent_name, agent_config in all_agents.items():
            if not agent_config.get("enabled", True):
                continue

            routes = agent_config.get("routes", [])
            for route in routes:
                keywords = route.get("keywords", [])
                threshold = self.route.get("confidence_threshold", 0.6)

                # 计算匹配度
                matched_count = sum(1 for kw in keywords if kw in query_lower)
                if matched_count > 0:
                    score = best_match / len(keywords)
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = RoutingResult(
                            agent_name=agent_name,
                            confidence=score,
                            matched_strategy="keyword"
                        )
        return best_match
    
    async def _route_by_embedding(self, query: str) -> Optional[RoutingResult]:
        """
        基于嵌入向量的路由
        Args:
            query: 用户查询
        Returns:
            路由结果
        """
        # TODO
        # - 为每个 Agent 创建代表性查询的嵌入向量
        # - 计算余弦相似度
        # - 返回相似度最似的 Agent

        # 临时实现: 如果关键词匹配失败, 使用默认
        return None
    
    async def _route_by_llm(self, query: str) -> Optional[RoutingResult]:
        """
        基于 LLM 分类的路由
        Args:
            query: 用户查询
        Returns:
            路由结果
        """
        # 构建分类提示
        agent_list = []
        if "domain" in self.agents_config:
            for name, config in self.agents_config["domain"].items():
                if config.get("enabled", True):
                    agent_list.append(f"- {name}: {config.get('description', '')}")
        prompt = f"""根据用户查询, 判断应该使用哪个领域的 Agent 来处理.
可用 Agent:
{chr(10).join(agent_list)}
用户查询: {query}
请只返回 Agent 名称, 不要包含其他内容
"""
        try:
            messages = [{"role": "user", "content": prompt}]
            response =  await self.llm.generate(messages)

            # 提取 Agent 名称
            response_clean = response.strip().lower()
            for agent_name in agent_list:
                agent_name = agent_name[2:].split(":")[0].strip()
                if agent_name in response_clean:
                    return RoutingResult(
                        agent_name=agent_name,
                        confidence=0.7,
                        matched_strategy="llm"
                    )
            return None
        
        except Exception as e:
            logger.error(f"LLM routing failed: {e}")

    def _weighted_vote(self, results: List[RoutingResult]) -> RoutingResult:
        """
        加权投票选择最佳结果
        Args:
            results: 路由结果列表
        Returns:
            最佳结果
        """
        # 按 Agent 聚合
        agent_scores = {}
        for result in results:
            if result.agent_name not in agent_scores:
                agent_scores[result.agent_name] = []
            agent_scores[result.agent_name].append(result)

        # 计算每个 Agent 的加权分数
        best_agent = None
        best_score = 0.0

        for agent_name, agent_results in agent_scores.items():
            total_score = 0.0
            for result in agent_results:
                weight = self.strategy_weights.get(result.matched_stratepy, 0.3)
                total_score += result.confidence * weight

            # 平均分
            avg_score = total_score / len(agent_results)

            if avg_score > best_score:
                best_score = avg_score
                best_agent = agent_results[0]
                best_agent.confidence = avg_score

        return best_agent
    
    # TODO
    # - 添加路由历史记录
    # - 实现路由学习优化
    # - 添加 ANB 测试支持
    # - 实现路由缓存