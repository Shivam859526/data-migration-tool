from sqlalchemy import text

from config.settings import (
    POSTGRES_CONFIG,
    MYSQL_CONFIG
)

from database.connection_manager import (
    ConnectionManager
)

postgres_engine = (
    ConnectionManager
    .get_postgres_engine(
        POSTGRES_CONFIG
    )
)

mysql_engine = (
    ConnectionManager
    .get_mysql_engine(
        MYSQL_CONFIG
    )
)

try:

    with postgres_engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    print("PostgreSQL Connected")

except Exception as e:
    print("PostgreSQL Error:", e)

try:

    with mysql_engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    print("MySQL Connected")

except Exception as e:
    print("MySQL Error:", e)