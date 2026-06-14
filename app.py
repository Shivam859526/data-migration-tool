"""Entry point for the Database Migration Tool."""

import sys

from utils.file_manager import FileManager


def main() -> None:
    FileManager.create_directories()

    from ui.main_window import run_app

    run_app()


if __name__ == "__main__":
    main()
