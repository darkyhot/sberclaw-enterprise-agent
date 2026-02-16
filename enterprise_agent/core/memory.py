"""SQLite-backed memory for conversation and tool logs."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Dict, List


class MemoryStore:
    """Simple persistent memory layer backed by SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_parent()
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _ensure_parent(self) -> None:
        parent = os.path.dirname(self.db_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

    def _create_tables(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                input TEXT NOT NULL,
                output TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def add_message(self, role: str, content: str) -> None:
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            "INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
            (role, content, now),
        )
        self.conn.commit()

    def get_history(self, limit: int = 200) -> List[Dict[str, str]]:
        rows = self.conn.execute(
            """
            SELECT role, content, timestamp
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        rows = list(reversed(rows))
        return [
            {"role": row["role"], "content": row["content"], "timestamp": row["timestamp"]}
            for row in rows
        ]

    def reset_conversation(self) -> None:
        self.conn.execute("DELETE FROM conversations")
        self.conn.commit()

    def get_tool_logs(self, limit: int = 20) -> List[Dict[str, str]]:
        rows = self.conn.execute(
            """
            SELECT tool_name, input, output, timestamp
            FROM tool_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        rows = list(reversed(rows))
        return [
            {
                "tool_name": row["tool_name"],
                "input": row["input"],
                "output": row["output"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def add_tool_log(self, tool_name: str, tool_input: str, tool_output: str) -> None:
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            "INSERT INTO tool_logs (tool_name, input, output, timestamp) VALUES (?, ?, ?, ?)",
            (tool_name, tool_input, tool_output, now),
        )
        self.conn.commit()

    def reset_tool_logs(self) -> None:
        self.conn.execute("DELETE FROM tool_logs")
        self.conn.commit()

    def reset_all(self) -> None:
        self.reset_conversation()
        self.reset_tool_logs()

    def close(self) -> None:
        self.conn.close()
