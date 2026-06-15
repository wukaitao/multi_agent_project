from typing import TypedDict, Optional
from llama_index.llms.ollama import Ollama
from core.security import check_auth, rate_limit
from core.optimizer import clean_text
from config.settings import *

class AgentState(TypedDict):
    user: str
    token: str
    query: str
    prompt: str
    reference: str
    image: str
    response: str
    route: str
    pending_delete: bool
    from_skill: Optional[str]  # None=普通请求, "rag_query"/"multimodal_generate"等

# ========== 替换原有 supervisor_node 的语义路由(路径C) ==========
def semantic_router(state) -> str:
    """使用 LLM 进行语义路由, 替换关键词匹配"""
    # ========== skill.md 进入则跳过 ==========
    from_skill = state.get("from_skill", None)
    route = state.get("route", "")
    if from_skill and route:
        print(f"跳过语义路由, 使用预设路由from_skill: {from_skill} -> {route}")
        return state["route"]
    
    # ========== 语义路由 ==========
    query = state["query"]
    llm = Ollama(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        temperature=0
    )
    prompt = f"""分析以下用户问题, 判断应该路由到哪个Agent.
    可选Agent:
    - rag: 知识检索、文档回答、信息查询
    - multimodal: 图片生成、图片理解
    - tool: 天气查询、代码生成、足球信息
    - approval: 审批流程、删除知识图谱
    - chat: 普通对话、闲聊

    用户问题: {query}

    只输出Agent名称, 不要输出其他内容:"""
    try: 
        result = llm.complete(prompt).text.strip().lower()
        print(f"语义路由判断结果:\n{result}")
        if result in ["rag", "multimodal", "tool", "approval", "chat"]:
            return result
        else:
            print("语义路由识别不出结果")
    except:
        pass

    # ========== 降级: 关键词匹配 ==========
    if any(k in query for k in ["图片", "生成图", "画图"]):
        return "multimodal"
    elif any(k in query for k in ["知识", "文档", "资料", "是谁", "什么是"]):
        return "rag"
    elif any(k in query for k in ["天气", "代码", "足球"]):
        return "tool"
    elif any(k in query for k in [
        # 普通申请流程
        "流程", "审核",
        # 申请流程
        "请假", "报销", "项目", "立项",
        # 审批流程
        "通过", "驳回", "转交", "审批",
        # 删除知识图谱识别(走审批节点)
        "删除知识图谱", "清除知识图谱", "清空知识图谱",
        "删除所有数据", "清空数据库", "重置知识库",
        "删除图谱", "清除图谱"]):
        return "approval"
    else:
        return "chat"
    
def semantic_supervisor_node(state: AgentState) -> AgentState:
    """
    语义路由版 supervisor_node
    替换原有的关键词匹配
    """
    print(f"========== SUPERVISOR 节点 ==========")
    # 鉴权
    print(f"state:\n{state}")
    if not check_auth(state["token"]):
        state["response"] = "鉴权失败, Token错误"
        state["route"] = "end"
        return state
    # 限流
    if not rate_limit():
        state["response"] = "访问频繁, 触发熔断限流"
        state["route"] = "end"
        return state
    # 清洗
    query = clean_text(state["query"])
    state["query"] = query

    # 使用语义路由低缓关键词匹配
    route = semantic_router(state)
    state["route"] = route

    return state