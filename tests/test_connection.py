"""Unit tests for connection manager."""

import unittest
from unittest.mock import MagicMock, patch

from database.connection_manager import ConnectionManager


class TestConnectionManager(unittest.TestCase):

    @patch("database.connection_manager.create_engine")
    def test_postgres_url_format(self, mock_create):
        config = {
            "host": "localhost",
            "port": 5432,
            "database": "testdb",
            "username": "user",
            "password": "pass",
        }
        ConnectionManager.get_postgres_engine(config)
        mock_create.assert_called_once()
        url = mock_create.call_args[0][0]
        self.assertIn("postgresql+psycopg2://", url)
        self.assertIn("testdb", url)

    @patch("database.connection_manager.create_engine")
    def test_mysql_url_format(self, mock_create):
        config = {
            "host": "localhost",
            "port": 3306,
            "database": "testdb",
            "username": "root",
            "password": "pass",
        }
        ConnectionManager.get_mysql_engine(config)
        url = mock_create.call_args[0][0]
        self.assertIn("mysql+pymysql://", url)
        self.assertIn("charset=utf8mb4", url)

    def test_test_connection_success(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
        engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        self.assertTrue(ConnectionManager.test_connection(engine, retries=1))

    def test_test_connection_failure(self):
        from sqlalchemy.exc import SQLAlchemyError

        engine = MagicMock()
        engine.connect.side_effect = SQLAlchemyError("connection refused")
        self.assertFalse(ConnectionManager.test_connection(engine, retries=1))


if __name__ == "__main__":
    unittest.main()
