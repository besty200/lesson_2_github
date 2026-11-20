"""SQLite persistence for the reminder application."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


DATABASE_PATH = Path(__file__).with_name("reminders.db")
STATUSES = ("Ожидает", "Готово", "Просрочено", "Отменено")


class ReminderDatabase:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = Path(path)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    due_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Ожидает'
                        CHECK (status IN ('Ожидает', 'Готово', 'Просрочено', 'Отменено')),
                    notified INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def add(self, title: str, description: str, due_at: datetime) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO reminders (title, description, due_at)
                VALUES (?, ?, ?)
                """,
                (title, description, due_at.strftime("%Y-%m-%d %H:%M:%S")),
            )
            return int(cursor.lastrowid)

    def list_reminders(self, status: Optional[str] = None) -> list[sqlite3.Row]:
        with self._connect() as connection:
            if status is None or status == "Все":
                rows = connection.execute(
                    "SELECT * FROM reminders ORDER BY due_at, id"
                ).fetchall()
            else:
                if status not in STATUSES:
                    raise ValueError(f"Неизвестный статус: {status}")
                rows = connection.execute(
                    "SELECT * FROM reminders WHERE status = ? ORDER BY due_at, id",
                    (status,),
                ).fetchall()
            return rows

    def delete(self, reminder_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))

    def set_status(self, reminder_id: int, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"Неизвестный статус: {status}")
        with self._connect() as connection:
            connection.execute(
                "UPDATE reminders SET status = ? WHERE id = ?",
                (status, reminder_id),
            )

    def claim_due_notifications(self, now: datetime) -> list[sqlite3.Row]:
        """Mark overdue reminders and atomically claim each due notification once."""
        now_text = now.strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE reminders
                SET status = 'Просрочено'
                WHERE status = 'Ожидает' AND due_at < ?
                """,
                (now_text,),
            )
            rows = connection.execute(
                """
                SELECT id, title, description, due_at
                FROM reminders
                WHERE due_at <= ? AND notified = 0
                    AND status IN ('Ожидает', 'Просрочено')
                ORDER BY due_at, id
                """,
                (now_text,),
            ).fetchall()
            if rows:
                connection.executemany(
                    "UPDATE reminders SET notified = 1 WHERE id = ?",
                    ((row["id"],) for row in rows),
                )
            return rows

    def mark_overdue(self, now: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE reminders
                SET status = 'Просрочено'
                WHERE status = 'Ожидает' AND due_at < ?
                """,
                (now.strftime("%Y-%m-%d %H:%M:%S"),),
            )
