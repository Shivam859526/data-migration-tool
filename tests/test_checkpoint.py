"""Unit tests for checkpoint engine."""

import json
import os
import tempfile
import unittest

from core.checkpoint_engine import CheckpointEngine


class TestCheckpointEngine(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self.tmp.write('{"jobs": {}}')
        self.tmp.close()
        self._original_file = CheckpointEngine.CHECKPOINT_FILE
        CheckpointEngine.CHECKPOINT_FILE = self.tmp.name

    def tearDown(self):
        CheckpointEngine.CHECKPOINT_FILE = self._original_file
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_save_and_load(self):
        CheckpointEngine.save_checkpoint("job-1", "users", 5000, 1)
        result = CheckpointEngine.load_checkpoint("job-1", "users")
        self.assertIsNotNone(result)
        self.assertEqual(result["offset"], 5000)
        self.assertEqual(result["batch_number"], 1)
        self.assertEqual(result["table_name"], "users")

    def test_get_table_offset_default(self):
        self.assertEqual(CheckpointEngine.get_table_offset("job-x", "missing"), 0)

    def test_clear_checkpoint(self):
        CheckpointEngine.save_checkpoint("job-1", "users", 100)
        CheckpointEngine.clear_checkpoint("job-1", "users")
        self.assertIsNone(CheckpointEngine.load_checkpoint("job-1", "users"))

    def test_multiple_tables(self):
        CheckpointEngine.save_checkpoint("job-1", "users", 100)
        CheckpointEngine.save_checkpoint("job-1", "orders", 200)
        checkpoints = CheckpointEngine.list_checkpoints("job-1")
        self.assertEqual(len(checkpoints), 2)


if __name__ == "__main__":
    unittest.main()
