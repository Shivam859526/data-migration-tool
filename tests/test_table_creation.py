from config.settings import (
    POSTGRES_CONFIG,
    MYSQL_CONFIG
)

from database.connection_manager import (
    ConnectionManager
)

from core.schema_engine import (
    SchemaEngine
)

from core.create_table_engine import (
    CreateTableEngine
)

source_engine = (
    ConnectionManager
    .get_postgres_engine(
        POSTGRES_CONFIG
    )
)

target_engine = (
    ConnectionManager
    .get_mysql_engine(
        MYSQL_CONFIG
    )
)

tables = (
    SchemaEngine
    .get_tables(
        source_engine
    )
)

for table in tables:

    metadata = (
        SchemaEngine
        .get_table_metadata(
            source_engine,
            table
        )
    )

    sql = (
        CreateTableEngine
        .generate_create_table_sql(
            metadata
        )
    )

    print(
        f"Creating {table}"
    )

    CreateTableEngine.create_table(
        target_engine,
        sql
    )