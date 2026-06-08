from config.settings import (
    POSTGRES_CONFIG
)

from database.connection_manager import (
    ConnectionManager
)

from core.schema_engine import (
    SchemaEngine
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

    print("\n")
    print("=" * 50)

    print(
        metadata["table_name"]
    )

    print("=" * 50)

    print("\nColumns:")

    for column in metadata["columns"]:

        print(
            f"{column['name']} "
            f"{column['type']}"
        )

    print("\nPrimary Keys:")

    print(
        metadata["primary_keys"]
    )