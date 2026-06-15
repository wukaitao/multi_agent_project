import asyncio
import httpx
import os
import json
import base64
import random
from datetime import datetime
from typing import Optional, Dict, Any
from config.settings import BOT_BASE_URL, BOT_TYPE, ANGET_API_URL, QRCODE_STATUS_PATH
from channels.wechat.bot import get_updates, get_bot_info
from channels.wechat.handlers import handle_message

# ========== 扫码获取登录凭证 ==========

async def get_qrcode():
    """获取登录二维码"""
    print(f"========== get_qrcode 节点 ==========")
    url = f"{BOT_BASE_URL}/ilink/bot/get_bot_qrcode?bot_type={BOT_TYPE}"
    print(f"---------- get_qrcode url: {url} ----------")
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        result = response.json()
        if result.get("ret") != 0:
            print(f"获取二维码失败: {result.get('err_msg')}")
        
        # 直接调用主函数启动轮询登录状态
        print(f"---------- 调用主函数: 获取二维码状态 - 账号配置 - 接收用户消息 - 处理信息[ - 上传资料] - 发送回复[正在输入] ----------")

        return result
    
async def get_qrcode_status(qrcode: str) -> dict:
    """查询二维码状态"""
    print(f"========== get_qrcode_status 节点 ==========")
    url = f"{BOT_BASE_URL}/ilink/bot/get_qrcode_status?qrcode={qrcode}"
    print(f"---------- get_qrcode_status url: {url} ----------")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=60)
            if response.status_code != 200:
                print(f"查询二维码状态 HTTP错误: {response.status_code}")
                return {
                    "status": "error",
                    "err_msg": f"HTTP {response.status_code}"
                }
            return response.json()
    
        except Exception as e:
            # 捕获所有异常，打印错误信息并返回
            print(f"查询二维码状态 异常: {str(e)}")
            return {
                "status": "error",
                "err_msg": f"Exception: {str(e)}"
            }

async def poll_login_status(qrcode: str):
    """
    轮询扫码状态
    wait:       等待扫码           ->   继续轮询
    scaned:    已扫码, 等待确认    ->   继续轮询
    confirmed:  已确认, 返回 token ->   保存凭证, 退出
    expired:    二维码已过期       ->   刷新二维码
    """
    print(f"========== poll_login_status 节点 ==========")
    while True:
        result = await get_qrcode_status(qrcode)
        status = result.get("status")
        if status == "wait":
            print("等待扫码...")
        elif status == "scaned":
            print("扫码已完成, 请在手机上点击确认...")
        elif status == "confirmed":
            # 获取 qrcode_status 并保存
            bot_token = result.get("bot_token", "")
            print(f"---------- poll_login_status result: {result} ----------")
            print(f"登录成功, bot_token: {bot_token}")
            return result
        elif status == "expired":
            print(f"二维码已过期, 请点击按钮重新生成二维码")
            return None
        else:
            print(f"未知状态: {status}, 信息: {result}")
        await asyncio.sleep(2)

# ========== 凭证管理 ==========

def save_qrcode_status(qrcode_status: dict):
    """将 qrcode_status 保存到本地文件"""
    # 确保文件存在
    os.makedirs(os.path.dirname(QRCODE_STATUS_PATH), exist_ok=True)
    data = {
        "baseurl": qrcode_status.get("baseurl", ""),
        "bot_token": qrcode_status.get("bot_token", ""),
        "ilink_bot_id": qrcode_status.get("ilink_bot_id", ""),
        "ilink_user_id": qrcode_status.get("ilink_user_id", ""),
        "saved_at": datetime.now().isoformat()
    }
    with open(QRCODE_STATUS_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"qrcode_status 已保存到 {QRCODE_STATUS_PATH}")

def load_qrcode_status():
    """从本地文件加载 qrcode_status"""
    if os.path.exists(QRCODE_STATUS_PATH):
        with open(QRCODE_STATUS_PATH, "r") as f:
            print(f"qrcode_status 已从 {QRCODE_STATUS_PATH} 加载")
            return json.load(f)
    print(f"未找到有效的 qrcode_status 文件")
    return None

async def run_bot(bot_token: str):
    """运行机器人主循环"""
    print(f"========== run_bot bot_token: {bot_token} ========")
    print(f"机器人已启动, 开始监听消息...")
    print(f"提示: 在微信中向「微信 ClawBot」发送消息测试")

    get_updates_buf = ""

    while True:
        try:
            print(f"========== run_bot 节点 ==========")
            messages, new_buf = await get_updates(bot_token, get_updates_buf)
            print(f"---------- messages, new_buf: {messages} {new_buf} ----------")

            if messages is None:
                # 连接错误, 等待后重试
                await asyncio.sleep(5)
                continue

            if new_buf != get_updates_buf:
                get_updates_buf = new_buf

            for msg in messages:
                await handle_message(bot_token, msg)

        except Exception as e:
            print(f"主循环异常: {str(e)}")
            await asyncio.sleep(5)

# ========== 主函数 ==========

async def main(qrcode: str):
    """
    主函数: 登录 + 启动机器人
    如果提供了 qrcode, 则直接使用它轮询登录状态
    """
    # 1. 检查是否有保存的 qrcode_status
    qrcode_status = load_qrcode_status()

    if qrcode_status:
        # 验证 bot_token 是否有效
        config = await get_bot_info(qrcode_status.get("bot_token"))
        if config:
            print(f"使用已保存的 qrcode_status: {qrcode_status}, 机器人名称: {config['bot_name']}")
            await run_bot(qrcode_status.get("bot_token"))
            return
        
    # 2. 如果没有 bot_token 或 bot_token 无效, 需要扫码登录
    if not qrcode:
        print("bot_token 无效, 需要扫码登录")
        return
    
    # 3. 轮询等待扫码确认
    qrcode_status = await poll_login_status(qrcode)

    if not qrcode_status:
        print(f"登录失败, 无法获取 qrcode_status")
        return
    
    # 4. 保存 qrcode_status 到本地
    save_qrcode_status(qrcode_status)

    # 5. 获取配置并启动机器人
    config = await get_bot_info(qrcode_status.get("bot_token"))
    if config:
        print(f"登录成功, 机器人名称: {config['bot_name']}")

    await run_bot(qrcode_status.get("bot_token"))