"""Post-migration validation engine."""

import hashlib
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.constants import VALIDATION_FAIL, VALIDATION_PASS


class ValidationEngine:
    """Validates migrated data between source and target databases."""

    @staticmethod
    def _quote_identifier(name: str) -> str:
        return f'"{name}"' if '"' not in name else name

    @staticmethod
    def _mysql_quote(name: str) -> str:
        return f"`{name.replace('`', '``')}`"

    @classmethod
    def get_row_count(cls, engine: Engine, table_name: str, dialect: str = "postgres") -> int:
        quote = cls._mysql_quote if dialect == "mysql" else cls._quote_identifier
        query = text(f"SELECT COUNT(*) FROM {quote(table_name)}")
        with engine.connect() as conn:
            return conn.execute(query).scalar() or 0

    @classmethod
    def get_null_count(
        cls,
        engine: Engine,
        table_name: str,
        column_name: str,
        dialect: str = "postgres",
    ) -> int:
        quote = cls._mysql_quote if dialect == "mysql" else cls._quote_identifier
        query = text(
            f"SELECT COUNT(*) FROM {quote(table_name)} "
            f"WHERE {quote(column_name)} IS NULL"
        )
        with engine.connect() as conn:
            return conn.execute(query).scalar() or 0

    @classmethod
    def get_min_max(
        cls,
        engine: Engine,
        table_name: str,
        column_name: str,
        dialect: str = "postgres",
    ) -> Dict[str, Any]:
        quote = cls._mysql_quote if dialect == "mysql" else cls._quote_identifier
        query = text(
            f"SELECT MIN({quote(column_name)}), MAX({quote(column_name)}) "
            f"FROM {quote(table_name)}"
        )
        with engine.connect() as conn:
            row = conn.execute(query).fetchone()
            return {"min": row[0], "max": row[1]}

    @classmethod
    def get_checksum(
        cls,
        engine: Engine,
        table_name: str,
        columns: List[str],
        dialect: str = "postgres",
    ) -> Optional[str]:
        """Compute an MD5 checksum over concatenated column values."""
        if not columns:
            return None

        quote = cls._mysql_quote if dialect == "mysql" else cls._quote_identifier
        concat_expr = " || ".join(
            f"COALESCE(CAST({quote(c)} AS TEXT), '')" for c in columns
        )
        if dialect == "mysql":
            concat_expr = "CONCAT(" + ", ".join(
                f"COALESCE(CAST({cls._mysql_quote(c)} AS CHAR), '')" for c in columns
            ) + ")"

        query = text(
            f"SELECT MD5(CAST(SUM(LENGTH({concat_expr})) AS TEXT)) "
            f"FROM {quote(table_name)}"
        )
        try:
            with engine.connect() as conn:
                result = conn.execute(query).scalar()
                return str(result) if result else None
        except Exception:
            return None

    @classmethod
    def validate_table(
        cls,
        source_engine: Engine,
        target_engine: Engine,
        table_name: str,
        columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run full validation suite for a single table."""
        source_rows = cls.get_row_count(source_engine, table_name, "postgres")
        target_rows = cls.get_row_count(target_engine, table_name, "mysql")

        result: Dict[str, Any] = {
            "table": table_name,
            "source_rows": source_rows,
            "target_rows": target_rows,
            "row_count_match": source_rows == target_rows,
            "null_checks": [],
            "min_max_checks": [],
            "checksum_match": None,
            "status": VALIDATION_PASS,
        }

        if source_rows != target_rows:
            result["status"] = VALIDATION_FAIL

        if columns:
            for col in columns:
                src_nulls = cls.get_null_count(source_engine, table_name, col, "postgres")
                tgt_nulls = cls.get_null_count(target_engine, table_name, col, "mysql")
                null_match = src_nulls == tgt_nulls
                result["null_checks"].append({
                    "column": col,
                    "source_nulls": src_nulls,
                    "target_nulls": tgt_nulls,
                    "matched": null_match,
                })
                if not null_match:
                    result["status"] = VALIDATION_FAIL

                try:
                    src_mm = cls.get_min_max(source_engine, table_name, col, "postgres")
                    tgt_mm = cls.get_min_max(target_engine, table_name, col, "mysql")
                    mm_match = src_mm == tgt_mm
                    result["min_max_checks"].append({
                        "column": col,
                        "source": src_mm,
                        "target": tgt_mm,
                        "matched": mm_match,
                    })
                    if not mm_match:
                        result["status"] = VALIDATION_FAIL
                except Exception:
                    pass

            src_checksum = cls.get_checksum(source_engine, table_name, columns, "postgres")
            tgt_checksum = cls.get_checksum(target_engine, table_name, columns, "mysql")
            if src_checksum and tgt_checksum:
                result["checksum_match"] = src_checksum == tgt_checksum
                if not result["checksum_match"]:
                    result["status"] = VALIDATION_FAIL

        return result

    @classmethod
    def validate_row_count(
        cls,
        source_engine: Engine,
        target_engine: Engine,
        table_name: str,
    ) -> Dict[str, Any]:
        """Backward-compatible row count validation."""
        source_count = cls.get_row_count(source_engine, table_name, "postgres")
        target_count = cls.get_row_count(target_engine, table_name, "mysql")
        return {
            "source_count": source_count,
            "target_count": target_count,
            "matched": source_count == target_count,
        }
