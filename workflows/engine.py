"""
工作流引擎
执行 DAG 定义的工作流
"""

from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import yaml
import json
import asyncio
from datetime import datetime
import networkx as nx
from concurrent.futures import ThreadPoolExecutor

from tools.registry import ToolRegistry
import logging

logger = logging.getLogger(__name__)

class WorkflowEngine:
    """工作流执行引擎"""

    def __int__(self, executor: Optional[ThreadPoolExecutor] = None):
        self.tool_registry = ToolRegistry()
        self.executor = executor or ThreadPoolExecutor(max_workers=10)
        self.workflows: Dict[str, Dict] = {}
        self.results: Dict[str, Any] = {}

    def load_workflow(self, yaml_path: str) -> Dict[str, Any]:
        """
        加载工作流定义
        Args:
            yaml_path: YAML文件路径
        Returns:
            工作流定义
        """
        with open(yaml_path, "r", encoding="utf-8") as f:
            workflow = yaml.safe_load(f)

        name = workflow.get("name")
        if name:
            self.workflows[name] = workflow
            logger.info(f"Loaded workflow: {name}")

        return workflow
    
    def validate_workflow(self, workflow: Dict[str, Any]) -> bool:
        """
        验证工作流定义
        Args:
            workflow: 工作流定义
        Returns:
            是否有效
        """
        required_fields = ["name", "version", "steps"]

        for field in required_fields:
            if field not in workflow:
                logger.error(f"Missing required field: {field}")
                return False
            
        # 验证步骤
        for step in workflow["steps"]:
            if "id" not in step:
                logger.error(f"Step missing 'id' field")
                return False
            if "tool" not in step:
                logger.error(f"Step {step.get('id')} missing 'tool' field")
                return False
        
        return True
    
    def build_dag(self, workflow: Dict[str, Any]) -> nx.DiGraph:
        """
        构建 DAG
        Args:
            workflow: 工作流定义
        Returns:
            DAG 图
        """
        dag = nx.DiGraph()

        # 添加节点
        for step in workflow["steps"]:
            dag.add_node(
                step["id"],
                tool=step["tool"],
                params=step.get("params", {}),
                description=step.get("description", "")
            )

            # 添加依赖边
            for dep in step.get("depends_on", []):
                dag.add_edge(dep, step["id"])

        # 检查是否有环
        if not nx.is_directed_acyclic_graph(dag):
            raise ValueError("Workflow contains cycles")
        
        return dag
    
    def topological_sort(self, dag: nx.DiGraph) -> List[str]:
        """拓扑排序"""
        return list(nx.topological_sort(dag))
    
    async def execute_workflow(
        self,
        workflow_name: str,
        context: Optional[Dict[str, Any]]=None
    ) -> Dict[str, Any]:
        """
        执行工作流
        Args:
            workflow_name: 工作流名称
            context: 上下文数据
        Returns:
            执行结果
        """
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_name}")
        
        # 验证
        if not self.validate_workflow(workflow):
            raise ValueError(f"Invalid workflow definition")
        
        # 构建 DAG
        dag = self.build_dag(workflow)
        order = self.topological_sort(dag)

        # 执行
        results = {}
        context = context or {}

        logger.info(f"Executing workflow: {workflow_name}")
        start_time = datetime.now()

        for step_id in order:
            step_data = dag.nodes[step_id]
            tool_name = step_data.get("tool")
            params = step_data.get("params", {})

            # 解析参数(支持引用之前步骤的结果)
            params = self._resolve_params(params, results, context)

            try:
                # 执行工具
                result = await self.tool_registry.execute(tool_name, **params)
                results[step_id] = {
                    "success": True,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
                logger.debug(f"Step {step_id} completed")
            except Exception as e:
                logger.error(f"Step {step_id} failed: {e}")
                results[step_id] = {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }

                # 错误处理策略
                error_strategy = step_data.get("on_error", "fail")
                if error_strategy == "fail":
                    break
                elif error_strategy == "continue":
                    continue
                elif error_strategy == "retry":
                    # TODO: 实现重试逻辑
                    pass
        
        execution_time = (datetime.now() - start_time).total_seconds()

        return {
            "workflow": workflow_name,
            "status": "completed",
            "execution_time": execution_time,
            "steps": results,
            "context": context
        }

    def _resolve_params(
        self,
        params: Dict[str, Any],
        results: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        解析参数引用
        Args:
            params: 参数定义
            results: 之前步骤的结果
            context: 上下文
        Returns:
            解析后的参数
        """

        resolved = {}

        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                # 引用格式: $step_id.result.field
                parts = value[1:].split(".")
                if len(parts) >= 2:
                    step_id = parts[0]
                    path = parts[1:]

                    if step_id in results:
                        data = results[step_id].get("result")
                        for p in path:
                            if isinstance(data, dict):
                                data = data.get(p)
                            elif isinstance(data, list):
                                try:
                                    idx = int(p)
                                    data = data[idx] if idx < len(data) else None
                                except ValueError:
                                    data = None
                            else:
                                data = None
                                break
                        resolved[key] = data
                    else:
                        # 尝试从 context 获取
                        data = context
                        for p in parts:
                            if isinstance(data, dict):
                                data = data.get(p)
                            else:
                                data = None
                                break
                        resolved[key] = data
                else:
                    resolved[key] = context.get(parts[0])
            else:
                resolved[key] = value
        
        return resolved
    
    def get_workflow_status(self, workflow_name: str) -> Dict[str, Any]:
        """获取工作流状态"""
        # TODO: 实现状态查询
        return {
            "name": workflow_name,
            "status": "idle",
            "last_execution": None
        }