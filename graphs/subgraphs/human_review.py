"""
人机协作子图
处理需要人工介入的环节
"""

from typing import Dict, Any, Optional, List
from langgraph.graph import StateGraph, END
from datetime import datetime, timedelta

from core.graph_base import BaseGraph
from core.state_base import BaseState
from core.exceptions import TimeoutExpection
import logging

logger = logging.getLogger(__name__)

class HumanReviewState(BaseState):
    """人机协作状态"""
    review_id: Optional[str]
    review_type: Optional[str]  # kg_deletion, data_export, system_config, code_execution
    reviewer_id: Optional[str]
    review_status: Optional[str]  # pending, approved, rejected, transfered, timeout
    review_comment: Optional[str]
    review_timeout: Optional[int]
    review_created_at: Optional[str]
    review_completed_at: Optional[str]
    payload: Optional[Dict[str, Any]]
    context: Optional[Dict[str, Any]]

class HumanReviewSubgraph(BaseGraph):
    """人机协作子图"""

    def __init__(self, checkpointer=None):
        super().__init__(
            name="human_review_subgraph",
            state_class=HumanReviewState,
            checkpointer=checkpointer
        )

        # 配置不同操作类型的审批人
        self.reviewer_config = {
            "kg_deletion": {
                "reviewers": ["kg_admin", "data_governance"],
                "timeout": 86400,  # 24小时
                "requires_all": False
            },
            "data_export": {
                "reviewers": ["data_governance", "security_team"],
                "timeout": 43200,  # 12小时
                "requires_all": False
            },
            "system_config": {
                "reviewers": ["sys_admin", "devops"],
                "timeout": 43200,
                "requires_all": True
            },
            "code_execution": {
                "reviewers": ["tech_lead", "security_team"],
                "timeout": 3600,  # 1小时
                "requires_all": False
            }
        }

        logger.info("HumanReviewSubgraph initialized")

    def _add_nodes(self):
        """添加节点"""
        self.workflow.add_node("validate_review", self._validate_review)
        self.workflow.add_node("request_review", self._request_review)
        self.workflow.add_node("wait_for_review", self._wait_for_review)
        self.workflow.add_node("process_review", self._process_review)
        self.workflow.add_node("execute_action", self._execute_action)
        self.workflow.add_node("notify_reviewers", self._notify_reviewers)
        self.workflow.add_node("handle_error", self._handle_error)

    def _add_edges(self):
        """添加边"""
        self.workflow.add_edge("validate_review", "request_review")
        self.workflow.add_edge("request_review", "notify_reviewers")
        self.workflow.add_edge("notify_reviewers", "wait_for_review")

        # 条件路由
        self.workflow.add_conditional_edges(
            "wait_for_review",
            self._check_review_status,
            {
                "approved": "process_review",
                "rejected": "process_review",
                "timeout": "process_review",
                "pending": "wait_for_review"
            }
        )

        self.workflow.add_edge("process_review", "execute_action")
        self.workflow.add_edge("execute_action", END)
        self.workflow.add_edge("handle_error", END)

    def _configure_entry_and_exit(self):
        """配置入口和出口"""
        self.workflow.set_entry_point("validate_review")
        self.workflow.set_finish_point("execute_action")

    async def _validata_review(self, state: HumanReviewState) -> HumanReviewState:
        """
        验证人机协作请求
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        review_type = state.get("review_type")
        payload = state.get("payload", {})

        # 验证类型是否支持
        if review_type not in self.review_config:
            return await self._handle_error(
                state,
                f"不支持的操作类型: {review_type}"
            )
        # 验证数据
        if not payload:
            return await self._handle_error(
                state,
                "缺少操作数据"
            )
        # 特定类型的数据验证
        if review_type == "kg_deletion":
            if not payload.get("node_id") and not payload.get("relation_id"):
                return await self._handle_error(
                    state,
                    "KG 删除需要指定的 node_id 或 relation_id"
                )
        elif review_type == "code_execution":
            if not payload.get("code"):
                return await self._handle_error(
                    state,
                    "代码执行需要提供代码"
                )
            
        state["status"] = "validated"
        return state

    async def _request_review(self, state: HumanReviewState) -> HumanReviewState:
        """
        请求人工审查
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        review_type = state.get("review_type")
        config = self.reviewer_config.get(review_type, {})

        # 生成审查 ID
        import uuid
        state["review_id"] = str(uuid.uuid4())
        state["review_status"] = "pending"
        state["review_created_at"] = datetime.now().isoformat()

        # 设置超时时间
        timeout = state.get("review_timeout") or config.get("timeout", 86400)
        state["review_timeout"] = timeout

        # 设置审查人
        reviewers = config.get("reviewers", ["default_reviewer"])
        state["reviewer_id"] = ",".join(reviewers)  # 简单实现, 实际应使用列表

        logger.info(f"Review requested: {state['review_id']} for type {review_type}")
        return state
    
    async def _wait_for_review(self, state: HumanReviewState) -> HumanReviewState:
        """
        等待审查结果
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        review_id = state.get("review_id")
        created_at = state.get("review_created_at")
        timeout = state.get("review_timeout", 86400)

        # TODO
        # - 从数据库获取审查状态
        # - 检查是否超时
        # - 实际应使用异步等待或 webhook

        # 检查超时
        if created_at:
            created_time = datetime.fromisoformat(created_at)
            elapsed = (datetime.now() - created_time).total_seconds()
            if elapsed > timeout:
                state["review_status"] = "timeout"
                logger.warning(f"Review {review_id} time out")

        return state
    
    async def _process_review(self, state: HumanReviewState) -> HumanReviewState:
        """
        处理审查结果
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        status = state.get("review_status")
        state["review_completed_at"] = datetime.now().isoformat()

        if status == "approved":
            state["status"] = "approved"
            logger.info(f"Review {state.get('review_id')} approved")
        elif status == "rejected":
            state["status"] = "rejected"
            comment = state.get("review_comment", "审查被拒绝")
            state["review_comment"] = comment
            logger.info(f"Review {state.get('review_id')} rejected: {comment}")
        elif status == "timeout":
            state["status"] = "timeout"
            logger.info(f"Review {state.get('review_id')} time out")

        return state
    
    async def _execute_action(self, state: HumanReviewState) -> HumanReviewState:
        """
        执行审查后的操作
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        # 只有审查通过才执行
        if state.get("review_status") != "approved":
            state["execution_result"] = {
                "success": False,
                "reason": "审查未通过"
            }
            return state
        
        review_type = state.get("review_type")
        payload = state.get("payload", {})

        try:
            # 根据类型执行不同的操作
            if review_type == "kg_deletion":
                result = await self._execute_kg_deletion(payload)
            elif review_type == "data_export":
                result = await self._execute_data_export(payload)
            elif review_type == "system_config":
                result = await self._execute_system_config(payload)
            elif review_type == "code_execution":
                result = await self._execute_code_execution(payload)
            else:
                result = {
                    "success": False,
                    "error": f"未知操作类型: {review_type}"
                }

            state["execution_result"] = result
            state["status"] = "executed"

            logger.info(f"Action executed for review {state.get('review_id')}: {result.get('success')}")
            return state
        except Exception as e:
            logger.error(f"Failded to execute action: {e}")
            state["execution_result"] = {
                "success": False,
                "error": str(e)
            }
            return state
    
    async def _execute_kg_deletion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 KG 删除操作
        Args:
            payload: 删除参数
        Returns:
            执行结果
        """
        # TODO
        # - 连接 Neo4j 执行删除
        # - 记录删除日志
        # - 支持回滚

        return {
            "success": True,
            "deleted": {
                "nodes": payload.get("node_id", []),
                "relations": payload.get("relation_id", [])
            }
        }
    
    async def _execute_data_export(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行数据导出
        Args:
            payload: 导出参数
        Returns:
            执行结果
        """
        # TODO
        # - 导出数据到文件
        # - 生成下载连接
        # - 加密敏感数据

        return {
            "success": True,
            "export_url": "/data/exports/export_20260101.csv",
            "file_size": 1024
        }
    
    async def _execute_system_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行系统配置变更
        Args:
            payload: 配置参数
        Returns:
            执行结果
        """
        # TODO
        # - 验证配置变更
        # - 备份旧配置
        # - 应用新配置
        return {
            "success": True,
            "changed": payload.get("config_key"),
            "backup_created": True
        }
    
    async def _execute_node_execution(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行代码(沙箱)
        Args:
            payload: 代码和参数
        Returns:
            执行结果
        """
        # TODO
        # - 在沙箱中执行代码
        # - 限制执行时间和资源
        # - 捕获输出和错误
        return {
            "success": True,
            "output": "代码执行结果占位",
            "execution_time": 0.5
        }
    
    async def _notify_reviewers(self, state: HumanReviewState) -> HumanReviewState:
        """
        通知审查人
        Args:
            state: 当前状态
        Returns:
            更新后的状态
        """
        # TODO
        # - 发送通知(微信|邮件等)
        # - 更新审查状态
        return state
    
    async def _handle_error(self, state: HumanReviewState, error_msg: str) -> HumanReviewState:
        """
        处理错误
        Args:
            state: 当前状态
            error_msg: 错误信息
        Returns:
            更新后的状态
        """
        state["status"] = "failed"
        state["errors"] = state.get("errors", []) + [error_msg]

        logger.info(f"Human review subgraph error: {error_msg}")
        return state