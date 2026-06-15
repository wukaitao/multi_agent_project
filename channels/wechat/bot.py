"""
微信插件 ClawBot 集成: 将 Langraph 多智能体系统接入 wechat, 实现类似微信好友聊天的交互体验
- getUpdates[ilink/bot/getupdates]: 长轮询拉取新消息
- sendMessage[ilink/bot/sendmessage]: 发送消息给用户
- getUploadUrl[ilink/bot/getuploadurl]: 获取媒体文件上传地址
- getConfig[ilink/bot/getconfig]: 获取正在输入凭证
- sendTyping[ilink/bot/sendtyping]: 发送[正在输入]状态

# 实现流程: 本地windows内网穿透(ngrok http 8001) -> 通过扫描二维码获取 bot_token -> [getConfig 获取账号配置 ->] getUpdates -> 处理消息(调用 Langgraph Agent) [-> getUploadUrl 上传文件到微信服务器]  -> sendMessage 回复消息给用户 -> sendTyping 控制输入状态
"""
import asyncio
import httpx
import os
import json
import base64
import random
from datetime import datetime
from typing import Optional, Dict, Any
from config.settings import BOT_BASE_URL, BOT_TYPE, ANGET_API_URL, QRCODE_STATUS_PATH
from channels.wechat.handlers import build_headers, upload_media

# ========== ClawBot 微信插件集成 ==========

# ========== 1. getUpdates 长轮询获取消息 ==========
async def get_updates(bot_token: str, get_updates_buf: str = ""):
    """"
    长轮询获取新消息
    Args:
        get_updates_buf: ""    # 上次拉取的未知标识, 首次为空

    Returns:
        get_updates_buf: "new_buf_value_12345"    # 新的未知标识
        msgs: [
            {
                "msg_id": "123456",
                "from_user_id": "user_abc",
                "to_user_id": "bot_xyz",
                "msg_type": "text",
                "content": "用户发的消息内容",
                "timestamp": 1234567890
            }
        ]
    """
    print(f"========== get_updates 节点 ==========")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{BOT_BASE_URL}/ilink/bot/getupdates",
                json={"get_updates_buf": get_updates_buf},
                headers=build_headers(bot_token),
                timeout=10
            )
            data = response.json()
            print(f"---------- get_updates data: {data} ----------")
            get_updates_buf = data.get("get_updates_buf", "")
            msgs = data.get("msgs", [])
            return msgs, get_updates_buf
        except httpx.RequestError as e:
            # 长轮询超时是正常的
            print(f"---------- get_updates timeout ----------")
            return [], get_updates_buf
        except Exception as e:
            print(f"get_updates 异常: {str(e)}")
            return None, get_updates_buf

# ========== 2. sendMessage 发送消息给用户 ==========
async def send_message(bot_token, to_user_id, text, context_token, client_id: str, type: str, typing_ticket: str):
    """
    发送消息给用户
    type: 消息类型(text/image/voice/video/file)
    message_type: 1 固定值 - 单聊普通业务消息(图文/语音/文件/视频都归在此大类); 2 - 群消息; 3 - 系统通知; 4 - 事件推送（入群/被撤回等)
    """
    print(f"========== send_message 节点 ==========")
    item_list = []
    if type == "text":
        item_list = [{
            "type": 1,
            "text_item": {"text": text}
        }]
    elif type == "image":
        media_id = await upload_media(text, file_type="image")
        if not media_id:
            item_list = [{
                "type": "TEXT",
                "text_item": {"text": "图片上传失败, 请稍后重试."}
            }]
        else:
            item_list = [{
                "type": "IMAGE",
                "image_item": {"media_id": media_id}
            }]
    elif type == "voice":
        media_id = await upload_media(text, file_type="voice")
        if not media_id:
            item_list = [{
                "type": "TEXT",
                "text_item": {"text": "语音上传失败, 请稍后重试."}
            }]
        else:
            item_list = [{
                "type": "VOICE",
                "voice_item": {"media_id": media_id}
            }]
    elif type == "video":
        media_id = await upload_media(text, file_type="video")
        if not media_id:
            item_list = [{
                "type": "TEXT",
                "text_item": {"text": "视频上传失败, 请稍后重试."}
            }]
        else:
            item_list = [{
                "type": "VIDEO",
                "video_item": {"media_id": media_id}
            }]
    elif type =="file":
        media_id = await upload_media(text, file_type="file")
        if not media_id:
            item_list = [{
                "type": "TEXT",
                "text_item": {"text": "文件上传失败, 请稍后重试."}
            }]
        else:
            item_list = [{
                "type": "FILE",
                "file_item": {"media_id": media_id}
            }]
    payload = {
        "msg": {
            "to_user_id": to_user_id,
            "context_token": context_token,
            "client_id": client_id,
            "item_list": item_list,
            "message_type": 2,
            "message_state": 2
        }
    }
    print(f"---------- send_message payload: {payload} ----------")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BOT_BASE_URL}/ilink/bot/sendmessage",
            json=payload,
            headers=build_headers(bot_token)
        )
        if response.status_code == 200:
            result = response.json()
            print(f"---------- send_message result: {result} ----------")
            print("成功发送消息..........")
            # 关闭[正在输入]状态
            await send_typing(bot_token, to_user_id, typing_ticket, 2)
        return response.status_code == 200

# ========== 3. getUploadUrl 获取媒体文件上传地址 ==========
async def get_upload_url(bot_token: str,file_type: str = "image", file_size: int = 0) -> Optional[Dict[str, Any]]:
    """
    获取媒体文件上传地址
    Args:
        file_type: 文件类型(image/voice/video/file)
        file_size: 文件大小(字节)
    Returns:
        {
            "upload_url": "https://...",
            "media_id": "generated_media_id",
            "expire_time": "2026-12-31T23:59:59Z"
        }
    """
    print(f"========== get_upload_url 节点 ==========")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BOT_BASE_URL}/ilink/bot/getuploadurl",
            json={
                "file_type": file_type,
                "file_size": file_size
            },
            headers=build_headers(bot_token),
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("errcode") == 0:
                return {
                    "upload_url": data.get("upload_url"),
                    "media_id": data.get("media_id"),
                    "expire_time": data.get("expire_time")
                }
            else:
                print(f"获取上传地址失败: {data.get('errmsg')}")
                return None

# ========== 4. getConfig 获取正在输入凭证 ==========
async def get_config(bot_token: str, ilink_user_id: str, context_token: str):
    """
    获取账号配置信息
    Args:
        "ilink_user_id": "wechat",     # iLink 用户ID (微信用户)
        "context_token": "xxxxxx"      # 消息上下文令牌, 来自用户消息体 context_token 字段, 携带可绑定会话上下文
    Returns:
        {
            "typing_ticket": "正在输入凭证",
            "expire_time": "凭证过期时间"
        }
    """
    print(f"========== get_config 节点 ==========")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BOT_BASE_URL}/ilink/bot/getconfig",
            json={
                "ilink_user_id": ilink_user_id,
                "context_token": context_token
            },
            headers=build_headers(bot_token),
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("ret") == 0:
                print(f"---------- get_config data: {data} ----------")
                # data.typing_ticket # 正在输入凭证
                # data.expire_time   # 凭证过期时间
                return data
            else:
                print(f"获取正在输入凭证失败: {data.get('ret')}")
                return None
        else:
            print(f"get_config HTTP错误: {response.status_code}")
            return None

# ========== 5. sendTyping [正在输入]状态 ==========
async def send_typing(bot_token: str, ilink_user_id: str, typing_ticket: str, status: int):
    """
    发送[正在输入]状态
    Args:
        "ilink_user_id": "用户 ID, 来自 getupdates 消息体 from_user_id, 格式oxxx@im.wechat"
        "typing_ticket": "getconfig 接口返回的 typing_ticket, 票据过期需重新拉取"
        "status": "1=开启正在输入(聊天框弹窗); 2=关闭正在输入(消失弹窗)"
        "base_info": "网关版本校验, 固定{'channel_version': '1.0.3'}"
    """
    print(f"========== send_typing 节点 ==========")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BOT_BASE_URL}/ilink/bot/sendtyping",
            json={
                "ilink_user_id": ilink_user_id,
                "typing_ticket": typing_ticket,
                "status": status
            },
            headers=build_headers(bot_token),
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ret") == 0:
                print(f"正在输入接口{'开启' if status == 1 else '取消'}成功")
            else:
                print(f"正在输入接口操作失败: {data.get('ret')}")
                return None
        else:
            print(f"HTTP错误: {response.status_code}")

# ========== 6. getBotInfo 获取账号配置 ==========
async def get_bot_info(bot_token: str):
    """
    获取账号配置信息[ClawBot尚未开放类似接口]
    Args:
    Returns:
        {
            "bot_name": "机器人账号昵称",
            "bot_avatar": "机器人头像远程 URL 地址",
            "max_friends": 5000,       # 机器人最大可添加好友上限(示例 5000)
            "message_rate_limit": 20,  # 每分钟消息发送频次限额(示例 20 条/分钟), 用来做发送限流
            "supported_message_types": # 机器人支持收发的消息类型：文本 / 图片 / 语音 / 视频 / 文件 ["text", "image", "voice", "video", "file"]
        }
    """
    print(f"========== get_bot_info 节点 ==========")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BOT_BASE_URL}/ilink/bot/getbotinfo",
            json={},
            headers=build_headers(bot_token),
            timeout=60
        )
        print(f"headers:\n{build_headers(bot_token)}")
        if response.status_code == 200:
            data = response.json()
            if data.get("ret") == 0:
                print(f"---------- get_bot_info data: {data.get('data')} ----------")
                return data.get("data")
                # return {
                #     "bot_name": data.get("bot_name", "AI助手"),
                #     "bot_avatar": data.get("bot_avatar", ""),
                #     "max_friends": data.get("max_friends", 5000),
                #     "message_rate_limit": data.get("message_rate_limit", 20),
                #     "supported_message_types": data.get("supported_message_types", ["text", "image", "voice", "video", "file"])
                # }
            else:
                print(f"获取配置失败: {data.get('errmsg')}")
                return None
        else:
            print(f"get_bot_info HTTP错误: {response.status_code}")
            return None