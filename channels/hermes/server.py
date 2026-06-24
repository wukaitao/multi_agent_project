"""
Hermes Agent Server
对外暴露 Skills 供 Hermes Agent 调用
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import uvicorn
import logging
from datetime import datetime
import json

from tools.skills.registry_loader import SkillRegistryLoader
from tools.registry import ToolRegistry
from config.settings import *

logger = logging.getLogger(__name__)

class SkillRequest(BaseModel):
    """Skill 调用请求"""
    skill_name: str = Field(..., description="Skill 名称")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="参数")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="上下文")

class SkillResponse(BaseModel):
    """Skill 调用响应"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class HermesServer:
    """Hermes Agent 服务器"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Hermes Agent Gateway", version="1.0.0")
        self.skill_loader = SkillRegistryLoader()
        self.tool_registry = ToolRegistry()

        self._setup_middleware()
        self._setup_routes()

        logger.info(f"HermesServer initialized on {host}:{port}")

    def _setup_middleware(self):
        """设置中间件"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )

    def _setup_routes(self):
        """设置路由"""

        @self.app.get("/hermes/health")
        async def health_check():
            """健康检查"""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "skills_count": len(self.skill_loader.list_skills())
            }
        
        @self.app.get("/hermes/skillls")
        async def list_skills():
            """列出所有可用的 Skills"""
            skills = self.skill_loader.list_skills()
            return {
                "skills": skills,
                "count": len(skills)
            }
        
        @self.app.get("/hermes/skills/{skill_name}")
        async def get_skill(skill_name: str):
            """获取 Skill 详情"""
            skill = self.skill_loader.get_skill(skill_name)
            if not skill:
                raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")
            return skill
        
        @self.app.post("/hermes/skills/{skill_name}")
        async def execute_skill(
            skill_name: str,
            request: SkillRequest,
            api_key: Optional[str]=Header(None, alias="X-API-Key")
        ):
            """执行Skill"""
            # 认证检查
            if not self._authenticate(api_key):
                raise HTTPException(status_code=401, detail="Invalid API Key")
            
            # 获取 Skill
            skill = self.skill_loader.get_skill(skill_name)
            if not skill:
                raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")
            
            # 执行 SKill

            start_time = datetime.now()
            try:
                # 从注册表获取工具函数
                tool_func = self.tool_registry.get_tool(skill_name)
                if not tool_func:
                    # 尝试从 Skill 加载器执行
                    result = await self.skill_loader.execute_skill(
                        skill_name,
                        request.parameters,
                        request.context
                    )
                else:
                    # 直接执行工具
                    if callable(tool_func):
                        result = await tool_func(**request.parameters)
                    else:
                        result = {"error": "Tool not callable"}

                execution_time = (datetime.now() - start_time).total_seconds()

                return SkillResponse(
                    success=True,
                    result=result,
                    execution_time=execution_time
                )
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.error(f"Skill execution failed: {e}")
                return SkillResponse(
                    success=False,
                    error=str(e),
                    execution_time=execution_time
                )
            
        @self.app.post("/hermes/skills/batch")
        async def execute_skills_batch(
            requests: List[SkillRequest],
            api_key: Optional[str]=Header(None, alias="X-API-Key")
        ):
            """批量执行 Skill"""
            if not self._authenticate(api_key):
                raise HTTPException(status_code=401, detail="Invalid API Key")
            
            results = []
            for req in requests:
                start_time = datetime.now()
                try:
                    result = await self.skill_loader.execute_skill(
                        req.skill_name,
                        req.parameters,
                        req.context
                    )
                    execution_time = (datetime.now() - start_time).total_seconds()
                    results.append({
                        "skill": req.skill_name,
                        "success": True,
                        "result": result,
                        "execution_time": execution_time
                    })
                except Exception as e:
                    execution_time = (datetime.now() - start_time).total_seconds()
                    results.append({
                        "skill": req.skill_name,
                        "success": False,
                        "error": str(e),
                        "execution_time": execution_time
                    })
            return {"results": results}
        
        def _authenticate(self, api_key: Optional[str]) -> bool:
            """认证检查"""
            # TODO: 实现完整的认证逻辑
            # 从配置读取有效的API Key
            valid_keys = 'HERMES_API_KEYS'  # config/settings.py 中读取
            if not valid_keys:
                return True  # 如果没有配置Key, 允许所有请求
            
            return api_key in valid_keys
        
        def run(self):
            """启动服务器"""
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info"
            )
        
        async def run_async(self):
            """异步启动服务器"""
            import asyncio
            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            await server.serve()

def create_hermes_server(host: str="0.0.0.0", port: int=8080) -> HermesServer:
    """创建 Hermes 服务器实例"""
    return HermesServer(host, port)