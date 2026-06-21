from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """LangGraph 全局状态Schema"""

    # 消息历史(使用 add_messages reducer 自动合并)
    messages: Annotated[List[Dict], add_messages]

    # 任务相关
    task_id: Optional[str]
    user_id: Optional[str]
    domain: Optional[str]  # medial, finance, coding 等
    intent: Optional[str]

    # 执行状态
    current_agent: Optional[str]
    next_agent: Optional[str]
    iteration: int
    max_iterations: int

    # 中间结果
    intermediate_steps: List[Dict]
    tool_results: Dict[str, Any]

    # 最终输出
    final_answer: Optional[str]
    status: str  # pending, running, completed, failed, requires_approval

    # 记忆相关
    short_term_memory: List[Dict]  #会话级记忆
    long_term_context: Optional[Dict]  # 检索到的长期记忆

    # 审批相关
    requires_approval: bool
    approval_status: Optional[str]  # pending, approval, rejected
    approval_request_id: Optional[str]

    # 元数据
    metadata: Dict[str, Any]
    error: List[str]

    # TODO:
    # - 添加更多领域特定的状态字段
    # - 实现状态压缩机制(长对话时自动摘要)
    # - 实现状态版本控制(支持回滚)