"""
ChromaDB 数据模型定义
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

@dataclass
class DocumentChunk:
    """文档快"""
    id: str
    text: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] =  field(default_factory=dict)

    # 元数据字段
    source: Optional[str] = None
    source_type: Optional[str] = None  # document, conversation, knownledge_base
    domain: Optional[str] = None  # medical, finance, coding, office
    chunk_index: int = 0
    total_chunks: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转化为字典"""
        return {
            "id": self.id,
            "text": self.text,
            "embedding": self.embedding,
            "metadata": {
                "source": self.source,
                "source_type": self.source_type,
                "domain": self.domain,
                "chunk_index": self.chunk_index,
                "total_chunks": self.total_chunks,
                "creaetd_at": self.created_at,
                **self.metadata
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentChunk":
        """从字典创建"""
        metadata = data.get("metadata", {})
        return cls(
            id=data["id"],
            text=data["text"],
            embeddign=data.get("embedding"),
            source=metadata.get("source"),
            source_type=metadata.get("source_type"),
            domain=metadata.get("domain"),
            chunk_index=metadata.get("chunk_index", 0),
            total_chunks=metadata.get("total_chunks", 1),
            created_at=metadata.get("created_at", datetime.now().isoformat()),
            metadata={k: v for k, v in metadata.items()
                    if k not in ["source", "source_type", "domain", "chunk_index", "total_chunks", "created_at"]}
        )
    
@dataclass
class ConversationMemory:
    """对话记忆"""
    id: str
    session_id: str
    user_id: str
    messages: List[Dict[str, str]]
    summary: Optional[str] = None
    embedding: Optional[List[float]] = None
    domain: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转化为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": json.dumps(self.messages),
            "summary": self.summary,
            "embedding": self.embedding,
            "domain": self.domain,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
@dataclass
class KnowledgeEntry:
    """知识条目"""
    id: str
    title: str
    content: str
    embedding: Optional[List[float]] = None
    domain: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    source: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": {
                "domain": self.domain,
                "category": self.category,
                "tags": self.tags,
                "source": self.source,
                "created_at": self.created_at,
                "updatad_at": self.updated_at
            }
        }
    
# ChromaDB 集合名称
COLLECTIONS = {
    "documents": "agent_documents",
    "conversations": "agent_conversations",
    "knowledge": "agent_knowledge",
    "medical": "medical_knowledge",
    "finance": "finance_knowledge",
    "coding": "coding_knowledge",
    "office": "office_knowledge"
}