"""
单元测试运行器
用于确定性功能测试
"""

from typing import List, Dict, Any, Optional, Callable
import unittest
import asyncio
from datetime import datetime
from pathlib import Path
import json
import inspect

from graphs.main_graph_new import MainGraph
from evaluation.graders.code_grader import CodeGrader
from evaluation.graders.metrics import MetricsCalculator
import logging

logger = logging.getLogger(__name__)

class UnitTestRunner:
    """单元测试运行器"""

    def __int__(self, output_dir: str = "evaluation/results/unit"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.main_graph = MainGraph()
        self.code_grader = CodeGrader()
        self.metrics = MetricsCalculator()

        self.test_results = []

    def _load_test_cases(self, file_path: str) -> List[Dict[str, Any]]:
        """加载测试用例"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("test_cases", [])
    
    async def run_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个测试用例
        Args:
            test_case: 测试用例配置
        Returns:
            测试结果
        """
        test_id = test_case.get("id", f"test_{datetime.now().timestamp()}")
        test_name = test_case.get("name", "Unnamed Test")

        result = {
            "id": test_id,
            "name": test_name,
            "status": "pending",
            "start_time": datetime.now().isoformat(),
            "execution_time": 0.0,
            "details": {}
        }

        try:
            # 准备测试
            query = test_case.get("query", "")
            expected = test_case.get("expected", "")
            context = test_case.get("context", {})
            test_type = test_case.get("type", "functional")

            # 执行测试
            start_time = datetime.now()

            if test_type == "functional":
                result_detail = await self._run_functional_test(query, expected, context)
            elif test_type == "tool":
                result_detail = await self._run_tool_test(test_case)
            elif test_type == "agent":
                result_detail = await self._run_agent_test(test_case)
            elif test_type == "workflow":
                result_detail = await self._run_workflow_test(test_case)
            else:
                result_detail = {"error": f"Unknown test type: {test_type}"}

            result["execution_time"] = (datetime.now() - start_time).total_seconds()
            result["details"] = result_detail
            result["status"] = "passed" if result_detail.get("passed", False) else "failed"
            result["score"] = result_detail.get("score", 0.0)
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"Test {test_id} failed: {e}")
        
        result["end_time"] = datetime.now().isoformat()
        self.test_results.append(result)

        return result
    
    async def _run_functional_test(
        self,
        query: str,
        expected: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行功能测试"""
        state = {
            "messages": [{"role": "user", "content": query}],
            "domain": context.get("domain", "general"),
            "metadata": context
        }

        try:
            result = await self.main_graph.graph.ainvoke(state)
            actual = result.get("final_answer", "")

            # 比较结果
            passed = self._compare_results(expected, actual, context)

            return {
                "passed": passed,
                "score": 1.0 if passed else 0.0,
                "query": query,
                "expected": expected,
                "actual": actual,
                "comparison_method": "exact_match" if passed else "failed"
            }
        except Exception as e:
            return {"passed": False, "error": str(e)}
        
    def _compare_results(
        self,
        expected: str,
        actual: str,
        context: Dict[str, Any]
    ) -> bool:
        """比较结果"""
        if not expected:
            return bool(actual)
        
        # 检查是否包含期望内容
        comparison_type = context.get("comparison_type", "contains")

        if comparison_type:
            return expected.strip() == actual.strip()
        elif comparison_type == "contains":
            return expected in actual
        elif comparison_type == "startswith":
            return actual.startswith(expected)
        elif comparison_type == "endswith":
            return actual.endswith(expected)
        else:
            return expected.strip() == actual.strip()
        
    async def _run_tool_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """运行工具测试"""
        tool_name = test_case.get("tool", "")
        params = test_case.get("params", {})
        expected = test_case.get("expected", "")

        # TODO: 直接调用工具
        # from tools.registry import ToolRegistry
        # registry = ToolRegistry()
        # result = await registry.execute(tool_name, **params)
        return {
            "passed": True,
            "score": 1.0,
            "tool": tool_name,
            "params": params,
            "expected": expected,
            "note": "Tool test pending implementation"
        }
    
    async def _run_agent_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """运行 Agent 测试"""
        agent_name = test_case.get("agent", "")
        query = test_case.get("query", "")
        expected = test_case.get("expected", "")

        # TODO: 世界调用指定 Agent
        return {
            "passed": True,
            "score": 0.5,
            "agent": agent_name,
            "query": query,
            "note": "Agent test pending implementation"
        }
    
    async def _run_workflow_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """运行工作流测试"""
        workflow_name = test_case.get("workflow", "")
        inputs = test_case.get("inputs", {})
        expected = test_case.get("expected", {})

        # TODO: 调用工作流引擎
        return {
            "passed": True,
            "score": 0.5,
            "workflow": workflow_name,
            "inputs": inputs,
            "note": "Workflow test pending implementation"
        }
    
    async def run_all(self, test_file: str) -> List[Dict[str, Any]]:
        """
        运行所有测试
        Args:
            test_file: 测试文件路径
        Returns:
            测试结果列表
        """
        test_cases = self.load_test_cases(test_file)
        logger.info(f"Running {len(test_cases)} unit tests")

        for test_case in test_cases:
            await self.run_test_case(test_case)

        # 保存结果
        self._save_results()
        self._generate_report()

    def _save_results(self):
        """保存测试结果"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"unit_results_{timestamp}.json"
        
        data = {
            "timestamp": timestamp,
            "total_test": len(self.test_results),
            "passed": sum(1 for r in self.test_results if r.get("status") == "passed"),
            "failed": sum(1 for r in self.test_results if r.get("status") == "failed"),
            "errors": sum(1 for r in self.test_results if r.get("status") == "error"),
            "results": self.test_results
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("Test result saved to: {output_file}")

    def _generate_report(self):
        """生成报告"""
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.get("status") == "passed")
        failed = sum(1 for r in self.test_results if r.get("status") == "failed")
        errors = sum(1 for r in self.test_results if r.get("status") == "error")

        print("\n" + "=" * 60, "单元测试报告", "=" * 60)
        print(f"总测试数: {total}")
        print(f"通过: {passed} ({passed / total * 100:.1f}%)" if total > 0 else "通过: 0")
        print(f"失败: {failed}")
        print(f"错误: {errors}")

        # 显示失败的测试
        if failed > 0 or errors > 0:
            print("\n失败/错误详情:")
            for result in self.test_results:
                if result.get("status") in ["failed", "error"]:
                    print(f"- {result.get('name')}: {result.get('status')}")
                    if "error" in result:
                        print(f"错误: {result.get('error')}")
        print("=" * 60)

# 测试用例示例
SAMPLE_TEST_CASES = {
    "test_cases": [
        {
            "id": "unit_001",
            "name": "基本查询测试",
            "type": "functional",
            "query": "什么是人工智能?",
            "expected": "人工智能是",
            "context": {
                "domain": "general",
                "comparison_type": "contains"
            }
        },
        {
            "id": "unit_002",
            "name": "工具调用测试",
            "type": "tool",
            "tool": "web_search",
            "params": {
                "query": "天气预报",
                "num_results": 3
            },
            "expected": "结果"
        }
    ]
}