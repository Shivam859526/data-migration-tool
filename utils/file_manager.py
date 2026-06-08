import os


class FileManager:

    @staticmethod
    def create_directories():

        folders = [
            "logs",
            "reports",
            "exports"
        ]

        for folder in folders:

            os.makedirs(
                folder,
                exist_ok=True
            )