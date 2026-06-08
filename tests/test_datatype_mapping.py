"""Unit tests for datatype mapping."""

import unittest

from mappings.datatype_mapping import DataTypeMapping


class TestDataTypeMapping(unittest.TestCase):

    def test_basic_integer_mapping(self):
        self.assertEqual(DataTypeMapping.get_mysql_type("INTEGER"), "INT")

    def test_varchar_with_length(self):
        self.assertEqual(
            DataTypeMapping.get_mysql_type("VARCHAR(100)"), "VARCHAR(100)"
        )

    def test_boolean_mapping(self):
        self.assertEqual(DataTypeMapping.get_mysql_type("BOOLEAN"), "TINYINT(1)")

    def test_serial_mapping(self):
        self.assertEqual(
            DataTypeMapping.get_mysql_type("INTEGER", is_serial=True),
            "INT AUTO_INCREMENT",
        )

    def test_uuid_mapping(self):
        self.assertEqual(DataTypeMapping.get_mysql_type("UUID"), "CHAR(36)")

    def test_jsonb_mapping(self):
        self.assertEqual(DataTypeMapping.get_mysql_type("JSONB"), "JSON")

    def test_unknown_fallback(self):
        self.assertEqual(DataTypeMapping.get_mysql_type("UNKNOWN_TYPE"), "LONGTEXT")

    def test_custom_mapping_registration(self):
        DataTypeMapping.register_mapping("CUSTOM", "TEXT")
        self.assertEqual(DataTypeMapping.get_mysql_type("CUSTOM"), "TEXT")

    def test_parse_type_with_params(self):
        base, params = DataTypeMapping.parse_type("NUMERIC(10,2)")
        self.assertEqual(base, "NUMERIC")
        self.assertEqual(params, "10,2")


if __name__ == "__main__":
    unittest.main()
