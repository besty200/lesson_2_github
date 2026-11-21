"""Background scheduling and user-facing reminder notifications."""

import os
import queue
import sqlite3
import threading
import tkinter as tk
from collections.abc import Mapping
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

from database import ReminderDatabase


Notification = sqlite3.Row | Mapping[str, object]


class NotificationManager:
    def __init__(
        self,
        root: tk.Tk,
        database: ReminderDatabase,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.database = database
        self.on_change = on_change
        self.stop_event = threading.Event()
        self.notifications: queue.Queue[tuple[str, object]] = queue.Queue()
        self.scheduler = threading.Thread(
            target=self._monitor_database,
            name="reminder-scheduler",
            daemon=True,
        )

    def start(self) -> None:
        self.scheduler.start()
        self.root.after(250, self._process_notifications)

    def stop(self) -> None:
        self.stop_event.set()

    def _monitor_database(self) -> None:
        while not self.stop_event.is_set():
            try:
                if self.database.mark_overdue(datetime.now()):
                    self.notifications.put(("refresh", None))
                for reminder in self.database.claim_due_notifications(datetime.now()):
                    self.notifications.put(("reminder", reminder))
                    if reminder["is_recurring"]:
                        self.database.create_next_occurrence(reminder["id"])
            except Exception as error:
                self.notifications.put(("error", error))
            self.stop_event.wait(1)

    def _process_notifications(self) -> None:
        try:
            while True:
                kind, payload = self.notifications.get_nowait()
                if kind == "reminder" and isinstance(
                    payload, (sqlite3.Row, Mapping)
                ):
                    self._show_notification(payload)
                elif kind == "refresh" and self.on_change is not None:
                    self.on_change()
                elif isinstance(payload, sqlite3.Error):
                    messagebox.showerror(
                        "Ошибка напоминаний",
                        f"Не удалось проверить напоминания:\n{payload}",
                    )
        except queue.Empty:
            pass
        if not self.stop_event.is_set() and self.root.winfo_exists():
            self.root.after(250, self._process_notifications)

    def _show_notification(self, reminder: Notification) -> None:
        title = str(reminder["title"])
        description = str(reminder["description"] or "")
        if self._show_toast(title, description):
            return
        self._show_popup(reminder)

    @staticmethod
    def _show_toast(title: str, description: str) -> bool:
        if os.name != "nt":
            return False
        try:
            from win10toast import ToastNotifier

            return bool(
                ToastNotifier().show_toast(
                    title, description or "Пришло время напоминания.", threaded=True
                )
            )
        except (ImportError, OSError, RuntimeError):
            return False

    def _show_popup(self, reminder: Notification) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("Напоминание")
        popup.attributes("-topmost", True)
        popup.geometry("360x190")

        ttk.Label(
            popup,
            text=str(reminder["title"]),
            font=("", 12, "bold"),
            wraplength=320,
        ).pack(anchor=tk.W, padx=16, pady=(16, 8))
        ttk.Label(
            popup,
            text=str(reminder["description"] or " "),
            wraplength=320,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=16, expand=True, fill=tk.BOTH)

        buttons = ttk.Frame(popup)
        buttons.pack(anchor=tk.E, padx=12, pady=12)

        reminder_id = (
            reminder.get("id")
            if isinstance(reminder, Mapping)
            else reminder["id"]
        )
        if reminder_id is not None:
            def mark_done() -> None:
                self.database.update_status(int(reminder_id), "Готово")
                if self.on_change is not None:
                    self.on_change()
                popup.destroy()

            ttk.Button(buttons, text="Готово", command=mark_done).pack(
                side=tk.LEFT, padx=4
            )
        ttk.Button(buttons, text="Закрыть", command=popup.destroy).pack(side=tk.LEFT)
        popup.lift()
        popup.focus_force()
        popup.after(30_000, lambda: popup.destroy() if popup.winfo_exists() else None)

    def show_manual_notification(self, reminder: Notification) -> None:
        self._show_notification(reminder)

    def test_notification(self) -> None:
        self.show_manual_notification(
            {
                "title": "Тестовое уведомление",
                "description": "Уведомления работают.",
            }
        )
