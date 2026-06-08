from config.settings import POSTGRES_CONFIG

from database.connection_manager import (
    ConnectionManager
)

from core.schema_engine import (
    SchemaEngine
)


def main():

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

    print("\nTABLES FOUND:")
    print("-" * 50)

    for table in tables:

        print(f"\nTable: {table}")

        columns = (
            SchemaEngine
            .get_columns(
                engine,
                table
            )
        )

        print("Columns:")

        for column in columns:
            print(
                f"  {column['name']} "
                f"({column['type']})"
            )

        pk = (
            SchemaEngine
            .get_primary_key(
                engine,
                table
            )
        )

        print("Primary Key:")
        print(pk)


if __name__ == "__main__":
    main()