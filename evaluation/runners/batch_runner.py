import json
import csv
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from graphs.main_graph import MainGraph
from evaluation.graders.llm_grader import LLMGrader
from evaluation.graders.code_grader import CodeGrader
from evaluation.graders.metrics import MetricsCalculator
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import asyncio
import logging

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """任务执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

@dataclass
class EvaluationResult:
    """评估结果数据类"""
    task_id: str
    task_name: str
    status: TaskStatus
    input_query: str
    expected_output: Optional[str] = None
    actual_output: Optional[str] = None
    execution_time: float = 0.0
    token_usage: Dict[str, int] = field(default_factroy=dict)
    grader_scores: Dict[str, float] = field(default_factory=dict)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "input_query": self.input_query,
            "expected_output": self.expected_output,
            "actual_output": self.actual_output,
            "execution_time": self.execution_time,
            "token_usage": self.token_usage,
            "grader_scores": self.grader_scores,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }

class BatchRunner:
    """批量评估执行器"""

    def __init__(self, eval_file: str, output_dir: Optional[str]=None, max_concurrent: int=0, timeout: int=60, graders: Optional[List[str]]=None):
        """
        初始化批量评估执行器
        
        Args:
            eval_file: 评估任务文件路径(支持.json, .csv, .xlsx)
            output_dir: 输出结果目录
            max_concurrent: 最大并发数
            timeout: 单个任务超时时间(秒)
            graders: 使用的评分器列表['llm', 'code', 'exact_match', 'semantic']
        """
        self.eval_file = Path(eval_file)
        self.output_dir = Path(output_dir) if output_dir else Path("evaluation/results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.grader = self.grader or ["llm", "exact_match"]

        self.tasks = self._load_tasks()
        self.results: List[EvaluationResult] = []
        self.main_graph = MainGraph()

        # 初始化评分器
        self._init_graders()

        # 统计信息
        self.stats = {
            "total": len(self.tasks),
            "completed": 0,
            "failed": 0,
            "timeout": 0,
            "avg_score": 0.0,
            "total_tokens": 0,
            "total_time": 0.0
        }

    def _init_graders(self):
        """初始化评分器"""
        self.grader_instances = {}

        if "llm" in self.graders:
            self.grader_instances["llm"] = LLMGrader()
        if "code" in self.graders:
            self.grader_instances["code"] = CodeGrader()
        if "exect_match" in self.graders:
            # 精确匹配评分器(内置)
            self.grader_instances["exect_match"] = self._exact_grader
        if "semantic" in self.graders:
            # TODO: 语义相似度评分器(使用embedding)
            self.grader_instances["semantic"] = self._semantic_similarity_grader

        # 初始化指标计算器
        self.metrics_calculator = MetricsCalculator()

    def _load_tasks(self) -> List[Dict]:
        """加载评估任务, 支持多种格式"""
        # - 支持 JOSN/CSV 格式
        # - 任务数据校验
        # - 支持数据集成版本管理
        
        if not self.eval_file.exists():
            raise FileNotFoundError(f"评估文件不存在: {self.eval_file}")
        
        suffix =  self.eval_file.suffix.lower()

        try:
            if suffix == ".json":
                return self._load_json_tasks()
            elif suffix == ".csv":
                return self._load_csv_tasks()
            elif suffix in [".xlsx", ".xls"]:
                return self._load_excel_tasks()
            else:
                raise ValueError(f"不支持的文件格式: {suffix}")
        except Exception as e:
            logger.error(f"加载任务文件失败: {e}")
            raise

    def _load_json_tasks(self) -> List[Dict]:
        """加载 JSON 格式任务"""
        with open(self.eval_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 支持两种 JSON 格式
        # 1. {"tasks": [...]}
        # 2. [...]
        if isinstance(data, dict):
            tasks = data.get("tasks", data.get("data", []))
        else:
            tasks = data
        
        # 验证并标准化任务格式
        validated_tasks = []
        for i, task in enumerate(tasks):
            validated_task = self._validate_task(task, i)
            validated_tasks.append(validated_task)

        logger.info(f"从 JSON 加载了 {len(validated_tasks)} 个任务")
        return validated_tasks
    
    def _load_csv_task(self) -> List[Dict]:
        """加载 CSV 格式任务"""
        tasks = []
        with open(self.eval_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                task = {
                    "query": row.get("query", ""),
                    "expected": row.get("expected", ""),
                    "domain": row.get("domain", "general"),
                    "task_name": row.get("task_name", f"task_{i}")
                }
                tasks.append(self._validate_task(task, i))
        
        logger.info(f"从 CSV 加载了 {len(tasks)} 个任务")
        return tasks
    
    def _load_excel_tasks(self) -> List[Dict]:
        """加载 Excel 格式任务"""
        df = pd.read_excel(self.eval_file)
        tasks = []
        for i, row in df.iterrows():
            task = {
                "query": str(row.get("query", "")),
                "expected": str(row.get("expected", "")),
                "domain": str(row.get("domain", "general")),
                "task_name": str(row.get("task_name", f"task_{i}"))
            }
            tasks.append(self._validate_task(task, i))

        logger.info(f"从 Excel 加载了 {len(tasks)} 个任务")
        return tasks
    
    def _validate_task(self, task: Dict, index: int) -> Dict:
        """验证并标准化单个任务"""
        validated = {
            "id": task.get("id", f"task_{index:04d}"),
            "task_name": task.get("task_name", f"Task {index}"),
            "query": task.get("query", task.get("input", task.get("question", ""))),
            "expected": task.get("expected", task.get("expected_output", task.get("answer", ""))),
            "domain": task.get("domain", "general"),
            "context": task.get("context", {}),
            "metadata": task.get("metadata", {})
        }

        # 验证必填字段
        if not validated["query"]:
            logger.warning(f"任务 {index} 缺少 query 字段")
            validated["query"] = ""

        return validated
    
    def _exact_match_grader(self, expected: str, actual: str) -> float:
        """精确匹配评分器"""
        if not expected or not actual:
            return 0.0
        # 清理空白字符串后比较
        expected_clean = expected.strip().lower()
        actual_clean = actual.strip().lower()
        return 1.0 if expected_clean == actual_clean else 0.0
    
    def _semantic_similarity_grader(self, expected: str, actual: str) -> float:
        """语义相似度评分器"""
        # TODO
        # - 使用 embedding 模型计算语义相似度
        # - 返回 0-1 之间的分数
        # - 缓存 embedding 结果
        return 0.0  # 占位
    
    async def _evaluate_single_task(self, task: Dict) -> EvaluationResult:
        """评估单个任务"""
        start_time = datetime.now()

        result = EvaluationResult(
            task_id = task["id"],
            task_name = task["task_name"],
            status = TaskStatus.PENDING,
            input_query = task["query"],
            expected_output = task.get("expected"),
            metadata = task.get("metadata", {})
        )

        try:
            # 执行任务
            state = {
                "messages": [{"role": "user", "content": task["query"]}],
                "domain": task.get("domain", "general"),
                "metadata": task.get("context", {})
            }

            # 带超时的执行
            async with asyncio.timeout(self.timeout):
                output = await self._execute_with_retry(state)

            # 记录实际输出
            result.actual_output = output.get("final_anwer", "")
            result.status = TaskStatus.COMPLETED

            # 计算 Token 使用量(示例)
            result.token_usage = {
                "prompt_tokens": output.get("prompt_tokens", 0),
                "completion_tokens": output.get("completion_tokens", 0),
                "total_tokens": output.get("total_tokens", 0)
            }

            # 运行评分器
            scores = {}
            for grader_name, grader in self.grader_instances.items():
                try:
                    if isinstance(grader, (LLMGrader, CodeGrader)):
                        # 异步评分器
                        score = await grader.grade(
                            expected = task.get("expected", ""),
                            actual = result.actual_output,
                            context = task.get("context", {})
                        )
                    else:
                        # 同步评分器
                        score = grader(
                            expected = task.get("expected", ""),
                            actual = result.actual_output
                        )
                    scores[grader_name] = float(score)
                except Exception as e:
                    logger.error(f"评分器 {grader_name} 失败: {e}")
                    scores[grader_name] = 0.0

            result.grader_scores = scores

            # 更新统计信息
            self.stats["completed"] += 1
            self.stats["total_tokens"] += sum(result.token_usage.values())

        except asyncio.TimeoutError:
            result.status = TaskStatus.TIMEOUT
            result.error_message = f"任务超时 ({self.timeout}) 秒"
            self.stats["timeout"] += 1
            self.stats["failed"] += 1

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            self.stats["failed"] += 1
            logger.error(f"任务 {task['id']} 执行失败: {e}")

        # 计算执行时间
        result.execution_time = (datetime.now() - start_time).total_seconds()
        self.stats["total_time"] += result.execution_time

        # 添加到结果列表
        self.results.append(result)
        
        return result
    
    async def _execute_with_retry(self, state: Dict, max_retries: int = 2) -> Dict:
        """带重试的任务执行"""
        for attempt in range(max_retries + 1):
            try:
                # TODO: 集成重试逻辑
                # result = await self.main_graph.graph.ainvoke(state)
                # 临时返回占位结果
                result = {
                    "final_answer": f"执行结果占位 (attempt {attempt + 1})",
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150
                }
                return result
            except Exception as e:
                if attempt == max_retries:
                    raise
                logger.warning(f"执行失败, 重试 {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(1 * (attempt + 1))  # 指数退避

        return {}
    
    async def run(self) -> List[EvaluationResult]:
        """
        执行批量评估
        
        Returns:
            评估结果列表
        """
        logger.info(f"开始批量评估, 供 {len(self.tasks)} 个任务")
        logger.info(f"最大并发数: {self.max_concurrent}, 超时时间: {self.timeout}秒")
        logger.info(f"评分器: {self.graders}")

        # 创建任务队列
        task_queue = asyncio.Queue()
        for task in self.tasks:
            await task_queue.put(task)
        
        # 创建工作线程
        workers = []
        for _ in range(min(self.max_concurrent, len(self.tasks))):
            worker = asyncio.create_task(self._worker(task_queue))
            workers.append(worker)
        
        # 等待所有任务完成
        await task_queue.join()

        # 取消工作线程
        for worker in workers:
            worker.cancel()

        # 保存结果
        self._save_results()
        self._generate_report()
        
        logger.info(f"批量评估完成: 成功 {self.stats['completed']}, 失败 {self.stats['failed']}, 超时 {self.stats['timeout']}")

        return self.results
    
    async def _worker(self, task_queue: asyncio.Queue):
        """工作线程"""
        while True:
            try:
                task = await task_queue.get()
                await self._evaluate_single_task(task)
                task_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"工作线程异常: {e}")
                task_queue.task_done()

    def _save_results(self):
        """保存评估结果"""
        # 保存为 JSON 格式
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"eval_results_{timestamp}.json"

        results_data = {
            "timestamp": timestamp,
            "stats": self.stats,
            "results": [r.to_dict() for r in self.results]
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)

        logger.info(f"结果已保存到: {output_file}")

        # 可选: 保存为 CSV 格式
        if self.results:
            csv_file = self.output_dir / f"eval_results_{timestamp}.csv"
            df = pd.DataFrame([r.to_dict() for r in self.results])
            df.to_csv(csv_file, index=False, encoding="utf-8-sig")
            logger.info(f"CSV 结果已保存到: {csv_file}")

    def _generate_report(self):
        """生成评估报告"""
        if not self.results:
            return
        
        # 计算统计指标
        scores = []
        for r in self.results:
            if r.grader_scores:
                avg_score = sum(r.grader_scores.values()) / len(r.grader_scores)
                scores.append(avg_score)
        
        if scores:
            import statistics
            self.stats["avg_score"] = statistics.mean(scores)
            self.stats["median_score"] = statistics.median(scores)
            self.stats["min_score"] = min(scores)
            self.stats["max_score"] = max(scores)

        # 按领域统计
        domain_stats = {}
        for r in self.results:
            domain = r.metadata.get("domain", "unknown")
            if domain not in domain_stats:
                domain_stats[domain] = {"total": 0, "passed": 0}
            domain_stats[domain]["total"] += 1
            if r.status == TaskStatus.COMPLETED:
                domain_stats[domain]["passed"] += 1
            
        # 保存报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(self.tasks),
            "completed": self.stats["completed"],
            "failed": self.stats["failed"],
            "timeout": self.stats["timeout"],
            "success_rate": self.stats["completed"] / len(self.tasks) if self.tasks else 0,
            "avg_score": self.stats.get("avg_score", 0),
            "median_score": self.stats.get("median_score", 0),
            "total_tokens": self.stats["total_tokens"],
            "total_time": self.stats["total_time"],
            "avg_time": self.stats["total_time"] / len(self.tasks) if self.tasks else 0,
            "domain_stats": domain_stats
        }

        report_file = self.output_dir / f"eval_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"评估报告已生成: {report_file}")

        # 打印报告
        self._print_summary(report)
    
    def _print_summary(self, report: Dict):
        """打印评估摘要"""
        print("\n" + "=" * 60)
        print(f"评估结果摘要")
        print("=" * 60)
        print(f"总任务数: {report['total_tasks']}")
        print(f"成功: {report['completed']} ({report['success_rate'] * 100:.1f})")
        print(f"失败: {report['failed']}")
        print(f"超时: {report['timeout']}")
        print(f"平均分: {report['avg_score']:.3f}")
        print(f"中位数分: {report['median_score']:.3f}")
        print(f"总耗时: {report['total_time']:.3f}秒")
        print(f"平均耗时: {report['avg_time']:.3f}秒")
        print(f"Token 使用: {report['total_tokens']}")
        print(f"\n领域统计:")
        for domain, stats in report.get("domain_stats", {}).items():
            pass_rate = stats["passed"] / stats["total"] * 100 if stats["passed"] > 0 else 0
            print(f"- {domain}: {stats['passed']} / {stats['total']} ({pass_rate:.1f%})")
        print("=" * 60)

    def get_failed_tasks(self) -> List[EvaluationResult]:
        """获取失败的任务列表"""
        return [r for r in self.results if r.status in [TaskStatus.FAILED, TaskStatus.TIMEOUT]]
    
    def get_best_tasks(self, top_n: int=5) -> List[EvaluationResult]:
        """获取评分最高的任务"""
        sorted_results = sorted(
            [r for r in self.results if r.grader_scores],
            key=lambda x: sum(x.grader_scores.values()) / len(x.grader_scores) if x.grader_scores else 0,
            reverse=True
        )
        return sorted_results[:top_n]
    
    def get_worst_tasks(self, top_n: int=5) -> List[EvaluationResult]:
        """获取评分最低的任务"""
        sorted_results =  sorted(
            [r for r in self.results if r.grader_scores],
            key=lambda x: sum(x.grader_scores.values()) / len(x.grader_scores) if x.grader_scores else 999,
            reverse=False
        )
        return sorted_results[:top_n]
    
# 命令行入口
async def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="批量评估执行器")
    parser.add_argument("eval_file", type=str, help="评估任务文件路径")
    parser.add_argument("--output", "-o", type=str, default="evaluation/results", help="输出目录")
    parser.add_argument("--concurrent", "-c", type=int, default=5, help="最大并发数")
    parser.add_argument("--timeout", "-t", type=int, default=60, help="单个任务超时时间(秒)")
    parser.add_argument("--graders", "-g", type=str, default="llm,exact_match", help="评分器列表, 逗号分隔(llm, code, exact_match, semantic)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 配置日志
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    # 创建执行器
    grader_list = [g.strip() for g in args.graders.split(",")]

    runner = BatchRunner(
        eval_file=args.eval_file,
        output_dir=args.output,
        max_concurrent=args.max_concurrent,
        timeout=args.timeout,
        graders=grader_list
    )

    # 执行评估
    try:
        results = await runner.run()

        # 打印失败任务
        failed = runner.get_failed_tasks()
        if failed:
            print(f"\n有 {len(failed)} 个任务失败:")
            for task in failed:
                print(f"- {task.task_name}: {task.error_message}")
        
        # 打印最佳和最差任务
        if results:
            print(f"\n最佳任务:")
            for task in runner.get_best_tasks(3):
                avg_score = sum(task.grader_scores.values()) / len(task.grader_scores) if task.grader_scores else 0
                print(f"- {task.task_name}: {avg_score:.3f}")
            print(f"\n最差任务:")
            for task in runner.get_worst_tasks(3):
                avg_score = sum(task.grader_scores.values()) / len(task.grader_scores) if task.grader_scores else 0
                print(f"- {task.task_name}: {avg_score:.3f}")

    except KeyboardInterrupt:
        print(f"\n用户中断")
    except Exception as e:
        logger.error(f"执行失败: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())