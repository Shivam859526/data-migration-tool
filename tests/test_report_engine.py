"""Unit tests for report engine."""

import json
import os
import tempfile
import unittest

from core.report_engine import ReportEngine


class TestReportEngine(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self._orig_folder = None
        import core.report_engine as re_mod
        self._orig_folder = re_mod.REPORT_FOLDER
        re_mod.REPORT_FOLDER = self.tmp_dir

    def tearDown(self):
        import core.report_engine as re_mod
        re_mod.REPORT_FOLDER = self._orig_folder

    def test_report_lifecycle(self):
        engine = ReportEngine()
        engine.start("test-job")
        engine.record_table("users", 100)
        engine.record_validation({
            "table": "users",
            "source_rows": 100,
            "target_rows": 100,
            "status": "PASS",
        })
        report = engine.finish("COMPLETED")

        self.assertEqual(report["job_id"], "test-job")
        self.assertEqual(report["total_rows_migrated"], 100)
        self.assertEqual(report["status"], "COMPLETED")

    def test_export_json(self):
        engine = ReportEngine()
        engine.start("job-1")
        engine.finish()
        path = engine.export_json("test_report.json")
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["job_id"], "job-1")


if __name__ == "__main__":
    unittest.main()
