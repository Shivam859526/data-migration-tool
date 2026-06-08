import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from utils.logger import Logger

logger = Logger.setup_logger()

logger.info("Migration Tool Started")

print("Log Created Successfully")