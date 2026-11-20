"""Application entry point."""

import tkinter as tk

from gui import ReminderApp


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
    ReminderApp(root).run()


if __name__ == "__main__":
    main()
