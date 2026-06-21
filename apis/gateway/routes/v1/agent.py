from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from  typing import Optional, Dict, Any
from graphs.main_graph_new import MainGraph

router = APIRouter()
main_graph = MainGraph()

class AgentRequest(BaseModel):
    """Agent 请求模型"""
    query: str
    user_id: str
    domain: Optional[str]=None
    context: Optional[Dict[str, Any]]=None
    stream: bool=False

class AgentResponse(BaseModel):
    """Agent 响应模型"""
    task_id: str
    answer: str
    status: str
    sources: Optional[list]=None

@router.post("/chat")
async def chat(request: AgentRequest, background_task: BackgroundTasks):
    """同步对话接口"""
    # TODO
    # - 参数验证
    # - 用户认证与权限检查
    # - 请求去重(相同 query 短时间内不重复处理)
    # - 超时控制

    state = {
        "messages": [{"role": "user", "content": request.query}],
        "user_id": request.user_id,
        "domain": request.domain,
        "metadata": request.context or {}
    }

    # 执行 Agent 工作流
    result = await main_graph.graph.ainvoke(state)

    # 后台记录日志
    background_task.add_task(log_interaction, request, result)

    return AgentResponse(
        task_id=result.get("task_id", ""),
        answer=result.get("final_answer", ""),
        status=result.get("status", "completed")
    )

@router.post("/chat/stream")
async def chat_stream(request: AgentRequest):
    """流式对话接口 (SSE)"""
    # TODO
    # - 实现 Server-Sent Events
    # - 支持中断控制
    pass

async def log_interaction(request: AgentRequest, result: Dict):
    """记录交互日志到数据库"""
    # TODO
    # - 保存到 SQLite
    # - 异步写入, 不阻塞主流程
    pass