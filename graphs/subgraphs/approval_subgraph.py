"""
审批子图
处理各类审批流程
"""

from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from datetime import datetime

from core.graph_base import BaseGraph
from core.state_base import BaseState
from core.exceptions import ApprovalException
from agents.specialized.approval_agent_new import ApprovalAgent
import logging

logger = logging.getLogger(__name__)

class ApprovalState(BaseState):
    """审批子图状态"""
    approval_id: Optional[str]
    approval_type: Optional[str]
    approval_status: Optional[str]  # pending, approved, rejected, expired
    approval_action: Optional[str]  # request, approve, reject, transfer, cancel
    approver_id: Optional[str]
    approver_comment: Optional[str]
    payload: Optional[str]

class ApprovalSubgraph(BaseGraph):
    """审批子图"""

    def __init__(self, checkpointer=None):
        super().__init__(
            name="approval_subgraph",
            state_class=ApprovalState,
            checkpointer=checkpointer
        )
        self.approval_agent = ApprovalAgent()
        logger.info("ApprovalSubgraph initialized")

    def _add_nodes(self):
        """添加审批节点"""
        self.workflow.add_node("validate_approval", self._validate_approval)
        self.workflow.add_node("create_approval", self._create_approval)
        self.workflow.add_node("wait_for_approval", self._wait_for_approval)
        self.workflow.add_node("process_approval", self._process_approval)
        self.workflow.add_node("execute_approval", self._execute_approval)
        self.workflow.add_node("notify_result", self._notify_result)
        self.workflow.add_node("handle_error", self._handle_error)

    def _add_edges(self):
        """添加审批边"""
        self.workflow.add_edge("validate_approval", "create_approval")
        self.workflow.add_edge("create_approval", "wait_for_approval")

        # 条件路由
        self.workflow.add_conditional_edges(
            "wait_for_approval",
            self._check_approval_status,
            {
                "approved": "process_approval",
                "rejected": "process_approval",
                "expired": "process_approval",
                "pending": "wait_for_approval"
            }
        )

        self.workflow.add_edge("process_approval", "execute_approval")
        self.workflow.add_edge("execute_approval", "notify_result")
        self.workflow.add_edge("notify_result", END)
        self.workflow.add_edge("handle_error",END)

    def _configure_entry_exit(self):
        """配置入口和出口"""
        self.workflow.set_entry_point("validate_approval")
        self.workflow.set_finish_point("notify_result")

    async def _validate_approval(self, state: ApprovalState) -> ApprovalState:
        """
        验证审批请求
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        approval_type = state.get("approval_type")
        payload = state.get("payload", {})

        # 验证必填字段
        if not approval_type:
            return await self._handle_error(state, "缺少审批类型")
        
        if not payload:
            return await self._handle_error(state, "缺少审批数据")
        
        # 验证审理配型是否支持
        supported_types = [
            "kg_node_delete", "kg_relation_delete", "kg_batch_delete",
            "leave", "project", "reimbursement", "purchase"
        ]
        if approval_type not in supported_types:
            return await self._handle_error(state, f"不支持的审批类型: {approval_type}")
        
        state["status"] = "validated"
        return state
    
    async def _create_approval(self, state: ApprovalState) -> ApprovalState:
        """
        创建审批请求
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        try:
            # 调用审批 Agent 创建审批
            result = await self.approval_agent.process({
                "action": "request",
                "approval_type": state.get("approval_type"),
                "requester_id": state.get("user_id"),
                "requester_name": state.get("user_id"),
                "payload": state.get("playload", {}),
                "metadata": state.get("metadata", {})
            })

            state["approval_id"] = result.get("approval_id")
            state["approval_status"] = "pending"
            state["status"] = "approval_created"

            logger.info(f"Approval created: {state['approval_id']}")
            return state
        except Exception as e:
            logger.error(f"Failed to create approval: {e}")
            return await self._handle_error(state, str(e))
        
    async def _wait_for_approval(self, state: ApprovalState) -> ApprovalState:
        """
        等待审批结果
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        # 在实际场景中, 这里会轮询数据库或等待 webhook 回调
        # 此处简化为检查状态

        approval_id = state.get("approval_id")

        # TODO
        # - 从数据库获取审批状态
        # - 检查是否超时
        # - 检查是否升级

        # 模拟检查(实际应从数据库读取)
        # current_status = self.db.get_approval_status(approval_id)
        current_status = state.get("approval_status", "pending")

        if current_status == "pending":
            # 检查超时
            created_at = state.get("created_at")
            if created_at:
                # 假设超时时间为24小时
                # if (datetime.now() - created_at).total_seconds() > 86400:
                #   state["approvavl_status"] = "expired"
                pass
        
        state["approval_status"] = current_status
        return state
    
    def _check_approval_status(self, state: ApprovalState) -> str:
        """
        检查审批状态决定下一步
        Args:
            state: 当前状态
        Returns:
            下一步节点名称
        """
        status =  state.get("approval_status", "pending")

        if status in ["approved", "rejected", "expired", "transfered"]:
            return status
        else:
            return "pending"
        
    async def _process_approval(self, state: ApprovalState) -> ApprovalState:
        """
        处理审批结果
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        status = state.get("approval_status")

        if status == "pending":
            state["status"] = "approved"
            logger.info(f"Approval {state.get('approval_id')} approved")
        elif status == "rejected":
            state["status"] = "rejected"
            state["approval_comment"] = state.get("approval_comment", "审批被拒绝")
            logger.info(f"Approval {state.get('approval_id')} rejected")
        elif status == "expired":
            state["status"] = "expired"
            logger.warning(f"Approval {state.get('approval_id')} expired")

        return state
    
    async def _execute_approval(self, state: ApprovalState) -> ApprovalState:
        """
        执行审批后的操作
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        if state.get("approval_status") != "approved":
            return state
        
        try:
            # 调用审批 Agent 执行后置操作
            result = await self.approval_agent.process({
                "action": "execute",
                "approval_id": state.get("approval_id"),
                "approval_type": state.get("approval_type"),
                "payload": state.get("payload", {})
            })

            state["execution_result"] = result
            state["status"] = "executed"

            logger.info(f"Approval {state.get('approval_id')} executed")
            return state
        except Exception as e:
            logger.error(f"Failed to execute approval: {e}")
            return await self._handle_error(state, str(e))
        
    async def _notify_result(self, state: ApprovalState) -> ApprovalState:
        """
        通知审批结果
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        # TODO
        # - 发送通知给申请人
        # - 发送通知给审批人
        # - 更新审批状态到数据库

        logger.info(f"Approval {state.get('apaproval_id')} notification sent")
        return state
    
    async def _handle_error(self, state: ApprovalState, error_msg: str) -> ApprovalState:
        """
        处理错误
        Args:
            state: 当前状态
            error_msg: 错误信息
        Returns:
            更新后的状态
        """
        state["status"] = "failed"
        state["error"] = state.get("errors", []) + [error_msg]

        logger.error(f"Approval subgraph error: {error_msg}")
        return state