"""PostgreSQL to MySQL datatype mapping engine."""

import re
from typing import Any, Dict, Optional, Tuple


class DataTypeMapping:
    """Maps PostgreSQL column types to MySQL equivalents."""

    POSTGRES_TO_MYSQL: Dict[str, str] = {
        "SMALLINT": "SMALLINT",
        "INTEGER": "INT",
        "INT": "INT",
        "BIGINT": "BIGINT",
        "SERIAL": "INT AUTO_INCREMENT",
        "BIGSERIAL": "BIGINT AUTO_INCREMENT",
        "NUMERIC": "DECIMAL",
        "DECIMAL": "DECIMAL",
        "FLOAT": "FLOAT",
        "REAL": "FLOAT",
        "DOUBLE": "DOUBLE",
        "DOUBLE PRECISION": "DOUBLE",
        "BOOLEAN": "TINYINT(1)",
        "BOOL": "TINYINT(1)",
        "TEXT": "LONGTEXT",
        "VARCHAR": "VARCHAR",
        "CHAR": "CHAR",
        "CHARACTER": "CHAR",
        "CHARACTER VARYING": "VARCHAR",
        "DATE": "DATE",
        "TIME": "TIME",
        "TIMESTAMP": "DATETIME",
        "TIMESTAMP WITHOUT TIME ZONE": "DATETIME",
        "TIMESTAMP WITH TIME ZONE": "DATETIME",
        "TIMESTAMPTZ": "DATETIME",
        "UUID": "CHAR(36)",
        "JSON": "JSON",
        "JSONB": "JSON",
        "BYTEA": "LONGBLOB",
        "BYTE": "LONGBLOB",
        "BLOB": "LONGBLOB",
    }

    _TYPE_PATTERN = re.compile(
        r"^([A-Z][A-Z0-9 ]*?)(?:\(([^)]*)\))?$"
    )

    @classmethod
    def parse_type(cls, postgres_type: Any) -> Tuple[str, Optional[str]]:
        """Extract base type name and parameter string from a PG type."""
        type_str = str(postgres_type).upper().strip()

        for compound in ("TIMESTAMP WITHOUT TIME ZONE", "TIMESTAMP WITH TIME ZONE", "DOUBLE PRECISION", "CHARACTER VARYING"):
            if type_str.startswith(compound):
                params = None
                if "(" in type_str:
                    params = type_str[type_str.index("(") + 1 : type_str.rindex(")")]
                return compound, params

        match = cls._TYPE_PATTERN.match(type_str.split()[0] if "(" not in type_str.split()[0] else type_str)
        if not match:
            base = type_str.split("(")[0].strip()
            params = None
            if "(" in type_str:
                params = type_str[type_str.index("(") + 1 : type_str.rindex(")")]
            return base, params

        base = match.group(1).strip()
        params = match.group(2)
        if params is None and "(" in type_str:
            params = type_str[type_str.index("(") + 1 : type_str.rindex(")")]
        return base, params

    @classmethod
    def get_mysql_type(
        cls,
        postgres_type: Any,
        is_serial: bool = False,
        is_bigserial: bool = False,
    ) -> str:
        """Return the MySQL column type for a PostgreSQL type."""
        if is_bigserial:
            return "BIGINT AUTO_INCREMENT"
        if is_serial:
            return "INT AUTO_INCREMENT"

        base, params = cls.parse_type(postgres_type)
        mysql_base = cls.POSTGRES_TO_MYSQL.get(base, "LONGTEXT")

        if mysql_base in ("DECIMAL", "NUMERIC") and params:
            return f"DECIMAL({params})"
        if mysql_base == "VARCHAR":
            return f"VARCHAR({params or '255'})"
        if mysql_base == "CHAR" and params:
            return f"CHAR({params})"
        if "AUTO_INCREMENT" in mysql_base:
            return mysql_base

        return mysql_base

    @classmethod
    def is_serial_column(cls, column: Dict[str, Any]) -> bool:
        """Detect SERIAL/BIGSERIAL via default sequence or type name."""
        col_type = str(column.get("type", "")).upper()
        if "SERIAL" in col_type:
            return "BIG" not in col_type.split("SERIAL")[0]
        default = column.get("default")
        if default is not None and "nextval" in str(default).lower():
            return True
        return False

    @classmethod
    def is_bigserial_column(cls, column: Dict[str, Any]) -> bool:
        """Detect BIGSERIAL via type name or bigint + sequence default."""
        col_type = str(column.get("type", "")).upper()
        if "BIGSERIAL" in col_type:
            return True
        default = column.get("default")
        if default is not None and "nextval" in str(default).lower():
            if "BIGINT" in col_type or "INT8" in col_type:
                return True
        return False

    @classmethod
    def register_mapping(cls, postgres_type: str, mysql_type: str) -> None:
        """Extend the mapping table at runtime."""
        cls.POSTGRES_TO_MYSQL[postgres_type.upper()] = mysql_type
