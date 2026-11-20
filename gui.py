"""Tkinter user interface for reminders."""

import sqlite3
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from database import DATETIME_FORMAT, STATUSES, ReminderDatabase
from notifications import NotificationManager


DISPLAY_DATE_FORMAT = "%Y-%m-%d %H:%M"


class ReminderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.database = ReminderDatabase()
        self.filter_status = tk.StringVar(value="Все")
        self.due_var: tk.StringVar | None = None

        self.root.title("Напоминания")
        self.root.geometry("850x490")
        self.setup_ui()
        self.refresh_reminders()
        self.notifications = NotificationManager(
            self.root, self.database, self.refresh_reminders
        )
        self.notifications.start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self) -> None:
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="Добавить", command=self._open_add_dialog).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Удалить", command=self.delete_reminder).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(toolbar, text="Готово", command=self.mark_as_done).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(
            toolbar,
            text="Показать",
            command=self.show_manual_notification,
        ).pack(side=tk.LEFT, padx=6)
        ttk.Button(
            toolbar,
            text="Тест уведомления",
            command=self.test_notification,
        ).pack(side=tk.LEFT, padx=6)

        ttk.Label(toolbar, text="Статус:").pack(side=tk.LEFT, padx=(16, 5))
        status_filter = ttk.Combobox(
            toolbar,
            textvariable=self.filter_status,
            values=("Все", *STATUSES),
            state="readonly",
            width=14,
        )
        status_filter.pack(side=tk.LEFT)
        status_filter.bind(
            "<<ComboboxSelected>>", lambda _event: self.refresh_reminders()
        )

        columns = ("title", "description", "due_at", "status")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings")
        self.tree.heading("title", text="Заголовок")
        self.tree.heading("description", text="Описание")
        self.tree.heading("due_at", text="Дата и время")
        self.tree.heading("status", text="Статус")
        self.tree.column("title", width=170)
        self.tree.column("description", width=320)
        self.tree.column("due_at", width=150)
        self.tree.column("status", width=110, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))
        self.tree.bind("<Double-1>", self.on_double_click)

        self.status_bar = ttk.Label(self.root, anchor=tk.W, padding=(10, 4))
        self.status_bar.pack(fill=tk.X)

    def update_status_bar(self) -> None:
        count = self.database.get_reminders_count()
        self.status_bar.configure(
            text=f"Всего напоминаний: {count}"
        )

    def test_notification(self) -> None:
        self.notifications.test_notification()

    def show_manual_notification(self) -> None:
        reminder = self._selected_reminder()
        if reminder is None:
            messagebox.showinfo("Напоминания", "Сначала выберите напоминание.")
            return
        self.notifications.show_manual_notification(reminder)

    def set_quick_time(self, minutes: int) -> None:
        if self.due_var is not None:
            due_at = datetime.now() + timedelta(minutes=minutes)
            self.due_var.set(due_at.strftime(DISPLAY_DATE_FORMAT))

    def add_reminder(
        self, title: str, description: str, due_at: datetime
    ) -> int:
        reminder_id = self.database.add_reminder(title, description, due_at)
        self.refresh_reminders()
        return reminder_id

    def refresh_reminders(self) -> None:
        self.database.mark_overdue(datetime.now())
        for item in self.tree.get_children():
            self.tree.delete(item)
        for reminder in self.database.get_all_reminders(self.filter_status.get()):
            due_at = datetime.strptime(reminder["due_at"], DATETIME_FORMAT)
            self.tree.insert(
                "",
                tk.END,
                iid=str(reminder["id"]),
                values=(
                    reminder["title"],
                    reminder["description"],
                    due_at.strftime(DISPLAY_DATE_FORMAT),
                    reminder["status"],
                ),
            )
        self.update_status_bar()

    def _selected_id(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def _selected_reminder(self) -> sqlite3.Row | None:
        reminder_id = self._selected_id()
        return (
            self.database.get_reminder_by_id(reminder_id)
            if reminder_id is not None
            else None
        )

    def delete_reminder(self) -> None:
        reminder_id = self._selected_id()
        if reminder_id is None:
            messagebox.showinfo("Напоминания", "Сначала выберите напоминание.")
            return
        self.database.delete_reminder(reminder_id)
        self.refresh_reminders()

    def mark_as_done(self) -> None:
        reminder_id = self._selected_id()
        if reminder_id is None:
            messagebox.showinfo("Напоминания", "Сначала выберите напоминание.")
            return
        self.database.update_status(reminder_id, "Готово")
        self.refresh_reminders()

    def on_double_click(self, _event: tk.Event) -> None:
        reminder = self._selected_reminder()
        if reminder is None:
            return
        messagebox.showinfo(
            reminder["title"],
            f"{reminder['description'] or 'Без описания'}\n\n"
            f"Дата и время: {reminder['due_at']}\n"
            f"Статус: {reminder['status']}",
            parent=self.root,
        )

    def _open_add_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Новое напоминание")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        title_var = tk.StringVar()
        self.due_var = tk.StringVar(value=datetime.now().strftime(DISPLAY_DATE_FORMAT))
        ttk.Label(dialog, text="Заголовок:").grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 4)
        )
        title_entry = ttk.Entry(dialog, textvariable=title_var, width=48)
        title_entry.grid(row=0, column=1, padx=10, pady=(10, 4))

        ttk.Label(dialog, text="Описание:").grid(
            row=1, column=0, sticky=tk.NW, padx=10, pady=4
        )
        description_text = tk.Text(dialog, width=36, height=5, wrap=tk.WORD)
        description_text.grid(row=1, column=1, padx=10, pady=4)

        ttk.Label(dialog, text="Дата и время:").grid(
            row=2, column=0, sticky=tk.W, padx=10, pady=4
        )
        ttk.Entry(dialog, textvariable=self.due_var, width=48).grid(
            row=2, column=1, padx=10, pady=4
        )
        quick_times = ttk.Frame(dialog)
        quick_times.grid(row=3, column=1, sticky=tk.W, padx=10, pady=4)
        for minutes in (1, 5, 15):
            ttk.Button(
                quick_times,
                text=f"+{minutes} мин",
                command=lambda value=minutes: self.set_quick_time(value),
            ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(dialog, text="Формат: ГГГГ-ММ-ДД ЧЧ:ММ").grid(
            row=4, column=1, sticky=tk.W, padx=10
        )

        def save() -> None:
            title = title_var.get().strip()
            if not title:
                messagebox.showerror("Ошибка", "Введите заголовок.", parent=dialog)
                return
            try:
                due_at = datetime.strptime(
                    self.due_var.get().strip(), DISPLAY_DATE_FORMAT
                )
            except ValueError:
                messagebox.showerror(
                    "Ошибка",
                    "Укажите корректные дату и время в формате ГГГГ-ММ-ДД ЧЧ:ММ.",
                    parent=dialog,
                )
                return
            description = description_text.get("1.0", tk.END).strip()
            self.add_reminder(title, description, due_at)
            self.due_var = None
            dialog.destroy()

        def cancel() -> None:
            self.due_var = None
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=5, column=0, columnspan=2, sticky=tk.E, padx=10, pady=10)
        ttk.Button(buttons, text="Сохранить", command=save).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(buttons, text="Отмена", command=cancel).pack(side=tk.LEFT)
        title_entry.focus_set()

    def on_closing(self) -> None:
        if messagebox.askyesno("Выход", "Вы уверены, что хотите выйти?"):
            self.notifications.stop()
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
