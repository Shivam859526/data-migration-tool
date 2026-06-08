from sqlalchemy import inspect

from database.base_adapter import (
    BaseAdapter
)


class PostgresAdapter(
        BaseAdapter
):

    def __init__(
            self,
            engine
    ):
        self.engine = engine

    def get_tables(self):

        inspector = inspect(
            self.engine
        )

        return (
            inspector
            .get_table_names()
        )

    def get_columns(
            self,
            table_name
    ):

        inspector = inspect(
            self.engine
        )

        return (
            inspector
            .get_columns(
                table_name
            )
        )