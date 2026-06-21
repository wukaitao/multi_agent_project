"""
嵌入模型客户端
使用 Ollama 进行文本嵌入
"""
from typing import List, Optional, Union
import asyncio
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import aiohttp
import numpy as np
from config.settings import *
import logging

logger = logging.getLogger(__name__)

class OllamaEmbeddings:
    """Ollama 嵌入模型客户端"""

    def __init__(
        self,
        model_name: Optional[str]=None,
        base_url: Optional[str]=None,
        cache_enabled: bool=True,
        cache_size: int=1000,
        batch_size: int=10
    ):
        """
        初始化嵌入客户端
        Args:
            model_name: 模型名称, 默认使用配置
            base_url: Ollama 基础 URL, 默认使用配置
            cache_enabled: 是否启用缓存
            cache_size: 缓存大小
            batch_size: 批量处理大小
        """
        self.model_name = model_name
        self.base_url = base_url
        self.cache_enabled = cache_enabled
        self.batch_size = batch_size

        self._session: Optional[aiohttp.ClientSession]=None
        self._cache = {}
        self._cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0

        logger.info(f"Initialized OllamaEmbeddings with model: {self.model_name}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    
    async def embed(self, text: str) -> List[float]:
        """
        生成单个文本的嵌入向量

        Args:
            text: 输入文本
        Returns:
            嵌入向量列表
        """
        # 检查缓存
        if self.cache_enabled:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                self._cache_hits += 1
                logger.debug(f"Cache hit for text: {text[:50]}...")
                return self._cache[cache_key]
            self._cache_misses += 1

        # 调用 API
        session = await self._get_session()
        payload = {
            "model": self.model_name,
            "prompt": text
        }
        try:
            async with session.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error: {response.status} - {error_text}")
                
                result = await response.json()
                embedding = result.get("embedding", {})

                # 缓存结果
                if self.cache_enabled:
                    self._add_to_cache(cache_key, embedding)
                
                return embedding
        except asyncio.TimeoutError:
            raise TimeoutError(f"Embedding request timed out for text: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed top get embeddings: {e}")
            raise

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成嵌入向量
        Args:
            texts: 文本列表
        Returns:
            嵌入向量列表
        """
        # 分批处理
        results = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_results = await asyncio.gather(
                *[self.embed(text) for text in batch],
                return_exceptions = True
            )

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch embedding failed: {result}")
                    # 返回零向量作为占位
                    results.append([0.0] * 768)  # 默认维度
                else:
                    results.append(result)
            
        return results
    
    def _add_to_cache(self, key: str, embedding: List[float]):
        """添加到缓存, 维护缓存大小"""
        if len(self._cache) >= self._cache_size:
            # 移除最找的条目
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[key] = embedding

    def get_cache_starts(self) -> dict:
        """获取缓存统计信息"""
        return {
            "cache_size": len(self._cache),
            "max_cache_size": self._cache_size,
            "hits": self._cache_hits,
            "misses": self._cache_hits,
            "hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info(f"Embedding cache cleared")

    async def close(self):
        """关闭会话"""
        if self._session:
            await self._session.close()

    # TODO
    # - 支持多种嵌入模型切换
    # - 添加嵌入向量归一化
    # - 支持维度压缩
    # - 实现持久化缓存(Redis / 磁盘)

# 便捷函数
_embedding_client: Optional[OllamaEmbeddings] = None

def get_embedding_client() -> OllamaEmbeddings:
    """获取单例嵌入客户端"""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OllamaEmbeddings()
    return _embedding_client

async def get_embedding(text: str) -> List[str]:
    """便捷函数: 获取单个文件的嵌入"""
    client = get_embedding_client()
    return await client.embed(text)

async def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """便捷函数: 批量获取嵌入"""
    client = get_embedding_client()
    return await client.embed_batch(texts)