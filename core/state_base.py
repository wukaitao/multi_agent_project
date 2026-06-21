"""
LangGraph 状态基类
定义统一的状态结构和操作接口
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph.message import add_messages
from datetime import datetime
from enum import Enum

class ExecutionStatus(str, Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    REQUIRES_APPROVAL = "requires_approval"

class BaseState(TypedDict, total=False):
    """
    LangGraph 全局状态基类
    所有状态字段都是可选的, 由具体实现决定使用哪些字段
    """

    # ========== 消息相关 ==========
    messages: Annotated[List[Dict], add_messages]
    """消息历史列表, 使用add_messages reducer自动合并"""

    # ========== 任务信息 ==========
    task_id: Optional[str]
    """任务唯一标识"""

    user_id: Optional[str]
    """用户 ID"""

    session_id: Optional[str]
    """会话 ID"""

    # ========== 意图与路由 ==========
    itent: Optional[str]
    """用户意图类"""

    domain: Optional[str]
    """领域标识(medical, finance, coding, office, entertainment)"""

    next_agent: Optional[str]
    """下一个要执行的 Agent 名称"""

    # ========== 执行控制 ==========
    interation: int
    """当前迭代次数"""

    max_interations: int
    """最大迭代次数"""

    status: ExecutionStatus
    """执行状态"""

    step_count: int
    """已执行步骤数"""

    # ========== 中间结果 ==========
    intermediate_steps: List[Dict]
    """中间步骤记录 [(action, result), ...]"""

    too_results: Dict[str, Any]
    """工具调用结果缓存"""

    # ========== 最终输出 ==========
    final_answer: Optional[str]
    """最终答案"""

    output_data: Optional[Dict[str, Any]]
    """结构化输出数据"""

    # ========== 记忆系统 ==========
    short_term_memory: List[Dict]
    """短期记忆(当前会话)"""

    long_term_context: Optional[Dict[str, Any]]
    """长期记忆上下文(从向量/图数据库检索)"""

    memory_retrieved: bool
    """是否已检索长期记忆"""

    # ========== 审批流程 ==========
    requires_approval: bool
    """是否需要人工审批"""

    approval_status: Optional[str]
    """审批状态(pending, approved, rejected, expired)"""

    approval_request_id: Optional[str]
    """审批请求 ID"""

    approval_type: Optional[str]
    """审批类型"""

    # ========== 错误处理 ==========
    errors: List[str]
    """错误列表"""

    error_count: int
    """错误计数"""

    retry_count: int
    """重试次数"""

    # ========== 元数据 ==========
    metadata: Dict[str, Any]
    """扩展元数据"""

    created_at: Optional[str]
    """创建时间"""

    updated_at: Optional[str]
    """更新时间"""

    elapsed_time: float
    """已用时间(秒)"""

# ========== 辅助函数 ==========
def create_inital_state(
    query: str,
    user_id: Optional[str]=None,
    domain: Optional[str]=None,
    **kwargs
) -> BaseState:
    """
    创建初始状态
    Args:
        query: 用户查询
        user_id: 用户 ID
        domain: 领域
        **kwargs: 额外状态字段
    Returns:
        初始状态
    """
    return {
        "messages": [{"role": "user", "content": query}],
        "user_id": user_id,
        "domain": domain,
        "iteration": 0,
        "max_iterations": 10,
        "status": ExecutionStatus.PENDING,
        "step_count": 0,
        "intermediate_steps": [],
        "tool_results": {},
        "short_term_memory": [],
        "memory_retrieved": False,
        "requires_approval": False,
        "errors": [],
        "error_count": 0,
        "retry_count": 0,
        "metadata": kwargs.get("kwargs", {}),
        "created_at": datetime.now().isoformat(),
        "elapsed_time": 0,
        **kwargs
    }

def update_state_with_result(state: BaseState, result: Dict[str, Any]) -> BaseState:
    """
    更新状态中的结果
    Args:
        state: 当前状态
        result: 执行结果

    Returns:
        更新后的状态
    """
    state["final_answer"] = result.get("final_answer", state.get("final_answer"))
    state["output_data"] = result.get("data", state.get("output_data"))
    state["status"] = ExecutionStatus.COMPLETED
    state["updated_at"] = datetime.now().isoformat()

    # 添加中间步骤
    if "step_result" in result:
        state["intermediate_steps"].append(result["step_result"])
    
    return state

def update_state_error(state: BaseState, error: Exception, context: Optional[str]=None) -> BaseState:
    """
    更新状态中的错误信息
    Args:
        state: 当前状态
        error: 异常对象
        context: 错误上下文
    Returns:
        更新后的状态
    """
    error_msg = f"{context}: {str(error)}" if context else str(error)
    state["errors"].append(error_msg)
    state["error_count"] = len(state["errors"])
    state["status"] = ExecutionStatus.FAILED
    state["updated_at"] = datetime.now().isoformat()

    return state

def update_state_with_approval(state: BaseState, approval_id: str, approval_type: str) -> BaseState:
    """
    更新状态为需要审批
    Args:
        state: 当前状态
        approval_id: 审批请求 ID
        approval_type: 审批类型

    Returns:
        更新后的状态
    """
    state["requires_approval"] = True
    state["approval_status"] = "pedding"
    state["approval_request_id"] = approval_id
    state["approval_type"] = approval_type
    state["status"] = ExecutionStatus.REQUIRES_APPROVAL
    state["updated_at"] = datetime.now().isoformat()

    return state

def is_state_terminal(state: BaseState) -> bool:
    """
    检查状态是否处于终态
    Args:
        state: 当前状态
    Returns:
        是否终态
    """
    terminal_statuses = {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED
    }
    return state.get("status") in terminal_statuses

def should_continue(state: BaseState) -> bool:
    """
    检查是否应该继续执行
    Args:
        state: 当前状态
    Returns:
        是否继续
    """
    if is_state_terminal(state):
        return False
    
    if state.get("iteration", 0) >= state.get("max_iterations", 10):
        return False
    
    if state.get("requires_approval", False):
        return False
    
    return True