"""
Neo4j 图数据库模型定义
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Node:
    """图节点"""
    id: str
    label: str  # Person, Organization, Cancept, Document, etc.
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_cypher_create(self) -> str:
        """生成 Cypher 创建语句"""
        props = {**self.properties, "id": self.id, "created_at": self.created_at}
        props_str = ", ".join([f"{k}: ${k}" for k in props.keys()])
        return f"CREATE (n:(self.label)) {{props_str}}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "label": self.label,
            "properties": self.properties,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
@dataclass
class Relationship:
    """图关系"""
    id: str
    source_id: str
    target_id: str
    type: str  # KNOWS, BELONGS_TO, REFERENCES, etc.
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_cypher_create(self) -> str:
        """生成 Cypher 创建语句"""
        props = {**self.properties, "id": self.id, "created_at": self.created_at}
        props_str = ", ".join([f"{k}: ${k}" for k in props.keys()]) if props else ""

        if props_str:
            return f"MATCH (a {{id: $source_id}}), (b {{id: $target_id}}) CREATE (a)-[r:{self.type} {{{props_str}}}]->(b)"
        else:
            return f"MATCH (a {{id: $source_id}}), (b {{id: $target_id}}) CREATE (a)-[r:{self.type}]->(b)"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type,
            "properties": self.properties,
            "created_at": self.created_at
        }
    
# 节点标签定义
class NodeLabels:
    PERSON = "Person"
    ORGANIZATION = "Organization"
    CONCEPT = "Concept"
    DOCUMENT = "Document"
    TASK = "Task"
    PROJECT = "Project"
    KNOWLEDGE = "Knowledge"
    AGENT = "Agent"
    USER = "User"
    SESSION = "Session"
    DOMAIN = "Domain"  # medical, finance, coding, office

# 关系类型定义
class RelationshipTypes:
    KNOWS = "KNOWS"
    BELONGS_TO = "BELONGS_TO"
    REFERENCES = "REFERENCES"
    CREATED_BY = "CREATED_BY"
    MIDIFIED_BY = "MODIFIED_BY"
    HAS_SESSION = "HAS_SESSION"
    HAS_TASK = "HAS_TASK"
    RELATES_TO = "RELATES_TO"
    CATEGORIZED_AS = "CATEGORIZED_AS"
    DEPENDS_ON = "DEPENDS_ON"
    FOLLOWS = "FOLLOWS"
    IMPLEMENTS = "IMPLEMENTS"

# 示例数据
EXAMPLE_NODES = {
    "user": Node(
        id:="user_001",
        label=NodeLabels.USER,
        properties={"name": "张三", "email": "zhangsan@example.com", "role": "developer"}
    ),
    "domain_medical": Node(
        id="domain_medical",
        label=NodeLabels.DOMAIN,
        properties={"name": "Medical", "description": "医疗领域"}
    ),
    "concept_disease": Node(
        id="concept_disease",
        label=NodeLabels.CONCEPT,
        properties={"name": "疾病", "category": "health"}
    )
}

EXAMPLE_RELATIONSHIPS = {
    Relationship(
        id="rel_001",
        source_id="user_001",
        target_id="domain_medical",
        type=RelationshipTypes.BELONGS_TO,
        properties={"level": "expert"}
    )
}