"""
通用对话 Agent
处理一般性对话和问答
"""

from typing import Dict, Any, Optional, List
from langgraph.graph import StateGraph, END

from core.agent_base import BaseAgent
from core.state_base import BaseState
from llm.factory import LLMFactory
import logging

logger = logging.getLogger(__name__)

class ChatState(BaseState):
    """对话状态"""
    conversation_history: List[Dict[str, str]]
    context: Dict[str, Any]
    response_style: str  # casual, professional, concise, detailed
class ChatAgent(BaseAgent):
    """通用对话 Agent"""

    def __init__(self):
        super().__init__(name="chat_agent")
        self.llm = LLMFactory.get_client("ollama")

        # 对话风格配置
        self.style_prompts = {
            "casual": "以轻松、友好的语气回答, 使用口语化表达",
            "professional": "使用专业、正式的语气, 保持严谨",
            "cancise": "简洁明了, 直接回答问题, 不冗余",
            "detailed": "提供详细、全面的回答, 包含背景信息和例子"
        }

        logger.info("ChatAgent initialized")

    def build_graph(self) -> StateGraph:
        """构建 ChatAgent 工作流"""
        workflow = StateGraph(ChatState)

        workflow.add_node("process_query", self._process_query)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("handle_error", self._handle_error)

        workflow.set_entry_point("process_query")
        workflow.add_edge("process_query", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile()
    
    async def _execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行对话逻辑"""
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        style = input_data.get("style", "cansual")

        state = ChatState(
            messages=[{"role": "user", "content": query}],
            context=context,
            response_style=style
        )

        result = await self._process_query(state)
        result = await self._generate_response(result)

        return {
            "answer": result.get("final_answer", ""),
            "status": result.get("status", "completed"),
            "style": style
        }
    
    async def _process_query(self, state: ChatState) -> ChatState:
        """
        处理查询 - 意图识别和上下文提取
        """
        query = state.get("messages", [{}])[-1].get("content", "")

        # TODO: 使用 LLM 进行意图识别
        # 这里简化为基础处理

        # 检索是否有上下文
        if "context" in state:
            context = state["context"]
            logger.info(f"Processing with context: {context}")

        # 保存查询到历史
        if "conversation_history" not in state:
            state["conversation_history"] = []
        state["conversation_history"].append({
            "role": "user",
            "content": query,
            "timestamp": None  # TODO: 添加时间戳
        })

        state["status"] = "processed"
        return state
    
    async def _generate_response(self, state: ChatState) -> ChatState:
        """
        生成回复
        """
        query = state.get("messages", [{}])[-1].get("content", "")
        style = state.get("response_style", "casual")

        # 构建消息
        style_prompt = self.style_prompts.get(style, self.style_prompts["casual"])

        messages = [
            {"role": "system", "content": f"你是一个 AI 助手. {style_prompt}"}
        ]

        # 添加上下文
        if state.get("conversation_history"):
            # 取最近5条消息作为上下文
            history = state["conversation_history"][-5:]
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        else:
            messages.append({"role": "user", "content": query})

        try:
            # 调用 LLM
            response = await self.llm.generate(messages)

            # 保存回复
            state["final_answer"] = response
            state["status"] = "completed"

            # 更新历史
            if "conversation_history" in state:
                state["conversation_history"].append({
                    "role": "assistant",
                    "content": response
                })

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            state["final_answer"] = "抱歉, 我暂时无法回答这个问题. 请稍后再试."
            state["status"] = "failed"

        return state
    
    async def _handle_error(self, state: ChatState) -> ChatState:
        """
        错误处理
        """
        state["status"] = "failed"
        state["final_answer"] = "处理您的请求时出了错误, 请稍后重试."
        return state