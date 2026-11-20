import tkinter as tk
import unittest
from unittest.mock import patch

import main


class MainTests(unittest.TestCase):
    def test_missing_display_has_actionable_error(self) -> None:
        with patch.object(tk, "Tk", side_effect=tk.TclError("no display")):
            with self.assertRaises(SystemExit) as raised:
                main.main()

        self.assertIn("локальной Windows-среде", str(raised.exception))
        self.assertIn("no display", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
