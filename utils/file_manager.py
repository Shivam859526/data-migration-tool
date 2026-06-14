import os


class FileManager:

    @staticmethod
    def create_directories():
        os.makedirs("exports", exist_ok=True)
