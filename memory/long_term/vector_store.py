"""
ChromaDB 向量存储
用于语义检索和长期记忆
"""

from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions
from config.settings import *
from memory.long_term.schemas.chroma_models_new import DocumentChunk, COLLECTIONS
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class VectorStore:
    """ChromaDB 向量存储"""

    def __init__(self):
        self.persist_dir = str(CHROMA_PATH)
        self.client = None
        self.collections = {}
        self.embedding_function = None
        self._initialized = False

    async def _initialize(self):
        """初始化向量存储"""
        if self._initialized:
            return
        
        try:
            # 创建客户端
            self.client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False)
            )

            # 初始化嵌入函数(使用 Ollama)
            self.embedding_function = embedding_functions.OllamaEmbeddingFunction(
                model_name=EMBED_MODEL,
                url=LLM_BASE_URL
            )

            # 初始化各集合
            for name, collection_name in COLLECTIONS.items():
                try:
                    collection = self.client.get_collection(collection_name)
                except:
                    collection = self.client.create_collection(
                        name=collection_name,
                        embedding_function=self.embedding_function
                    )
                self.collections[name] = collection
            self._initialized = True
            logger.info(f"VectorStore initialized at {self.persist_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize VectorStore: {e}")
            raise
    
    async def close(self):
        """关闭连接"""
        self._initialized = False
        logger.info("VectorStore closed")

    async def add_document(
        self,
        text: str,
        metadata: Optional[Dict]=None,
        collection_name: str="docuemnts"
    ) -> str:
        """添加文档"""
        doc_id = str(uuid.uuid4())
        try:
            collection = self.collections.get(collection_name)
            if not collection:
                raise ValueError(f"Collection not found: {collection_name}")
            
            # 分隔文档为块
            chunks = self._chunk_text(text, chunk_size=500, overlap=100)
            chunk_ids = []
            chunk_metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk{i}"
                chunk_ids.append(chunk_id)

                chunk_metadata = {
                    "document_id": doc_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "created_at": datetime.now().isoformat(),
                    **(metadata or {})
                }
                chunk_metadatas.append(chunk_metadata)

            # 添加到集合
            collection.add(
                documents=chunks,
                ids=chunk_ids,
                metadatas=chunk_metadatas
            )

            logger.debug(f"Added document {doc_id} with {len(chunks)} chunks")
            return doc_id
        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            raise

    async def search(
        self,
        query: str,
        top_k: int=5,
        domain: Optional[str]=None,
        collection_name: str="documents"
    ) -> List[Dict[str, Any]]:
        """搜索文档"""
        try:
            collection = self.collections.get(collection_name)
            if not collection:
                return []
            
            # 构建查询过滤条件
            where_filter = None
            if domain:
                where_filter = {"domain": domain}

            # 执行查询
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter
            )

            # 格式化结果
            documents = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    document = {
                        "id": results["ids"][0][i] if results.get("ids") else "",
                        "text": doc,
                        "score": results["distances"][0][i] if results.get("distances") else 0,
                        "metadata": results["metadata"][0][i] if results.get("metadata") else {}
                    }
                    documents.append(document)

            return documents
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
        
    async def search_by_user(
        self,
        user_id: str,
        query: str,
        top_k: int=5
    ) -> List[Dict[str, Any]]:
        """按用户搜索"""
        try:
            collection = self.collections.get("conversations")
            if not collection:
                return []
            
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
                where={"user_id": user_id}
            )

            return self._format_results(results)
        except Exception as e:
            logger.error(f"User search failed: {e}")
            return []
        
    async def delete_document(self, doc_id: str, collection_name: str="documents") -> bool:
        """删除文档"""
        try:
            collection = self.collections.get(collection_name)
            if not collection:
                return False
            
            # 查找所有属于该文档的块
            results = collection.get(where={"document_id": doc_id})
            if results and results.get("ids"):
                collection.delete(ids=results["ids"])
                logger.debug(f"Deleted document {doc_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False
        
    async def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """获取集合统计信息"""
        try:
            collection = self.collections.get(collection_name)
            if not collection:
                return {}
            
            count = collection.count()
            return {
                "name": collection_name,
                "count": count,
                "embedding_function": str(self.embedding_function)
            }
        except Exception as e:
            logger.error(f"Failed top get stats: {e}")
            return {}
        
    def _chunk_text(self, text: str, chunk_size: int=500, overlap: int=100) -> List[str]:
        """分割文本为块"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start <= len(text):
            end = min(start + chunk_size, len(text))
            # 尝试在句号或换行处分隔
            if end < len(text):
                # 在句号、问好、感叹号或换行处分隔
                for separator in ["。", "！", "？", "\n", ".", "!", "?"]:
                    last_sep = text.rfind(separator, start, end)
                    if last_sep > start + chunk_size * 0.5:
                        end = last_sep + 1
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks
    
    def _format_results(self, results: Dict) -> List[Dict[str, Any]]:
        """格式化搜索结果"""
        documents = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                document = {
                    "id": results["ids"][0][i] if results.get("ids") else "",
                    "text": doc,
                    "score": 1 - results["distances"][0][i] if results.get("distance") else 0,
                    "metadata": results["metadata"][0][i] if results.get("metadata") else {}
                }
                documents.append(document)
        return documents