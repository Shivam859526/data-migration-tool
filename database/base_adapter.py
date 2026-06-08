from abc import (
    ABC,
    abstractmethod
)


class BaseAdapter(ABC):

    @abstractmethod
    def get_tables(self):
        pass

    @abstractmethod
    def get_columns(
            self,
            table_name
    ):
        pass