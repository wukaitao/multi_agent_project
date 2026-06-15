import sqlite3
from typing import List
from config.settings import MEMORY_DB

# 短期记忆(内存)
short_memory_cache = []
MAX_SHORT_MEM = 12

def add_short_memory(content: str):
    short_memory_cache.append(content)
    if len(short_memory_cache) > MAX_SHORT_MEM:
        short_memory_cache.pop(0)

def get_short_memory() -> str:
    return "\n".join(short_memory_cache)