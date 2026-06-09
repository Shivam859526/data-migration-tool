"""Unit tests for FK dependency resolution."""

import unittest
from unittest.mock import MagicMock, patch

from core.dependency_resolver import DependencyResolver


def _fk(referred_table: str, name: str = "fk"):
    return {
        "name": name,
        "constrained_columns": ["parent_id"],
        "referred_table": referred_table,
        "referred_columns": ["id"],
    }


class TestDependencyResolver(unittest.TestCase):

    @patch.object(DependencyResolver, "get_dependencies")
    def test_sort_parents_before_children(self, mock_deps):
        mock_deps.side_effect = lambda engine, table: {
            "orders": {"users"},
            "order_items": {"orders"},
            "users": set(),
        }[table]

        engine = MagicMock()
        result = DependencyResolver.sort_tables(
            engine, ["order_items", "orders", "users"]
        )
        self.assertEqual(result.index("users"), 0)
        self.assertLess(result.index("orders"), result.index("order_items"))

    @patch.object(DependencyResolver, "get_dependencies")
    def test_circular_dependencies_still_returns_all_tables(self, mock_deps):
        mock_deps.side_effect = lambda engine, table: {
            "a": {"b"},
            "b": {"a"},
        }[table]

        engine = MagicMock()
        result = DependencyResolver.sort_tables(engine, ["a", "b"])
        self.assertEqual(set(result), {"a", "b"})
        self.assertTrue(
            DependencyResolver.has_circular_dependencies(engine, ["a", "b"])
        )

    @patch.object(DependencyResolver, "get_dependencies")
    @patch("core.dependency_resolver.SchemaEngine.get_tables")
    def test_expand_includes_missing_parents(self, mock_tables, mock_deps):
        mock_tables.return_value = ["users", "orders"]
        mock_deps.side_effect = lambda engine, table: {
            "orders": {"users"},
            "users": set(),
        }[table]

        engine = MagicMock()
        expanded, auto_added = DependencyResolver.expand_with_dependencies(
            engine, ["orders"]
        )
        self.assertIn("users", expanded)
        self.assertIn("users", auto_added)
        self.assertLess(expanded.index("users"), expanded.index("orders"))


class TestCreateTableDeferredFK(unittest.TestCase):

    def test_create_sql_excludes_fk_by_default(self):
        from core.create_table_engine import CreateTableEngine

        metadata = {
            "table_name": "orders",
            "columns": [{"name": "id", "type": "INTEGER", "nullable": False}],
            "primary_keys": {"constrained_columns": ["id"]},
            "foreign_keys": [_fk("users")],
            "indexes": [],
            "unique_constraints": [],
        }
        sql = CreateTableEngine.generate_create_table_sql(metadata)
        self.assertNotIn("FOREIGN KEY", sql)

        fk_sql = CreateTableEngine.generate_foreign_key_sql(metadata)
        self.assertEqual(len(fk_sql), 1)
        self.assertIn("ALTER TABLE", fk_sql[0])
        self.assertIn("REFERENCES `users`", fk_sql[0])


if __name__ == "__main__":
    unittest.main()
