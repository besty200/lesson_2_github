"""SQLite persistence for the reminder application."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional, Sequence


DATABASE_PATH = Path(__file__).with_name("reminders.db")
STATUSES = ("Ожидает", "Готово", "Просрочено", "Отменено")
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class ReminderDatabase:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = Path(path)
        self.initdatabase()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initdatabase(self) -> None:
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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    notified INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(reminders)")
            }
            if "created_at" not in columns:
                connection.execute(
                    "ALTER TABLE reminders ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"
                )
                connection.execute(
                    """
                    UPDATE reminders SET created_at = CURRENT_TIMESTAMP
                    WHERE created_at = ''
                    """
                )
            if "notified" not in columns:
                connection.execute(
                    "ALTER TABLE reminders ADD COLUMN notified INTEGER NOT NULL DEFAULT 0"
                )
            if "is_recurring" not in columns:
                connection.execute(
                    "ALTER TABLE reminders ADD COLUMN is_recurring INTEGER NOT NULL DEFAULT 0"
                )
            if "recurrence_interval_minutes" not in columns:
                connection.execute(
                    "ALTER TABLE reminders ADD COLUMN recurrence_interval_minutes INTEGER"
                )

    def add_reminder(
        self,
        title: str,
        description: str,
        due_at: datetime,
        is_recurring: bool = False,
        recurrence_interval_minutes: Optional[int] = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO reminders (title, description, due_at, created_at, is_recurring, recurrence_interval_minutes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    description,
                    due_at.strftime(DATETIME_FORMAT),
                    datetime.now().strftime(DATETIME_FORMAT),
                    1 if is_recurring else 0,
                    recurrence_interval_minutes,
                ),
            )
            return int(cursor.lastrowid)

    def create_next_occurrence(self, reminder_id: int) -> Optional[int]:
        """Создать следующее вхождение периодического напоминания."""
        reminder = self.get_reminder_by_id(reminder_id)
        if reminder is None or not reminder["is_recurring"]:
            return None
        interval = reminder["recurrence_interval_minutes"]
        if interval is None or interval <= 0:
            return None
        due_at = datetime.strptime(reminder["due_at"], DATETIME_FORMAT)
        next_due = due_at + timedelta(minutes=interval)
        return self.add_reminder(
            str(reminder["title"]),
            str(reminder["description"] or ""),
            next_due,
            is_recurring=True,
            recurrence_interval_minutes=interval,
        )

    def get_all_reminders(
        self, status: Optional[str] = None
    ) -> list[sqlite3.Row]:
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

    def get_due_reminders(self, now: Optional[datetime] = None) -> list[sqlite3.Row]:
        now_text = (now or datetime.now()).strftime(DATETIME_FORMAT)
        with self._connect() as connection:
            return connection.execute(
                """
                SELECT * FROM reminders
                WHERE due_at <= ? AND notified = 0
                    AND status IN ('Ожидает', 'Просрочено')
                ORDER BY due_at, id
                """,
                (now_text,),
            ).fetchall()

    def sort_by_due_time(
        self, reminders: Optional[Sequence[sqlite3.Row]] = None
    ) -> list[sqlite3.Row]:
        rows = list(reminders) if reminders is not None else self.get_all_reminders()
        return sorted(rows, key=lambda reminder: (reminder["due_at"], reminder["id"]))

    def update_status(self, reminder_id: int, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"Неизвестный статус: {status}")
        with self._connect() as connection:
            connection.execute(
                "UPDATE reminders SET status = ? WHERE id = ?",
                (status, reminder_id),
            )

    def delete_reminder(self, reminder_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))

    def mark_overdue(self, now: Optional[datetime] = None) -> int:
        cutoff = (now or datetime.now()) - timedelta(minutes=1)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE reminders
                SET status = 'Просрочено'
                WHERE status = 'Ожидает' AND due_at < ?
                """,
                (cutoff.strftime(DATETIME_FORMAT),),
            )
            return cursor.rowcount

    def get_reminder_by_id(self, reminder_id: int) -> Optional[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            ).fetchone()

    def get_reminders_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM reminders").fetchone()
            return int(row[0])

    def claim_due_notifications(self, now: datetime) -> list[sqlite3.Row]:
        """Atomically claim each due notification once."""
        now_text = now.strftime(DATETIME_FORMAT)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT id, title, description, due_at, status,
                       is_recurring, recurrence_interval_minutes
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

    # Compatibility with the original API used by existing callers.
    def initialize(self) -> None:
        self.initdatabase()

    def add(
        self,
        title: str,
        description: str,
        due_at: datetime,
        is_recurring: bool = False,
        recurrence_interval_minutes: Optional[int] = None,
    ) -> int:
        return self.add_reminder(
            title,
            description,
            due_at,
            is_recurring=is_recurring,
            recurrence_interval_minutes=recurrence_interval_minutes,
        )

    def list_reminders(self, status: Optional[str] = None) -> list[sqlite3.Row]:
        return self.get_all_reminders(status)

    def delete(self, reminder_id: int) -> None:
        self.delete_reminder(reminder_id)

    def set_status(self, reminder_id: int, status: str) -> None:
        self.update_status(reminder_id, status)
