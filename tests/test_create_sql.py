from config.settings import (
    POSTGRES_CONFIG
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

engine = (
    ConnectionManager
    .get_postgres_engine(
        POSTGRES_CONFIG
    )
)

tables = (
    SchemaEngine
    .get_tables(engine)
)

for table in tables:

    metadata = (
        SchemaEngine
        .get_table_metadata(
            engine,
            table
        )
    )

    sql = (
        CreateTableEngine
        .generate_create_table_sql(
            metadata
        )
    )

    print("\n")
    print(sql)