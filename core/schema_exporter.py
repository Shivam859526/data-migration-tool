import json
import os


class SchemaExporter:

    @staticmethod
    def export_schema(
            metadata,
            file_name
    ):

        os.makedirs(
            "exports",
            exist_ok=True
        )

        path = (
            f"exports/{file_name}"
        )

        with open(
                path,
                "w"
        ) as file:

            json.dump(
                metadata,
                file,
                indent=4,
                default=str
            )

        return path