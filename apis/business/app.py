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

class ChatRequest(BaseModel):
    user: str
    query: str
    thread_id: str = "default"
    from_skill: str = None

# ========== 集成层 ==========
class BusinessApi:
    """
    Agent 业务API
    """

    def __init__(self, graph):
        """类初始化"""
        self.graph = graph
        self.action_sessions = {} # 会话管理
        self.app = None

    async def _process_message_sync(self, user: str, query: str, thread_id: str = "default_id", from_skill: str = None) -> Dict:
        """同步处理消息(用于API)"""
        try:

            skill_def = self.get_skill_definition(from_skill)
            if skill_def:
                route = skill_def.get("route", "chat")
            else:
                route = "chat"
            
            state = {
                "user": user,
                "token": SECRET_TOKEN,
                "query": query,
                "from_skill": from_skill,
                "route": route
            }
            print(f"***** from_skill: {state['from_skill']} *****\n***** route: {state['route']} *****")

            config = {
                "configurable": {
                    "thread_id":  f"{thread_id}"
                }
            }
            result = self.graph.invoke(state, config=config)

            return {
                "success": True,
                "response": result.get("response", ""),
                "route": result.get("route", "chat")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # ========== FastAPI (可供 LangGraph 或 外部网关调用[跨域]) ==========
    def create_fastapi_app(self) -> FastAPI:
        """ 创建后端 FastAPI 接口: 可被 LangGraph 或外部网关调用[跨域] """
        app = FastAPI(title="Multi_Agent API", description="创建后端 FastAPI 接口")

        @app.post("/api/chat")
        async def chat_endpoint(request: ChatRequest):
            """供 Hermes 调用的 API 端点"""
            print(f"========== 业务 API 接口 节点 ==========")
            user = request.user
            query = request.query
            thread_id = request.thread_id
            from_skill = request.from_skill
            result = await self._process_message_sync(user, query, thread_id, from_skill)
            print(f"***** result: {result} *****")
            return {
                "response": result.get("response", ""),
                "image": result.get("image")
            }
        
        @app.get("/health")
        async def health():
            """健康检查"""
            return {
                "status": "ok"
            }
        
        self.app = app
        return app