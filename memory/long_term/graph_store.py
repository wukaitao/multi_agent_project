"""
Neo4j 图数据库存储
用户管理知识图谱和关系数据
"""

from typing import List, Dict, Any, Optional, Tuple
from neo4j import AsyncGraphDatabase, Driver, Record
from config.settings import *
from memory.long_term.schemas.neo4j_models_new import Node, Relationship, NodeLabels, RelationshipTypes
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class GraphStore:
    """Neo4j 图存储"""
    
    def __init__(self):
        self.uri = NEO4J_URI
        self.user = NEO4J_USER
        self.password = NEO4J_PASSWORD
        self.driver: Optional[Driver] = None
        self._initialized = False

    async def initialize(self):
        """初始化数据库连接"""
        if self._initialized:
            return
        
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # 验证连接
            async with self.driver.session() as session:
                await session.run("RETURN 1")
                self._initialized = True
                logger.info(f"GraphStore connected to {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        """关闭连接"""
        if self.driver:
            await self.driver.close()
            self._initialized = False
            logger.info(f"Graphstore closed")
    
    async def create_node(self, node: Node) -> bool:
        """创建节点"""
        try:
            async with self.driver.session() as session:
                query = node.to_cypher_create()
                params = {**node.properties, "id": node.id, "created_at": node.created_at}
                await session.run(query, **params)
                logger.debug(f"Node created: {node.id}")
                return True
        except Exception as e:
            logger.error(f"Failed to create node: {e}")
            return False
        
    async def create_nodes_batch(self, nodes: List[Node]) -> int:
        """批量创建节点"""
        created = 0
        async with self.driver.session() as session:
            async with session.begin_transaction() as tx:
                for node in nodes:
                    try:
                        query = node.to_cypher_create()
                        params = {**node.properties, "id": node.id, "created_at": node.created_at}
                        await tx.run(query, **params)
                        created += 1
                    except Exception as e:
                        logger.error(f"Failed to create node {node.id}: {e}")
                        await tx.rollback()
                        return created
                await tx.commit()
        logger.info(f"Batch created {created} nodes")
        return created
    
    async def create_relationship(self, rel: Relationship) -> bool:
        """创建关系"""
        try:
            async with self.driver.session() as session:
                query = rel.to_cypher_create()
                params = {
                    "source_id": rel.source_id,
                    "target_id": rel.target_id,
                    "id": rel.id,
                    **rel.properties,
                    "created_at": rel.created_at
                }
                await session.run(query, **params)
                logger.debug(f"Relationship created: {rel.id}")
                return True
        except Exception as e:
            logger.debug(f"Failed top create relationship: {e}")
            return False
        
    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点"""
        try:
            async with self.driver.session() as session:
                result = await session.run(
                    "MATCH (n {id: $id}) RETURN n",
                    id=node_id
                )
                record = await result.single()
                if record:
                    node_data = record["n"]
                    return {
                        "id": node_data.get("id"),
                        "label": list(node_data.labels)[0] if node_data.labels else None,
                        "properties": dict(node_data.items())
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get node: {e}")
            return None
    
    async def query_nodes(self, label: str, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """查询节点"""
        try:
            async with self.driver.session() as session:
                query = f"MATCH (n:{label})"
                params = {}
                
                if filters:
                    conditions = []
                    for key, value in filters.items():
                        conditions.append(f"n.{key} = ${key}")
                        params[key] = value
                    query += " WHERE " + " AND ".join(conditions)

                query += " RETURN n"

                result = await session.run(query, **params)
                records = await result.data()
                
                return [
                    {
                        "id": record.get("n").get("id"),
                        "label": list(record["n"].labels)[0] if record["n"].labels else None,
                        "properties": dict(record["n"].items())
                    }
                    for record in records
                ]
        except Exception as e:
            logger.error(f"Failed to query nodes: {e}")
            return []
    
    async def delete_node(self, node_id: str, cascade: bool = False) -> bool:
        """删除节点"""
        try:
            async with self.driver.session() as session:
                if cascade:
                    # 级联删除: 删除所有相关关系
                    await session.run(
                        "MATCH (n {id: $id}) DETACH DELETE n",
                        id=node_id
                    )
                else:
                    await session.run(
                        "MATCH (n {id: $id}) DELETE n",
                        id=node_id
                    )
                logger.debug(f"Node deleted: {node_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete node: {e}")
            return False
    
    async def find_path(self, source_id: str, target_id: str, max_depth: int = 5) -> List[Dict]:
        """查询两个节点之间的路径"""
        try:
            async with self.driver.session() as session:
                result = await session.run(
                    """
                    MATCH path = shortestPath(a {id: $source})-[*..$max_depth]-(b {id: $target})
                    RETURN path
                    """
                    source=source_id,
                    target=target_id,
                    max_depth=max_depth
                )
                records = await result.data()
                return records
        except Exception as e:
            logger.error(f"Failed to find path: {e}")
            return []
    async def get_neighbors(self, node_id: str, relationship_type: Optional[str] = None) -> List[Dict]:
        """获取节点的邻居"""
        try:
            async with self.driver.session() as session:
                query = "MATCH (n {id: $id})"
                if relationship_type:
                    query += f"-[r:{relationship_type}]-(neighbor)"
                else:
                    query += f"-[r]-(neighbor)"
                query += " RETURN neighbor, type(r) as relationship_type"

                result = await session.run(query, id=node_id)
                records = await result.data()

                return [
                    {
                        "node": dict(record["neighbor"].items()),
                        "relationship_type": record.get("relationship_type")
                    }
                    for record in records
                ]
        except Exception as e:
            logger.error(f"Failed to get neighbors: {e}")
            return []
        
    async def get_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        try:
            async with self.driver.session() as session:
                # 节点统计
                result = await session.run("MATCH (n) RETRUN count(n) as count, labels(n) as labels")
                node_stats = await result.data()

                # 关系统计
                result = await session.run("MATCH ()-[r]->() RETURN count(n) as count, type(r) as types")
                rel_stats = await result.data()

                return {
                    "ndoes": node_stats,
                    "relationships": rel_stats
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}