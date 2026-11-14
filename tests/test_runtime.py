"""Headless checks for playback lifecycle and bounded diagnostics."""
import unittest
from unittest.mock import Mock

import beyond


class PlaybackLifecycleTests(unittest.TestCase):
    def player(self):
        player = beyond.Film.__new__(beyond.Film)
        player.stopped = False
        player.failure = None
        player.root = Mock()
        player.save_report = Mock()
        return player

    def test_render_failure_reaches_the_launcher(self):
        player = self.player()
        player.callback_error(ValueError, ValueError("broken draw"), None)
        player.root.destroy.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, "broken draw"):
            player.run()

    def test_diagnostic_failure_still_closes_the_window(self):
        player = self.player()
        player.save_report.side_effect = PermissionError("diagnostic path is read-only")
        with self.assertRaises(PermissionError):
            player.close("complete")
        player.root.destroy.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, "diagnostic path is read-only"):
            player.run()

    def test_normal_close_succeeds_and_is_idempotent(self):
        player = self.player()
        player.close("user-exit")
        player.close("user-exit")
        player.run()
        player.root.destroy.assert_called_once()
        player.save_report.assert_called_once_with("user-exit", None)


class FrameTimingTests(unittest.TestCase):
    def test_long_playback_keeps_a_bounded_window_and_correct_totals(self):
        timings = beyond.FrameTimings(capacity=8)
        for i in range(100):
            timings.record(i, i*.5)
        metrics = timings.summary()
        self.assertEqual(len(timings.recent_fields), 8)
        self.assertEqual(metrics["meanFieldMs"], 49.5)
        self.assertEqual(metrics["meanTextUpdateMs"], 24.75)
        self.assertEqual(metrics["p95FieldMs"], 98.65)
        self.assertEqual(metrics["fieldSampleWindowFrames"], 8)

    def test_empty_timings_are_finite_zeroes(self):
        metrics = beyond.FrameTimings().summary()
        self.assertEqual(metrics, {"meanFieldMs": 0, "p95FieldMs": 0,
                                   "meanTextUpdateMs": 0, "fieldSampleWindowFrames": 0})


if __name__ == "__main__":
    unittest.main(verbosity=2)
