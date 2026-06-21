import aiohttp
import asyncio
from typing import List, Optional, AsyncGenerator
from ..base import BaseLLM, Message
from config.settings import LLM_BASE_URL, LLM_MODEL, EMBED_MODEL

class OllamaClient(BaseLLM):
    """Ollama 本地模型客户端"""
    def __init__(self):
        self.base_url = LLM_BASE_URL
        self.model = LLM_MODEL
        self.embed_model = EMBED_MODEL
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def generate(self, messages: List[Message], **kwargs) -> str:
        """调用 Ollama 生成响应"""
        session = await self._get_session()
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "temperature": kwargs.get("temperature", ""),
            "max_tokens": kwargs.get("max_tokens", ""),
            "top_p": kwargs.get("top_p", "")
        }

        # TODO
        # - 添加重试机制(指数退避, 最多3次)
        # - 添加超时控制(默认60秒)
        # - 添加请求/响应日志记录
        # - 添加 Token 使用量统计
        # - 处理模型未加载时的自动加载逻辑

        async with session.post(
            f"{self.base_url}/api/chat",
            json=payload
        ) as resp:
            result = await resp.json()
            return result.get("message", {}).get("content", "")
        
    async def stream(self, messages: List[Message], **kwargs) -> AsyncGenerator[str, None]:
        """流式生成"""
        session = await self._get_session()
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "temperature": kwargs.get("temperature", "")
        }

        async with session.post(
            f"{self.base_url}/api/chat",
            json=payload
        ) as resp:
            async for line in resp.content:
                if line:
                    # TODO: 解析 SSE 格式的响应流
                    pass
                yield line.decode()

    async def embed(self, text: str) -> List['float']:
        """生成文本嵌入向量"""
        session = await self._get_session()
        payload = {
            "model": self.embed_model,
            "prompt": text
        }

        # TODO
        # - 批量嵌入优化(一次处理多个文本)
        # - 嵌入结果缓存(避免重复计算)
        # - 异步批量处理机制

        async with session.post(
            f"{self.base_url}/api/embedding",
            json=payload
        ) as resp:
            result = await resp.json()
            return result.get("embedding", [])
        
    async def close(self):
        """关闭"""
        if self._session:
            await self._session.close()