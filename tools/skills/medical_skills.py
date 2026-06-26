"""
医疗领域 Skills
提供药品查询、症状分析、医院推荐等功能
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from tools.registry import register
import logging

logger = logging.getLogger(__name__)

# 模拟药品数据库
DEBUG_DTABASE = {
    "布洛芬": {
        "category": "非甾体抗炎药",
        "usage": "缓解轻至中度疼痛, 退热",
        "dosage": "承认: 200-400mg, 每日最多4次",
        "side_effects": ["肠胃不适", "头痛", "皮疹"],
        "contraindications": ["消化道溃疡", "严重肝肾损伤", "孕妇慎用"],
        "interactions": ["抗凝血药", "其他 NSAIDS"]
    },
    "对乙酰氨基酚": {
        "category": "解热镇痛药",
        "usage": "退热, 缓解轻中度疼痛",
        "dosage": "成人: 500-1000mg, 每日最多4次, 24小时不到4000mg",
        "side_effects": ["肝功能异常", "皮疹"],
        "contraindications": ["严重肝功能不全", "对本品过敏"],
        "interactions": ["抗凝血药"]
    },
    "阿莫西林": {
        "category": "抗生素(青霉素类)",
        "usage": "细菌感染",
        "dosage": "成人: 500mg, 每日3次",
        "side_effects": ["胃肠道反应", "过敏反应", "皮疹"],
        "contraindications": ["青霉素过敏", "传染性单核细胞增多症"],
        "interactions": ["口服避孕药", "丙磺舒"]
    }
}

@register(name="drug_query", schema={
    "name": "drug_query",
    "description": "查询药品信息",
    "parameters": {
        "type": "object",
        "properties": {
            "drug_name": {
                "type": "string",
                "description": "药品名称"
            },
            "detail_level": {
                "type": "string",
                "enum": ["basic", "detailed", "full"],
                "description": "详细程度",
                "default": "basic"
            }
        },
        "required": ["drug_name"]
    }
})
async def drug_query(
    drug_name: str,
    detail_level: str = "basic"
) -> Dict[str, Any]:
    """
    查询药品信息
    Args:
        drug_name: 药品名称
        detail_level: 详细程度
    Returns:
        药品信息
    """
    # 查询药品数据库
    drug_info = DEBUG_DTABASE.get(drug_name)

    if not drug_info:
        # 尝试模糊匹配
        for known_drug in DEBUG_DTABASE.keys():
            if drug_name in known_drug or known_drug in drug_name:
                drug_info = DEBUG_DTABASE[known_drug]
                drug_name = known_drug
                break

    result = {
        "name": drug_name,
        "found": drug_info is not None,
        "timestamp": datetime.now().isoformat(),
        "disclaimer": "药品信息仅供参考, 具体用药请遵医嘱"
    }

    if drug_info:
        result.update(drug_info)

        # 根据详细程度裁剪信息
        if detail_level == "basic":
            result.pop("intercations", None)
            result.pop("contraindications", None)
        elif detail_level == "detailed":
            # 保存所有信息
            pass
    else:
        result["message"] = f"未找到药品 '{drug_name}' 的信息"

    return result

@register(name="symptom_analysis", schema={
    "name": "symptom_analysis",
    "description": "分析症状并提供初步建议",
    "parameters": {
        "type": "object",
        "properties": {
            "symptoms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "症状列表"
            },
            "duration": {
                "type": "string",
                "description": "持续时间"
            },
            "severity": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "严重程度(1-10)"
            }
        },
        "required": ["symptoms"]
    }
})
async def symptom_analysis(
    symptoms: List[str],
    duration: Optional[str] = None,
    severity: int = 5
) -> Dict[str, Any]:
    """
    症状分析
    Args:
        symptoms: 症状列表
        duration: 持续时间
        severity: 严重程度
    Returns:
        分析结果
    """
    # TODO: 接入专业的医学知识库

    # 简单分析
    possible_conditions = []
    recommendations = []

    if "头痛" in symptoms:
        possible_conditions.append({"condition": "紧张性头痛", "confidence": 0.4})
        possible_conditions.append({"condition": "偏头痛", "confidence": 0.3})
        recommendations.append("建议休息, 避免用眼过度")

    if "发热" in symptoms and severity > 5:
        possible_conditions.append({"condition": "感染", "confidence": 0.5})
        recommendations.append("建议测量体温, 如持续发热请就医")

    if "咳嗽" in symptoms:
        possible_conditions.append({"condition": "上呼吸道感染", "confidence": 0.6})
        recommendations.append("建议多喝水, 保持空气湿润")

    # 紧急程度判断
    urgency_level = "low"
    if severity > 8:
        urgency_level = "high"
    elif severity > 5:
        urgency_level = "medium"

    if "胸痛" in symptoms or "呼吸困难" in symptoms:
        urgency_level = "emergency"
        recommendations.insert(0, "请立即就医!")

    result = {
        "symptoms": symptoms,
        "duration": duration,
        "possible_conditions": possible_conditions,
        "recommendations": recommendations,
        "urgency_level": urgency_level,
        "disclaimer": "以上建议仅供参考, 不构成医疗诊断. 如有不适, 请及时就医.",
        "timestamp": datetime.now().isoformat()
    }

    return result

@register(name="hospital_recommendation", schema={
    "name": "hospital_recommendation",
    "description": "根据位置和需求推荐医院",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "位置信息"
            },
            "department": {
                "type": "string",
                "description": "科室名称"
            },
            "emergency": {
                "type": "boolean",
                "description": "是否急诊",
                "default": False
            }
        },
        "required": ["location"]
    }
})
async def hospital_recommendation(
    location: str,
    department: Optional[str] = None,
    emergency: bool = False
) -> Dict[str, Any]:
    """
    推荐医院
    Args:
        location: 位置
        department: 科室
        emergency: 是否急诊
    Returns:
        医院推荐结果
    """

    # TODO: 接入地图 API 或医院数据库
    
    # 模拟医院数据
    hospitals = [
        {
            "name": "市第一人民医院",
            "address": f"{location}中心路22号",
            "distance": "2.5km",
            "rating": 4.3,
            "departments": ["内科", "外科", "急诊科", "妇产科"],
            "phone": "010-12345678",
            "emergency": True
        },
        {
            "name": "市立中心医院",
            "address": f"{location}健康路33号",
            "distance": "5.0km",
            "rating": 4.1,
            "departments": ["内科", "外科", "急诊科", "心内科"],
            "phone": "010-87654321",
            "emergency": True
        },
        {
            "name": "市妇幼保健院",
            "address": f"{location}花园路63号",
            "distance": "3.8km",
            "rating": 4.0,
            "departments": ["妇产科", "儿科", "妇科"],
            "phone": "010-98765432",
            "emergency": False
        }
    ]

    # 根据可是和紧急情况筛选
    if department:
        hospitals = [h for h in hospitals if department in h["departments"]]

    if emergency:
        hospitals = [h for h in hospitals if h["emergency"]]

    result = {
        "location": location,
        "department": department,
        "emergency": emergency,
        "hospitals": hospitals,
        "count": len(hospitals),
        "timestamp": datetime.now().isoformat()
    }