"""Unit tests for progress tracker."""

import unittest

from core.progress_tracker import ProgressTracker


class TestProgressTracker(unittest.TestCase):

    def test_update_progress(self):
        tracker = ProgressTracker(total_rows=100)
        progress = tracker.update(50)
        self.assertEqual(progress, 50.0)

    def test_snapshot(self):
        tracker = ProgressTracker(total_rows=1000)
        tracker.set_total_tables(5)
        tracker.set_current_table("users", 1000)
        tracker.update(250)
        snap = tracker.get_snapshot()
        self.assertEqual(snap["current_table"], "users")
        self.assertEqual(snap["rows_processed"], 250)
        self.assertEqual(snap["table_progress"], 25.0)

    def test_complete_table(self):
        tracker = ProgressTracker()
        tracker.set_total_tables(2)
        tracker.complete_table()
        snap = tracker.get_snapshot()
        self.assertEqual(snap["tables_completed"], 1)


if __name__ == "__main__":
    unittest.main()
