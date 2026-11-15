"""No-GUI checks for novice launch preparation and visible control behavior."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import beyond
import desktop
import start_here


class SourceLauncherTests(unittest.TestCase):
    def test_prepared_environment_works_without_installing_again(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            python = start_here.environment_python(root / ".venv-play")
            python.parent.mkdir(parents=True)
            python.touch()
            with patch.object(start_here.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
                with patch.object(start_here.venv, "EnvBuilder") as builder:
                    self.assertEqual(start_here.prepare_runtime(root), root / ".venv-play")
            builder.assert_not_called()
            self.assertEqual(run.call_count, 1)

    def test_missing_dependencies_are_installed_only_in_local_environment(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            python = start_here.environment_python(root / ".venv-play")
            python.parent.mkdir(parents=True)
            python.touch()
            results = [SimpleNamespace(returncode=1), SimpleNamespace(returncode=0), SimpleNamespace(returncode=0)]
            with patch.object(start_here.subprocess, "run", side_effect=results) as run:
                start_here.prepare_runtime(root)
            install = run.call_args_list[1].args[0]
            self.assertEqual(install[:4], [str(python), "-m", "pip", "install"])
            self.assertIn(str(root / "requirements.txt"), install)

    def test_path_with_spaces_and_chinese_is_passed_as_arguments(self):
        root = Path("项目 测试")
        environment = root / ".venv-play"
        with patch.object(start_here, "ROOT", root):
            with patch.object(start_here, "prepare_runtime", return_value=environment):
                with patch.object(start_here.subprocess, "Popen") as popen:
                    self.assertEqual(start_here.main(["--seek", "117"]), 0)
        command = popen.call_args.args[0]
        self.assertIsInstance(command, list)
        self.assertEqual(command[1:], [str(root / "desktop.py"), "--seek", "117"])
        self.assertNotIn("shell", popen.call_args.kwargs)


class VisibleControlTests(unittest.TestCase):
    def player(self):
        player = beyond.Film.__new__(beyond.Film)
        player.paused = False
        player.fullscreen = False
        player.help = False
        player.report = {}
        player.root = Mock()
        player.buttons = {name: Mock() for name in ("pause", "fullscreen", "help")}
        return player

    def test_pause_button_tells_viewer_how_to_continue(self):
        player = self.player()
        player.toggle_pause()
        self.assertTrue(player.paused)
        player.buttons["pause"].configure.assert_called_with(text="继续")
        player.toggle_pause()
        self.assertFalse(player.paused)
        player.buttons["pause"].configure.assert_called_with(text="暂停")

    def test_fullscreen_button_always_offers_a_way_back(self):
        player = self.player()
        player.toggle_fullscreen()
        player.buttons["fullscreen"].configure.assert_called_with(text="退出全屏")
        player.toggle_fullscreen()
        player.buttons["fullscreen"].configure.assert_called_with(text="全屏")

    def test_space_on_a_focused_button_does_not_also_pause(self):
        player = self.player()
        widget = Mock()
        widget.winfo_class.return_value = "Button"
        player.keyboard_pause(SimpleNamespace(widget=widget))
        self.assertFalse(player.paused)
        widget.winfo_class.return_value = "Canvas"
        self.assertEqual(player.keyboard_pause(SimpleNamespace(widget=widget)), "break")
        self.assertTrue(player.paused)


class DesktopEntryTests(unittest.TestCase):
    def test_startup_failure_shows_friendly_message_and_returns_failure(self):
        with patch.object(beyond, "main", side_effect=RuntimeError("could not start")):
            with patch.object(desktop, "show_startup_error") as notify:
                self.assertEqual(desktop.main([]), 1)
        notify.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
