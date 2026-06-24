"""
医疗领域 Agent 的工作流图定义
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from core.graph_base import BaseGraph
from core.state_base import BaseState
from agents.domain.medical.prompts import (
    SYSTEM_PROMPT,
    SYMPTOM_ANALYSIS_PROMPT,
    DEBUG_QUERY_PROMPT,
    HOSPITAL_RECOMMENDATION_PROMPT,
    EMERGENCY_DETECTION_PROMPT
)

import logging

logger = logging.getLogger(__name__)

class MedicalState(BaseState):
    """医疗领域状态"""
    # 患者信息
    patient_age: Optional[int]
    patient_gender: Optional[str]
    patient_symptoms: List[str]
    symptom_duration: Optional[str]
    symptom_severity: Optional[int]

    # 分析结果
    possible_conditions: List[Dict[str, Any]]
    urgency_level: str  # low, medium, high, emergency
    recommendations: List[str]

    # 药品查询
    drug_name: Optional[str]
    drug_info: Optional[Dict[str, Any]]

    # 医院推荐
    location: Optional[str]
    hospital_results: List[Dict[str, Any]]

    # 安全标记
    requires_emergency: bool
    disclaimer_shown: bool

class MedicalGraph(BaseGraph):
    """医疗领域工作流图"""

    def __init__(self, checkpointer=None):
        super().__init__(
            name="medical_graph",
            state_class=MedicalState,
            checkpointer=checkpointer
        )
        logger.info("MedicalGraph initialized")

    def _add_nodes(self):
        """添加节点"""
        self.workflow.add_node("detect_emergency", self._detect_emergency)
        self.workflow.add_node("analyze_symptoms", self._analyze_symptoms)
        self.workflow.add_node("query_drug", self._query_drug)
        self.workflow.add_node("recommend_hospital", self._recommend_hospital)
        self.workflow.add_node("generate_advice", self._generate_advice)
        self.workflow.add_node("handle_emergency", self._handle_emergency)
        self.workflow.add_node("add_disclaimer", self._add_disclaimer)
        self.workflow.add_node("handle_error", self._handle_error)

    def _add_edges(self):
        """添加边"""
        # 入口 -> 紧急检测
        self.workflow.add_edge("detect_emergency", "analyze_symptoms")

        # 症状分析后的条件路由
        self.workflow.add_conditional_edges(
            "analyze_symptoms",
            self._route_after_analysis,
            {
                "drug_query": "drug_query",
                "hospital": "recommend_hospital",
                "advice": "generate_advice",
                "emergency": "handle_emergency",
                "error": "handle_error"
            }
        )

        # 药品查询 -> 建议生成
        self.workflow.add_edge("query_drug", "generate_advice")

        # 医院推荐 -> 建议生成
        self.workflow.add_edge("recommend_hospital", "generate_advice")

        # 紧急处理 -> 结束
        self.workflow.add_edge("handle_emergency", "add_disclaimer")

        # 建议生成 -> 免责声明
        self.workflow.add_edge("generate_advice", "add_disclaimer")

        # 免责声明 -> 结束
        self.workflow.add_edge("add_disclaimer", END)
        self.workflow.add_edge("handle_error", END)

    def _configure_entry_and_exit(self):
        """配置入口和出口"""
        self.workflow.set_entry_point("detect_emergency")

    async def _detect_emergency(self, state: MedicalState) -> MedicalState:
        """
        检测紧急情况
        """
        query = state.get("messages", [{}])[-1].get("content", "")
        symptoms = state.get("patient_symptoms", [])

        # 紧急关键词检测
        emergency_keywords = [
            "胸痛", "呼吸困难", "出血", "昏迷", "癫痫",
            "中风", "心脏病", "过敏反应", "窒息", "剧烈疼痛"
        ]

        state["requires_emergency"] = False
        state["requires_approval"] = False

        for keyword in emergency_keywords:
            if keyword in query or any(keyword in s for s in symptoms):
                state["requires_emergency"] = True
                state["urgency_level"] = "emergency"
                logger.warning(f"Emergency detected: {keyword}")
                break
        return state
    
    async def _analyze_symptoms(self, state: MedicalState) -> MedicalState:
        """
        分析症状
        """
        query = state.get("messages", [{}])[-1].get("content", "")
        # TODO: 调用 LLM 进行症状分析
        # 这里实现简化的分析逻辑
        
        # 提取症状
        symptoms = []
        common_symptoms = ["头痛", "发热", "咳嗽", "喉咙痛", "乏力", "恶心", "呕吐", "腹泻"]
        for s in common_symptoms:
            if s in query:
                symptoms.append(s)
        
        state["patient_symptoms"] = symptoms

        # 严重程度评估
        severity_keywords = {
            "high": ["剧烈", "严重", "无法忍受", "昏迷"],
            "medium": ["明显", "持续", "反复"],
            "low": ["轻微", "偶尔", "轻度"]
        }
        severity = "low"
        for level, keywords in severity_keywords:
            if any(kw in query for kw in keywords):
                severity = level
                break

        state["symptom_severity"] = 1 if severity == "low" else 2 if severity == "medium" else 3

        # 初步建议
        if state["requires_emergency"]:
            state["recommendations"] = ["请立即就医或拨打急救电话"]
        elif len(symptoms) == 0:
            state["recommendations"] = ["请提供更详细的症状表述以便分析"]
        else:
            state["recommendations"] = ["建议休息, 多喝水, 观察症状变化"]

        return state
    
    def _route_after_analysiz(self, state: MedicalState) -> MedicalState:
        """
        分析后的路由决策
        """
        if state.get("requires_emergency"):
            return "emergency"
        
        query = state.get("messages", [{}])[-1].get("content", "")

        if "药品" in query or "药物" in query or "药名" in query:
            return "drug_query"
        
        if "医院" in query or "就诊" in query or "挂号" in query:
            return "hospital"
        
        return "advice"
    
    async def _query_drug(self, state: MedicalState) -> MedicalState:
        """
        查询药品信息
        """
        query = state.get("messages", [{}])[-1].get("content", "")

        # TODO: 实现药品查询逻辑
        # 可以调用药品 API 或查询本地药品库

        state["drug_name"] = query
        state["drug_info"] = {
            "name": query,
            "category": "未知",
            "usage": "请咨询医生或药剂师",
            "side_effects": ["请咨询专业医疗人员"],
            "status": "查询中"
        }

        return state
    
    async def _recommend_hospital(self, state: MedicalState) -> MedicalState:
        """
        推荐医院
        """
        # TODO: 实现余元推荐逻辑
        # 可以调用地图 API 或查询本地医院数据库

        state["location"] = "用户位置"  # 从上下文获取
        state["hospital_results"] = [
            {
                "name": "示例医院",
                "distance": "2.5km",
                "department": "全科",
                "phone": "010-12345678"
            }
        ]
        
        return state
    
    async def _generate_advice(self, state: MedicalState) -> MedicalState:
        """生成医疗建议"""
        # 构建建议内容
        advice_parts = []

        # 症状分析结果
        if state.get("patient_symptoms"):
            advice_parts.append(f"症状分析: {', '.join(state('patient_symptoms'))}")

        # 严重程度
        severity_map = {1: "低", 2: "中", 3: "高"}
        severity = state.get("symptom_severity", 1)
        advice_parts.append(f"严重程度: {severity_map.get(severity, '未知')}")

        # 建议
        if state.get("recommendations"):
            advice_parts.append("\n建议:")
            for rec in state["recommendations"]:
                advice_parts.append(f"- {rec}")

        # 药品信息
        if state.get("drug_info"):
            drug = state["drug_info"]
            advice_parts.append(f"\n药品信息: {drug.get('name', '未知')}")

        # 医院信息
        if state.get("hospital_results"):
            hospital = state["hospital_results"][0]
            advice_parts.append(f"\n推荐医院: {hospital.get('name', '未知')}")
            advice_parts.append(f"距离: {hospital.get('distance', '未知')}")

        state["final_answer"] = "\n".join(advice_parts)

        return state
    
    async def _handle_emergency(self, state: MedicalState) -> MedicalState:
        """
        处理紧急情况
        """
        state["final_answer"] = """
**紧急情况检测**

检测到您可能处于紧急医疗状况. 请立即:
1. 拨打急救电话(120)
2. 寻求附近医疗帮助
3. 不要自行驾车前往医院

**重要**: 这是紧急情况, 请立即采取行动!
"""
        return state
    
    async def _add_disclaimer(self, state: MedicalState) -> MedicalState:
        """
        添加免责声明
        """
        disclaimer = """

---
**免责声明**:
以上建议仅供参考, 不构成医疗诊断.
如有不适, 请及时就医.
AI Agent 不能替代专业医生的诊断和治疗.
"""
        if state.get("final_answer"):
            state["final_answer"] = state["final_answer"] + disclaimer

        state["disclaimer_shown"] = True
        return state
    
    async def _handle_error(self, state: MedicalState) -> MedicalState:
        """
        处理错误
        """
        state["status"] = "failed"
        state["final_answer"] = "抱歉, 医疗咨询处理出现错误. 请稍后重试或直接咨询医生."
        return state