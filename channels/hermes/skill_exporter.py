"""
完整集成: 将 Langraph 多智能体系统接入 Hermes
- 路径A: 封装为 Hermes 技能
- 路径B: 统一消息网关
- 路径C: 于一路由替代关键词匹配
"""
import os
import asyncio
import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from pydantic import BaseModel
from contextlib import asynccontextmanager
from llama_index.llms.ollama import Ollama
from agents.specialized.component.approval_agent_humaninloop import handle_delete_kg
from config.settings import SECRET_TOKEN, ANGET_API_URL, SKILL_PATH

# ========== 集成层 ==========
class SkillExporter:
    """
    技能类
    """

    def __init__(self, graph):
        """初始类"""
        self.graph = graph

    def get_all_skill_definitions(self) -> Dict[str, Dict]:
        """
        获取所有技能定义
        这些定义会被写入 SKILL.md 文件供 Hermes 发现
        """
        return {
            "rag_query": {
                "name": "rag_query",
                "description": "检索知识库并回答问题. 支持文档搜索、知识图谱查询. 当用户询问知识库中的信息、任务介绍、技术问题时使用.",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "用户的问题",
                        "required": True
                    }
                },
                "examples": [
                    {"query": "伍凯桃是谁"},
                    {"query": "介绍中山市"},
                    {"query": "什么是RAG"}
                ],
                "route": "rag"
            },
            "multimodal_generate": {
                "name": "multimodal_generate",
                "description": "生成图片、理解图片内容. 支持文生图、图生文.",
                "parameters": {
                    "prompt": {
                        "type": "string",
                        "description": "图片描述或生成指令",
                        "required": True
                    }
                },
                "examples": [
                    {"prompt": "生成一只可爱的柴犬"},
                    {"prompt": "画一幅山水画"}
                ],
                "route": "multimodal"
            },
            "approval_submit": {
                "name": "approval_submit",
                "description": "提交审批申请. 支持请假、报销、项目立项等. 当用户提交申请时使用.",
                "parameters": {
                    "content": {
                        "type": "string",
                        "description": "申请内容",
                        "required": True
                    },
                    "type": {
                        "type": "string",
                        "description": "申请类型 - leave(请假)/expense(报销)/project(项目)",
                        "required": False,
                        "default": "general"
                    }
                },
                "examples": [
                    {"content": "我想请3天年假", "type": "leave"},
                    {"content": "报销差旅费500元", "type": "expense"}
                ],
                "route": "approval"
            },
            "approval_handle": {
                "name": "approval_handle",
                "description": "处理审批 - 通过、驳回或转交. 当用户作为审批人需要处理待办申请时使用.",
                "parameters": {
                    "action": {
                        "type": "string",
                        "description": "操作: approve/reject/transfer",
                        "required": True
                    },
                    "request_id": {
                        "type": "string",
                        "description": "申请单号",
                        "required": True
                    },
                    "comment": {
                        "type": "string",
                        "description": "审批意见|转交人",
                        "required": False
                    }
                },
                "examples": [
                    {"action": "approve", "request_id": "REQ202412011200001"},
                    {"action": "reject", "request_id": "REQ202412011200001", "comment": "理由不充分"},
                    {"action": "transfer", "request_id": "REQ202412011200001", "comment": "张三"}
                ],
                "route": "approval"
            },
            "delete_knowledge_graph": {
                "name": "delete_knowledge_graph",
                "description": "删除知识图谱中的所有数据. 危险操作, 需要二次确认. 当用户明确要求删除知识图谱时使用.",
                "parameters": {
                    "confirm": {
                        "type": "boolean",
                        "description": "是否确认删除",
                        "required": True
                    }
                },
                "warning": "此操作不可恢复, 必须要求用户二次确认后才能执行",
                "examples": [
                    {},
                    {"confirm": True},
                    {"confirm": False}
                ],
                "route": "approval"
            }
        }
    
    def get_skill_definition(self, skill_name: str | None) -> Optional[Dict]:
        """获取单个技能定义"""
        skills = self.get_all_skill_definitions()
        return skills.get(skill_name) if skill_name else None
    
    def execute_skill(self, skill_name: str | None, params: Dict, context: Dict) -> Dict:
        """
        执行技能: 通过 HTTP API 调用你的 LangGraph Agent

        Args:
            skill_name: 技能名称(rag_query/multimodal_generate/approval_submit/approval_handle/delete_knowledge_graph等)
            params: 技能参数
            context: Hermes 上下文, 包含 user, thread_id 等
        Returns:
            {"response": "回答内容", "image": "图片路径(可选)"}
        """
        # 构建状态
        state = {
            "user": context.get("user", "hermes_user"),
            "token": SECRET_TOKEN,
            "from_skill": skill_name
        }

        # 根据技能类型构造查询
        if skill_name == "rag_query":
            state["query"] = params.get("query", "")
        elif skill_name == "multimodal_generate":
            state["query"] = f"生成图 {params.get("prompt", "")}"
        elif skill_name == "approval_submit":
            req_type = params.get("type", "general")
            state["query"] = params.get("content", "")
        elif skill_name == "approval_handle":
            action = params.get("action", "")
            req_id = params.get("request_id", "")
            comment = params.get("comment", "")
            state["query"] = f"{action} {req_id} {comment}"
        elif skill_name == "delete_knowledge_graph":
            result = handle_delete_kg(params, context)
            return {
                "response": result.get("response", "")
            }

        print(f"***** state: {state} *****")
        if not state.get("query"):
            return {"response": f"无法处理技能 {skill_name}, 请检查参数"}
        
        # 调用 LangGraph API
        try:
            response = requests.post(
                ANGET_API_URL,
                json={
                    "user": state["user"],
                    "query": state["query"],
                    "thread_id": context.get("thread_id", "hermes_default_thread"),
                    "from_skill": state["from_skill"]
                },
                headers={
                    "Authorization": f"Bearer {SECRET_TOKEN}"
                },
                timeout=180
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "response": result.get("response", "处理完成"),
                    "image": result.get("image")
                }
            else:
                return {
                    "response": f"API 调用失败: {response.status_code}"
                }
        except requests.exceptions.ConnectionError:
            return {
                "response": "无法连接到 Agent 服务, 请确保 app.py 正在运行."
            }
        except Exception as e:
            return {
                "response": f"执行失败: {str(e)}"
            }
        
    def generate_skill_md_files(self, output_dir: str = SKILL_PATH):
        """
        为每个技能生成独立的 SKILL.md 文件
        Hermes 会自动扫描这个目录并加载技能
        """
        skills = self.get_all_skill_definitions()

        # 展开用户目录
        output_dir = os.path.expanduser(output_dir)

        for skill_name, skill_def in skills.items():
            # 创建技能目录
            skill_dir = os.path.join(output_dir, skill_name)
            os.makedirs(skill_dir, exist_ok=True)

            # 生成 SKILL.md 内容
            skill_md = f"""---
name: {skill_def['name']}
description: {skill_def['description']}
version: 1.0.0
---

# {skill_def['name']}

## 描述
{self._format_params(skill_def.get('parameters', {}))}

## 示例
{self._format_examples(skill_def.get('examples', []))}

## 执行指令
当用户请求符合此技能描述时, 请构造以下 API 请求:

```json
POST http://localhost:8001/api/skill/{skill_name}
Content-Type: application/json
{{
    "skill": "{skill_name}",
    "params": {self._format_params_json(skill_def.get('parameters', {}))},
    "context": {{
        "user": "{{user}}",
        "thread_id": "{{thread_id}}"
    }}
}}
```
## 注意事项
- 必须等待 API 返回结果后再回复用户
- 如果 API 返回 image 字段, 需要以适当方式展示图片
- 对于 delete_knowledge_graph 技能, 必须先确认用户意图
"""
            # 写入文件
            md_path = os.path.join(skill_dir, "SKILL.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(skill_md)
                print(f"已生成技能文件: {md_path}")

        print(f"所有技能已生成到: {output_dir}")
        print(f"请重启 Hermes 或运行'/skills reload'加载新技能")
        
    def _format_params(self, params: Dict) -> str:
        """格式参数为 Markdown 表格"""
        if not params:
            return "无参数"
        
        lines = ["|参数名|类型|必填|描述|", "|------|----|----|----|"]
        for name, info in params.items():
            required = "是" if info.get("required") else "否"
            lines.append(f"|{name}|{info.get('type')}|{required}|{info.get('description')}|")
        return "\n".join(lines)

    def _format_examples(self, examples: list) -> str:
        """格式化示例"""
        if not examples:
            return "无示例"
        
        lines = []
        for ex in examples:
            lines.append(f"- {json.dumps(ex, ensure_ascii=False)}")
        return "\n".join(lines)
    
    def _format_params_json(self, params: Dict) -> str:
        """格式化参数为 JSON 示例"""
        if not params:
            return "{}"
        
        example = {}
        for name, info in params.items():
            if info.get("type") == "string":
                example[name] = f"<{name}>"
            elif info.get("type") == "boolean":
                example[name] = False
            elif info.get("type") == "integer":
                example[name] = 0
        return json.dumps(example, ensure_ascii=False)