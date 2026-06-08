"""Unit tests for transformation engine."""

import json
import unittest
import uuid
from datetime import datetime, timezone

from core.transformation_engine import TransformationEngine


class TestTransformationEngine(unittest.TestCase):

    def setUp(self):
        self.engine = TransformationEngine()

    def test_null_passthrough(self):
        self.assertIsNone(self.engine.transform_value("col", None))

    def test_boolean_to_int(self):
        self.assertEqual(self.engine.transform_value("col", True), 1)
        self.assertEqual(self.engine.transform_value("col", False), 0)

    def test_uuid_to_string(self):
        uid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(
            self.engine.transform_value("col", uid),
            "550e8400-e29b-41d4-a716-446655440000",
        )

    def test_dict_to_json(self):
        result = self.engine.transform_value("col", {"key": "value"})
        self.assertEqual(json.loads(result), {"key": "value"})

    def test_timestamp_strips_tz(self):
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = self.engine.transform_value("col", dt)
        self.assertIsNone(result.tzinfo)

    def test_custom_hook(self):
        self.engine.register_hook("col", lambda name, val: val.upper())
        self.assertEqual(self.engine.transform_value("col", "hello"), "HELLO")

    def test_transform_chunk(self):
        rows = [{"a": True, "b": None}]
        result = self.engine.transform_chunk(rows)
        self.assertEqual(result[0]["a"], 1)
        self.assertIsNone(result[0]["b"])


if __name__ == "__main__":
    unittest.main()
