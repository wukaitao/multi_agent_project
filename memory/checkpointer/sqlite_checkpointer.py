"""
SQLite 检查点管理
用于 LangGraph 状态持久化
"""

import sqlite3
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import hashlib

from langgraph.checkpoint.sqlite import SqliteSaver
from config.settings import *
import logging

logger = logging.getLogger(__name__)

class SQLiteCheckpointer:
    """SQLite 检查点管理器"""

    def __init__(self, db_path: Optional[str]=None):
        self.db_path = db_path or str('SQLITE_PATH')  # config/setting.py 中读取
        self.conn = None
        self.checkpointer = None
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(self.conn)

        # 创建检查点表(如果不存在)
        self._create_tables()
        logger.info(f"SQLiteCheckpointer initialized at {self.db_path}")

    def _create_table(self):
        """创建检查点表"""
        cursor = self.conn.cursor()

        # 检查点主表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT PRIMARY KEY,
                checkpoint_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                version TEXT
            )
        """)

        # 检查点历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                checkpoint_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version TEXT,
                FOREING KEY (thread_id) REFERENCES checkpoints(thread_id)
            )
        """)

        self.conn.commit()
    
    def save_checkpoint(self, thread_id: str, state: Dict[str, Any], metadata: Optional[Dict]=None) -> bool:
        """
        保存检查点
        Args:
            thread_id: 线程ID
            state: 状态数据
            metadata: 元数据
        Returns:
            是否保存成功
        """
        try:
            checkpoint_data = json.dumps(state, default=str)
            metadata_json = json.dumps(metadata) if metadata else None
            version = hashlib.md5(checkpoint_data.encode()).hexdigest()[:8]

            cursor = self.conn.cursor()

            # 检查是否存在
            cursor.execute("SELECT thread_id FROM checkpoints WHERE thread_id = ?", (thread_id,))
            exists = cursor.fetchone()
            
            if exists:
                # 更新
                cursor.execute("""
                    UPDATE checkpoints
                    SET checkpoint_data = ?, updated_at = CURRENT_TIMESTAMP, metadata = ?, version = ?,
                    WHERE thread_id = ?,
                    """, (checkpoint_data, metadata_json, version, thread_id)
                )
            else:
                # 插入
                cursor.execute("""
                    INSERT INTO checkpoints (thread_id, checkpoint_data, metadata, version)
                    VALUES (?, ?, ?, ?)
                    """, (thread_id, checkpoint_data, metadata_json, version)
                )

            # 保存历史
            cursor.execute("""
                INSERT INTO checkpoint_history (thread_id, checkpoint_data, version)
                VALUES (?, ?, ?)
                """, (thread_id, checkpoint_data, version)
            )

            self.conn.commit()
            logger.debug(f"Checkpoint saved for thread: {thread_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False
        
    def load_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        加载检查点
        Args:
            thread_id: 线程ID
        Returns:
            状态数据
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT checkpoint_data FROM checkpoints WHERE thread_id = ? 
                """, (thread_id,)
            )

            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
        
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
        
    def get_checkpoint_history(self, thread_id: str, limit: int=10) -> List[Dict[str, Any]]:
        """
        获取检查点历史
        Args:
            thread_id: 线程ID
            limit: 返回数量限制
        Returns:
            历史记录列表
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT checkpoint_data, created_at, version 
                FROM checkpoint_history
                WHERE thread_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """, (thread_id, limit)
            )

            rows = cursor.fetchall()
            return [
                {
                    "data": json.loads(row[0]),
                    "timestamp": row[1],
                    "timestamp": row[2]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get checkpoint history: {e}")
            return []
        
    def delete_checkpoint(self, thread_id: str) -> bool:
        """
        删除检查点
        Args:
            thread_id: 线程ID
        Returns:
            是否删除成功
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT FROM checkpoints WHERE thead_id = ?""", (thread_id,)
            )
            cursor.execute("""
                DELETE FROM checkpoint_history WHERE thread_id = ?""", (thread_id,)
            )
            self.conn.commit()
            logger.debug(f"Checkpoint deleted for thread: {thread_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")
            return False
        
    def list_threads(self) -> List[str]:
        """列出所有线程 ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT thread_id FROM checkpoints")
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to list threads: {e}")
            return []
        
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("SQLiteCheckpointer closed")