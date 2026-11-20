"""Tkinter interface and background reminder notifications."""

import queue
import sqlite3
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from database import ReminderDatabase, STATUSES


DATE_FORMAT = "%Y-%m-%d %H:%M"


class ReminderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.database = ReminderDatabase()
        self.notifications: queue.Queue[
            tuple[str, sqlite3.Row | sqlite3.Error]
        ] = queue.Queue()
        self.stop_event = threading.Event()
        self.filter_status = tk.StringVar(value="Все")

        self.root.title("Напоминания")
        self.root.geometry("850x450")
        self._build_interface()
        self.refresh_reminders()

        self.scheduler = threading.Thread(
            target=self._schedule_notifications,
            name="reminder-scheduler",
            daemon=True,
        )
        self.scheduler.start()
        self.root.after(250, self._process_notifications)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_interface(self) -> None:
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="Добавить", command=self._open_add_dialog).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Удалить", command=self._delete_selected).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(
            toolbar,
            text="Готово",
            command=lambda: self._set_selected_status("Готово"),
        ).pack(side=tk.LEFT, padx=6)
        ttk.Button(
            toolbar,
            text="Отменить",
            command=lambda: self._set_selected_status("Отменено"),
        ).pack(side=tk.LEFT, padx=6)

        ttk.Label(toolbar, text="Статус:").pack(side=tk.LEFT, padx=(20, 5))
        status_filter = ttk.Combobox(
            toolbar,
            textvariable=self.filter_status,
            values=("Все", *STATUSES),
            state="readonly",
            width=14,
        )
        status_filter.pack(side=tk.LEFT)
        status_filter.bind("<<ComboboxSelected>>", lambda _event: self.refresh_reminders())

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
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def refresh_reminders(self) -> None:
        self.database.mark_overdue(datetime.now())
        for item in self.tree.get_children():
            self.tree.delete(item)
        status = self.filter_status.get()
        for reminder in self.database.list_reminders(status):
            due_at = datetime.strptime(reminder["due_at"], "%Y-%m-%d %H:%M:%S")
            self.tree.insert(
                "",
                tk.END,
                iid=str(reminder["id"]),
                values=(
                    reminder["title"],
                    reminder["description"],
                    due_at.strftime(DATE_FORMAT),
                    reminder["status"],
                ),
            )

    def _selected_id(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def _delete_selected(self) -> None:
        reminder_id = self._selected_id()
        if reminder_id is None:
            messagebox.showinfo("Напоминания", "Сначала выберите напоминание.")
            return
        self.database.delete(reminder_id)
        self.refresh_reminders()

    def _set_selected_status(self, status: str) -> None:
        reminder_id = self._selected_id()
        if reminder_id is None:
            messagebox.showinfo("Напоминания", "Сначала выберите напоминание.")
            return
        self.database.set_status(reminder_id, status)
        self.refresh_reminders()

    def _open_add_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Новое напоминание")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        title_var = tk.StringVar()
        due_var = tk.StringVar(value=datetime.now().strftime(DATE_FORMAT))
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
        ttk.Entry(dialog, textvariable=due_var, width=48).grid(
            row=2, column=1, padx=10, pady=4
        )
        ttk.Label(dialog, text="Формат: ГГГГ-ММ-ДД ЧЧ:ММ").grid(
            row=3, column=1, sticky=tk.W, padx=10
        )

        def save() -> None:
            title = title_var.get().strip()
            if not title:
                messagebox.showerror("Ошибка", "Введите заголовок.", parent=dialog)
                return
            try:
                due_at = datetime.strptime(due_var.get().strip(), DATE_FORMAT)
            except ValueError:
                messagebox.showerror(
                    "Ошибка",
                    "Укажите корректные дату и время в формате ГГГГ-ММ-ДД ЧЧ:ММ.",
                    parent=dialog,
                )
                return
            description = description_text.get("1.0", tk.END).strip()
            self.database.add(title, description, due_at)
            self.refresh_reminders()
            dialog.destroy()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=4, column=0, columnspan=2, sticky=tk.E, padx=10, pady=10)
        ttk.Button(buttons, text="Сохранить", command=save).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Отмена", command=dialog.destroy).pack(side=tk.LEFT)
        title_entry.focus_set()

    def _schedule_notifications(self) -> None:
        while not self.stop_event.is_set():
            try:
                due_reminders = self.database.claim_due_notifications(datetime.now())
                for reminder in due_reminders:
                    self.notifications.put(("reminder", reminder))
            except sqlite3.Error as error:
                self.notifications.put(("error", error))
            self.stop_event.wait(1)

    def _process_notifications(self) -> None:
        try:
            while True:
                kind, payload = self.notifications.get_nowait()
                if kind == "reminder" and isinstance(payload, sqlite3.Row):
                    self._show_notification(payload)
                elif isinstance(payload, sqlite3.Error):
                    messagebox.showerror(
                        "Ошибка напоминаний",
                        f"Не удалось проверить напоминания:\n{payload}",
                    )
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(250, self._process_notifications)

    def _show_notification(self, reminder: sqlite3.Row) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("Напоминание")
        popup.attributes("-topmost", True)
        popup.geometry("360x190")

        ttk.Label(
            popup,
            text=reminder["title"],
            font=("", 12, "bold"),
            wraplength=320,
        ).pack(anchor=tk.W, padx=16, pady=(16, 8))
        description = reminder["description"] or " "
        ttk.Label(popup, text=description, wraplength=320, justify=tk.LEFT).pack(
            anchor=tk.W, padx=16, expand=True, fill=tk.BOTH
        )

        buttons = ttk.Frame(popup)
        buttons.pack(anchor=tk.E, padx=12, pady=12)

        def mark_done() -> None:
            self.database.set_status(reminder["id"], "Готово")
            self.refresh_reminders()
            popup.destroy()

        ttk.Button(buttons, text="Готово", command=mark_done).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(buttons, text="Закрыть", command=popup.destroy).pack(side=tk.LEFT)
        popup.lift()
        popup.focus_force()

    def _close(self) -> None:
        self.stop_event.set()
        self.root.destroy()


def main() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise SystemExit(
            "Не удалось запустить графический интерфейс Tkinter. "
            "Приложению нужен доступный рабочий стол. Если вы запускаете его "
            "в удалённой Linux-среде или контейнере без графического дисплея, "
            "запустите `python main.py` в локальной Windows-среде либо настройте "
            "графический дисплей.\n"
            f"Причина: {error}"
        ) from None
    ReminderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
