from config.settings import (
    POSTGRES_CONFIG
)

from database.connection_manager import (
    ConnectionManager
)

from core.schema_engine import (
    SchemaEngine
)

from core.schema_exporter import (
    SchemaExporter
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

all_metadata = []

for table in tables:

    metadata = (
        SchemaEngine
        .get_table_metadata(
            engine,
            table
        )
    )

    all_metadata.append(
        metadata
    )

path = (
    SchemaExporter
    .export_schema(
        all_metadata,
        "schema.json"
    )
)

print(path)