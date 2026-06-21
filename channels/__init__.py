"""渠道层 - 处理各种输入输出渠道"""
from .base import BaseChannel
from .web.app_new import create_streamlit_app

__all__ = [
    "BaseChannel",
    "create_streamlit_app"
]