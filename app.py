"""Entry point for the Database Migration Tool."""

import sys

from utils.file_manager import FileManager
from utils.logger import Logger


def main() -> None:
    Logger.setup_logger()
    FileManager.create_directories()

    logger = Logger.get_logger()
    logger.info("Application starting")

    from ui.main_window import run_app

    run_app()


if __name__ == "__main__":
    main()
