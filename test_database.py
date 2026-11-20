import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from database import ReminderDatabase


class ReminderDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = ReminderDatabase(Path(self.temp_dir.name) / "reminders.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_due_reminder_is_claimed_once_and_becomes_overdue(self) -> None:
        due_at = datetime(2026, 11, 20, 14, 0)
        reminder_id = self.database.add("Проверка", "Описание", due_at)

        claimed = self.database.claim_due_notifications(due_at)
        self.assertEqual([row["id"] for row in claimed], [reminder_id])
        self.assertEqual(self.database.claim_due_notifications(due_at), [])

        self.database.mark_overdue(due_at + timedelta(seconds=60))
        self.assertEqual(len(self.database.list_reminders("Просрочено")), 0)
        self.database.mark_overdue(due_at + timedelta(seconds=61))
        reminders = self.database.list_reminders("Просрочено")
        self.assertEqual([row["id"] for row in reminders], [reminder_id])
        self.assertTrue(reminders[0]["created_at"])

    def test_due_query_and_sort_order(self) -> None:
        later = self.database.add(
            "Позже", "", datetime(2026, 11, 20, 14, 5)
        )
        earlier = self.database.add(
            "Раньше", "", datetime(2026, 11, 20, 14, 0)
        )

        due = self.database.get_due_reminders(datetime(2026, 11, 20, 14, 0))
        self.assertEqual([row["id"] for row in due], [earlier])
        all_reminders = self.database.sort_by_due_time(
            self.database.get_all_reminders()
        )
        self.assertEqual([row["id"] for row in all_reminders], [earlier, later])
        self.assertEqual(self.database.get_reminders_count(), 2)

    def test_existing_database_gets_creation_timestamp_column(self) -> None:
        path = Path(self.temp_dir.name) / "existing.db"
        with sqlite3.connect(path) as connection:
            connection.execute(
                """
                CREATE TABLE reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    due_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Ожидает',
                    notified INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                INSERT INTO reminders (title, due_at)
                VALUES ('Старое напоминание', '2026-11-20 14:00:00')
                """
            )

        migrated = ReminderDatabase(path).get_reminder_by_id(1)
        self.assertIsNotNone(migrated)
        self.assertTrue(migrated["created_at"])

    def test_terminal_status_is_not_changed_or_notified(self) -> None:
        due_at = datetime(2026, 11, 20, 14, 0)
        reminder_id = self.database.add("Отмененное", "", due_at)
        self.database.set_status(reminder_id, "Отменено")

        self.database.mark_overdue(due_at + timedelta(days=1))
        self.assertEqual(len(self.database.list_reminders("Просрочено")), 0)
        self.assertEqual(
            self.database.claim_due_notifications(due_at + timedelta(days=1)), []
        )
        self.assertEqual(len(self.database.list_reminders("Отменено")), 1)


if __name__ == "__main__":
    unittest.main()
