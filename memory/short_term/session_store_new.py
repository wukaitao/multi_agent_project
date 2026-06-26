"""
会话存储
管理用户的会话状态
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid
from memory.short_term.redis_store import RedisStore
import logging

logger = logging.getLogger(__name__)

class SessionStore:
    """会话管理器"""

    def __init__(self):
        self.redis_store = RedisStore()
        self._initialized = False

    async def initialize(self):
        """初始化"""
        if self._initialized:
            return
        await self.redis_store.initialize()
        self._initialized = True
        logger.info("SessionStore initialized")

    async def close(self):
        """关闭"""
        await self.redis_store.close()
        self._initialized = False

    async def create_session(
        self,
        user_id: str,
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建会话"""
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "messages": [],
            "context": data or {},
            "expires_at": (datetime.now() + timedelta(hours=24)).isoformat()
        }

        await self.redis_store.set_session(session_id, session_data)
        logger.info(f"Session created: {session_id} for {user_id}")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        session = await self.redis_store.get_session(session_id)
        if session:
            # 更新最后活动时间:
            session["last_activity"] = datetime.now().isoformat()
            await self.redis_store.set_session(session_id, session)
        return session
    
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """更新会话"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.update(data)
        session["last_activity"] = datetime.now().isoformat()
        return await self.redis_store.set_session(session_id, session)
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        return await self.redis_store.delete(f"session:{session_id}")
    
    async def add_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """添加消息会话"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        if "messages" not in session:
            session["messages"] = []
        
        message["timestamp"] = datetime.now().isoformat()
        session["messages"].append(message)

        # 限制消息数量
        if len(session["messages"]) > 50:
            session["messages"] = session["messages"][-50:]
        
        session["last_activity"] = datetime.now().isoformat()
        return await self.redis_store.get_session(session_id, session)
    
    async def get_messages(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取会话消息"""
        session = await self.get_session(session_id)
        if not session:
            return []
        
        messages = session.get("messages", [])
        return messages[-limit:] if limit > 0 else messages
    
    async def set_context(self, session_id: str, context: Dict[str, Any]) -> bool:
        """设置会话上下文"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session["context"].update(context)
        session["last_activity"] = datetime.now().isoformat()
        return await self.redis_store.set_session(session_id, session)
    
    async def get_context(self, session_id: str) -> Dict[str, Any]:
        """获取会话上下文"""
        session = await self.get_session(session_id)
        if not session:
            return {}
        return session.get("context", {})
    
    async def list_user_sessions(self, user_id: str) -> List[str]:
        """列出用户的所有会话"""
        # TODO: 实现用户会话索引
        return []