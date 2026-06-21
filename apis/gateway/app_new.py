from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .routes.v1 import agent, skills, health
from channels.wechat.bot import WeChatBot
from config.settings import *
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logging.info("Starting Agent Gateway...")

    # TODO
    # - 初始化数据连接池
    # - 加载各领域 Agent
    # - 初始化 LLM 客户端
    # - 启动后台任务(清理过期数据等)

    # 启动微信机器人(如配置)
    if "WECHAT_ENABLED":
        wechat_bot = WeChatBot()
        await wechat_bot.start()
        app.state.wechat_bot = wechat_bot

    yield

    # 关闭时清理
    logging.info("Shutting down...")
    # TODO: 关闭连接、保存状态等

app = FastAPI(
    title="AI Agent Gateway",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],  # TODO: 配置具体的允许域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# 注册路由
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])
app.include_router(skills.router, prefix="/api/v1/skills", tags=["skills"])
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])

@app.get("/")
async def root():
    return {"message": "AI Agent Gateway", "version": "1.0.0"}

# TODO
# - 添加 WebSocket 支持(实时对话)
# - 添加请求限制中间件
# - 添加 JWT 认证
# - 添加 OpenTelemetry 追踪