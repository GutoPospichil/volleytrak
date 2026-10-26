import subprocess
import sys
import unittest

from app import subprocess_utils


class HiddenSubprocessTest(unittest.TestCase):
    def test_windows_kwargs_hide_console(self):
        kwargs = subprocess_utils.hidden_kwargs()
        if sys.platform != "win32":
            self.assertEqual(kwargs, {})
            return
        self.assertEqual(
            kwargs["creationflags"],
            getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.assertTrue(kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW)
        self.assertEqual(kwargs["startupinfo"].wShowWindow, subprocess.SW_HIDE)

    def test_run_hidden_still_returns_output(self):
        result = subprocess_utils.run_hidden(
            [sys.executable, "-c", "print('volleytrak')"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "volleytrak")
