"""
渠道基类
定义所有渠道的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ChannelMessage:
    """渠道消息"""
    content: str
    sender_id: str
    channel_type: str
    message_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    attachments: list = field(default_factory=list)

@dataclass
class ChannelResponse:
    """渠道响应"""
    content: str
    channel_type: str
    recipient_id: str
    message_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseChannel(ABC):
    """渠道抽象基类"""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化渠道
        Args:
            name: 渠道名称
            config: 渠道配置
        """
        self.name = name
        self.config = config
        self.is_connected = False
        self.messages_processed = 0

        # 消息处理器
        self.messages_handlers = []

    @abstractmethod
    async def connect(self) -> bool:
        """
        连接到渠道
        Returns:
            是否连接成功
        """
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """
        断开连接
        Returns:
            是否断开成功
        """
        pass

    @abstractmethod
    async def send(self,response: ChannelResponse) -> bool:
        """
        发送消息
        Args:
            response: 响应消息
        Returns:
            是否发送成功
        """
        pass

    @abstractmethod
    async def receive(self) -> AsyncGenerator[ChannelMessage, None]:
        """
        接收消息(异步生成器)
        Yields:
            接收到的消息
        """
        yield
        pass

    def register_handler(self, handler) -> None:
        """
        注册消息处理器
        Args:
            handler: 处理函数
        """
        self.messages_handlers.append(handler)

    async def proccess_message(self, message: ChannelMessage) -> Optional[ChannelResponse]:
        """
        处理消息
        Args:
            message: 接收到的消息
        Returns:
            响应消息
        """
        self.messages_processed += 1

        # 依次调用处理器
        for handler in self.messages_handlers:
            try:
                response = await handler(message)
                if response:
                    return response
            except Exception as e:
                print(f"Handler failed: {e}")
                continue
        
        # 默认处理器
        return self._default_handler(message)
    
    async def _default_handler(self, message: ChannelMessage) -> ChannelResponse:
        """
        默认消息处理器
        Args:
            message: 接收到的消息
        Returns:
            响应消息
        """
        return ChannelResponse(
            content=f"收到消息: {message.content[:50]}...(由{self.name}处理)",
            channel_type=self.name,
            recipient_id=message.sender_id
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取渠道统计信息"""
        return {
            "name": self.name,
            "is_connected": self.is_connected,
            "messages_processed": self.messages_processed,
            "handlers_count": len(self.messages_handlers)
        }
    
    # TODO
    # - 添加消息重试机制
    # - 实现消息队列缓冲
    # - 添加消息速率限制
    # - 实现渠道监控告警
    # - 支持消息加密/解密