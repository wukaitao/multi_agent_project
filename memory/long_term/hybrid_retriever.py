"""
混合检索器
结合向量检索和图检索
"""

from typing import List, Dict, Any, Optional, Tuple
from memory.long_term.vector_store import VectorStore
from memory.long_term.graph_store import GraphStore
from memory.long_term.schemas.chroma_models_new import DocumentChunk
from memory.long_term.schemas.neo4j_models_new import Node, RelationshipTypes
import logging

logger = logging.getLogger(__name__)

class HybridRetriever:
    """混合检索器"""

    def __init__(self):
        self.vector_store = VectorStore()
        self.graph_store = GraphStore()
        self._initialized = False

    async def initialize(self):
        """初始化所有存储"""
        if self._initialized:
            return
        await self.vector_store.initialize()
        await self.graph_store.initialize()
        self._initialized = True
        logger.info("HybridRetriever initialized")

    async def retrieve(
        self,
        query: str,
        top_k: int=5,
        domain: Optional[str]=None,
        use_graph: bool=True,
        use_vector: bool=True
    ) -> List[Dict[str, Any]]:
        """
        混合检索
        Args:
            query: 查询文本
            top_k: 返回结果数量
            domain: 领域过滤
            use_graph: 是否使用图检索
            use_vector: 是否使用向量检索
        Returns:
            检索结果列表
        """
        results = []
        scores = []

        # 向量检索
        if use_vector:
            vector_results = await self._vector_retrieve(query, top_k, domain)
            for item in vector_results:
                item_id = item.get("id", "")
                scores[item_id] = scores.get(item_id, 0) + item.get("score", 0) * 0.6
                results.append(item)

        # 图检索
        if use_graph:
            graph_results = await self._graph_retrieve(query, domain)
            for item in graph_results:
                item_id = item.get("id", "")
                scores[item_id] = scores.get(item_id, 0) + item.get("score", 0) * 0.4
                results.append(item)

        # 去重和排序
        unique_results = {}
        for item in results:
            item_id = item.get("id", "")
            if item_id not in unique_results:
                unique_results[item_id] = item
                unique_results[item_id]["score"] = scores.get(item_id, 0)
            else:
                # 合并属性
                if "metadata" not in unique_results[item_id]:
                    unique_results[item_id]["metadata"] = {}
                unique_results[item_id]["metadata"].update(item.get("metadata", {}))

        # 按分数排序
        sorted_results = sorted(
            unique_results.values(),
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        return sorted_results[:top_k]
    
    async def _vector_retrieve(self, query: str, top_k: int, domain: Optional[str]=None) -> List[Dict]:
        """向量检索"""
        try:
            results = await self.vector_store.search(query, top_k, domain)
            return [
                {
                    "id": r.get("id"),
                    "text": r.get("text", ""),
                    "score": r.get("score", 0),
                    "metadata": r.get("metadata", {})
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Vector retrieval failed: {e}")
            return []
        
    async def _graph_retrieve(self, query: str, domain: Optional[str]=None) -> List[Dict]:
        """图检索"""
        try:
            # 从查询中提取实体
            entities = await self._extract_entities(query)
            results = []

            for entity in entities:
                # 查找相关节点
                nodes = await self.graph_store.query_nodes(
                    label=entity.get("label", "Concept"),
                    filters={"name": entity.get("name", "")}
                )

                for node in nodes:
                    # 获取邻居
                    neighbors = await self.graph_store.get_neighbors(
                        node.get("id"),
                        relationship_type=RelationshipTypes.RELATES_TO
                    )
                    results.append({
                        "id": node.get("id"),
                        "text": node.get("properties", {}).get("name", ""),
                        "score": 0.7,
                        "metadata": {
                            "type": "graph",
                            "node": node,
                            "neighbors": neighbors,
                        }
                    })
            return results
        except Exception as e:
            logger.error(f"Graph retrieval failed: {e}")
            return []
        
    async def _extract_entities(self, query: str) -> List[Dict[str, str]]:
        """从查询中提取实体"""
        # TODO: 使用 NER 模型提取实体
        # 简单的关键词提取
        entities = []
        keywords = ["医疗", "金融", "编程", "办公", "疾病", "药品", "股票", "代码"]

        for keyword in keywords:
            if keyword in query:
                entities.append({
                    "name": keyword,
                    "label": "Concept"
                })
        return entities
    
    async def retrieve_with_context(
        self,
        query: str,
        context: Dict[str, Any],
        top_k: int=5
    ) -> List[Dict[str, Any]]:
        """
        带上下文的检索
        """
        # 从上下文中提取领域信息
        domain = context.get("domain")
        user_id = context.get("user_id")

        # 检索历史对话
        history = await self.vector_store.search_by_user(
            user_id=user_id,
            query=query,
            top_k=3
        )

        # 检索知识库
        knowledge = await self.retrieve(query, top_k, domain)

        return {
            "history": history,
            "knowledge": knowledge
        }