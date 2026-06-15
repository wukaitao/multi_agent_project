import asyncio
import httpx
import os
import json
import base64
import random
from datetime import datetime
from typing import Optional, Dict, Any
from config.settings import BOT_BASE_URL, BOT_TYPE, ANGET_API_URL, QRCODE_STATUS_PATH

# ========== 辅助函数 ==========

async def handle_message(bot_token: str, msg: Dict[str, Any]):
    """处理消息: 调用你的 Langgraph Agent"""
    print(f"========== handle_message 节点 ==========")
    from channels.wechat.bot import get_config, send_typing, send_message
    # msg["to_user_id"] 机器人自身ID(bot唯一标识)
    user_id = msg["from_user_id"]
    context_token = msg.get("context_token")
    client_id = msg.get("client_id")
    user_text = extract_text(msg)
    config_result = await get_config(bot_token, user_id, context_token)
    typing_ticket = config_result.get("typing_ticket", "") if config_result else ""
    
    # 开启[正在输入]状态
    await send_typing(bot_token, user_id, typing_ticket, 1)

    if not user_text:
        await send_message(bot_token, user_id, "暂时仅支持文字对话, 请发送文字消息", context_token, client_id, "text", typing_ticket)
        return

    async with httpx.AsyncClient() as client:
        try:
            # 调用 LangGraph Agent
            response = await client.post(
                ANGET_API_URL,
                json={
                    "user": user_id,
                    "query": user_text,
                    "thread_id": f"wechat_{user_id}",
                    "from_skill": "rag_query" # ToDo 暂时固定为RAG知识库查询
                },
                headers={
                    "Authorization": f"Bearer {bot_token}"
                },
                timeout=180
            )
            if response.status_code == 200:
                result = response.json()
                response_text = result.get("response", "抱歉, 我无法回答这个问题.")
                print(f"---------- handle_message response_text: {response_text} ----------")
                response_image = result.get("image", "")
                # 回复支持类型: 文本(text)/图片(image)/语音(voice)/视频(video)/文件(file)  # 判断 response_text 回复
                # 发送回复
                await send_message(bot_token, user_id, response_text, context_token, client_id, "text", typing_ticket)
            else:
                raise Exception(f"接口 HTTP 异常: {response.status_code}")
        except Exception as e:
            await send_message(bot_token, user_id, f"处理失败: {str(e)}", context_token, client_id, "text", typing_ticket)

def build_headers(token):
    """构建请求头"""
    print(f"---------- build_headers bot_token: {token} ----------")
    print(f"---------- randomWechatUin: {randomWechatUin()} ----------")
    return {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Authorization": f"Bearer {token}",
        "X-WECHAT-UIN": randomWechatUin()
    }
def extract_text(msg) -> str:
    """从消息中提取文本内容"""
    result = extract_message_content(msg)
    return result["content"] if result["type"] == "text" else ""

def randomWechatUin():
    # 生成 4 字节随机数(对应 crypto.randomBytes(4))
    uint32_bytes = random.getrandbits(32).to_bytes(4, byteorder='big', signed=False)
    # 转为 uint32 十进制字符串
    uint32 = int.from_bytes(uint32_bytes, byteorder='big', signed=False)
    # 转 utf8 字节 → base64 编码
    return base64.b64encode(str(uint32).encode('utf-8')).decode('utf-8')

def extract_message_content(msg) -> dict:
    """
    提取消息完整内容(支持文本、图片、语音等)
    返回格式:
    {
        "type": "text",        # 消息类型: text/image/voice/video/file
        "content": "文本消息",  # 文本内容或文件URL/ID
        "raw": {...}           # 原始数据
    }
    """
    result = {"type": "unknown", "content": "", "raw": msg}

    # 1. 从item_list中提取解析
    if "item_list" in msg:
        for item in msg["item_list"]:
            msg_type = item.get("type", "")
            """
            # 1 text_item - 纯文本消息; 
            # 2 image_item -- 图片消息(原图 + 缩略图 url、aes 密钥); 
            # 3 voice_item - 微信语音消息(silk/m4a); 
            # 4 file_item - 普通文件(txt/m4a / 压缩包等); 
            # 5 video_item - 短视频消息(视频 + 封面缩略图)
            """

            if msg_type == 1:
                text_item = item.get("text_item", {})
                result["type"] = "text"
                result["content"] = text_item.get("text", "")
            elif msg_type == 2:
                image_item = item.get("image_item", {})
                result["type"] = "image"
                result["content"] = image_item.get("media", {}).get("full_url", "")
                result["media_id"] = image_item.get("media", {}).get("aes_key", "")
            elif msg_type == 3:
                voice_item = item.get("voice_item", {})
                result["type"] = "voice"
                result["content"] = voice_item.get("media", {}).get("full_url", "")
                result["media_id"] = voice_item.get("media", {}).get("aes_key", "")
            elif msg_type == 4:
                file_item = item.get("file_item", {})
                result["type"] = "file"
                result["content"] = file_item.get("media", {}).get("full_url", "")
                result["file_name"] = file_item.get("file_name", "")
            elif msg_type == 5:
                video_item = item.get("video_item", {})
                result["type"] = "video"
                result["content"] = video_item.get("media", {}).get("full_url", "")
                result["media_id"] = video_item.get("media", {}).get("aes_key", "")
            
    # 2. 兼容直接字段格式
    elif "msg_type" in msg:
        if msg["msg_type"] == "text":
            result["type"] = "text"
            result["content"] = msg.get("content", "")

    # 3. 简单文本回退
    elif "content" in msg:
        result["type"] = "text"
        result["content"] = msg.get("content", "")

    elif "text" in msg:
        result["type"] = "text"
        result["content"] = msg.get("text", "")

    return result

async def upload_media(bot_token: str, file_path: str, file_type: str = "image") -> Optional[str]:
    """
    上传媒体文件到微信服务器
    Args:
        bot_token: 机器人令牌
        file_path: 本地文件路径
        file_type: 文件类型(image/voice/video/file)
    Returns:
        media_id: 微信服务器返回的媒体ID, 可用于发送消息
    """
    import os
    from pathlib import Path
    from channels.wechat.bot import get_upload_url

    # 1. 获取文件信息
    file_size = os.path.getsize(file_path)

    # 2. 获取上传地址
    upload_info = await get_upload_url(bot_token, file_type, file_size)
    if not upload_info:
        return None
    
    upload_url = upload_info["upload_url"]

    # 3. 上传文件
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, f, "application/octet-stream")}
            response = await client.post(
                upload_url,
                files=files,
                timeout=60
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    return upload_info["media_id"]
                else:
                    print(f"上传失败: {result.get('errmsg')}")
                    return None
            else:
                print(f"上传HTTP错误: {response.status_code}")
                return None