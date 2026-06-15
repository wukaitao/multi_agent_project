"""
完整集成: 将 Langraph 多智能体系统接入 Hermes
- 路径A: 封装为 Hermes 技能
- 路径B: 统一消息网关
- 路径C: 于一路由替代关键词匹配
"""
import os
import asyncio
import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from pydantic import BaseModel
from contextlib import asynccontextmanager
from llama_index.llms.ollama import Ollama
from agents.specialized.component.approval_agent_humaninloop import handle_delete_kg
from config.settings import SECRET_TOKEN

class SkillRequest(BaseModel):
    """技能请求模型"""
    skill: str
    params: Dict[str, Any] = {}
    context: Dict[str, Any] = {}

# ========== 集成层 ==========
class GatewayApi:
    """
    Gateway API 网关API
    """

    def __init__(self, graph):
        """类初始化"""
        self.graph = graph
        self.action_sessions = {} # 会话管理
        self.app = None

    async def _process_message(self, user: str, query: str, platform: str):
        """异步处理消息"""
        try:

            # 构建状态
            state = {
                "user": user,
                "token": SECRET_TOKEN,
                "query": query
            }

            config = {
                "configurable": {
                    "thread_id":  f"{platform}_{user}"
                }
            }
            result = self.graph.invoke(state, config=config)

            response = result.get("response", "处理完成")

            # 发送回复(根据平台格式)
            await self._send_reply(platform, user, response)
        except Exception as e:
            await self._send_reply(platform, user, f"处理失败: {str(e)}")

    async def _send_reply(self, platform: str, user_id: str, message: str):
        """发送回复到各平台(简化版)"""
        # 这里需要根据各平台API实现
        print(f"***** [{platform}] To {user_id}: {message[:100]} *****")
        # 实际接入需要调用各平台API
    
    def create_gateway_app(self) -> FastAPI:
        """创建统一消息网关的 FastAPI 应用"""
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # 启动时初始化
            print("Hermes 网关已启动")
            yield
            # 关闭时清理
            print("Hermes 网关已关闭")

        app = FastAPI(title="Multi_Agent Hermes Gateway", description="将你的 LangGraph Agent 暴露为 Hermes 技能", lifespan=lifespan)

        # ========== 供 wechat/dingtalk/feishu/telegram 等平台接入 ==========
        # 微信公众号 方式接入
        @app.post("/webhook/{platform}")
        async def platform_webhook(platform: str, request: Request, background_tasks: BackgroundTasks):
            """接收各平台的消息"""
            data = await request.json()

            # 解析不同平台的消息格式
            if platform == "wechat":
                user = data.get("FromUserName", "")
                query = data.get("Content", "")
            elif platform == "dingtalk":
                user = data.get("senderStaffId", "")
                query = data.get("text", {}).get("content", "")
            elif platform == "feishu":
                user = data.get("sender", {}).get("sender_id", {}).get("user_id", "")
                query = data.get("message", {}).get("content", "")
            elif platform == "telegram":
                user = str(data.get("message", {}).get("from", {}).get("id", ""))
                query = data.get("message", {}).get("text", "")
            else:
                user = data.get("user_id", "unknown")
                query = data.get("message", "")

            # 后台处理, 不阻塞
            background_tasks.add_task(self._process_message, user, query, platform)

            # 立即返回(异步处理)
            return {
                "code": 0,
                "msg": "ok"
            }
        
        # ========== 供 Hermes Agent 接入 ==========
        @app.post("/api/skill/{skill_name}")
        async def execute_skill(skill_name: str, request: SkillRequest):
            print(f"========== SKILL NAME 接口 节点 ==========")
            """执行技能端点"""
            result = self.execute_skill(
                skill_name=skill_name,
                params=request.params,
                context=request.context
            )
            return result

        @app.get("/api/skills")
        async def list_skills():
            """列出所有可用技能"""
            return self.get_all_skill_definitions()
            
        @app.get("/health")
        async def health():
            """健康检查"""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat()
            }
        
        self.app = app
        return app