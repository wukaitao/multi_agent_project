"""
Redis 短期储存
用户会话管理和缓存
"""

from typing import Optional, Dict, List, Any
import redis.asyncio as redis
import json
from datetime import datetime
from config.settings import *
import logging

logger = logging.getLogger(__name__)

class RedisStore:
    """Redis 存储"""

    def __init__(self, url: Optional[str]=None):
        self.url = url or REDIS_URL
        self.client: Optional[redis.Redis] = None
        self._initialized = False

        # 默认过期时间
        self.default_ttl = 3600  # 1小时
        self.session_ttl = 86400  # 2小时
        self.cache_ttl = 300  # 5分钟

    async def initialize(self):
        """初始化 Redis 连接"""
        if self._initialized:
            return
        
        try:
            self.client = redis.from_url(self.url, decode_response=True)
            await self.client.ping()
            self._initialized = True
            logger.info(f"RedisStore connected to {self.url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close(self):
        """关闭连接"""
        if self.client:
            await self.client.close()
            self._initialized = False
            logger.info(f"RedisStore closed")

    async def set(self, key: str, value: Any, ttl: Optional[int]=None) -> bool:
        """设置键值"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            
            if ttl:
                await self.client.setex(key, ttl, value)
            else:
                await self.client.set(key, value)
            
            return True
        except Exception as e:
            logger.error(f"Failed to set {key}: {e}")
            return False
        
    async def get(self, key: str) -> Optional[Any]:
        """获取键值"""
        try:
            value = await self.client.get(key)
            if value:
                try:
                    return json.loads(value)
                except:
                    return value
            return None
        except Exception as e:
            logger.error(f"Failed to get {key}: {e}")
            return None
        
    async def delete(self, key: str) -> bool:
        """删除键"""
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete {key}: {e}")
            return False
        
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Failed to check {key}: {e}")
            return False
        
    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        try:
            return await self.client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Failed to set expire for {key}: {e}")
            return False
        
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """设置哈希字段"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            await self.client.hset(key, field, value)
            return True
        except Exception as e:
            logger.error(f"Failed to hset {key}.{field}: {e}")
            return False
        
    async def hget(self, key: str, field: str) -> Optional[Any]:
        """获取哈希字段"""
        try:
            value = await self.client.hget(key, field)
            if value:
                try:
                    return json.loads(value)
                except:
                    return value
            return None
        except Exception as e:
            logger.error(f"Failed to hget {key}.{field}: {e}")
            return None
        
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """获取所有哈希字段"""
        try:
            data = await self.client.hgetall(key)
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except:
                    result[k] = v
            return result
        except Exception as e:
            logger.error(f"Failed to hgetall {key}: {e}")
            return {}
    
    async def set_session(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """设置会话数据"""
        ttl = ttl or self.session_ttl
        return await self.set(f"session:{session_id}", data, ttl)
    
    async def get_session(self, seesion_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据""" 
        return await self.get(f"session:{seesion_id}")
    
    async def set_cache(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存"""
        ttl = ttl or self.cache_ttl
        return await self.set(f"cache:{key}", data, ttl)
    
    async def get_cache(self, key: str) -> Optional[Any]:
        """获取缓存"""
        return await self.get(f"cache:{key}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            info = await self.client.info()
            return {
                "connected": self._initialized,
                "used_memory": info.get("used_memory_human", "unknown"),
                "total_connections": info.get("total_connections_received", 0),
                "uptime": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"connected": self._initialized}