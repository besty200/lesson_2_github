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

        self.database.mark_overdue(due_at + timedelta(seconds=1))
        reminders = self.database.list_reminders("Просрочено")
        self.assertEqual([row["id"] for row in reminders], [reminder_id])

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
