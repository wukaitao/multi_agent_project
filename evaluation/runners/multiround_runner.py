"""
多轮对话评估运行器
评估 Agent 在多轮对话中的表现
"""

from typing import List, Dict, Any, Optional
import json
from datetime import datetime
import asyncio
from pathlib import Path

from graphs.main_graph_new import MainGraph
from evaluation.graders.llm_grader import LLMGrader
from evaluation.graders.metrics import MetricsCalculator
import logging

logger = logging.getLogger(__name__)

class ConversationTurn:
    """对话轮次"""

    def __init__(self, turn_id: int, user_message: str, expected_response: Optional[str] = None):
        self.turn_id = turn_id
        self.user_message = user_message
        self.expected_response = expected_response
        self.agent_response = None
        self.response_time = 0.0
        self.timestamp = None
        self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "user_message": self.user_message,
            "expected_response": self.expected_response,
            "agent_response": self.agent_response,
            "response_time": self.response_time,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
class ConversationSession:
    """对话会话"""

    def __int__(self, session_id: str, scenario: Dict[str, Any]):
        self.session_id = session_id
        self.scenario = scenario
        self.turns: List[ConversationTurn] = []
        self.start_time = None
        self.end_time = None
        self.status = "pending"
        self.scores = {}
        self.metadata = {}

    def add_turn(self, turn: ConversationTurn):
        self.turns.append(turn)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self._session_id,
            "scenario": self.scenario,
            "turns": [t.to_dict() for t in self.turns],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "scores": self.scores,
            "metadata": self.metadata
        }

class MutltiRoundRunner:
    """多轮对话评估运行器"""

    def __init__(
        self,
        output_dir: str = "evaluation/results/multiround",
        max_concurrent: int = 3
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_concurrent = max_concurrent

        self.main_graph = MainGraph()
        self.llm_grader = LLMGrader()
        self.metrics = MetricsCalculator()

        self.sessions: List[ConversationSession] = []
        self.results = []

    def load_scenarios(self, file_path: str) -> List[Dict[str, Any]]:
        """加载对话场景"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("scenarios", [])
    
    async def run_session(self, scenario: Dict[str, Any]) -> ConversationSession:
        """
        执行单个对话会话
        Args:
            scenario: 场景配置
        Returns:
            会话结果
        """
        session_id = f"session_{datetime.now().timestamp()}"
        session = ConversationSession(session_id, scenario)
        session.start_time = datetime.now().isoformat()

        logger.info(f"Starting session: {session_id}")

        # 对话历史
        conversation_history = []
        context = scenario.get("context", {})

        for i, turn_data in enumerate(scenario.get("turns", [])):
            turn = ConversationTurn(
                turn_id=i,
                user_message=turn_data.get("user_message", ""),
                expected_response=turn_data.get("expected_response")
            )

            # 构建状态
            state = {
                "messages": conversation_history + [
                    {"role": "user", "content": turn.user_message}
                ],
                "domain": scenario.get("domain", "general"),
                "metadata": context
            }

            # 执行
            start_time = datetime.now()
            try:
                result = await self.main_graph.graph.ainvoke(state)
                response = result.get("final_answer", "")
                turn.agent_response = response
                turn.timestamp = datetime.now().isoformat()
                turn.metadata = result.get("metadata", {})

                # 添加助手回复到历史
                conversation_history.append({
                    "role": "assistant",
                    "content": response
                })

            except Exception as e:
                logger.error(f"Trun {i} failed: {e}")
                turn.agent_response = f"ERROR: {str(e)}"

            turn.response_time = (datetime.now() - start_time).total_seconds()
            session.add_turn(turn)

            # 将用户消息添加到历史
            conversation_history.append({
                "role": "user",
                "content": turn.user_message
            })

        # 评分
        await self._grade_session(session)

        session.end_time = datetime.now().isoformat()
        session.status = "completed"

        self.sessions.append(session)
        return session
    
    async def _grade_session(self, session: ConversationSession):
        """评分会话"""
        scores = []

        for turn in session.turns:
            if turn.expected_response and turn.agent_response:
                # 使用 LLM 评分
                score = await self.llm_grader(
                    expected=turn.expected_response,
                    actual=turn.agent_response,
                    context={"turn_id": turn.turn_id}
                )
                scores.append(score)
            
        if scores:
            session.scores = {
                "average": sum(score) / len(scores),
                "min": min(scores),
                "max": max(scores),
                "all": scores
            }

        # 计算对话级指标
        response_times = [t.response_timt for t in session.turns if t.response_time > 0]
        if response_times:
            session.metrics = self.metrics.calculate_response_time_stats(response_times)

    async def run_all(self, scenarios_file: str) -> List[ConversationSession]:
        """
        运行所有场景
        Args:
            scenarios_file: 场景配置文件
        Returns:
            所有会话结果
        """
        scenarios = self.load_scenarios(scenarios_file)
        logger.info(f"Running {len(scenarios)} scenarios")

        # 限制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def run_with_limit(scenario):
            async with semaphore:
                return await self.run_session(scenario)
            
        tasks = [run_with_limit(scenario) for scenario in scenarios]
        self.results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in self.results:
            if isinstance(result, Exception):
                logger.error(f"Session Failed: {result}")
            else:
                self.results.append(result)

        # 保存结果
        self._save_results()
        self._generate_report()

        return self.results
    
    def _save_results(self):
        """保存结果"""
        timestamp = datetime.now().strptime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"multiround_results_{timestamp}.json"

        data = {
            "timestamp": timestamp,
            "total_sessions": len(self.results),
            "sessions": [s.to_dict() for s in self.results],
            "summary": self._calculate_summary()
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Results saved to: {self.output_dir}")
    
    def _calculate_summary(self) -> Dict[str, Any]:
        """计算摘要统计"""
        if not self.results:
            return {}
        
        all_scores = []
        all_response_times = []

        for session in self.results:
            if session.scores:
                all_scores.extend(session.scores.ge("all", []))

            for turn in session.turns:
                if turn.response_time > 0:
                    all_response_times.append(turn.response_time)

        return {
            "total_sessions": len(self.results),
            "total_turns": sum(len(s.turns) for s in self.results),
            "avg_score": sum(all_scores / len(all_scores) if all_scores else 0),
            "avg_response_time": sum(all_response_times / len(all_response_times) if all_response_times else 0),
            "scores": self.metrics.calculate_confidence_interval(all_scores) if all_scores else {}
        }
    
    def _generate_report(self):
        """生成报告"""
        summary = self._calculate_summary()

        print("\n" + "=" * 60, "多轮对话评估报告", "\n" + "=" * 60)
        print(f"总会话数: {summary.get("total_sessions", 0)}")
        print(f"总论次数: {summary.get("total_turns", 0)}")
        print(f"平均得分: {summary.get("avg_score", 0):.3f}")
        print(f"平均响应时间: {summary.get("avg_response_time", 0):0.3f}s")

        if "scores" in summary and summary["scores"]:
            conf = summary["scores"]
            print(f"置信区间(95%): [{conf.get('lower', 0):.3f}, {conf.get('upper', 0):.3f}]")
        print("=" * 60)