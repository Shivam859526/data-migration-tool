"""Schema creation engine — generates and executes MySQL DDL."""

from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from mappings.datatype_mapping import DataTypeMapping


class CreateTableEngine:
    """Generates CREATE TABLE statements and applies them to MySQL."""

    @staticmethod
    def _quote_identifier(name: str) -> str:
        return f"`{name.replace('`', '``')}`"

    @staticmethod
    def _format_default(default: Any) -> Optional[str]:
        if default is None:
            return None
        default_str = str(default)
        if default_str.startswith("nextval("):
            return None
        if default_str.upper() in ("NOW()", "CURRENT_TIMESTAMP"):
            return "CURRENT_TIMESTAMP"
        if default_str.startswith("'") and default_str.endswith("'"):
            return default_str
        try:
            float(default_str)
            return default_str
        except ValueError:
            return f"'{default_str}'"

    @staticmethod
    def _map_referential_action(action: Optional[str]) -> str:
        if not action:
            return ""
        mapping = {
            "CASCADE": "ON DELETE CASCADE",
            "SET NULL": "ON DELETE SET NULL",
            "SET DEFAULT": "ON DELETE SET DEFAULT",
            "RESTRICT": "ON DELETE RESTRICT",
            "NO ACTION": "ON DELETE NO ACTION",
        }
        upper = action.upper().replace("_", " ")
        return mapping.get(upper, f"ON DELETE {upper}")

    @classmethod
    def generate_create_table_sql(
        cls,
        metadata: Dict[str, Any],
        include_foreign_keys: bool = False,
    ) -> str:
        """Build a CREATE TABLE statement from discovered metadata."""
        table_name = metadata["table_name"]
        pk_columns = metadata["primary_keys"].get("constrained_columns", [])
        serial_columns = set()

        for column in metadata["columns"]:
            if DataTypeMapping.is_bigserial_column(column):
                serial_columns.add(column["name"])
            elif DataTypeMapping.is_serial_column(column):
                serial_columns.add(column["name"])

        column_defs: List[str] = []

        for column in metadata["columns"]:
            col_name = column["name"]
            is_serial = col_name in serial_columns and col_name in pk_columns

            mysql_type = DataTypeMapping.get_mysql_type(
                column["type"],
                is_serial=is_serial and not DataTypeMapping.is_bigserial_column(column),
                is_bigserial=DataTypeMapping.is_bigserial_column(column),
            )

            parts = [cls._quote_identifier(col_name), mysql_type]

            if column.get("nullable") is False:
                parts.append("NOT NULL")

            default_sql = cls._format_default(column.get("default"))
            if default_sql and "AUTO_INCREMENT" not in mysql_type:
                parts.append(f"DEFAULT {default_sql}")

            column_defs.append(" ".join(parts))

        if pk_columns:
            pk_list = ", ".join(cls._quote_identifier(c) for c in pk_columns)
            column_defs.append(f"PRIMARY KEY ({pk_list})")

        for uc in metadata.get("unique_constraints", []):
            cols = uc.get("column_names", [])
            if cols:
                col_list = ", ".join(cls._quote_identifier(c) for c in cols)
                column_defs.append(f"UNIQUE ({col_list})")

        if include_foreign_keys:
            column_defs.extend(cls._inline_foreign_key_defs(metadata))

        body = ",\n  ".join(column_defs)
        sql = f"CREATE TABLE {cls._quote_identifier(table_name)} (\n  {body}\n)"
        return sql

    @classmethod
    def _inline_foreign_key_defs(cls, metadata: Dict[str, Any]) -> List[str]:
        defs: List[str] = []
        for fk in metadata.get("foreign_keys", []):
            clause = cls._foreign_key_clause(metadata["table_name"], fk)
            if clause:
                defs.append(clause)
        return defs

    @classmethod
    def _foreign_key_clause(cls, table_name: str, fk: Dict[str, Any]) -> Optional[str]:
        constrained = fk.get("constrained_columns", [])
        referred_table = fk.get("referred_table")
        referred_cols = fk.get("referred_columns", [])
        if not (constrained and referred_table and referred_cols):
            return None

        local = ", ".join(cls._quote_identifier(c) for c in constrained)
        remote = ", ".join(cls._quote_identifier(c) for c in referred_cols)
        options = fk.get("options", {}) or {}
        on_delete = cls._map_referential_action(options.get("ondelete"))
        suffix = f" {on_delete}" if on_delete else ""
        return (
            f"FOREIGN KEY ({local}) "
            f"REFERENCES {cls._quote_identifier(referred_table)} ({remote}){suffix}"
        )

    @classmethod
    def generate_foreign_key_sql(cls, metadata: Dict[str, Any]) -> List[str]:
        """Generate ALTER TABLE statements to add foreign keys after data load."""
        table_name = metadata["table_name"]
        statements: List[str] = []

        for fk in metadata.get("foreign_keys", []):
            clause = cls._foreign_key_clause(table_name, fk)
            if not clause:
                continue
            constraint_name = fk.get("name") or (
                f"fk_{table_name}_{'_'.join(fk.get('constrained_columns', []))}"
            )
            statements.append(
                f"ALTER TABLE {cls._quote_identifier(table_name)} "
                f"ADD CONSTRAINT {cls._quote_identifier(constraint_name)} "
                f"{clause}"
            )
        return statements

    @classmethod
    def generate_index_sql(cls, metadata: Dict[str, Any]) -> List[str]:
        """Generate CREATE INDEX statements for non-unique indexes."""
        table_name = metadata["table_name"]
        pk_columns = set(metadata["primary_keys"].get("constrained_columns", []))
        statements: List[str] = []

        for index in metadata.get("indexes", []):
            if index.get("unique"):
                continue
            cols = index.get("column_names", [])
            if not cols or set(cols) == pk_columns:
                continue
            index_name = index.get("name", f"idx_{table_name}_{'_'.join(cols)}")
            col_list = ", ".join(cls._quote_identifier(c) for c in cols)
            statements.append(
                f"CREATE INDEX {cls._quote_identifier(index_name)} "
                f"ON {cls._quote_identifier(table_name)} ({col_list})"
            )
        return statements

    @classmethod
    def table_exists(cls, engine: Engine, table_name: str) -> bool:
        return table_name in inspect(engine).get_table_names()

    @classmethod
    def create_table(
        cls,
        engine: Engine,
        sql: str,
        skip_existing: bool = True,
    ) -> bool:
        """Execute CREATE TABLE SQL. Returns True if created, False if skipped."""
        table_name = sql.split("CREATE TABLE")[1].strip().split("(")[0].strip().strip("`")
        if skip_existing and cls.table_exists(engine, table_name):
            return False

        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
            return True
        except SQLAlchemyError:
            raise

    @classmethod
    def apply_foreign_keys(
        cls,
        engine: Engine,
        metadata: Dict[str, Any],
    ) -> None:
        """Apply deferred foreign key constraints after tables and data exist."""
        for fk_sql in cls.generate_foreign_key_sql(metadata):
            try:
                with engine.begin() as conn:
                    conn.execute(text(fk_sql))
            except SQLAlchemyError as exc:
                err = str(exc).lower()
                if "duplicate" in err or "already exists" in err:
                    continue
                raise

    @classmethod
    def create_table_from_metadata(
        cls,
        engine: Engine,
        metadata: Dict[str, Any],
        skip_existing: bool = True,
        defer_foreign_keys: bool = True,
    ) -> bool:
        """Generate and execute CREATE TABLE plus indexes (FKs optional/deferred)."""
        sql = cls.generate_create_table_sql(
            metadata, include_foreign_keys=not defer_foreign_keys
        )
        created = cls.create_table(engine, sql, skip_existing=skip_existing)

        if created or not skip_existing:
            for index_sql in cls.generate_index_sql(metadata):
                try:
                    with engine.begin() as conn:
                        conn.execute(text(index_sql))
                except SQLAlchemyError:
                    pass

            if not defer_foreign_keys:
                cls.apply_foreign_keys(engine, metadata)

        return created

    @classmethod
    def migrate_schema_batch(
        cls,
        engine: Engine,
        ordered_metadata: List[Dict[str, Any]],
        skip_existing: bool = True,
    ) -> List[str]:
        """
        Create all tables without FKs, then apply FK constraints in order.

        This handles interlinked and circular FK relationships safely.
        """
        created: List[str] = []

        for metadata in ordered_metadata:
            table = metadata["table_name"]
            if cls.create_table_from_metadata(
                engine, metadata, skip_existing=skip_existing, defer_foreign_keys=True
            ):
                created.append(table)

        for metadata in ordered_metadata:
            if skip_existing and not cls.table_exists(engine, metadata["table_name"]):
                continue
            cls.apply_foreign_keys(engine, metadata)

        return created
