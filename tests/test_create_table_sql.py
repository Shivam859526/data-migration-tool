"""Unit tests for CREATE TABLE SQL generation."""

import unittest

from core.create_table_engine import CreateTableEngine


SAMPLE_METADATA = {
    "table_name": "users",
    "columns": [
        {
            "name": "id",
            "type": "INTEGER",
            "nullable": False,
            "default": "nextval('users_id_seq'::regclass)",
        },
        {
            "name": "email",
            "type": "VARCHAR(255)",
            "nullable": False,
            "default": None,
        },
        {
            "name": "active",
            "type": "BOOLEAN",
            "nullable": True,
            "default": None,
        },
    ],
    "primary_keys": {"constrained_columns": ["id"]},
    "foreign_keys": [],
    "indexes": [],
    "unique_constraints": [
        {"column_names": ["email"]},
    ],
}


class TestCreateTableEngine(unittest.TestCase):

    def test_generates_create_table(self):
        sql = CreateTableEngine.generate_create_table_sql(SAMPLE_METADATA)
        self.assertIn("CREATE TABLE `users`", sql)
        self.assertIn("AUTO_INCREMENT", sql)
        self.assertIn("PRIMARY KEY (`id`)", sql)
        self.assertIn("UNIQUE (`email`)", sql)
        self.assertIn("TINYINT(1)", sql)

    def test_quote_identifier(self):
        self.assertEqual(
            CreateTableEngine._quote_identifier("my`table"),
            "`my``table`",
        )


if __name__ == "__main__":
    unittest.main()
